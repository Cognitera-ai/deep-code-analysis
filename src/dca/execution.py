"""Bounded subprocess execution for the engines that are binaries, not libraries.

The three rules here each come from a production incident in the project that motivated
this package, and each looks like over-engineering until it happens (ADR-0013):

* **Output is drained to EOF with a cap, never buffered** (R-11). ``capture_output=True``
  holds everything the child writes before returning, so one generated block printing in
  an infinite loop accumulated hundreds of MB per second in the parent and got the process
  OOM-killed, losing a whole export.
* **Draining continues past the cap, discarding the excess.** If we stopped reading, the
  child would block on a full pipe and only die at the wall-clock timeout — so a program
  that prints a lot and then exits cleanly would be misreported as a timeout.
* **A memory ceiling is set in the child** (R-10), because a runaway allocation in an
  analysis binary should kill that binary, not the host.
"""

from __future__ import annotations

import json
import os
import resource
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: Wall-clock ceiling per fragment per tool (R-10).
DEFAULT_TIMEOUT_SEC = 30
#: Address-space ceiling for the child (R-10).
DEFAULT_MEMORY_LIMIT_BYTES = 1 * 1024**3
#: Most we keep from a child's stdout/stderr (R-11). Analysis tools emit JSON measured in
#: kilobytes; anything past this is a malfunction, not output.
MAX_OUTPUT_BYTES = 10 * 1024**2
OUTPUT_TRUNCATION_MARKER = b"\n...[dca: output truncated]..."

_READ_CHUNK = 64 * 1024


@dataclass(slots=True)
class CommandResult:
    """Outcome of one bounded subprocess call."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def json(self) -> object:
        """Parse stdout as JSON, or raise ValueError with context worth reading."""
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError as exc:
            head = self.stdout[:200].replace("\n", " ")
            raise ValueError(
                f"expected JSON on stdout, got {head!r} (rc={self.returncode}, "
                f"stderr={self.stderr[:200]!r})"
            ) from exc


def _drain(stream, cap: int) -> tuple[bytes, bool]:
    """Read ``stream`` to EOF keeping at most ``cap`` bytes; report whether more arrived.

    Reading past the cap instead of stopping is the whole point — see the module
    docstring. The excess is read and thrown away so the child never blocks on a full pipe.
    """
    kept = bytearray()
    truncated = False
    while True:
        chunk = stream.read(_READ_CHUNK)
        if not chunk:
            break
        if len(kept) < cap:
            room = cap - len(kept)
            kept.extend(chunk[:room])
            if len(chunk) > room:
                truncated = True
        else:
            truncated = True
    return bytes(kept), truncated


def _limit_child() -> None:  # pragma: no cover - runs in the forked child
    """Apply the address-space ceiling inside the child before exec."""
    try:
        resource.setrlimit(
            resource.RLIMIT_AS,
            (DEFAULT_MEMORY_LIMIT_BYTES, DEFAULT_MEMORY_LIMIT_BYTES),
        )
    except (ValueError, OSError):
        # A platform that refuses the limit is not a reason to refuse the analysis.
        pass


def which(binary: str) -> str | None:
    """Absolute path to ``binary``, or None. Never raises.

    Looks beside the running interpreter **before** consulting PATH. This is not a
    nicety: when dca is installed into a virtual environment, ``pip install vulture``
    puts the console script in that environment's ``bin/`` directory, which is on PATH
    only while the environment is activated. A user who installed an engine into the
    same environment and then found it undetected would be right to call that a bug.
    """
    here = Path(sys.executable).parent
    candidate = here / binary
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return shutil.which(binary)


@lru_cache(maxsize=32)
def responds(binary_path: str, *args: str) -> bool:
    """Whether a binary actually runs, not merely whether it exists on disk.

    ``which`` answering yes is not the same as the tool working. A pyscn binary shipped for
    the wrong libc, a Go runtime that panics on a particular kernel, a half-finished
    install — all present a file that is executable and then aborts the moment it is asked
    to do anything.

    That distinction matters because the two states need opposite handling: a missing
    engine is a configuration choice and its columns are legitimately null, while a
    crashing engine is a fault someone should hear about. Without this probe both look
    identical, and a batch of thousands silently loses a whole engine's columns.

    Cached: this costs a process spawn, and it is asked once per adapter per run.
    """
    result = run([binary_path, *args], timeout=20)
    return result.returncode == 0 and not result.timed_out


def run(
    argv: list[str],
    *,
    stdin_text: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    cwd: str | None = None,
) -> CommandResult:
    """Run ``argv`` with bounded time, memory and captured output.

    Never raises for a failing child: a non-zero return code, a timeout and a crash are
    all ordinary outcomes here, reported in the result. Only a genuinely broken invocation
    (a missing binary) raises, and callers guard that with :func:`which`.
    """
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=_limit_child,
        cwd=cwd,
        env=env,
    )

    out_box: dict[str, tuple[bytes, bool]] = {}
    threads = [
        threading.Thread(
            target=lambda: out_box.__setitem__("out", _drain(proc.stdout, MAX_OUTPUT_BYTES))
        ),
        threading.Thread(
            target=lambda: out_box.__setitem__("err", _drain(proc.stderr, MAX_OUTPUT_BYTES))
        ),
    ]
    for t in threads:
        t.daemon = True
        t.start()

    if stdin_text is not None:
        try:
            proc.stdin.write(stdin_text.encode("utf-8"))
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()

    for t in threads:
        t.join(timeout=5)

    raw_out, trunc_out = out_box.get("out", (b"", False))
    raw_err, trunc_err = out_box.get("err", (b"", False))
    truncated = trunc_out or trunc_err
    if trunc_out:
        raw_out += OUTPUT_TRUNCATION_MARKER
    if trunc_err:
        raw_err += OUTPUT_TRUNCATION_MARKER

    return CommandResult(
        returncode=proc.returncode,
        stdout=raw_out.decode("utf-8", errors="replace"),
        stderr=raw_err.decode("utf-8", errors="replace"),
        timed_out=timed_out,
        truncated=truncated,
    )

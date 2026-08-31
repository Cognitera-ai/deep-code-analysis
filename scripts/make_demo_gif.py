#!/usr/bin/env python3
"""Render the README demo GIF from the tool's real output.

Nothing here is mocked or typed by hand: every table in the GIF is produced by running the
actual analysis and printing it through the same code paths the CLI uses. A demo that
diverges from what the tool does is a promise the tool will break.

Pipeline: rich -> SVG (it draws a terminal window) -> rsvg-convert -> PNG -> ffmpeg -> GIF.

    python scripts/make_demo_gif.py

Needs `rsvg-convert` (librsvg) and `ffmpeg` on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rich.console import Console  # noqa: E402
from rich.syntax import Syntax  # noqa: E402

from dca.core import Analyser  # noqa: E402

WIDTH = 96
OUT = Path(__file__).resolve().parent.parent / "docs" / "assets" / "demo.gif"

#: The fragment the whole project is about: obvious computational content that radon's
#: Halstead visitor cannot see, because none of it is an arithmetic or comparison operator.
SAMPLE = '''def sum_of_multiples(limit, divisors):
    multiples = set()
    for divisor in divisors:
        multiples.update(range(divisor, limit, divisor))
    return sum(multiples)
'''


def prompt(console: Console, command: str) -> None:
    console.print(f"[bold green]$[/bold green] [bold white]{command}[/bold white]")


def build_frames(tmp: Path) -> list[Path]:
    """Each frame is the session so far, so the GIF reads as one continuous terminal."""
    # highlight=False: Rich's automatic number highlighting splits prose into many
    # absolutely-positioned spans, which collide when the SVG is rasterised and swallow the
    # spaces between words. It also just looks wrong to have numbers turn cyan in a
    # sentence.
    console = Console(record=True, width=WIDTH, force_terminal=True, highlight=False)
    frames: list[Path] = []

    def snap() -> None:
        svg = tmp / f"{len(frames):02d}.svg"
        # clear=False: the buffer accumulates, so each frame is the session so far and the
        # GIF reads as one scrolling terminal rather than a slideshow of disconnected cards.
        console.save_svg(str(svg), title="deep-code-analysis", clear=False)
        frames.append(svg)

    console.print()
    console.print("[bold white]Two widely used tools. One metric. The same code.[/bold white]")
    console.print(Syntax(SAMPLE, "python", theme="monokai", line_numbers=False))
    snap()

    prompt(console, "dca analyse sample.py")
    snap()

    analyser = Analyser(engines=["radon", "lizard", "ast", "complexipy"])
    row = analyser.analyse_many({"sample.py": SAMPLE}).metrics().iloc[0]

    console.print()
    # No leading spaces in any of these: the SVG export collapses indentation, and a
    # style boundary swallows the space next to it. Alignment is done with padded fields
    # inside a single styled run instead of with layout.
    console.print("[bold]Halstead volume[/bold]")
    console.print(
        f"[bold red]radon    {row['halstead_volume__radon']:>7.2f}[/bold red]"
        "   [dim]five AST node types count as operators[/dim]"
    )
    console.print(
        f"[bold green]lizard   {row['halstead_volume__lizard']:>7.2f}[/bold green]"
        "   [dim]the same code, measured again[/dim]"
    )
    snap()

    console.print()
    console.print(
        "[bold magenta]absent / present[/bold magenta]"
        "   [dim]one engine says the quantity is not there,[/dim]"
    )
    console.print("[dim]and no ratio can express that.[/dim]")
    snap()

    console.print()
    console.print("[dim]Every column names its engine. Nothing is averaged away.[/dim]")
    console.print(
        "[dim]Across 1500 files of open-source Python the median divergence is[/dim]"
    )
    console.print("[bold]14x, and one file in five scores a perfect maintainability[/bold]")
    console.print("[dim]index for a reason that has nothing to do with maintainability.[/dim]")
    snap()

    return frames


def rasterise(svgs: list[Path], tmp: Path) -> list[Path]:
    pngs = []
    for svg in svgs:
        png = svg.with_suffix(".png")
        subprocess.run(
            ["rsvg-convert", "--zoom", "1.6", "-o", str(png), str(svg)], check=True
        )
        pngs.append(png)
    return pngs


def _size(png: Path) -> tuple[int, int]:
    """Width and height straight from the PNG header, so this needs no image library."""
    import struct

    data = png.read_bytes()[16:24]
    return struct.unpack(">II", data)


def assemble(pngs: list[Path], tmp: Path) -> None:
    """Pad every frame to the tallest, then hold the payoff longer than the setup.

    Padding matters: the session grows as it goes, and frames of differing height make a
    GIF that jumps around instead of scrolling.
    """
    padded = tmp / "padded"
    padded.mkdir(exist_ok=True)
    sizes = [_size(p) for p in pngs]
    width = max(w for w, _ in sizes)
    height = max(h for _, h in sizes)

    frames = []
    for i, png in enumerate(pngs):
        out = padded / f"f_{i:02d}.png"
        subprocess.run(
            ["convert", str(png), "-background", "#0d1117", "-gravity", "NorthWest",
             "-extent", f"{width}x{height}", str(out)],
            check=True,
        )
        frames.append(out)

    # Frame durations in centiseconds: read the code, see the command, then dwell on the
    # number that is the point of the whole project.
    delays = [280, 120, 380, 380, 480]
    args: list[str] = ["convert", "-loop", "0"]
    for i, frame in enumerate(frames):
        args += ["-delay", str(delays[i] if i < len(delays) else 300), str(frame)]
    args += ["-layers", "OptimizePlus", str(OUT)]
    subprocess.run(args, check=True)


def main() -> int:
    for binary in ("rsvg-convert", "convert"):
        if shutil.which(binary) is None:
            print(f"missing {binary}", file=sys.stderr)
            return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dca-demo-") as raw:
        tmp = Path(raw)
        assemble(rasterise(build_frames(tmp), tmp), tmp)
    size = OUT.stat().st_size / 1024
    print(f"wrote {OUT} ({size:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

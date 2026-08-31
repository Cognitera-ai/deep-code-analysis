"""The provenance envelope."""

from __future__ import annotations

from dca.adapters import build
from dca.provenance import GenerationProvenance, package_version
from dca.provenance import build as build_provenance


def test_versions_come_from_the_running_process_not_declarations():
    """R-12. A floor specifier is re-resolved at install time, so reporting the declared
    pin would be a fabrication."""
    envelope = build_provenance(build(["radon", "lizard"]), run_id="r", fragment_count=1)

    assert envelope.analysis_chain["radon"] == "6.0.1"
    assert envelope.analysis_chain["lizard"].startswith("1.")


def test_envelope_records_interpreter_package_and_environment():
    envelope = build_provenance(build(["radon"]), run_id="r", fragment_count=3).as_dict()

    assert envelope["interpreter"]["python_version"]
    assert envelope["interpreter"]["implementation"]
    assert envelope["package"]["schema_version"]
    assert envelope["environment"]["os"]
    assert envelope["inputs"]["fragment_count"] == 3


def test_hostname_is_hashed_not_disclosed():
    """The hostname answers 'same machine?' for reproducibility, but publishing it leaks
    institutional detail into a shared dataset."""
    import platform

    envelope = build_provenance(build(["radon"]), run_id="r", fragment_count=1).as_dict()
    fingerprint = envelope["environment"]["hostname_hash"]

    assert fingerprint
    assert platform.node() not in str(envelope)
    assert len(fingerprint) == 16


def test_generation_block_carries_sampling_parameters():
    """What makes the envelope specifically useful for LLM research: a metric without the
    parameters that produced its input is not a reproducible observation."""
    generation = GenerationProvenance(
        model="qwen2.5:14b", temperature=0.7, top_p=0.9, seed=1, repetition_penalty=1.1
    )
    envelope = build_provenance(
        build(["radon"]), run_id="r", fragment_count=1, generation=generation
    ).as_dict()

    assert envelope["generation"]["model"] == "qwen2.5:14b"
    assert envelope["generation"]["repetition_penalty"] == 1.1


def test_provenance_never_raises_on_a_broken_version_probe():
    """A failed version probe must not fail a run."""

    class Broken:
        name = "broken"

        @property
        def version(self):
            raise RuntimeError("probe exploded")

    envelope = build_provenance([Broken()], run_id="r", fragment_count=1)
    assert envelope.analysis_chain["broken"] is None


def test_package_version_is_resolvable():
    assert package_version()

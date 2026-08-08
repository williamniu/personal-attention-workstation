from __future__ import annotations

from pathlib import Path

from hcis.profiles.loader import import_document, load_profile

PROJECT = Path(__file__).parents[2]


def test_unknown_candidate_facts_are_not_invented() -> None:
    william = load_profile(PROJECT / "config" / "roles", "william")
    girlfriend = load_profile(PROJECT / "config" / "roles", "girlfriend")

    assert william.education.program is None
    assert girlfriend.education.program is None
    assert girlfriend.experience[0].description is None
    assert girlfriend.experience[0].quantitative_results == []


def test_document_import_is_candidate_isolated(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("evidence only")
    william = import_document(tmp_path / "private", "william", source, "resume")
    girlfriend = import_document(tmp_path / "private", "girlfriend", source, "resume")

    assert "/william/" in william["path"]
    assert "/girlfriend/" in girlfriend["path"]
    assert william["path"] != girlfriend["path"]

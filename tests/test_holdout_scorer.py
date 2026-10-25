"""Spelling equivalence checks must not alter frozen questions or predictions."""
import json

import pytest

from eval_holdout import (FIXTURE, SCORER_VERSION, compound_normalize, contradiction_hit,
                          digest, found, rescore_saved_report, validate_fixture, variants)


@pytest.mark.parametrize("answer", ["3-month brand warranty", "three-month brand warranty",
                                    "3\u2011month brand warranty", "3 months of brand warranty"])
def test_attributive_duration_matches_same_quantity(answer):
    assert found(r"\b3\s*months?\b.{0,30}brand", variants(answer))


@pytest.mark.parametrize("answer", ["30-month brand warranty", "13-month brand warranty",
                                    "3-year brand warranty", "3-week brand warranty"])
def test_duration_normalization_does_not_change_quantity_or_unit(answer):
    assert not found(r"\b3\s*months?\b", variants(answer))


def test_quantity_punctuation_and_identifiers_are_preserved():
    original = "ELE-0004 2-3 -3.5 2026-10-23"
    assert compound_normalize(original) == original


def test_hyphenated_word_boundaries_keep_negation():
    answer = "A change-of-mind return does not qualify for fee refunds."
    assert found(r"change of mind.{0,70}not", variants(answer))
    forbidden = {"regex": r"qualif.{0,30}fee refund", "negation_aware": True}
    assert not contradiction_hit(forbidden, variants(answer))
    assert contradiction_hit(forbidden, variants("A change-of-mind return qualifies for fee refunds."))


def test_duration_wrong_claim_is_still_detected():
    forbidden = {"regex": r"\b30\s*months?\b.{0,30}brand", "negation_aware": True}
    assert contradiction_hit(forbidden, variants("It includes a thirty-month brand warranty."))
    assert not contradiction_hit(forbidden, variants("It does not include a thirty-month brand warranty."))


def test_rescore_preserves_original_and_records_scorer_only_delta(tmp_path):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    coverage = validate_fixture(fixture)
    case = next(item for item in fixture["single_cases"] if item["id"] == "H004")
    prediction = {"answer": "12 months of Assured coverage in addition to the 3-month brand warranty. "
                             "Start an Assured claim in My Orders and the brand claim at the manufacturer service centre.",
                  "decision": case["expected_decisions"][0], "language": "en",
                  "retrieved_chunk_ids": case["gold_evidence"], "tool_calls": []}
    entry = {"id": "H004", "category": case["category"], "actual_output": prediction,
             "judgment": {"passed": False, "checks": [{"check": "required:claim_1", "passed": False}]}}
    baseline = {"coverage": coverage, "results": [entry],
                "summary": {"passed": 0, "failed": 1, "evaluated": 1, "elapsed_seconds": 4}}
    source, target = tmp_path / "original.json", tmp_path / "rescored.json"
    original = json.dumps(baseline).encode("utf-8")
    source.write_bytes(original)
    fixture_hash = digest(fixture)
    result = rescore_saved_report(source, target, fixture)
    assert source.read_bytes() == original
    assert result["results"][0]["actual_output"] == prediction
    assert result["scorer"]["version"] == SCORER_VERSION
    assert result["rescoring"]["predictions_unchanged"] is True
    assert result["rescoring"]["product_rerun"] is False
    assert result["rescoring"]["passed_delta"] == 1
    assert digest(fixture) == fixture_hash
    with pytest.raises(ValueError, match="different file"):
        rescore_saved_report(source, source, fixture)


def test_rescore_rejects_a_different_frozen_rubric(tmp_path):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source = tmp_path / "wrong.json"
    source.write_text(json.dumps({"coverage": {"questions_sha256": "different", "rubric_sha256": "different"}}))
    with pytest.raises(ValueError, match="same frozen"):
        rescore_saved_report(source, tmp_path / "result.json", fixture)

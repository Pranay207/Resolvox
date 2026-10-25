"""Independent frozen holdout evaluation; no voice or Gnani API calls.

Run --check-only to validate without importing the agent.  Run --offline for
retrieval/tool evaluation with compose=False; omit it to evaluate generation.
The fixture and rubric must not be revised in response to observed failures.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
from typing import Any

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "tests" / "holdout_cases.json"
QUESTION_HASH = "dae8714691901953f1ee0dea2c4c74f45764a4b60509046a117d1d39004373dc"
RUBRIC_HASH = "5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7"
SCORER_VERSION = "2.0.0"
PRIVATE_EMAIL = r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}"
PRIVATE_PHONE = r"\+?91[ -]?5(?:[ -]?\d){9}"
ROMAN_HINDI = r"\b(?:hai|hain|ka|ki|ke|ko|aap|nahi|nahin|karein|karo|mein|liye|aur|hoga|hogi|rakhein|karna|hote|karke)\b"
EN_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
HI_NUMBERS = {
    "\u090f\u0915": "1", "\u0926\u094b": "2", "\u0924\u0940\u0928": "3", "\u091a\u093e\u0930": "4", "\u092a\u093e\u0901\u091a": "5", "\u092a\u093e\u0902\u091a": "5",
    "\u091b\u0939": "6", "\u0938\u093e\u0924": "7", "\u0906\u0920": "8", "\u0928\u094c": "9", "\u0926\u0938": "10",
    "\u092c\u093e\u0930\u0939": "12", "\u091a\u094c\u0926\u0939": "14", "\u092a\u0902\u0926\u094d\u0930\u0939": "15", "\u092a\u0928\u094d\u0926\u094d\u0930\u0939": "15",
    "\u092a\u091a\u094d\u091a\u0940\u0938": "25", "\u0924\u0940\u0938": "30", "\u0905\u0921\u093c\u0924\u093e\u0932\u0940\u0938": "48", "\u0905\u095c\u0924\u093e\u0932\u0940\u0938": "48",
    "\u0909\u0928\u091a\u093e\u0938": "49", "\u0938\u0924\u0939\u0924\u094d\u0924\u0930": "77", "\u0909\u0928\u094d\u0928\u093e\u0938\u0940": "79",
}
_NUMBER_WORDS = sorted(list(EN_NUMBERS) + ["hundred", "thousand", "lakh"], key=len, reverse=True)
_NUMBER_SPAN = re.compile(r"\b(?:" + "|".join(_NUMBER_WORDS) + r")(?:[ -]+(?:" + "|".join(_NUMBER_WORDS) + r"))*\b", re.I)


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def base_normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).lower()
    text = "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in text)
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u2212", "-").replace("\u2013", "-")
    return re.sub(r"\s+", " ", text).strip()


def number_normalize(text: str) -> str:
    def convert(match: re.Match[str]) -> str:
        total = current = 0
        words = re.split(r"[ -]+", match.group().lower())
        for word in words:
            if word == "hundred":
                current = max(current, 1) * 100
            elif word in ("thousand", "lakh"):
                total += max(current, 1) * (1000 if word == "thousand" else 100000)
                current = 0
            else:
                current += EN_NUMBERS[word]
        return str(total + current)
    text = _NUMBER_SPAN.sub(convert, text)
    for word, number in HI_NUMBERS.items():
        text = re.sub(r"(?<![\w])" + re.escape(word) + r"(?![\w])", number, text)
    return re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", r"\1", text)


def compound_normalize(text: str) -> str:
    """Canonicalize equivalent English hyphen compounds, retaining quantities.

    Attributive ``3-month warranty`` means the same duration as ``3 months``.
    Hyphens between words are word boundaries (``change-of-mind``), but minus
    signs, numeric ranges, identifiers and decimal points remain untouched.
    This is a spelling transformation, not stemming or semantic paraphrasing.
    """
    hyphens = r"[-\u2010-\u2015]"
    units = r"day|week|month|year|hour|minute|second"

    def unit(match: re.Match[str]) -> str:
        quantity, name = match.group(1), match.group(2)
        return quantity + " " + name + ("" if quantity == "1" else "s")

    text = re.sub(r"\b(\d+)\s*" + hyphens + r"\s*(" + units + r")s?\b", unit, text)
    return re.sub(r"(?<=[a-z])" + hyphens + r"(?=[a-z])", " ", text)


def variants(text: Any) -> list[str]:
    first = base_normalize(text)
    numbers = number_normalize(first)
    return list(dict.fromkeys([first, numbers, compound_normalize(first), compound_normalize(numbers)]))


def scorer_metadata() -> dict[str, Any]:
    return {
        "version": SCORER_VERSION,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "normalizations": ["unicode_nfkc_and_digits", "lowercase_and_whitespace",
                           "english_and_hindi_number_words", "english_ordinal_suffixes",
                           "hyphenated_duration_units", "hyphens_between_english_words"],
        "frozen_rubric_unchanged": True,
        "limitation": "Regex checks approximate meaning; equivalent spellings do not prove semantic correctness.",
    }


def found(pattern: str, texts: list[str]) -> bool:
    return any(re.search(pattern, text, re.I | re.S) for text in texts)


def negated_prefix(text: str, start: int) -> bool:
    # A deliberately modest heuristic: ignore "do not try a different socket",
    # but retain the actual matched answer so human review can audit this choice.
    prefix = re.split(r"[.!?;:\n]|\b(?:but|however|lekin)\b|\u0932\u0947\u0915\u093f\u0928", text[:start])[-1][-60:]
    return bool(re.search(r"\b(?:not|never|cannot|can't|don't|won't|avoid)\b|\u0928\u0939\u0940\u0902|\u0928\u0939\u0940|\u092e\u0924|\u0928 \u0915\u0930\u0947\u0902", prefix, re.I))


def contradiction_hit(rule: dict[str, Any], texts: list[str]) -> bool:
    for text in texts:
        for match in re.finditer(rule["regex"], text, re.I | re.S):
            if not rule.get("negation_aware", True) or not negated_prefix(text, match.start()):
                return True
    return False


def evidence_ids(output: dict[str, Any]) -> set[str]:
    ids = {str(x) for x in output.get("retrieved_chunk_ids", []) if isinstance(x, (str, int))}
    for source in output.get("sources", []):
        if isinstance(source, dict):
            for key in ("id", "chunk_id", "section_id"):
                if source.get(key):
                    ids.add(str(source[key]))
    return ids


def evidence_matches(expected: str, ids: set[str]) -> bool:
    return any(value == expected or re.fullmatch(re.escape(expected) + r"(?:[#:]|::|/chunk/).+", value) for value in ids)


def partial_equal(expected: dict[str, Any], actual: Any) -> bool:
    if not isinstance(actual, dict):
        return False
    return all(key in actual and (partial_equal(value, actual[key]) if isinstance(value, dict)
                                 else actual[key] == value) for key, value in expected.items())


def tool_matches(expected: dict[str, Any], actual: Any, submitted: list[str]) -> bool:
    if not isinstance(actual, dict) or actual.get("name") != expected["name"]:
        return False
    arguments = actual.get("arguments", {})
    if not partial_equal(expected.get("arguments", {}), arguments):
        return False
    if not partial_equal(expected.get("result", {}), actual.get("result", {})):
        return False
    for key, pattern in expected.get("arguments_regex", {}).items():
        if key not in arguments or not found(pattern, variants(arguments[key])):
            return False
    if expected.get("submitted_verification"):
        value = str(arguments.get("verification_value", ""))
        if value not in submitted and value.upper() not in ("[REDACTED]", "[REDACTED_VERIFICATION]", "[MASKED]"):
            return False
    return True


def redact(value: Any, submitted: list[str]) -> Any:
    if isinstance(value, dict):
        protected = {"verification_value", "phone_last4", "phone", "email", "street_address", "address"}
        return {key: "[REDACTED]" if key.lower() in protected else redact(item, submitted)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, submitted) for item in value]
    if isinstance(value, str):
        result = value
        for proof in submitted:
            pattern = r"(?<!\d)" + re.escape(proof) + r"(?!\d)" if proof.isdigit() else re.escape(proof)
            result = re.sub(pattern, "[REDACTED]", result)
        result = re.sub(PRIVATE_EMAIL, "[REDACTED_EMAIL]", result, flags=re.I)
        result = re.sub(PRIVATE_PHONE, "[REDACTED_PHONE]", result)
        result = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]+", "[REDACTED_SECRET]", result, flags=re.I)
        return result
    return value


def judge(case: dict[str, Any], output: Any, submitted: list[str]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def check(name: str, passed: bool, detail: Any = None) -> None:
        item = {"check": name, "passed": bool(passed)}
        if detail is not None:
            item["detail"] = detail
        checks.append(item)
    if not isinstance(output, dict):
        check("response_is_object", False, type(output).__name__)
        return {"passed": False, "checks": checks}
    answer = output.get("answer", "")
    texts = variants(answer)
    check("nonempty_answer", isinstance(answer, str) and bool(answer.strip()))
    check("decision", output.get("decision") in case["expected_decisions"],
          {"expected": case["expected_decisions"], "actual": output.get("decision")})
    language = case.get("expected_language")
    if language:
        check("language_label", output.get("language") == language,
              {"expected": language, "actual": output.get("language")})
        if language == "hi":
            check("hindi_script", bool(re.search(r"[\u0900-\u097f]", str(answer))))
        if language == "hi-en":
            check("hinglish_wording", found(ROMAN_HINDI, texts))
    for rule in case.get("required_assertions", []):
        check("required:" + rule["id"], any(found(pattern, texts) for pattern in rule["any_regex"]),
              rule["description"])
    for rule in case.get("forbidden_assertions", []):
        check("forbidden:" + rule["id"], not contradiction_hit(rule, texts), rule["description"])
    check("no_private_email", not found(PRIVATE_EMAIL, texts))
    check("no_full_phone_number", not found(PRIVATE_PHONE, texts))
    if "max_question_marks" in case:
        check("one_question_at_a_time", str(answer).count("?") <= case["max_question_marks"])
    ids = evidence_ids(output)
    missing = [expected for expected in case.get("gold_evidence", []) if not evidence_matches(expected, ids)]
    check("gold_evidence_coverage", not missing, {"missing": missing, "observed": sorted(ids)})
    calls = output.get("tool_calls", [])
    if not isinstance(calls, list):
        calls = []
        check("tool_calls_is_list", False)
    expectations = case.get("tool_expectations", {})
    for number, expected in enumerate(expectations.get("required", []), 1):
        check("required_tool:" + str(number) + ":" + expected["name"],
              any(tool_matches(expected, call, submitted) for call in calls),
              redact(expected, submitted))
    for forbidden in expectations.get("forbidden", []):
        check("forbidden_tool:" + forbidden,
              not any(isinstance(call, dict) and call.get("name") == forbidden for call in calls))
    for number, call in enumerate(calls, 1):
        if not isinstance(call, dict):
            check("tool_record:" + str(number), False)
            continue
        result = call.get("result", {})
        arguments = call.get("arguments", {})
        if call.get("name") == "lookup_order" and isinstance(result, dict) and not result.get("verified"):
            disclosed = bool(result.get("order") or result.get("items") or result.get("customer_first_name"))
            check("unverified_lookup_has_no_private_data:" + str(number), not disclosed)
        if call.get("name") == "create_ticket":
            summary = str(arguments.get("summary", ""))
            check("ticket_has_substantive_summary:" + str(number), len(summary.strip()) >= 30)
            order_id = arguments.get("order_id")
            if order_id:
                check("ticket_summary_has_order_id:" + str(number), str(order_id) in summary)
            intent = str(output.get("intent", "")).strip()
            stated_intent = str(arguments.get("intent", "")).strip()
            check("ticket_records_detected_intent:" + str(number),
                  bool(intent) and (intent == stated_intent or intent.lower().replace("_", " ") in summary.lower()))
    failed_ticket = any(isinstance(call, dict) and call.get("name") == "create_ticket"
                        and not call.get("result", {}).get("created") for call in calls)
    if failed_ticket:
        rule = {"regex": r"(?:ticket|case).{0,25}(?:created|raised)|created.{0,25}ticket",
                "negation_aware": True}
        check("no_false_success_after_ticket_failure", not contradiction_hit(rule, texts))
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def validate_fixture(data: dict[str, Any]) -> dict[str, Any]:
    singles, scenarios = data["single_cases"], data["scenarios"]
    payload = {"single_cases": singles, "scenarios": scenarios}
    questions = [{"id": case["id"], "question": case["question"]} for case in singles]
    questions += [{"id": scenario["id"] + "/" + turn["id"], "question": turn["question"]}
                  for scenario in scenarios for turn in scenario["turns"]]
    question_hash, rubric_hash = digest(questions), digest(payload)
    if question_hash != QUESTION_HASH or question_hash != data["metadata"]["questions_sha256"]:
        raise ValueError("Frozen question hash mismatch; restore the original fixture.")
    if rubric_hash != RUBRIC_HASH or rubric_hash != data["metadata"]["rubric_sha256"]:
        raise ValueError("Frozen rubric hash mismatch; restore the original fixture.")
    if len(singles) < 50 or len(scenarios) < 8:
        raise ValueError("Holdout coverage below minimum.")
    ids = [case["id"] for case in singles] + [scenario["id"] for scenario in scenarios]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate case/scenario ID.")
    for scenario in scenarios:
        if len(scenario["turns"]) < 2:
            raise ValueError("A scenario must contain multiple turns.")
    all_cases = singles + [turn for scenario in scenarios for turn in scenario["turns"]]
    for case in all_cases:
        if not case["question"] or not case["expected_decisions"] or not case["required_assertions"]:
            raise ValueError("Each case needs a question, decisions and semantic assertions.")
        for assertion in case.get("required_assertions", []):
            for pattern in assertion["any_regex"]:
                re.compile(pattern)
        for assertion in case.get("forbidden_assertions", []):
            re.compile(assertion["regex"])
        for expected in case.get("tool_expectations", {}).get("required", []):
            for pattern in expected.get("arguments_regex", {}).values():
                re.compile(pattern)
    return {"single_cases": len(singles), "scenarios": len(scenarios),
            "scenario_turns": sum(len(scenario["turns"]) for scenario in scenarios),
            "total_turns": len(all_cases), "questions_sha256": question_hash, "rubric_sha256": rubric_hash}


def summarize(results: list[dict[str, Any]], planned: int, elapsed: float) -> dict[str, Any]:
    passed = sum(item["judgment"]["passed"] for item in results)
    failures = Counter(check["check"].split(":")[0] for item in results
                       for check in item["judgment"]["checks"] if not check["passed"])
    categories: dict[str, dict[str, int]] = {}
    for item in results:
        totals = categories.setdefault(item["category"], {"passed": 0, "total": 0})
        totals["total"] += 1
        totals["passed"] += int(item["judgment"]["passed"])
    return {"passed": passed, "failed": len(results) - passed, "evaluated": len(results),
            "planned": planned, "complete": len(results) == planned,
            "pass_rate": passed / len(results) if results else 0.0,
            "failed_check_counts": dict(failures), "by_category": categories,
            "elapsed_seconds": round(elapsed, 3)}


def rescore_saved_report(source: Path, output: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    """Rejudge unchanged saved predictions and keep the original artifact intact."""
    if source.resolve() == output.resolve():
        raise ValueError("Rescoring must write to a different file; preserve the original predictions and judgments.")
    coverage = validate_fixture(fixture)
    original_bytes = source.read_bytes()
    report = json.loads(original_bytes)
    previous_scorer = report.get("scorer", {"version": "legacy_v1_unversioned"})
    source_coverage = report.get("coverage", {})
    if any(source_coverage.get(key) != coverage[key] for key in ("questions_sha256", "rubric_sha256")):
        raise ValueError("Saved report does not use the same frozen questions and rubric.")
    cases = {case["id"]: (case, []) for case in fixture["single_cases"]}
    cases.update({scenario["id"] + "/" + turn["id"]: (turn, scenario.get("sensitive_values", []))
                  for scenario in fixture["scenarios"] for turn in scenario["turns"]})
    predictions = [{"id": entry["id"], "actual_output": entry.get("actual_output")}
                   for entry in report["results"]]
    seen: set[str] = set()
    changes: list[dict[str, Any]] = []
    old_summary = report["summary"]
    for entry in report["results"]:
        case_id = entry["id"]
        if case_id in seen or case_id not in cases:
            raise ValueError("Unknown or duplicate saved case ID: " + case_id)
        seen.add(case_id)
        case, proofs = cases[case_id]
        previous = entry["judgment"]
        # A runtime failure is a product failure, not a normalization opportunity.
        updated = previous if entry.get("error") else judge(case, entry.get("actual_output"), proofs)
        changed_checks = [check["check"] for check in updated["checks"]
                          if any(old["check"] == check["check"] and old["passed"] != check["passed"]
                                 for old in previous["checks"])]
        if updated != previous:
            changes.append({"id": case_id, "previous_passed": previous["passed"],
                            "rescored_passed": updated["passed"], "changed_checks": changed_checks})
        entry["previous_judgment"] = previous
        entry["judgment"] = updated
    assert predictions == [{"id": entry["id"], "actual_output": entry.get("actual_output")}
                           for entry in report["results"]]
    report["summary"] = summarize(report["results"], coverage["total_turns"], old_summary.get("elapsed_seconds", 0))
    report["scorer"] = scorer_metadata()
    report["rescoring"] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": source.name,
        "source_file_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "source_scorer": previous_scorer,
        "predictions_sha256": digest(predictions), "predictions_unchanged": True,
        "product_rerun": False, "previous_summary": old_summary,
        "passed_delta": report["summary"]["passed"] - old_summary["passed"],
        "changed_cases": changes,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Validate frozen hashes and rubric without importing runtime.")
    parser.add_argument("--offline", action="store_true", help="Use compose=False; this is not an LLM generation evaluation.")
    parser.add_argument("--lexical", action="store_true", help="Use dense=False for a diagnostic lexical retrieval run.")
    parser.add_argument("--rescore-input", type=Path, help="Rejudge saved predictions only; no runtime or model calls.")
    parser.add_argument("--output", type=Path, help="Defaults to eval_holdout.json, or eval_holdout_rescored.json when rescoring.")
    args = parser.parse_args()
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    coverage = validate_fixture(data)
    if args.check_only:
        print(json.dumps({"validated": True, **coverage}, indent=2))
        return 0

    if args.rescore_input:
        output = args.output or ROOT / "sample_outputs" / "eval_holdout_rescored.json"
        rescored = rescore_saved_report(args.rescore_input, output, data)
        print(json.dumps({"summary": rescored["summary"], "rescoring": rescored["rescoring"]}, indent=2))
        return 0 if rescored["summary"]["failed"] == 0 else 1
    args.output = args.output or ROOT / "sample_outputs" / "eval_holdout.json"
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    report = {
        "evaluation": data["metadata"]["name"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "offline_compose_false" if args.offline else "llm_compose_true",
        "dense_retrieval": not args.lexical,
        "reference_date": data["metadata"]["reference_date"],
        "coverage": coverage,
        "scorer": scorer_metadata(),
        "judging_limitations": data["metadata"]["judging_limitations"],
        "results": results,
    }

    def persist() -> None:
        report["summary"] = summarize(results, coverage["total_turns"], time.perf_counter() - started)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    def run(case: dict[str, Any], agent: Any, case_id: str, category: str, proofs: list[str]) -> None:
        tick = time.perf_counter()
        try:
            output = agent.respond(case["question"])
            judgment = judge(case, output, proofs)
            error = None
        except Exception as exc:
            output = None
            judgment = {"passed": False, "checks": [{"check": "runtime_exception", "passed": False,
                         "detail": type(exc).__name__}]}
            error = redact(str(exc)[:2000], proofs)
        entry = {
            "id": case_id, "category": category, "question": redact(case["question"], proofs),
            "expected_decisions": case["expected_decisions"],
            "expected_language": case.get("expected_language"), "gold_evidence": case.get("gold_evidence", []),
            "judgment": judgment, "actual_output": redact(output, proofs),
            "elapsed_seconds": round(time.perf_counter() - tick, 3),
        }
        if error:
            entry["error"] = error
        results.append(entry)
        persist()
        print(case_id + ": " + ("PASS" if judgment["passed"] else "FAIL"), flush=True)

    # The runtime is deliberately imported only after fixture integrity checks.
    try:
        from src.agent import Agent, Resources
        resources = Resources(dense=not args.lexical)
    except Exception as exc:
        report["initialization_error"] = {"type": type(exc).__name__, "message": redact(str(exc)[:2000], [])}
        persist()
        print(json.dumps({"initialization_failed": True, "output": str(args.output)}))
        return 2

    for case in data["single_cases"]:
        run(case, Agent(resources=resources, compose=not args.offline), case["id"], case["category"], [])
    for scenario in data["scenarios"]:
        agent = Agent(resources=resources, compose=not args.offline)
        for turn in scenario["turns"]:
            run(turn, agent, scenario["id"] + "/" + turn["id"], scenario["category"],
                scenario.get("sensitive_values", []))
    persist()
    print(json.dumps(report["summary"], indent=2))
    print("Actual outputs and per-assertion failures: " + str(args.output))
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

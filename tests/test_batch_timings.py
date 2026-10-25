"""Pipeline timing coverage using a fake clock and no external services."""
import json

import pytest

import run as runner
from src.voice import VoiceError


class Clock:
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def offline_pipeline(monkeypatch):
    clock = Clock()
    startup_calls = []
    mode = {"failure": None}
    agent_timings = {"retrieval_ms": 11., "llm_ms": 22., "validation_ms": 33.}

    def resources():
        startup_calls.append(True)
        clock.advance(.25)
        return object()

    class Agent:
        def __init__(self, shared, compose):
            assert compose is False

        def respond(self, transcript, **kwargs):
            clock.advance(2.)
            if mode["failure"] == "agent":
                raise RuntimeError("private-exception-sentinel")
            return {"transcript": transcript, "answer": "A safe answer.", "decision": "answer", "language": "en", "sources": [], "tool_calls": [], "timings": agent_timings.copy()}

    class Voice:
        def transcribe(self, path, language):
            clock.advance(1.)
            if mode["failure"] in {"stt", "recovery_tts"}:
                raise VoiceError("Invalid clip")
            if mode["failure"] == "unexpected_stt":
                raise RuntimeError("private-exception-sentinel")
            return "A policy question"

        def synthesize(self, text, path, language):
            clock.advance(3.)
            if mode["failure"] in {"tts", "recovery_tts"}:
                raise VoiceError("Speech unavailable")
            path.write_bytes(b"synthetic-test-audio")

    monkeypatch.setattr(runner.time, "perf_counter", clock)
    monkeypatch.setattr(runner, "resources", resources)
    monkeypatch.setattr(runner, "Agent", Agent)
    return Voice(), mode, startup_calls, agent_timings


def test_batch_records_startup_and_stage_times_without_replacing_agent_timings(tmp_path, offline_pipeline):
    voice, _, startup_calls, agent_timings = offline_pipeline
    folder = tmp_path / "inputs"
    folder.mkdir()
    for name in ["first.wav", "second.wav"]:
        (folder / name).write_bytes(b"fake-input")
    output = tmp_path / "outputs"

    result = runner.run_batch(folder, output, compose=False, voice=voice)

    assert len(startup_calls) == 1
    assert result["startup_ms"] == 250.
    assert result["batch_wall_ms"] == 12250.
    assert result["succeeded"] == 2 and result["failed"] == 0
    for entry in result["entries"]:
        assert entry["status"] == "ok"
        expected = {"stt_ms": 1000., "agent_ms": 2000., "tts_ms": 3000., "total_ms": 6000.}
        assert {name: entry[name] for name in expected} == expected
        assert entry["latency_ms"] == entry["total_ms"]
        saved = json.loads((output / (entry["output_prefix"] + ".json")).read_text(encoding="utf-8"))
        assert saved["timings"] == agent_timings
        assert saved["voice_timings"] == expected
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8")) == result


@pytest.mark.parametrize("failure,status,agent_ms,tts_ms", [
    ("stt", "error", 0., 3000.),
    ("recovery_tts", "error", 0., 3000.),
    ("tts", "tts_error", 2000., 3000.),
    ("unexpected_stt", "error", 0., 0.),
    ("agent", "error", 2000., 0.),
])
def test_failed_stages_and_recovery_are_timed_without_exposing_exception_details(tmp_path, offline_pipeline, failure, status, agent_ms, tts_ms):
    voice, mode, _, _ = offline_pipeline
    mode["failure"] = failure
    folder = tmp_path / "inputs"
    folder.mkdir()
    (folder / "clip.wav").write_bytes(b"fake-input")
    output = tmp_path / "outputs"

    result = runner.run_batch(folder, output, compose=False, voice=voice)

    entry = result["entries"][0]
    assert entry["status"] == status
    assert entry["stt_ms"] == 1000.
    assert entry["agent_ms"] == agent_ms
    assert entry["tts_ms"] == tts_ms
    assert entry["total_ms"] == 1000. + agent_ms + tts_ms
    assert entry["latency_ms"] == entry["total_ms"]
    assert result["batch_wall_ms"] == 250. + entry["total_ms"]
    assert result["succeeded"] == 0 and result["failed"] == 1
    saved = json.loads((output / (entry["output_prefix"] + ".json")).read_text(encoding="utf-8"))
    assert saved["voice_timings"]["tts_ms"] == tts_ms
    assert "private-exception-sentinel" not in json.dumps(result) + json.dumps(saved)
    if failure == "stt":
        assert entry["audio"] and saved["decision"] == "clarify"
    if failure == "recovery_tts":
        assert "audio" not in entry
    if failure == "tts":
        assert entry["agent_succeeded"] and saved["voice_error"] == "Speech unavailable"

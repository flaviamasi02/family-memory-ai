from __future__ import annotations

import json
from pathlib import Path

from ai_runtime.models import AIRuntimeInstallationRecord, AIRuntimeState, AIRuntimeStatus, PythonEnvironmentInfo
from vision.batch_embedding_service import BatchEmbeddingService, embedding_failure_diagnostic_lines
from vision.embedding_provider import EmbeddingStore, source_identity
from vision.managed_mobileclip_provider import ManagedMobileCLIPEmbeddingProvider

JPEG_BYTES = b'\xff\xd8\xffmanaged-test-jpeg'


def image(path: Path, marker: bytes = b"ok") -> Path:
    path.write_bytes(JPEG_BYTES + marker)
    return path


class FakeRuntimeManager:
    def __init__(self, state=AIRuntimeState.READY.value):
        self.state = state
        self.status_calls = []
        self.record = AIRuntimeInstallationRecord(
            provider_id="mobileclip",
            installation_state=state,
            interpreter_path="/managed/mobileclip/python",
            local_model_cache_path="/managed/mobileclip/cache",
            last_error="runtime not ready" if state != AIRuntimeState.READY.value else "",
        )

    def status(self, provider_id: str, deep: bool = True):
        self.status_calls.append((provider_id, deep))
        return AIRuntimeStatus(
            provider_id=provider_id,
            state=self.state,
            provider_available=self.state == AIRuntimeState.READY.value,
            dependencies_available=self.state == AIRuntimeState.READY.value,
            model_files_available=self.state == AIRuntimeState.READY.value,
            last_error=self.record.last_error,
            environment=PythonEnvironmentInfo(self.record.interpreter_path, valid=True),
        )

    def installation_record(self, provider_id: str):
        return self.record


class FakeStdout:
    def __init__(self):
        self.lines = [json.dumps({"event": "ready"}) + "\n"]

    def readline(self):
        return self.lines.pop(0) if self.lines else ""


class FakeStderr:
    def read(self):
        return ""


class FakeStdin:
    def __init__(self, process):
        self.process = process
        self.buffer = ""

    def write(self, text):
        self.buffer += text

    def flush(self):
        request = json.loads(self.buffer.strip().splitlines()[-1])
        records = []
        for raw in request["paths"]:
            path = Path(raw)
            if "bad" in path.name:
                records.append({"status": "failed", "path": str(path), "error_type": "ValueError", "error": "Unable to read image data"})
            else:
                key, mt, sz, fp = source_identity(path)
                records.append({"status": "ok", "photo_key": key, "source_mtime_ns": mt, "source_size": sz, "source_fingerprint": fp, "embedding": [1.0, 0.0] + [0.0] * 510})
        self.process.stdout.lines.append(json.dumps({"event": "result", "records": records}) + "\n")


class FakeProcess:
    def __init__(self):
        self.stdout = FakeStdout()
        self.stderr = FakeStderr()
        self.stdin = FakeStdin(self)
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -1


def test_automatic_embedding_uses_configured_managed_interpreter_and_stores_embeddings(tmp_path):
    manager = FakeRuntimeManager()
    provider = ManagedMobileCLIPEmbeddingProvider(runtime_manager=manager)
    started = []

    def start(interpreter, cache):
        started.append((interpreter, cache))
        return FakeProcess()

    provider._start_process = start
    p = image(tmp_path / "ok.jpg")
    store = EmbeddingStore(tmp_path / "e.sqlite3")

    result = BatchEmbeddingService(provider, store).embed_images([p])

    assert result.processed_successfully == 1
    assert result.failed == 0
    assert started == [("/managed/mobileclip/python", "/managed/mobileclip/cache")]
    assert manager.status_calls == [("mobileclip", True)]
    assert store.get_valid(p, provider.metadata) is not None


def test_main_application_environment_does_not_need_torch_for_managed_embedding(tmp_path, monkeypatch):
    manager = FakeRuntimeManager()
    provider = ManagedMobileCLIPEmbeddingProvider(runtime_manager=manager)
    provider._start_process = lambda interpreter, cache: FakeProcess()
    real_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name in {"torch", "torchvision", "mobileclip"}:
            raise AssertionError(f"main app attempted to import {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)

    result = BatchEmbeddingService(provider, EmbeddingStore(tmp_path / "e.sqlite3")).embed_images([image(tmp_path / "ok.jpg")])

    assert result.processed_successfully == 1


def test_missing_managed_runtime_produces_one_grouped_runtime_failure(tmp_path):
    provider = ManagedMobileCLIPEmbeddingProvider(runtime_manager=FakeRuntimeManager(AIRuntimeState.DEPENDENCIES_MISSING.value))
    paths = [image(tmp_path / f"{idx}.jpg", str(idx).encode()) for idx in range(3)]

    result = BatchEmbeddingService(provider, EmbeddingStore(tmp_path / "e.sqlite3")).embed_images(paths)
    lines = embedding_failure_diagnostic_lines(result)

    assert result.failed == 3
    assert len(result.outcomes) == 1
    assert result.outcomes[0].image == "<runtime>"
    assert "x3" in lines[0]
    assert "not Ready" in lines[0]


def test_unreadable_files_remain_isolated_per_image_failures(tmp_path):
    manager = FakeRuntimeManager()
    provider = ManagedMobileCLIPEmbeddingProvider(runtime_manager=manager)
    provider._start_process = lambda interpreter, cache: FakeProcess()
    good = image(tmp_path / "good.jpg")
    bad = image(tmp_path / "bad.jpg")

    result = BatchEmbeddingService(provider, EmbeddingStore(tmp_path / "e.sqlite3")).embed_images([good, bad])

    assert result.processed_successfully == 1
    assert result.failed == 1
    failures = [outcome for outcome in result.outcomes if outcome.status == "failed"]
    assert len(failures) == 1
    assert failures[0].image == str(bad)
    assert failures[0].error == "Unable to read image data"

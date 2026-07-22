from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from threading import Event

from ai_runtime.manager import AIRuntimeManager, create_default_runtime_manager
from ai_runtime.models import AIRuntimeState
from vision.embedding_provider import EmbeddingRecord, ModelMetadata, ProviderStatus, VisionEmbeddingProvider, now_iso
from vision.mobileclip_provider import MOBILECLIP_S0


class ManagedMobileCLIPEmbeddingProvider:
    """MobileCLIP image embedding provider backed by the managed runtime interpreter.

    This provider intentionally never imports torch/mobileclip in the main app
    process. Inference runs in the interpreter selected and verified by the AI
    Runtime Manager.
    """

    def __init__(self, runtime_manager: AIRuntimeManager | None = None, batch_size: int = 4):
        self.metadata: ModelMetadata = MOBILECLIP_S0
        self.batch_size = max(1, min(16, int(batch_size)))
        self.requires_image_decode_validation = False
        self.runtime_manager = runtime_manager or create_default_runtime_manager()
        self._process = None
        self._interpreter = ""
        self._cache = ""

    def availability(self) -> ProviderStatus:
        try:
            status = self.runtime_manager.status(self.metadata.provider_id, deep=True)
        except Exception as exc:
            return ProviderStatus("Not installed", f"Managed MobileCLIP runtime status check failed: {exc}", ())
        if status.state != AIRuntimeState.READY.value:
            missing = tuple(status.missing_dependencies or ())
            details = status.last_error or status.state
            return ProviderStatus(status.state, f"Managed MobileCLIP runtime is not Ready: {details}", missing)
        return ProviderStatus("Ready", "Managed MobileCLIP runtime is Ready.", ())

    def prepare_batch(self, paths: list[Path], cancel_event: Event | None = None) -> None:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Cancelled")
        status = self.availability()
        if status.state != "Ready":
            raise RuntimeError(status.message)
        rec = self.runtime_manager.installation_record(self.metadata.provider_id)
        if not rec.interpreter_path:
            raise RuntimeError("Managed MobileCLIP runtime is not Ready: no interpreter is configured.")
        self._interpreter = rec.interpreter_path
        self._cache = rec.local_model_cache_path

    def load(self, cancel_event: Event | None = None) -> None:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Cancelled")
        if self._process is not None and self._process.poll() is None:
            return
        if not self._interpreter or not self._cache:
            self.prepare_batch([], cancel_event)
        self._process = self._start_process(self._interpreter, self._cache)
        line = self._readline(timeout_seconds=900, cancel_event=cancel_event)
        payload = _json_line(line)
        if payload.get("event") != "ready":
            raise RuntimeError(str(payload.get("error") or "Managed MobileCLIP worker did not become ready."))

    def embed_images(self, paths: list[Path], cancel_event: Event | None = None) -> list[EmbeddingRecord]:
        self.load(cancel_event)
        if cancel_event and cancel_event.is_set():
            return []
        assert self._process is not None
        request = {"paths": [str(Path(p)) for p in paths[: self.batch_size]]}
        try:
            self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self._process.stdin.flush()
        except Exception as exc:
            self.release()
            raise RuntimeError(f"Managed MobileCLIP worker request failed: {exc}") from exc
        line = self._readline(timeout_seconds=900, cancel_event=cancel_event)
        payload = _json_line(line)
        if payload.get("event") != "result":
            raise RuntimeError(str(payload.get("error") or "Managed MobileCLIP worker returned an unexpected response."))
        records = []
        for item in payload.get("records") or []:
            status = str(item.get("status") or "failed")
            if status == "ok":
                embedding = [float(v) for v in item.get("embedding") or []]
                records.append(EmbeddingRecord(str(item["photo_key"]), str(item["source_fingerprint"]), int(item["source_mtime_ns"]), int(item["source_size"]), self.metadata.provider_id, self.metadata.checkpoint_id, self.metadata.revision, len(embedding), embedding, now_iso()))
            else:
                records.append(EmbeddingRecord(str(item.get("photo_key") or item.get("path") or ""), "", 0, 0, self.metadata.provider_id, self.metadata.checkpoint_id, self.metadata.revision, self.metadata.embedding_dimension, [], now_iso(), "failed", str(item.get("error") or "Managed MobileCLIP worker failed for image.")))
        return records

    def embed_texts(self, prompts: list[str], cancel_event: Event | None = None) -> list[list[float]]:
        raise NotImplementedError("Managed MobileCLIP text embeddings are not required for import indexing yet.")

    def release(self) -> None:
        proc = self._process
        self._process = None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
        except Exception:
            pass

    def _start_process(self, interpreter: str, cache: str):
        return subprocess.Popen(
            [str(interpreter), "-u", "-c", _WORKER_SCRIPT, str(cache)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )

    def _readline(self, timeout_seconds: int, cancel_event: Event | None = None) -> str:
        assert self._process is not None
        start = time.perf_counter()
        while True:
            if cancel_event and cancel_event.is_set():
                self.release()
                raise RuntimeError("Cancelled")
            if self._process.poll() is not None:
                stderr = self._process.stderr.read() if self._process.stderr else ""
                raise RuntimeError(f"Managed MobileCLIP worker exited with code {self._process.returncode}: {stderr[-1000:]}")
            line = self._process.stdout.readline()
            if line:
                return line
            if time.perf_counter() - start > timeout_seconds:
                self.release()
                raise TimeoutError("Managed MobileCLIP worker timed out.")
            time.sleep(0.05)


_WORKER_SCRIPT = r'''
import hashlib, json, math, pathlib, sys, traceback
cache=pathlib.Path(sys.argv[1]); ckpt=cache/'mobileclip_s0.pt'
def emit(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)
def ident(path):
    st=path.stat(); resolved=str(path.resolve()); h=hashlib.sha256(); h.update(resolved.encode('utf-8')); h.update(str(st.st_size).encode('ascii')); h.update(str(st.st_mtime_ns).encode('ascii'))
    with path.open('rb') as f: h.update(f.read(1024*1024))
    return resolved, int(st.st_mtime_ns), int(st.st_size), h.hexdigest()
def norm(vec):
    vals=[float(v) for v in vec]; n=math.sqrt(sum(v*v for v in vals)); return vals if n <= 0 else [v/n for v in vals]
try:
    import torch, mobileclip
    from PIL import Image, ImageOps
    if not ckpt.exists(): raise FileNotFoundError(f'MobileCLIP checkpoint not found: {ckpt}')
    model,_,preprocess=mobileclip.create_model_and_transforms('mobileclip_s0', pretrained=str(ckpt)); model.eval(); model.to('cpu')
    emit({'event':'ready'})
except Exception as exc:
    emit({'event':'error','error_type':type(exc).__name__,'error':str(exc)})
    sys.exit(1)
for line in sys.stdin:
    try:
        req=json.loads(line); records=[]
        for raw in req.get('paths') or []:
            path=pathlib.Path(raw)
            try:
                key,mt,sz,fp=ident(path)
                with Image.open(path) as img:
                    tensor=preprocess(ImageOps.exif_transpose(img).convert('RGB')).unsqueeze(0)
                with torch.no_grad(): vec=model.encode_image(tensor).squeeze(0).cpu().tolist()
                records.append({'status':'ok','photo_key':key,'source_mtime_ns':mt,'source_size':sz,'source_fingerprint':fp,'embedding':norm(vec)})
            except Exception as exc:
                records.append({'status':'failed','path':str(path),'error_type':type(exc).__name__,'error':str(exc)})
        emit({'event':'result','records':records})
    except Exception as exc:
        emit({'event':'error','error_type':type(exc).__name__,'error':str(exc)})
'''


def _json_line(line: str) -> dict:
    try:
        data = json.loads(line.strip() or "{}")
        return data if isinstance(data, dict) else {"event": "error", "error": "Worker returned non-object JSON."}
    except Exception as exc:
        return {"event": "error", "error": f"Worker returned invalid JSON: {exc}"}

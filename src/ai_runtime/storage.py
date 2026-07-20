from __future__ import annotations
import json, shutil, traceback
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from typing import TypeVar
from core.application_data import ApplicationDataPathService, atomic_write_json
from vision.embedding_provider import now_iso
from ai_runtime.models import AIRuntimeBenchmarkRecord, AIRuntimeHistoryRecord, AIRuntimeInstallationRecord

class AIRuntimeRunLog:
    def __init__(self, path: Path, provider_id: str, action: str, interpreter: str):
        self.path = path
        self._finished = False
        self.write({"event":"start","provider_id":provider_id,"typed_action":action,"selected_interpreter":interpreter,"start_time":now_iso()})
    def write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
            fh.flush()
    def command(self, argv, stdout: str, stderr: str, exit_code: int, duration_seconds: float) -> None:
        self.write({"event":"command","command":list(argv),"stdout":stdout,"stderr":stderr,"exit_code":exit_code,"duration_seconds":duration_seconds,"time":now_iso()})
    def exception(self, exc: BaseException) -> None:
        self.write({"event":"exception","exception":repr(exc),"traceback":traceback.format_exc(),"time":now_iso()})
    def finish(self, outcome: str) -> None:
        self._finished = True
        self.write({"event":"finish","final_outcome":outcome,"finish_time":now_iso()})

T=TypeVar('T')
SCHEMA=1

class AIRuntimeStorage:
    def __init__(self, app_data: ApplicationDataPathService):
        self.app_data=app_data; self.root=app_data.root / 'ai-runtimes'; self.logs_dir=app_data.root/'logs'/'ai-runtime'; self.model_root=app_data.cache_dir('models')
        self.root.mkdir(parents=True, exist_ok=True); self.logs_dir.mkdir(parents=True, exist_ok=True); self.model_root.mkdir(parents=True, exist_ok=True)
    def _load(self, path: Path) -> dict:
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) and data.get('schema_version') == SCHEMA else {}
        except Exception:
            if path.exists(): shutil.copy2(path, path.with_suffix(path.suffix+'.corrupt'))
            return {}
    def installations(self) -> dict[str,AIRuntimeInstallationRecord]:
        data=self._load(self.root/'installations.json'); out={}
        for pid, rec in (data.get('installations') or {}).items():
            try: out[pid]=AIRuntimeInstallationRecord(**rec)
            except Exception: continue
        return out
    def save_installation(self, rec: AIRuntimeInstallationRecord) -> None:
        items=self.installations(); items[rec.provider_id]=rec
        atomic_write_json(self.root/'installations.json', {'schema_version':SCHEMA,'updated_at':now_iso(),'installations':{k:asdict(v) for k,v in items.items()}})
    def append_history(self, rec: AIRuntimeHistoryRecord) -> None:
        data=self._load(self.root/'history.json'); rows=list(data.get('records') or [])[-499:]; rows.append(asdict(rec))
        atomic_write_json(self.root/'history.json', {'schema_version':SCHEMA,'updated_at':now_iso(),'records':rows})
    def history(self) -> list[AIRuntimeHistoryRecord]:
        data=self._load(self.root/'history.json'); out=[]
        for rec in data.get('records') or []:
            try: out.append(AIRuntimeHistoryRecord(**rec))
            except Exception: continue
        return out
    def append_benchmark(self, rec: AIRuntimeBenchmarkRecord) -> None:
        data=self._load(self.root/'benchmarks.json'); rows=list(data.get('records') or [])[-199:]; rows.append(asdict(rec))
        atomic_write_json(self.root/'benchmarks.json', {'schema_version':SCHEMA,'updated_at':now_iso(),'records':rows})
    def benchmarks(self) -> list[AIRuntimeBenchmarkRecord]:
        data=self._load(self.root/'benchmarks.json'); out=[]
        for rec in data.get('records') or []:
            try: out.append(AIRuntimeBenchmarkRecord(**rec))
            except Exception: continue
        return out
    def cache_dir_for(self, provider_id: str) -> Path:
        path=self.model_root/provider_id; path.mkdir(parents=True, exist_ok=True)
        marker=path/'.family_memory_ai_owned'; marker.write_text(provider_id, encoding='utf-8') if not marker.exists() else None
        return path
    def is_owned_path(self, provider_id: str, path: Path) -> bool:
        try:
            path=Path(path).resolve(); root=(self.model_root/provider_id).resolve()
            return path == root and (path/'.family_memory_ai_owned').read_text(encoding='utf-8') == provider_id
        except Exception: return False
    def start_run_log(self, provider_id: str, action: str, interpreter: str = "") -> AIRuntimeRunLog:
        safe_action = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in action).strip("-") or "run"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        idx = 0
        while True:
            suffix = f"-{idx}" if idx else ""
            path = self.logs_dir / f"{stamp}-{provider_id}-{safe_action}{suffix}.jsonl"
            if not path.exists():
                return AIRuntimeRunLog(path, provider_id, action, interpreter)
            idx += 1

    def recent_log_text(self, limit: int = 5, max_chars: int = 12000) -> str:
        files = sorted(self.logs_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        if not files:
            return f"No AI runtime log files found in {self.logs_dir}"
        chunks = [f"AI runtime logs folder: {self.logs_dir}"]
        for file in files:
            text = file.read_text(encoding="utf-8", errors="replace")[-max_chars:]
            chunks.append(f"\n--- {file.name} ---\n{text}")
        return "\n".join(chunks)

    def disk_usage(self, path: Path) -> int:
        if not path.exists(): return 0
        return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())

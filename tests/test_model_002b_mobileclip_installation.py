from __future__ import annotations
import sys, threading
from pathlib import Path
from ai_runtime.manager import create_default_runtime_manager
from ai_runtime.models import AIRuntimeActionType, AIRuntimeState
from core.application_data import ApplicationDataPathService


def test_mobileclip_plan_uses_dedicated_interpreter_and_official_sources(tmp_path):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    plan=m.build_installation_plan('mobileclip', sys.executable)
    assert plan.device == 'CPU'
    assert 'apple/MobileCLIP-S0' == plan.checkpoint_id
    assert any('github.com/apple/ml-mobileclip' in p for p in plan.packages_to_install)
    assert any(a.argv[:3] == (plan.python_environment.interpreter_path,'-m','pip') for a in plan.actions if a.action_type == AIRuntimeActionType.INSTALL_PYTHON_PACKAGE)
    assert any('huggingface.co/apple/MobileCLIP-S0' in a.url for a in plan.actions if a.action_type == AIRuntimeActionType.DOWNLOAD_MODEL_FILE)
    assert str(tmp_path) in plan.destination_path
    assert not plan.confirmed


def test_ready_requires_full_provider_verification_record(tmp_path):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    rec=m.installation_record('mobileclip'); rec.interpreter_path=sys.executable; m.storage.save_installation(rec)
    cache=Path(rec.local_model_cache_path); (cache/'mobileclip_s0.pt').write_bytes(b'not a real checkpoint')
    status=m.status('mobileclip')
    assert status.state != AIRuntimeState.READY.value
    rec.last_validation_result='provider verification passed'; m.storage.save_installation(rec)
    status=m.status('mobileclip')
    if status.dependencies_available:
        assert status.state == AIRuntimeState.READY.value


def test_partial_download_cleanup_on_cancellation(tmp_path, monkeypatch):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    dst=tmp_path/'cache'/'mobileclip_s0.pt'
    class SlowResponse:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self, n): return b'x'*10
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: SlowResponse())
    event=threading.Event(); event.set()
    action=[a for a in m.build_installation_plan('mobileclip', sys.executable).actions if a.action_type == AIRuntimeActionType.DOWNLOAD_MODEL_FILE][0]
    action=type(action)(action.action_type, action.label, destination=str(dst), url=action.url)
    res=m._download(action, event)
    assert res.cancelled
    assert not dst.exists()
    assert not dst.with_suffix('.pt.partial').exists()

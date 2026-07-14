from __future__ import annotations
import sys, threading
from pathlib import Path
import pytest

from ai_runtime.manager import create_default_runtime_manager
from ai_runtime.models import AIRuntimeActionType, AIRuntimeInstallationPlan, AIRuntimeState
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


def test_generic_manager_has_no_hard_coded_mobileclip_download_url():
    source=Path('src/ai_runtime/manager.py').read_text(encoding='utf-8')
    assert 'huggingface.co/apple/MobileCLIP-S0' not in source


def test_selected_interpreter_is_persisted_and_install_uses_it(tmp_path):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    plan=m.build_installation_plan('mobileclip', sys.executable)
    plan.confirmed=True
    results=m.execute_installation_plan(AIRuntimeInstallationPlan(**{**plan.__dict__, 'actions': ()}))
    rec=m.installation_record('mobileclip')
    assert rec.interpreter_path == sys.executable
    assert rec.environment_path == plan.python_environment.environment_path
    assert rec.python_version == plan.python_environment.python_version
    assert rec.local_model_cache_path == plan.destination_path


def test_verify_requires_persisted_selected_interpreter(tmp_path):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    result=m.verify_provider('mobileclip')
    assert result.returncode != 0
    assert 'No persisted interpreter' in result.stderr


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


def test_partial_download_cleanup_and_progress_on_cancellation(tmp_path, monkeypatch):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    dst=tmp_path/'cache'/'mobileclip_s0.pt'
    class SlowResponse:
        headers={'Content-Length':'100'}
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self, n): return b'x'*10
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: SlowResponse())
    event=threading.Event(); event.set(); progress=[]
    action=[a for a in m.build_installation_plan('mobileclip', sys.executable).actions if a.action_type == AIRuntimeActionType.DOWNLOAD_MODEL_FILE][0]
    action=type(action)(action.action_type, action.label, destination=str(dst), url=action.url)
    res=m._download(action, event, lambda done,total: progress.append((done,total)))
    assert res.cancelled
    assert not dst.exists()
    assert not dst.with_suffix('.pt.partial').exists()


def test_existing_invalid_checkpoint_is_not_accepted(tmp_path):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    dst=tmp_path/'mobileclip_s0.pt'; dst.write_bytes(b'tiny')
    action=[a for a in m.build_installation_plan('mobileclip', sys.executable).actions if a.action_type == AIRuntimeActionType.DOWNLOAD_MODEL_FILE][0]
    action=type(action)(action.action_type, action.label, destination=str(dst), url=action.url)
    res=m._download(action, minimum_size_bytes=200)
    assert res.returncode != 0
    assert 'too small' in res.stderr


def test_removal_requires_confirmation_and_deletes_only_owned_files(tmp_path):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    cache=Path(m.installation_record('mobileclip').local_model_cache_path)
    owned=cache/'mobileclip_s0.pt'; owned.write_bytes(b'x')
    outside=tmp_path/'photo.jpg'; outside.write_bytes(b'photo')
    plan=m.removal_plan('mobileclip')
    with pytest.raises(PermissionError):
        m.execute_removal_plan(plan)
    plan.confirmed=True
    result=m.execute_removal_plan(plan)
    assert all(r.returncode == 0 for r in result)
    assert not owned.exists()
    assert outside.exists()


def test_settings_install_cancel_and_background_worker_are_wired(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError as exc:
        pytest.skip(f'PySide6 unavailable in this environment: {exc}')
    from ui.settings_page import SettingsPage
    monkeypatch.setenv('FAMILY_MEMORY_APP_DATA_ROOT', str(tmp_path))
    app=QApplication.instance() or QApplication([])
    page=SettingsPage()
    page.ai_env_input.setText(sys.executable)
    started=[]
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(page, '_start_ai_runtime_operation', lambda *a, **k: started.append((a,k)))
    page._confirm_and_install_mobileclip()
    assert not started
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    page._confirm_and_install_mobileclip()
    assert started and started[-1][0][0] == 'install'
    assert started[-1][1]['plan'].confirmed
    page.deleteLater()


def test_verify_and_test_use_background_worker(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f'PySide6 unavailable in this environment: {exc}')
    from ui.settings_page import SettingsPage
    monkeypatch.setenv('FAMILY_MEMORY_APP_DATA_ROOT', str(tmp_path))
    app=QApplication.instance() or QApplication([])
    page=SettingsPage(); page.ai_env_input.setText(sys.executable)
    calls=[]; monkeypatch.setattr(page, '_start_ai_runtime_operation', lambda *a, **k: calls.append((a,k)))
    page._verify_mobileclip_runtime()
    assert calls[-1][0][0] == 'verify'
    img=tmp_path/'one.jpg'; img.write_bytes(b'fake')
    monkeypatch.setattr(page, '_active_source_result', lambda: type('R',(),{'available':True,'paths':[img]})())
    page._test_mobileclip_one_image()
    assert calls[-1][0][0] == 'test'
    assert calls[-1][1]['image_path'] == img
    page.deleteLater()

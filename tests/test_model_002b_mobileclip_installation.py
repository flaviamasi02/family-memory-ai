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
    page._last_installation_plan = page.ai_runtime_manager.build_installation_plan("mobileclip", sys.executable)
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


def test_verify_provider_action_dispatch_runs_typed_command(tmp_path):
    from ai_runtime.executor import AIRuntimeCommandExecutor
    from ai_runtime.models import AIRuntimePlanAction

    executor = AIRuntimeCommandExecutor()
    action = AIRuntimePlanAction(
        AIRuntimeActionType.VERIFY_PROVIDER,
        "Verify fake provider",
        argv=(sys.executable, "-c", "print('provider verified')"),
    )

    result = executor.run_action(action)

    assert result.returncode == 0
    assert "provider verified" in result.stdout
    assert "MODEL-002A" not in result.stderr


def test_verify_provider_not_installed_preflight_records_clear_status(tmp_path):
    m = create_default_runtime_manager(ApplicationDataPathService(tmp_path, tmp_path))
    rec = m.installation_record("mobileclip")
    rec.interpreter_path = sys.executable
    m.storage.save_installation(rec)

    result = m.verify_provider("mobileclip")
    rec = m.installation_record("mobileclip")

    assert result.returncode != 0
    assert "Dependencies Missing" in result.stderr or "Checkpoint Missing" in result.stderr
    assert "missing" in result.stderr
    assert rec.last_validation_result == result.stderr
    assert rec.installation_state in (AIRuntimeState.DEPENDENCIES_MISSING.value, AIRuntimeState.CHECKPOINT_MISSING.value)
    assert list(m.storage.logs_dir.glob("*.jsonl"))
    assert "MODEL-002A" not in result.stderr


def test_settings_installation_plan_remains_detailed(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError as exc:
        pytest.skip(f"PySide6 unavailable in this environment: {exc}")
    from ui.settings_page import SettingsPage

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    app = QApplication.instance() or QApplication([])
    page = SettingsPage()
    page.ai_env_input.setText(sys.executable)
    started = []
    monkeypatch.setattr(page, "_start_ai_runtime_operation", lambda *a, **k: started.append((a, k)))

    page._show_ai_installation_plan()

    assert "Inspecting MobileCLIP environment" in page.ai_plan_box.toPlainText()
    assert started == [(("build_plan",), {"interpreter": sys.executable})]

    plan = page.ai_runtime_manager.build_installation_plan("mobileclip", sys.executable)
    page._on_ai_runtime_completed("build_plan", plan)
    text = page.ai_plan_box.toPlainText()

    assert "Installation plan for MobileCLIP" in text
    assert "Python environment:" in text
    assert "Typed actions (not executed until explicit confirmation):" in text
    assert "verify_provider" in text
    assert "Destination:" in text
    page.deleteLater()


def test_checkpoint_missing_is_distinct_when_imports_are_valid(tmp_path, monkeypatch):
    m = create_default_runtime_manager(ApplicationDataPathService(tmp_path, tmp_path))
    rec = m.installation_record("mobileclip")
    rec.interpreter_path = sys.executable
    m.storage.save_installation(rec)
    monkeypatch.setattr(m.executor, "imports_available", lambda *a, **k: ())

    result = m.verify_provider("mobileclip")
    rec = m.installation_record("mobileclip")

    assert result.returncode != 0
    assert "Checkpoint Missing" in result.stderr
    assert rec.installation_state == AIRuntimeState.CHECKPOINT_MISSING.value
    assert rec.last_error == result.stderr


def test_installation_subprocess_failure_is_logged_and_returned(tmp_path):
    m = create_default_runtime_manager(ApplicationDataPathService(tmp_path, tmp_path))
    plan = m.build_installation_plan("mobileclip", sys.executable)
    bad = next(a for a in plan.actions if a.action_type == AIRuntimeActionType.INSTALL_PYTHON_PACKAGE)
    bad = type(bad)(bad.action_type, "fail command", argv=(sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)"))
    plan = AIRuntimeInstallationPlan(**{**plan.__dict__, "actions": (bad,), "confirmed": True})

    results = m.execute_installation_plan(plan)
    log_text = m.storage.recent_log_text()

    assert results[0].returncode == 7
    assert "out" in log_text and "err" in log_text and "exit_code" in log_text
    assert "final_outcome" in log_text


def test_dependency_plan_uses_mobileclip_resolver_not_conflicting_torch_pins(tmp_path):
    m = create_default_runtime_manager(ApplicationDataPathService(tmp_path, tmp_path))
    plan = m.build_installation_plan("mobileclip", sys.executable)

    assert any(pkg.startswith("mobileclip @ git+https://github.com/apple/ml-mobileclip.git") for pkg in plan.packages_to_install)
    assert not any(pkg.startswith("torch>=2.1,<2.4") or pkg.startswith("torchvision>=0.16,<0.19") for pkg in plan.packages_to_install)
    assert any("Report installed package versions" in a.label for a in plan.actions)


def test_settings_restores_persisted_interpreter_and_shows_logs(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"PySide6 unavailable in this environment: {exc}")
    from ui.settings_page import SettingsPage

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path))
    m = create_default_runtime_manager(ApplicationDataPathService(tmp_path, tmp_path))
    m.save_environment_selection("mobileclip", sys.executable)
    m.storage.start_run_log("mobileclip", "verification", sys.executable).finish("Checkpoint Missing")
    app = QApplication.instance() or QApplication([])
    page = SettingsPage()

    assert page.ai_env_input.text() == sys.executable
    page._show_ai_runtime_logs()
    assert "verification" in page.ai_plan_box.toPlainText()
    page.deleteLater()


def test_cached_status_cleans_stale_dependency_error_without_deep_probe(tmp_path, monkeypatch):
    m = create_default_runtime_manager(ApplicationDataPathService(tmp_path, tmp_path))
    rec = m.installation_record("mobileclip")
    rec.interpreter_path = sys.executable
    rec.installation_state = AIRuntimeState.CHECKPOINT_MISSING.value
    rec.last_error = "Not Installed - missing Python packages: torch, torchvision, PIL, mobileclip; missing model files: mobileclip_s0.pt"
    rec.last_validation_result = rec.last_error
    m.storage.save_installation(rec)
    monkeypatch.setattr(m.executor, "validate_interpreter", lambda *a, **k: (_ for _ in ()).throw(AssertionError("deep env probe on cached status")))
    monkeypatch.setattr(m.executor, "imports_available", lambda *a, **k: (_ for _ in ()).throw(AssertionError("import probe on cached status")))

    status = m.status("mobileclip", deep=False)
    rec = m.installation_record("mobileclip")

    assert status.state == AIRuntimeState.CHECKPOINT_MISSING.value
    assert status.dependencies_available
    assert rec.last_error == "Checkpoint Missing - missing model files: mobileclip_s0.pt"


def test_state_aware_plan_skips_already_importable_packages(tmp_path, monkeypatch):
    m = create_default_runtime_manager(ApplicationDataPathService(tmp_path, tmp_path))
    monkeypatch.setattr(
        m.executor,
        "package_state",
        lambda *a, **k: {
            "mobileclip": {"available": True, "version": "0.1.0"},
            "torch": {"available": True, "version": "2.8.0"},
            "torchvision": {"available": True, "version": "0.23.0"},
            "PIL": {"available": True, "version": "10.4.0"},
        },
    )

    plan = m.build_installation_plan("mobileclip", sys.executable)

    assert plan.packages_to_install == ()
    assert not [a for a in plan.actions if a.action_type == AIRuntimeActionType.INSTALL_PYTHON_PACKAGE]
    assert any(a.action_type == AIRuntimeActionType.DOWNLOAD_MODEL_FILE for a in plan.actions)
    assert any("Already satisfied dependencies" in warning for warning in plan.warnings)


def test_settings_initial_status_uses_cached_metadata_not_deep_subprocess(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"PySide6 unavailable in this environment: {exc}")
    from ai_runtime.executor import AIRuntimeCommandExecutor
    from ai_runtime.models import AIRuntimeInstallationRecord
    from ai_runtime.storage import AIRuntimeStorage
    from ui.settings_page import SettingsPage

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path))
    storage = AIRuntimeStorage(ApplicationDataPathService(tmp_path, tmp_path))
    storage.save_installation(AIRuntimeInstallationRecord(provider_id="mobileclip", interpreter_path=sys.executable, python_version="3.10.11", installation_state=AIRuntimeState.CHECKPOINT_MISSING.value, local_model_cache_path=str(storage.cache_dir_for("mobileclip")), last_error="Not Installed - missing Python packages: torch, torchvision, PIL, mobileclip; missing model files: mobileclip_s0.pt"))
    monkeypatch.setattr(AIRuntimeCommandExecutor, "validate_interpreter", lambda *a, **k: (_ for _ in ()).throw(AssertionError("startup interpreter subprocess")))
    monkeypatch.setattr(AIRuntimeCommandExecutor, "imports_available", lambda *a, **k: (_ for _ in ()).throw(AssertionError("startup import subprocess")))

    app = QApplication.instance() or QApplication([])
    page = SettingsPage()

    assert page.ai_env_input.text() == sys.executable
    assert page.ai_detail_labels["Status"].text() == AIRuntimeState.CHECKPOINT_MISSING.value
    assert "missing Python packages" not in page.ai_detail_labels["Last error"].text()
    page.deleteLater()


def test_cached_status_does_not_scan_disk_usage_or_preserve_exact_old_error(tmp_path, monkeypatch):
    m = create_default_runtime_manager(ApplicationDataPathService(tmp_path, tmp_path))
    rec = m.installation_record("mobileclip")
    rec.interpreter_path = sys.executable
    rec.installation_state = AIRuntimeState.DEPENDENCIES_MISSING.value
    rec.installed_disk_usage_bytes = 12345
    old = "Not Installed - missing Python packages: torch, torchvision, PIL, mobileclip; missing model files: mobileclip_s0.pt"
    rec.last_error = old
    rec.last_validation_result = old
    m.storage.save_installation(rec)
    monkeypatch.setattr(m.storage, "disk_usage", lambda *a, **k: (_ for _ in ()).throw(AssertionError("startup disk scan")))
    monkeypatch.setattr(m.executor, "validate_interpreter", lambda *a, **k: (_ for _ in ()).throw(AssertionError("startup interpreter subprocess")))
    monkeypatch.setattr(m.executor, "imports_available", lambda *a, **k: (_ for _ in ()).throw(AssertionError("startup import subprocess")))

    status = m.status("mobileclip", deep=False)
    rec = m.installation_record("mobileclip")

    assert status.state == AIRuntimeState.CHECKPOINT_MISSING.value
    assert rec.installed_disk_usage_bytes == 12345
    assert rec.last_error == "Checkpoint Missing - missing model files: mobileclip_s0.pt"
    assert rec.last_validation_result == rec.last_error

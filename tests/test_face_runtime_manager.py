import json
from types import SimpleNamespace

import pytest

from faces.runtime import FaceRuntimeManager


class FakeRunner:
    def __init__(self, fail_install=False):
        self.calls = []
        self.fail_install = fail_install

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        if "install" in args and self.fail_install:
            return SimpleNamespace(returncode=1, stdout="", stderr="network unavailable")
        if "-c" in args:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"version": "4.10.0"}) + "\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")


def test_runtime_missing_install_verify_and_remove(tmp_path):
    runner = FakeRunner(); manager = FaceRuntimeManager(tmp_path, runner)
    assert manager.status().state == "Not installed"

    installed = manager.install()
    assert installed.ready and installed.installed_version == "4.10.0"
    assert "install" in runner.calls[0]
    assert manager.verify().ready

    removed = manager.remove()
    assert removed.state == "Not installed"
    assert "uninstall" in runner.calls[-1]


def test_repair_force_reinstalls_and_refreshes_status(tmp_path):
    runner = FakeRunner(); manager = FaceRuntimeManager(tmp_path, runner)
    assert manager.repair().ready
    assert "--force-reinstall" in runner.calls[0]
    assert manager.status().last_verification != "never"


def test_installation_failure_persists_reason_and_recommended_action(tmp_path):
    manager = FaceRuntimeManager(tmp_path, FakeRunner(fail_install=True))
    with pytest.raises(RuntimeError, match="try Repair"):
        manager.install()
    status = manager.status()
    assert status.state == "Installation failed"
    assert "network unavailable" in status.last_error

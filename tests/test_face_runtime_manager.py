import json, sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from faces.runtime import FaceRuntimeManager, OPENCV_PACKAGE, NUMPY_PACKAGE

class FakeRunner:
    def __init__(self, diagnostic=None, install_error="", repair_after_uninstall=False):
        self.calls=[]; self.diagnostic=diagnostic or self.valid(); self.install_error=install_error; self.repair_after_uninstall=repair_after_uninstall
    @staticmethod
    def valid(**updates):
        value={'executable':'managed-python','prefix':'managed','python_version':'3.12','cv2_file':'managed/site-packages/cv2/__init__.py','cv2_version':'4.10.0','has_data':True,'has_cascade':True,'in_site_packages':True,'distributions':{'opencv-python-headless':'4.10.0.84','numpy':'1.26.4'},'ok':True,'cascade_path':'managed/haarcascade_frontalface_default.xml'}
        value.update(updates); return value
    def __call__(self,args,**kwargs):
        self.calls.append(list(args))
        if '-m' in args and 'venv' in args:
            root=Path(args[-1]); executable=root/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python'); executable.parent.mkdir(parents=True,exist_ok=True); executable.write_text('fake')
        if 'install' in args and self.install_error: return SimpleNamespace(returncode=1,stdout='',stderr=self.install_error)
        if 'uninstall' in args and self.repair_after_uninstall:
            self.diagnostic = self.valid()
        if '-c' in args: return SimpleNamespace(returncode=0,stdout=json.dumps(self.diagnostic)+'\n',stderr='')
        return SimpleNamespace(returncode=0,stdout='ok',stderr='')

def test_install_uses_dedicated_environment_pins_versions_and_becomes_ready(tmp_path):
    runner=FakeRunner(); manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',runner)
    assert manager.status().state=='Not installed'; status=manager.install()
    assert status.ready and status.interpreter_path != sys.executable
    install=next(c for c in runner.calls if 'install' in c)
    assert OPENCV_PACKAGE in install and NUMPY_PACKAGE in install
    assert all('.venv-mobileclip' not in ' '.join(c) for c in runner.calls)

def test_missing_cascade_api_is_verification_not_network_error(tmp_path):
    data=FakeRunner.valid(ok=False,has_cascade=False,verification_error='CASCADE_API_MISSING')
    manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',FakeRunner(data))
    with pytest.raises(RuntimeError, match='invalid or incomplete') as caught: manager.install()
    assert 'internet' not in str(caught.value).lower()

@pytest.mark.parametrize('error', ['CV2_SHADOWED: project/cv2.py','CV2_DATA_MISSING','CASCADE_XML_MISSING','CASCADE_EMPTY'])
def test_invalid_module_and_model_checks_recommend_clean_repair(tmp_path,error):
    data=FakeRunner.valid(ok=False,verification_error=error)
    manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',FakeRunner(data))
    with pytest.raises(RuntimeError,match='invalid or incomplete') as caught: manager.install()
    assert 'internet' not in str(caught.value).lower()

def test_repair_uninstalls_all_conflicting_opencv_distributions_first(tmp_path):
    distributions={'cv2':'1.0','opencv-python':'4','opencv-contrib-python':'4','opencv-python-headless':'4.10.0.84','numpy':'1.26.4'}
    runner=FakeRunner(FakeRunner.valid(distributions=distributions),repair_after_uninstall=True); manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',runner)
    assert manager.repair().ready
    uninstall=next(c for c in runner.calls if 'uninstall' in c); install=next(c for c in runner.calls if 'install' in c)
    assert uninstall.index('uninstall') < len(uninstall) and runner.calls.index(uninstall) < runner.calls.index(install)
    assert {'cv2','opencv-python','opencv-contrib-python','opencv-python-headless'}.issubset(uninstall)

def test_multiple_active_distributions_fail_as_conflict(tmp_path):
    data=FakeRunner.valid(distributions={'opencv-python':'4','opencv-python-headless':'4.10.0.84','numpy':'1.26.4'})
    manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',FakeRunner(data))
    manager.interpreter_path.parent.mkdir(parents=True); manager.interpreter_path.write_text('fake')
    with pytest.raises(RuntimeError,match='Conflicting OpenCV'): manager.verify()

def test_download_error_is_distinct_from_verification_error(tmp_path):
    manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',FakeRunner(install_error='Could not fetch URL'))
    with pytest.raises(RuntimeError,match='download or installation'): manager.install()
    assert 'connection' in manager.status().last_error.lower()

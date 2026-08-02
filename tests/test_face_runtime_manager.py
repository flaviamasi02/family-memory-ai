import json, sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from faces.runtime import (COMPATIBILITY, FaceRuntimeManager, classify_pip_failure,
                           compatible_packages, meaningful_pip_error,
                           MANAGED_PYTHON_HOSTS, MANAGED_PYTHON_URL)

class FakeRunner:
    def __init__(self, diagnostic=None, install_error="", repair_after_uninstall=False, python=(3, 12), tooling_error="", architecture="64-bit"):
        self.calls=[]; self.diagnostic=diagnostic or self.valid(); self.install_error=install_error; self.repair_after_uninstall=repair_after_uninstall; self.python=python; self.tooling_error=tooling_error; self.architecture=architecture
    @staticmethod
    def valid(**updates):
        value={'executable':'managed-python','prefix':'managed','python_version':'3.12','cv2_file':'managed/site-packages/cv2/__init__.py','cv2_version':'4.10.0','has_data':True,'has_cascade':True,'in_site_packages':True,'distributions':{'opencv-python-headless':'4.10.0.84','numpy':'1.26.4'},'ok':True,'cascade_path':'managed/haarcascade_frontalface_default.xml'}
        value.update(updates); return value
    def __call__(self,args,**kwargs):
        self.calls.append(list(args))
        if '-m' in args and 'venv' in args and args[-1] != '--help':
            root=Path(args[-1]); executable=root/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python'); executable.parent.mkdir(parents=True,exist_ok=True); executable.write_text('fake')
        if 'install' in args and self.install_error and 'opencv-python-headless' in ' '.join(args): return SimpleNamespace(returncode=1,stdout='',stderr=self.install_error)
        if args[-3:]==['pip','setuptools','wheel'] and self.tooling_error: return SimpleNamespace(returncode=1,stdout='',stderr=self.tooling_error)
        if 'uninstall' in args and self.repair_after_uninstall:
            self.diagnostic = self.valid()
        if '-c' in args:
            script=args[args.index('-c')+1]
            if 'platform.python_version' in script:
                executable=Path(args[0]); prefix=executable.parent if executable.parent.name=='face-python' else executable.parent.parent; data={'executable':str(executable.resolve()),'prefix':str(prefix.resolve()),'python_version':f'{self.python[0]}.{self.python[1]}.0','python_major':self.python[0],'python_minor':self.python[1],'architecture':self.architecture,'platform':'Windows','pip_version':'pip 24.0'}
            else: data=self.diagnostic
            return SimpleNamespace(returncode=0,stdout=json.dumps(data)+'\n',stderr='')
        return SimpleNamespace(returncode=0,stdout='ok',stderr='')

def test_install_uses_dedicated_environment_pins_versions_and_becomes_ready(tmp_path):
    runner=FakeRunner(); manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',runner)
    assert manager.status().state=='Not installed'; status=manager.install()
    assert status.ready and status.interpreter_path != sys.executable
    installs=[c for c in runner.calls if 'install' in c]
    install=installs[-1]
    assert set(COMPATIBILITY[(3,12)]).issubset(install)
    assert installs[0][-3:] == ['pip','setuptools','wheel']
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
    uninstall=next(c for c in runner.calls if 'uninstall' in c); install=next(c for c in runner.calls if 'install' in c and 'opencv-python-headless' in ' '.join(c))
    assert uninstall.index('uninstall') < len(uninstall) and runner.calls.index(uninstall) < runner.calls.index(install)
    assert {'cv2','opencv-python','opencv-contrib-python','opencv-python-headless'}.issubset(uninstall)

def test_multiple_active_distributions_fail_as_conflict(tmp_path):
    data=FakeRunner.valid(distributions={'opencv-python':'4','opencv-python-headless':'4.10.0.84','numpy':'1.26.4'})
    manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',FakeRunner(data))
    manager.interpreter_path.parent.mkdir(parents=True); manager.interpreter_path.write_text('fake')
    with pytest.raises(RuntimeError,match='Conflicting OpenCV'): manager.verify()

def test_download_error_is_distinct_from_verification_error(tmp_path):
    manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',FakeRunner(install_error='Could not fetch URL'))
    with pytest.raises(RuntimeError,match='could not be reached'): manager.install()
    assert 'could not fetch' in manager.status().last_error.lower()


def test_error_extraction_uses_specific_error_before_trailing_hint():
    output='notice: A new release of pip is available.\nERROR: No matching distribution found for numpy==1.26.4\nhint: See above for details.'
    assert meaningful_pip_error(output) == 'ERROR: No matching distribution found for numpy==1.26.4'
    assert classify_pip_failure(output) == 'no_wheel'


@pytest.mark.parametrize(('output','kind'), [
    ('ERROR: package Requires-Python >=3.12', 'unsupported_python'),
    ('SSL: CERTIFICATE_VERIFY_FAILED', 'network'),
    ('ERROR: [WinError 5] Access is denied', 'permission'),
    ('ERROR: ResolutionImpossible dependency conflict', 'dependency'),
])
def test_pip_failure_classification(output, kind):
    assert classify_pip_failure(output) == kind


def test_compatible_package_policy_and_unsupported_python(tmp_path):
    assert compatible_packages(3,10) and compatible_packages(3,12) and compatible_packages(3,13)
    assert compatible_packages(3,14) is None
    runner=FakeRunner(python=(3,14)); manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',runner)
    with pytest.raises(RuntimeError,match=r'Python 3\.14\..* is not supported'): manager.install()
    runtime_installs=[c for c in runner.calls if 'install' in c and 'opencv-python-headless' in ' '.join(c)]
    assert runtime_installs == []


def test_repair_recreates_partial_environment_before_tooling(tmp_path):
    root=tmp_path/'.venv-face-runtime'; stale=root/'stale.txt'; stale.parent.mkdir(); stale.write_text('broken')
    runner=FakeRunner(); manager=FaceRuntimeManager(root,runner); assert manager.repair().ready
    assert not stale.exists()
    venv_index=next(i for i,c in enumerate(runner.calls) if 'venv' in c)
    tooling_index=next(i for i,c in enumerate(runner.calls) if c[-3:]==['pip','setuptools','wheel'])
    runtime_index=next(i for i,c in enumerate(runner.calls) if 'install' in c and 'opencv-python-headless' in ' '.join(c))
    assert venv_index < tooling_index < runtime_index


def test_stdout_and_stderr_are_combined_for_analysis():
    from faces.runtime import combined_output
    result=SimpleNamespace(stdout='ERROR: ResolutionImpossible',stderr='hint: See above for details.')
    assert classify_pip_failure(combined_output(result)) == 'dependency'


def test_installer_tooling_failure_is_separate_from_runtime_packages(tmp_path):
    runner=FakeRunner(tooling_error='ERROR: failed building wheel for installer tooling')
    manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',runner)
    with pytest.raises(RuntimeError,match='installer could not be prepared'): manager.install()
    assert not any('opencv-python-headless' in ' '.join(c) and 'install' in c for c in runner.calls)


class BootstrapRunner(FakeRunner):
    def __init__(self, signature="Valid"):
        super().__init__(); self.signature=signature
    def __call__(self,args,**kwargs):
        if args and args[0]=='powershell.exe':
            self.calls.append(list(args)); return SimpleNamespace(returncode=0,stdout=json.dumps({'Status':self.signature,'Subject':'CN=Python Software Foundation'})+'\n',stderr='')
        target=next((x.split('=',1)[1] for x in args if str(x).startswith('TargetDir=')),None)
        if target:
            self.calls.append(list(args)); path=Path(target)/'python.exe'; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('managed'); return SimpleNamespace(returncode=0,stdout='installed',stderr='')
        return super().__call__(args,**kwargs)


def test_python314_can_bootstrap_private_python312_without_dead_end(tmp_path):
    downloads=[]
    def download(url,destination,cancel): downloads.append(url); Path(destination).write_bytes(b'signed-installer')
    runner=BootstrapRunner(); manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',runner,download,platform_name='win32',discovery_candidates=[])
    assert manager.install().ready
    assert downloads == [MANAGED_PYTHON_URL]
    venv=next(c for c in runner.calls if 'venv' in c)
    assert Path(venv[0]) == manager.managed_python_executable
    assert manager.status().bootstrap_interpreter == str(manager.managed_python_executable)
    assert all('.venv-mobileclip' not in ' '.join(c) for c in runner.calls)


def test_existing_supported_interpreter_discovery_requires_64_bit(tmp_path):
    candidate=tmp_path/'Python312/python.exe'; candidate.parent.mkdir(); candidate.write_text('python')
    supported=FaceRuntimeManager(tmp_path/'one/.venv-face-runtime',FakeRunner(),discovery_candidates=[candidate])
    assert supported.find_supported_interpreter() == candidate
    rejected=FaceRuntimeManager(tmp_path/'two/.venv-face-runtime',FakeRunner(architecture='32-bit'),discovery_candidates=[candidate])
    assert rejected.find_supported_interpreter() is None


def test_managed_python_source_is_https_and_allowlisted():
    from urllib.parse import urlparse
    parsed=urlparse(MANAGED_PYTHON_URL)
    assert parsed.scheme == 'https' and parsed.hostname in MANAGED_PYTHON_HOSTS


def test_integrity_failure_blocks_execution_and_cleans_partial(tmp_path):
    def download(url,destination,cancel): Path(destination).write_bytes(b'untrusted')
    runner=BootstrapRunner(signature='NotSigned'); manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',runner,download,platform_name='win32',discovery_candidates=[])
    with pytest.raises(RuntimeError,match='integrity verification'): manager.install()
    assert not list(tmp_path.glob('*.partial'))
    assert not any(any(str(x).startswith('TargetDir=') for x in c) for c in runner.calls)


def test_cancelled_download_removes_partial(tmp_path):
    def download(url,destination,cancel):
        Path(destination).write_bytes(b'partial'); raise RuntimeError('download cancelled')
    manager=FaceRuntimeManager(tmp_path/'.venv-face-runtime',BootstrapRunner(),download,platform_name='win32',discovery_candidates=[])
    with pytest.raises(RuntimeError,match='cancelled'): manager.install()
    assert not list(tmp_path.glob('*.partial'))

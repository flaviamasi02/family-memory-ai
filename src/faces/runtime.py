"""Windows-safe managed environment for local face detection."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.application_data import get_app_data_service

CONFLICTS = ("cv2", "opencv-python", "opencv-python-headless", "opencv-contrib-python", "opencv-contrib-python-headless")
COMPATIBILITY = {
    (3, 10): ("opencv-python-headless==4.10.0.84", "numpy==1.26.4", "Pillow==10.4.0"),
    (3, 11): ("opencv-python-headless==4.10.0.84", "numpy==1.26.4", "Pillow==10.4.0"),
    (3, 12): ("opencv-python-headless==4.10.0.84", "numpy==1.26.4", "Pillow==10.4.0"),
    (3, 13): ("opencv-python-headless==4.11.0.86", "numpy==2.1.3", "Pillow==11.1.0"),
}
INSTALLER_PACKAGES = ("pip", "setuptools", "wheel")


def _now():
    return datetime.now(timezone.utc).isoformat()


ENVIRONMENT_SCRIPT = r'''
import json, platform, struct, subprocess, sys
p=subprocess.run([sys.executable,'-m','pip','--version'],capture_output=True,text=True)
print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,'python_version':platform.python_version(),
'python_major':sys.version_info.major,'python_minor':sys.version_info.minor,'architecture':str(struct.calcsize('P')*8)+'-bit',
'platform':platform.platform(),'pip_version':(p.stdout or p.stderr).strip()}))
'''
DIAGNOSTIC_SCRIPT = r'''
import importlib.metadata as md, json, pathlib, site, sys
names=['cv2','opencv-python','opencv-python-headless','opencv-contrib-python','opencv-contrib-python-headless','numpy']
out={'executable':sys.executable,'prefix':sys.prefix,'python_version':sys.version,'distributions':{}}
for n in names:
 try: out['distributions'][n]=md.version(n)
 except md.PackageNotFoundError: pass
try:
 import cv2
 out.update(cv2_file=getattr(cv2,'__file__',None),cv2_version=getattr(cv2,'__version__',None),has_data=hasattr(cv2,'data'),has_cascade=hasattr(cv2,'CascadeClassifier'))
 p=pathlib.Path(getattr(cv2,'__file__','')).resolve(); roots=[pathlib.Path(x).resolve() for x in site.getsitepackages()]
 out['in_site_packages']=any(p.is_relative_to(r) for r in roots)
except Exception as e: out['import_error']=type(e).__name__+': '+str(e)
print(json.dumps(out))
'''
VERIFY_SCRIPT = DIAGNOSTIC_SCRIPT + r'''
try:
 import cv2
 if not getattr(cv2,'__version__',None): raise RuntimeError('CV2_VERSION_MISSING')
 if not out.get('in_site_packages'): raise RuntimeError('CV2_SHADOWED:'+str(out.get('cv2_file')))
 if not hasattr(cv2,'data') or not getattr(cv2.data,'haarcascades',None): raise RuntimeError('CV2_DATA_MISSING')
 p=pathlib.Path(cv2.data.haarcascades)/'haarcascade_frontalface_default.xml'
 if not p.is_file(): raise RuntimeError('CASCADE_XML_MISSING')
 if not hasattr(cv2,'CascadeClassifier'): raise RuntimeError('CASCADE_API_MISSING')
 c=cv2.CascadeClassifier(str(p))
 if c.empty(): raise RuntimeError('CASCADE_EMPTY')
 out.update(ok=True,cascade_path=str(p))
except Exception as e: out.update(ok=False,verification_error=str(e))
print(json.dumps(out))
'''


@dataclass
class FaceRuntimeStatus:
    state: str = "Not installed"
    installed_version: str = "not installed"
    detector_backend: str = "OpenCV Haar (managed local CPU)"
    model_version: str = "haarcascade_frontalface_default v1"
    install_location: str = ""
    interpreter_path: str = ""
    last_verification: str = "never"
    last_error: str = "none"

    @property
    def ready(self):
        return self.state == "Ready"


def compatible_packages(major: int, minor: int) -> tuple[str, ...] | None:
    return COMPATIBILITY.get((int(major), int(minor)))


def combined_output(result) -> str:
    return "\n".join(part.strip() for part in (getattr(result, "stdout", ""), getattr(result, "stderr", "")) if part and part.strip())


def meaningful_pip_error(output: str) -> str:
    generic = ("hint: see above for details", "notice: a new release of pip", "for more information")
    lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
    candidates = [line for line in lines if not any(item in line.casefold() for item in generic)]
    priorities = ("error:", "could not find a version that satisfies", "no matching distribution found",
                  "resolutionimpossible", "requires-python", "requires python", "ssl", "certificate",
                  "proxy", "connection", "timed out", "permission", "access is denied", "winerror",
                  "failed building wheel", "incompatible")
    preferred = [line for line in candidates if any(item in line.casefold() for item in priorities)]
    return " | ".join((preferred or candidates)[-3:]) or "No specific installer error was reported; View Logs for the complete output."


def classify_pip_failure(output: str) -> str:
    text = str(output or "").casefold()
    if "requires-python" in text or "requires python" in text:
        return "unsupported_python"
    if "no matching distribution found" in text or "could not find a version that satisfies" in text:
        return "no_wheel"
    if "resolutionimpossible" in text or "dependency conflict" in text:
        return "dependency"
    if any(x in text for x in ("ssl", "certificate", "proxy", "connection", "could not fetch", "timed out", "temporary failure", "name resolution")):
        return "network"
    if any(x in text for x in ("permission", "access is denied", "winerror 5", "winerror 32", "being used by another process")):
        return "permission"
    return "package"


class FaceRuntimeManager:
    def __init__(self, root: Path | None = None, runner=None):
        self.root = Path(root or (get_app_data_service().root / "runtimes" / ".venv-face-runtime"))
        self.root.parent.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root.parent / "face-runtime.json"
        self.log_path = self.root.parent / "face-runtime.log"
        self.runner = runner or subprocess.run

    @property
    def interpreter_path(self):
        return self.root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    def status(self):
        if not self.state_path.exists():
            return self._base_status()
        try:
            status = FaceRuntimeStatus(**json.loads(self.state_path.read_text(encoding="utf-8")))
            if status.ready and (not status.interpreter_path or not Path(status.interpreter_path).is_file()):
                status.state = "Needs repair"
                status.last_error = "The managed runtime is incomplete. Repair will recreate it."
            return status
        except (OSError, ValueError, TypeError):
            return self._base_status("Needs repair", "Runtime state is damaged. Repair will recreate it.")

    def _base_status(self, state="Not installed", error="none"):
        return FaceRuntimeStatus(state=state, install_location=str(self.root), interpreter_path=str(self.interpreter_path), last_error=error)

    def install(self, progress=None):
        return self._install(progress, clean=False)

    def repair(self, progress=None):
        return self._install(progress, clean=True)

    def _install(self, progress=None, clean=False):
        clean = clean or (self.root.exists() and not self.status().ready)
        if clean and self.root.exists():
            if progress: progress(3, "Removing the incomplete Face Recognition runtime…")
            try:
                shutil.rmtree(self.root)
            except OSError as exc:
                return self._fail("permission", str(exc))
        if progress: progress(5, "Creating the separate Face Recognition environment…")
        if not self.interpreter_path.exists():
            result = self._run([sys.executable, "-m", "venv", str(self.root)])
            if result.returncode:
                return self._fail("venv", combined_output(result))
        environment = self._environment_details()
        self._validate_environment(environment)
        packages = compatible_packages(environment["python_major"], environment["python_minor"])
        if packages is None:
            version = environment["python_version"]
            return self._fail("unsupported_python", f"Python {version} has no validated Face Runtime package set.", version)
        if progress: progress(15, "Preparing the Face Recognition installer…")
        tooling = self._run([str(self.interpreter_path), "-m", "pip", "install", "--upgrade", *INSTALLER_PACKAGES])
        if tooling.returncode:
            return self._fail("tooling", combined_output(tooling), environment["python_version"])
        if progress: progress(25, "Diagnosing existing OpenCV packages…")
        diagnosis = self.diagnose()
        conflicts = [x for x in CONFLICTS if x in set(diagnosis.get("distributions", {}))]
        if conflicts:
            result = self._run([str(self.interpreter_path), "-m", "pip", "uninstall", "-y", *conflicts])
            if result.returncode:
                return self._fail("permission", combined_output(result), environment["python_version"])
        if progress: progress(40, f"Installing compatible packages for Python {environment['python_version']}…")
        result = self._run([str(self.interpreter_path), "-m", "pip", "install", "--upgrade", "--force-reinstall", *packages])
        if result.returncode:
            kind = classify_pip_failure(combined_output(result))
            return self._fail(kind, combined_output(result), environment["python_version"])
        if progress: progress(80, "Verifying OpenCV API and detector model…")
        return self.verify(progress)

    def _environment_details(self):
        result = self._run([str(self.interpreter_path), "-c", ENVIRONMENT_SCRIPT])
        if result.returncode:
            return self._fail("environment", combined_output(result))
        return self._json(result)

    def _validate_environment(self, details):
        expected = self.interpreter_path.resolve()
        actual = Path(details.get("executable", "")).resolve()
        prefix = Path(details.get("prefix", "")).resolve()
        if actual != expected or prefix != self.root.resolve():
            return self._fail("environment", "The reported interpreter or prefix is outside .venv-face-runtime.")

    def diagnose(self):
        return self._json(self._run([str(self.interpreter_path), "-c", DIAGNOSTIC_SCRIPT]))

    def verify(self, progress=None):
        if not self.interpreter_path.exists():
            return self._fail("environment", "Managed face interpreter is missing.")
        result = self._run([str(self.interpreter_path), "-c", VERIFY_SCRIPT])
        data = self._json(result)
        if result.returncode or not data.get("ok"):
            return self._fail("verification", data.get("verification_error") or data.get("import_error") or combined_output(result))
        active = [x for x in CONFLICTS if x in data.get("distributions", {})]
        if active != ["opencv-python-headless"]:
            return self._fail("conflict", "Multiple or unsupported OpenCV distributions are active: " + ", ".join(active))
        status = FaceRuntimeStatus("Ready", data["cv2_version"], install_location=str(self.root), interpreter_path=str(self.interpreter_path), last_verification=_now())
        self._save(status)
        if progress: progress(100, "Face recognition runtime is ready.")
        return status

    def remove(self, progress=None):
        if progress: progress(20, "Removing the separate Face Recognition environment…")
        shutil.rmtree(self.root, ignore_errors=True)
        status = self._base_status()
        self._save(status)
        if progress: progress(100, "Face recognition runtime removed.")
        return status

    def _fail(self, kind, detail, python_version="unknown"):
        cause = meaningful_pip_error(detail)
        messages = {
            "unsupported_python": f"Python {python_version} is not supported by the managed Face Runtime. Use the application's supported Windows build, then choose Repair.",
            "no_wheel": f"No compatible Face Runtime wheel is available for Python {python_version}.",
            "dependency": "The Face Runtime package dependencies conflict and could not be resolved.",
            "tooling": "The Face Recognition installer could not be prepared.",
            "network": "The package service could not be reached or its security certificate was rejected.",
            "permission": "Windows denied or locked access to the managed Face Runtime.",
            "venv": "The separate Face Recognition environment could not be created.",
            "environment": "The managed Face Recognition interpreter is missing or belongs to the wrong environment.",
            "conflict": "Conflicting OpenCV packages remain in the managed runtime.",
            "verification": "The OpenCV installation is invalid or incomplete. Repair will recreate it cleanly.",
            "package": "The Face Runtime packages could not be installed for an unknown reason.",
        }
        message = f"{messages[kind]} Cause: {cause}"
        status = self._base_status(kind.replace("_", " ").title() + " failed", message)
        status.last_verification = _now()
        self._save(status)
        raise RuntimeError(message)

    def _run(self, args):
        try:
            result = self.runner(args, capture_output=True, text=True, timeout=1800, cwd=str(self.root.parent))
        except (OSError, subprocess.SubprocessError) as exc:
            result = type("Result", (), {"returncode": 1, "stdout": "", "stderr": str(exc)})()
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{_now()}] {' '.join(args)}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n")
        return result

    @staticmethod
    def _json(result):
        for line in reversed((result.stdout or "").splitlines()):
            try: return json.loads(line)
            except json.JSONDecodeError: continue
        return {"import_error": combined_output(result) or "Diagnostic produced no JSON output"}

    def _save(self, status):
        self.state_path.write_text(json.dumps(asdict(status), indent=2), encoding="utf-8")

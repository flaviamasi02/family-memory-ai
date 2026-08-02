"""Managed, explicit installation lifecycle for the local face runtime."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.application_data import get_app_data_service


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FaceRuntimeStatus:
    state: str = "Not installed"
    installed_version: str = "not installed"
    detector_backend: str = "OpenCV Haar (local CPU)"
    model_version: str = "haarcascade_frontalface_default v1"
    install_location: str = ""
    last_verification: str = "never"
    last_error: str = "none"

    @property
    def ready(self) -> bool:
        return self.state == "Ready"


class FaceRuntimeManager:
    """Owns face-runtime state and pip operations; callers run operations off the UI thread."""

    PACKAGE = "opencv-python-headless"

    def __init__(self, root: Path | None = None, runner=None):
        self.root = Path(root or (get_app_data_service().root / "data" / "face_runtime"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "runtime.json"
        self.log_path = self.root / "face-runtime.log"
        self.runner = runner or subprocess.run

    def status(self) -> FaceRuntimeStatus:
        if not self.state_path.exists():
            return FaceRuntimeStatus(install_location=self.install_location)
        try:
            return FaceRuntimeStatus(**json.loads(self.state_path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return FaceRuntimeStatus(state="Needs repair", install_location=self.install_location,
                                     last_error="Runtime status could not be read. Choose Repair.")

    def install(self, progress=None) -> FaceRuntimeStatus:
        return self._install(False, progress)

    def repair(self, progress=None) -> FaceRuntimeStatus:
        return self._install(True, progress)

    def _install(self, force: bool, progress=None) -> FaceRuntimeStatus:
        action = "Repairing" if force else "Installing"
        if progress: progress(10, f"{action} the local face runtime…")
        args = [sys.executable, "-m", "pip", "install", "--upgrade"]
        if force: args.append("--force-reinstall")
        args.extend([self.PACKAGE, "numpy"])
        result = self._run(args)
        if result.returncode != 0:
            status = FaceRuntimeStatus(state="Installation failed", install_location=self.install_location,
                                       last_error=self._friendly_error(result.stderr))
            self._save(status)
            raise RuntimeError(status.last_error)
        if progress: progress(80, "Verifying detector and model files…")
        return self.verify(progress)

    def verify(self, progress=None) -> FaceRuntimeStatus:
        script = ("import cv2, json; p=cv2.data.haarcascades+'haarcascade_frontalface_default.xml'; "
                  "m=cv2.CascadeClassifier(p); assert not m.empty(); "
                  "print(json.dumps({'version':cv2.__version__}))")
        result = self._run([sys.executable, "-c", script])
        if result.returncode != 0:
            status = self.status(); status.state = "Verification failed"
            status.last_error = self._friendly_error(result.stderr); status.last_verification = _now()
            self._save(status); raise RuntimeError(status.last_error)
        version = json.loads(result.stdout.strip().splitlines()[-1])["version"]
        status = FaceRuntimeStatus("Ready", version, install_location=self.install_location,
                                   last_verification=_now(), last_error="none")
        self._save(status)
        if progress: progress(100, "Face recognition runtime is ready.")
        return status

    def remove(self, progress=None) -> FaceRuntimeStatus:
        if progress: progress(20, "Removing the managed face runtime…")
        result = self._run([sys.executable, "-m", "pip", "uninstall", "-y", self.PACKAGE])
        if result.returncode != 0:
            raise RuntimeError(self._friendly_error(result.stderr))
        status = FaceRuntimeStatus(install_location=self.install_location)
        self._save(status)
        if progress: progress(100, "Face recognition runtime removed.")
        return status

    def _run(self, args):
        result = self.runner(args, capture_output=True, text=True, timeout=1800)
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{_now()}] {' '.join(args)}\n{result.stdout}\n{result.stderr}\n")
        return result

    @property
    def install_location(self) -> str:
        return f"{sys.prefix} (runtime packages); {self.root} (managed state and logs)"

    def _save(self, status):
        self.state_path.write_text(json.dumps(asdict(status), indent=2), encoding="utf-8")

    @staticmethod
    def _friendly_error(stderr: str) -> str:
        detail = (stderr or "Unknown installer error").strip().splitlines()[-1]
        return f"The face runtime operation failed. Check your internet connection and try Repair. Technical detail: {detail}"

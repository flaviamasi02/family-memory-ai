from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, Signal

from ai_runtime.manager import AIRuntimeManager
from ai_runtime.models import AIRuntimeInstallationPlan


class AIRuntimeOperationWorker(QObject):
    progress = Signal(str, str)
    current_step = Signal(str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        manager: AIRuntimeManager,
        operation: str,
        *,
        plan: AIRuntimeInstallationPlan | None = None,
        provider_id: str = "mobileclip",
        image_path: str | Path | None = None,
        cancel_event: Event | None = None,
    ) -> None:
        super().__init__()
        self.manager = manager
        self.operation = operation
        self.plan = plan
        self.provider_id = provider_id
        self.image_path = Path(image_path) if image_path else None
        self.cancel_event = cancel_event or Event()

    def run(self) -> None:
        try:
            def callback(step, message):
                self.current_step.emit(str(step))
                self.progress.emit(str(step), str(message))
            if self.operation == "install":
                if self.plan is None:
                    raise ValueError("Installation plan is required.")
                result: Any = self.manager.execute_installation_plan(self.plan, self.cancel_event, callback)
            elif self.operation == "verify":
                result = self.manager.verify_provider(self.provider_id, self.cancel_event, callback)
            elif self.operation == "test":
                if self.image_path is None:
                    raise ValueError("Image path is required for MobileCLIP test.")
                result = self.manager.test_image_embedding(self.provider_id, self.image_path, self.cancel_event, callback)
            elif self.operation == "remove":
                if self.plan is None:
                    raise ValueError("Removal plan is required.")
                result = self.manager.execute_removal_plan(self.plan, self.cancel_event, callback)
            else:
                raise ValueError(f"Unsupported AI runtime operation: {self.operation}")
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

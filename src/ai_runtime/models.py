from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class AIRuntimeCapability(str, Enum):
    IMAGE_EMBEDDINGS = "image_embeddings"
    TEXT_EMBEDDINGS = "text_embeddings"
    ZERO_SHOT_CLASSIFICATION = "zero_shot_classification"
    CAPTIONING = "captioning"
    OCR = "ocr"
    OBJECT_DETECTION = "object_detection"
    FACE_DETECTION = "face_detection"
    FACE_EMBEDDINGS = "face_embeddings"


class AIRuntimeState(str, Enum):
    NOT_REGISTERED = "Not registered"
    NOT_INSTALLED = "Not installed"
    DEPENDENCIES_MISSING = "Dependencies missing"
    DEPENDENCIES_INSTALLING = "Dependencies installing"
    MODEL_NOT_DOWNLOADED = "Model not downloaded"
    MODEL_DOWNLOADING = "Model downloading"
    VERIFYING = "Verifying"
    READY = "Ready"
    UPDATE_AVAILABLE = "Update available"
    REMOVING = "Removing"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    UNSUPPORTED = "Unsupported"


class AIRuntimeActionType(str, Enum):
    CREATE_DIRECTORY = "create_directory"
    INSTALL_PYTHON_PACKAGE = "install_python_package"
    CLONE_OR_INSTALL_OFFICIAL_PACKAGE = "clone_or_install_official_package"
    DOWNLOAD_MODEL_FILE = "download_model_file"
    VERIFY_CHECKSUM = "verify_checksum"
    VERIFY_IMPORT = "verify_import"
    VERIFY_PROVIDER = "verify_provider"
    RECORD_INSTALLATION = "record_installation"
    REMOVE_OWNED_PATH = "remove_owned_path"
    RECORD_REMOVAL = "record_removal"


@dataclass(frozen=True)
class RequiredModelFile:
    relative_path: str
    description: str = ""
    sha256: str = ""
    size_bytes: int | None = None


@dataclass(frozen=True)
class RuntimeDependency:
    import_name: str
    package_name: str | None = None
    version_spec: str = ""
    shared: bool = True


@dataclass(frozen=True)
class AIRuntimeDescriptor:
    provider_id: str
    display_name: str
    description: str
    provider_type: str
    checkpoint_id: str
    revision: str
    capabilities: tuple[AIRuntimeCapability, ...]
    source_url: str
    code_license: str
    model_license: str
    expected_download_size: str
    supported_devices: tuple[str, ...] = ("CPU",)
    recommended_hardware: str = "CPU"
    required_python_packages: tuple[RuntimeDependency, ...] = ()
    required_model_files: tuple[RequiredModelFile, ...] = ()
    provider_factory: Callable[[Path], Any] | None = field(default=None, compare=False, repr=False)
    verifier: Callable[[Path], bool] | None = field(default=None, compare=False, repr=False)
    python_version_spec: str = ""
    planned: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("provider_factory", None); data.pop("verifier", None)
        return data


@dataclass
class PythonEnvironmentInfo:
    interpreter_path: str
    python_version: str = ""
    architecture: str = ""
    environment_path: str = ""
    environment_type: str = "unknown"
    pip_available: bool = False
    writable: bool = False
    valid: bool = False
    message: str = ""


@dataclass
class AIRuntimeInstallationRecord:
    provider_id: str
    installation_state: str = AIRuntimeState.NOT_INSTALLED.value
    interpreter_path: str = ""
    python_version: str = ""
    environment_path: str = ""
    environment_type: str = "unknown"
    local_model_cache_path: str = ""
    local_installation_path: str = ""
    installed_disk_usage_bytes: int = 0
    install_date: str = ""
    update_date: str = ""
    last_status_check: str = ""
    last_error: str = ""
    last_validation_result: str = ""
    checkpoint_id: str = ""
    revision: str = ""


@dataclass
class AIRuntimeStatus:
    provider_id: str
    state: str
    provider_available: bool
    dependencies_available: bool
    model_files_available: bool
    update_available: str = "Unknown"
    last_error: str = ""
    last_status_check: str = ""
    missing_dependencies: tuple[str, ...] = ()
    missing_model_files: tuple[str, ...] = ()
    environment: PythonEnvironmentInfo | None = None


@dataclass(frozen=True)
class AIRuntimePlanAction:
    action_type: AIRuntimeActionType
    label: str
    argv: tuple[str, ...] = ()
    destination: str = ""
    package_name: str = ""
    url: str = ""
    sha256: str = ""
    timeout_seconds: int = 900
    requires_confirmation: bool = True


@dataclass
class AIRuntimeInstallationPlan:
    provider_id: str
    provider_name: str
    checkpoint_id: str
    packages_to_install: tuple[str, ...]
    model_files_to_download: tuple[str, ...]
    expected_download_size: str
    destination_path: str
    licenses: dict[str, str]
    device: str
    python_environment: PythonEnvironmentInfo
    administrator_rights_expected: bool
    restart_may_be_required: bool
    estimated_disk_requirement: str
    warnings: tuple[str, ...]
    actions: tuple[AIRuntimePlanAction, ...]
    confirmed: bool = False


@dataclass
class AIRuntimeHistoryRecord:
    provider_id: str
    timestamp: str
    action: str
    outcome: str
    runtime_version: str = ""
    interpreter_path: str = ""
    message: str = ""
    error_summary: str = ""
    duration_seconds: float | None = None


@dataclass
class AIRuntimeBenchmarkRecord:
    provider_id: str
    checkpoint_id: str
    device: str
    interpreter: str
    image_count: int
    total_duration_seconds: float
    mean_duration_seconds: float
    median_duration_seconds: float
    p95_duration_seconds: float
    throughput_images_per_second: float
    memory_use_mb: float | None
    failures: int
    date: str
    app_version: str = ""

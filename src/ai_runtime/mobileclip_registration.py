from __future__ import annotations
from pathlib import Path
from ai_runtime.models import AIRuntimeCapability, AIRuntimeDescriptor, RequiredModelFile, RuntimeDependency
from ai_runtime.registry import AIRuntimeRegistry
from vision.mobileclip_provider import MOBILECLIP_S0, MobileCLIPEmbeddingProvider

def _verify_mobileclip(cache: Path) -> bool:
    provider=MobileCLIPEmbeddingProvider(model_cache_dir=cache)
    return provider.availability().state == 'Ready'

def register_mobileclip_runtime(registry: AIRuntimeRegistry) -> None:
    if registry.get('mobileclip'): return
    registry.register('mobileclip', AIRuntimeDescriptor(
        provider_id='mobileclip', display_name='MobileCLIP', description='Optional local MobileCLIP-S0 runtime for evaluation-only image/text embeddings and zero-shot reports. It does not replace the production classifier.', provider_type='vision_embedding', checkpoint_id=MOBILECLIP_S0.checkpoint_id, revision=MOBILECLIP_S0.revision,
        capabilities=(AIRuntimeCapability.IMAGE_EMBEDDINGS,AIRuntimeCapability.TEXT_EMBEDDINGS,AIRuntimeCapability.ZERO_SHOT_CLASSIFICATION), source_url=MOBILECLIP_S0.source_url, code_license='MIT for the official Apple MobileCLIP code', model_license='Apple ML Research Model Terms for MobileCLIP weights', expected_download_size='Approximately 216 MB checkpoint plus Python package/cache overhead', supported_devices=('CPU',), recommended_hardware='CPU-only baseline; Python 3.10 dedicated environment is supported for the Product Owner workflow.',
        required_python_packages=(RuntimeDependency('torch','torch'),RuntimeDependency('torchvision','torchvision'),RuntimeDependency('mobileclip','mobileclip @ git+https://github.com/apple/ml-mobileclip.git')),
        required_model_files=(RequiredModelFile('mobileclip_s0.pt','Explicitly downloaded apple/MobileCLIP-S0 PyTorch checkpoint; no automatic download in MODEL-002A',size_bytes=216*1024*1024),), provider_factory=lambda cache: MobileCLIPEmbeddingProvider(model_cache_dir=cache), verifier=_verify_mobileclip, python_version_spec='Python 3.10 is the supported dedicated environment for current Product Owner MobileCLIP validation.'
    ))

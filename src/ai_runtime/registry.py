from __future__ import annotations
from ai_runtime.models import AIRuntimeDescriptor

class AIRuntimeRegistry:
    def __init__(self): self._descriptors: dict[str, AIRuntimeDescriptor] = {}
    def register(self, provider_id: str, descriptor: AIRuntimeDescriptor) -> None:
        if provider_id != descriptor.provider_id: raise ValueError("provider_id must match descriptor.provider_id")
        if provider_id in self._descriptors: raise ValueError(f"AI runtime provider already registered: {provider_id}")
        self._descriptors[provider_id] = descriptor
    def get(self, provider_id: str) -> AIRuntimeDescriptor | None: return self._descriptors.get(provider_id)
    def require(self, provider_id: str) -> AIRuntimeDescriptor:
        d=self.get(provider_id)
        if not d: raise KeyError(provider_id)
        return d
    def all(self) -> list[AIRuntimeDescriptor]: return list(self._descriptors.values())
    def provider_ids(self) -> list[str]: return list(self._descriptors.keys())

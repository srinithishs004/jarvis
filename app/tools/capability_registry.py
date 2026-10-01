from app.models.capability import CapabilityDefinition


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}

    def register(self, capability: CapabilityDefinition) -> None:
        if capability.name in self._capabilities:
            raise ValueError(
                f"Capability already registered: {capability.name}"
            )
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> CapabilityDefinition:
        try:
            return self._capabilities[name]
        except KeyError:
            raise KeyError(f"Capability not found: {name}") from None

    def list(self) -> list[CapabilityDefinition]:
        return list(self._capabilities.values())

    def exists(self, name: str) -> bool:
        return name in self._capabilities

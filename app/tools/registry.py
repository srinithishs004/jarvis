from app.models.tool import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Tool not found: {name}") from None

    def list(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def exists(self, name: str) -> bool:
        return name in self._tools

from __future__ import annotations

from typing import Any


class ToolArgumentError(ValueError):
    """Raised when tool arguments violate the tool input schema."""


def validate_tool_arguments(
    arguments: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """
    Validate tool arguments against the supported subset of JSON Schema.

    Supported:
    - object
    - string
    - integer
    - number
    - boolean
    - array
    - enum
    - required
    - properties
    - additionalProperties=false
    """
    if not schema:
        return

    _validate(arguments, schema, path="$")


def _validate(
    value: Any,
    schema: dict[str, Any],
    *,
    path: str,
) -> None:
    expected = schema.get("type")

    if expected == "object":
        if not isinstance(value, dict):
            raise ToolArgumentError(
                f"{path} must be an object"
            )

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for name in required:
            if name not in value:
                raise ToolArgumentError(
                    f"{path}.{name} is required"
                )

        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(properties)

            if unknown:
                names = ", ".join(sorted(unknown))

                raise ToolArgumentError(
                    f"{path} contains unknown properties: {names}"
                )

        for name, child_schema in properties.items():
            if name in value:
                _validate(
                    value[name],
                    child_schema,
                    path=f"{path}.{name}",
                )

    elif expected == "string":
        if not isinstance(value, str):
            raise ToolArgumentError(
                f"{path} must be a string"
            )

    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ToolArgumentError(
                f"{path} must be an integer"
            )

    elif expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ToolArgumentError(
                f"{path} must be a number"
            )

    elif expected == "boolean":
        if not isinstance(value, bool):
            raise ToolArgumentError(
                f"{path} must be a boolean"
            )

    elif expected == "array":
        if not isinstance(value, list):
            raise ToolArgumentError(
                f"{path} must be an array"
            )

        item_schema = schema.get("items")

        if item_schema:
            for index, item in enumerate(value):
                _validate(
                    item,
                    item_schema,
                    path=f"{path}[{index}]",
                )

    elif expected is not None:
        raise ToolArgumentError(
            f"{path} uses unsupported schema type: {expected}"
        )

    if "enum" in schema and value not in schema["enum"]:
        raise ToolArgumentError(
            f"{path} must be one of {schema['enum']}"
        )

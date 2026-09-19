"""Selection and environment construction for configured process domains."""

from __future__ import annotations

import os
from typing import Any, Mapping


class ProcessConfigError(RuntimeError):
    pass


# These variables are process mechanics rather than site credentials. Everything
# else must be explicitly exposed by a processes.*.env entry.
BASELINE_ENVIRONMENT = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "TMP",
    "TEMP",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
)


def select_process(
    config: Mapping[str, Any], process_type: str, role: str | None = None
) -> tuple[str, dict[str, Any]]:
    processes = config.get("processes")
    if not isinstance(processes, dict):
        raise ProcessConfigError("processes must be configured")
    matches: list[tuple[str, dict[str, Any]]] = []
    for name, settings in processes.items():
        if not isinstance(name, str) or not isinstance(settings, dict):
            continue
        if settings.get("type") != process_type:
            continue
        if process_type == "agent" and role not in settings.get("roles", []):
            continue
        matches.append((name, settings))
    description = "broker" if process_type == "broker" else f'agent role "{role}"'
    if len(matches) != 1:
        raise ProcessConfigError(f"{description} must resolve to exactly one process")
    return matches[0]


def process_environment(
    name: str,
    settings: Mapping[str, Any],
    parent: Mapping[str, str] | None = None,
    additions: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if parent is None else parent
    environment = {key: source[key] for key in BASELINE_ENVIRONMENT if source.get(key)}
    entries = settings.get("env", {})
    if not isinstance(entries, dict):
        raise ProcessConfigError(f"processes.{name}.env must be a mapping")
    for child_name, entry in entries.items():
        if not isinstance(child_name, str) or not isinstance(entry, dict):
            raise ProcessConfigError(f"processes.{name}.env entries must be mappings")
        if "value" in entry:
            value = entry["value"]
            if not isinstance(value, str):
                raise ProcessConfigError(f"processes.{name}.env.{child_name}.value must be a string")
            environment[child_name] = value
            continue
        parent_name = entry.get("from_env")
        if not isinstance(parent_name, str) or not parent_name:
            raise ProcessConfigError(
                f"processes.{name}.env.{child_name}.from_env must be a non-empty string"
            )
        value = source.get(parent_name)
        if value:
            environment[child_name] = value
        elif entry.get("required") is True:
            raise ProcessConfigError(
                f"processes.{name} requires parent environment variable {parent_name}"
            )
    if additions:
        environment.update(additions)
    return environment


def process_secrets(
    settings: Mapping[str, Any], parent: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """Return non-empty values resolved from parent variables for redaction."""
    source = os.environ if parent is None else parent
    entries = settings.get("env", {})
    if not isinstance(entries, dict):
        return ()
    values = {
        source[parent_name]
        for entry in entries.values()
        if isinstance(entry, dict)
        and isinstance((parent_name := entry.get("from_env")), str)
        and source.get(parent_name)
    }
    return tuple(sorted(values, key=len, reverse=True))


def redact(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        text = text.replace(secret, "[REDACTED]")
    return text


def redact_value(value: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        return redact(value, secrets)
    if isinstance(value, list):
        return [redact_value(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: redact_value(item, secrets) for key, item in value.items()}
    return value


def broker_environment(
    config: Mapping[str, Any], additions: Mapping[str, str] | None = None
) -> tuple[str, dict[str, str], tuple[str, ...]]:
    name, settings = select_process(config, "broker")
    return (
        name,
        process_environment(name, settings, additions=additions),
        process_secrets(settings),
    )


def agent_environment(
    config: Mapping[str, Any], role: str, additions: Mapping[str, str] | None = None
) -> tuple[str, dict[str, str], tuple[str, ...]]:
    name, settings = select_process(config, "agent", role)
    return (
        name,
        process_environment(name, settings, additions=additions),
        process_secrets(settings),
    )

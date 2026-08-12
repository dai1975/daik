"""Local invocation records stored outside a daik site."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any
import uuid

from daiklib.workspaces import safe_slug


class InvocationError(RuntimeError):
    pass


def state_root(environment: dict[str, str] | None = None) -> Path:
    values = os.environ if environment is None else environment
    override = values.get("DAIK_STATE_HOME")
    if override:
        return Path(override).expanduser()
    xdg = values.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "daik"
    home = values.get("HOME")
    if not home:
        raise InvocationError("HOME is not set and no daik state directory is configured")
    return Path(home) / ".local" / "state" / "daik"


def state_key(label: str, identity: str) -> str:
    slug = safe_slug(label).rsplit("-", 1)[0]
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def ensure_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise InvocationError(f"state directory must not be a symlink: {path}")
    if path.exists():
        if not path.is_dir():
            raise InvocationError(f"state path is not a directory: {path}")
        if path.stat().st_uid != os.getuid():
            raise InvocationError(f"state directory is not owned by the current user: {path}")
        path.chmod(0o700)
        return
    path.mkdir(mode=0o700, parents=True)
    path.chmod(0o700)


def site_state_directory(site: Path) -> Path:
    root = state_root()
    if not root.is_absolute():
        raise InvocationError("daik state directory must be absolute")
    root = root.absolute()
    ensure_private_directory(root)
    site_resolved = site.resolve()
    site_key = state_key(site_resolved.name or "site", str(site_resolved))
    parent = root
    for component in ("sites", site_key):
        parent = parent / component
        ensure_private_directory(parent)
    return parent


def create_invocation_directory(site: Path, issue: str) -> tuple[str, Path]:
    issue_key = state_key(issue, issue)
    parent = site_state_directory(site)
    for component in ("invocations", issue_key):
        parent = parent / component
        ensure_private_directory(parent)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    invocation_id = str(uuid.uuid4())
    directory = parent / f"{timestamp}-{invocation_id}"
    directory.mkdir(mode=0o700)
    return invocation_id, directory


def write_private_json(path: Path, value: Any) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        stream.write(content)


def write_private_text(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        stream.write(content)


def replace_private_json(path: Path, value: Any) -> None:
    if path.is_symlink():
        raise InvocationError(f"state file must not be a symlink: {path}")
    temporary = path.parent / f".{path.name}.{uuid.uuid4()}.tmp"
    try:
        write_private_json(temporary, value)
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def link_native_artifacts(directory: Path, artifacts: Any) -> list[dict[str, Any]]:
    if artifacts is None:
        return []
    if not isinstance(artifacts, list):
        raise InvocationError("native_artifacts must be a list")
    records: list[dict[str, Any]] = []
    session_number = 0
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("type") != "session":
            records.append({"status": "rejected", "reason": "unsupported artifact"})
            continue
        session_number += 1
        target_value = artifact.get("path")
        target = Path(target_value) if isinstance(target_value, str) else Path()
        link_name = "native-session" if session_number == 1 else f"native-session-{session_number}"
        record = {
            "type": "session",
            "id": artifact.get("id"),
            "original_path": target_value,
            "link": link_name,
        }
        try:
            if not target.is_absolute():
                raise InvocationError("target is not absolute")
            target_stat = target.stat()
            if target_stat.st_uid != os.getuid():
                raise InvocationError("target is not owned by the current user")
            if not (stat.S_ISREG(target_stat.st_mode) or stat.S_ISDIR(target_stat.st_mode)):
                raise InvocationError("target is not a regular file or directory")
            link = directory / link_name
            if link.exists() or link.is_symlink():
                raise InvocationError("link already exists")
            link.symlink_to(target)
        except (InvocationError, OSError) as error:
            record.update({"status": "rejected", "reason": str(error)})
        else:
            record["status"] = "linked"
        records.append(record)
    if records:
        write_private_json(directory / "native-session.json", records)
    return records

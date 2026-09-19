"""Independent Git clone management with issue-tracker event output."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Sequence
from urllib.parse import urlsplit, urlunsplit

from daiklib.processes import ProcessConfigError, broker_environment, redact


class WorkspaceError(RuntimeError):
    pass


def run_git(
    arguments: Sequence[str], repository: Path, environment: dict[str, str] | None = None,
    secrets: tuple[str, ...] = (),
    *, redact_stdout: bool = True,
) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise WorkspaceError(redact(detail, secrets))
    stdout = result.stdout.strip()
    return redact(stdout, secrets) if redact_stdout else stdout


def event_remote_url(value: str, secrets: tuple[str, ...]) -> str:
    """Return a useful remote identity without URL credentials or parameters."""
    parsed = urlsplit(value)
    if parsed.scheme and parsed.netloc:
        hostname = parsed.hostname or ""
        if ":" in hostname:
            hostname = f"[{hostname}]"
        netloc = hostname
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        value = urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    return redact(value, secrets)


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48]
    if not slug:
        slug = "issue"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def event(kind: str, issue: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "daik.issue-event.v1",
        "kind": kind,
        "issue": issue,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data": data,
    }


class WorkspaceManager:
    def __init__(self, site: Path, config: dict[str, Any]):
        self.site = site.resolve()
        try:
            self.process_name, self.environment, self.secrets = broker_environment(config)
        except ProcessConfigError as error:
            raise WorkspaceError(str(error)) from error
        workspace = config.get("workspace")
        if not isinstance(workspace, dict):
            raise WorkspaceError("workspace configuration must be a mapping")
        root_name = workspace.get("root")
        if not isinstance(root_name, str) or not root_name:
            raise WorkspaceError("workspace.root must be a non-empty string")
        self.workspace_root = self._site_path(root_name)
        strategy = workspace.get("strategy")
        if strategy != "clone":
            raise WorkspaceError(
                "workspace.strategy must currently be 'clone'; add `strategy: clone` under `workspace`"
            )
        prefix = workspace.get("branch_prefix", "daik")
        if not isinstance(prefix, str) or not prefix or "/" in prefix:
            raise WorkspaceError("workspace.branch_prefix must be a non-empty path component")
        self.branch_prefix = prefix
        repositories = config.get("repositories")
        if not isinstance(repositories, dict) or not repositories:
            raise WorkspaceError("no repositories are configured")
        self.repositories = repositories

    def _git(self, arguments: Sequence[str], repository: Path) -> str:
        return run_git(arguments, repository, self.environment, self.secrets)

    def _git_raw(self, arguments: Sequence[str], repository: Path) -> str:
        return run_git(
            arguments, repository, self.environment, self.secrets, redact_stdout=False
        )

    def _site_path(self, relative_name: str) -> Path:
        relative = Path(relative_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise WorkspaceError(f"path must be site-relative: {relative_name}")
        resolved = (self.site / relative).resolve()
        try:
            resolved.relative_to(self.site)
        except ValueError as error:
            raise WorkspaceError(f"path escapes the site: {relative_name}") from error
        return resolved

    def workspace_id(self, issue: str) -> str:
        return safe_slug(issue)

    def selected_repositories(self, selected: Sequence[str]) -> list[tuple[str, Path, str]]:
        names = list(selected) if selected else sorted(self.repositories)
        unknown = sorted(set(names) - set(self.repositories))
        if unknown:
            raise WorkspaceError("unknown repositories: " + ", ".join(unknown))
        result: list[tuple[str, Path, str]] = []
        for name in names:
            if Path(name).name != name or name in {".", ".."}:
                raise WorkspaceError(f"repository name must be one path component: {name}")
            settings = self.repositories[name]
            if not isinstance(settings, dict):
                raise WorkspaceError(f"repositories.{name} must be a mapping")
            source_name = settings.get("path")
            base = settings.get("base", "HEAD")
            if not isinstance(source_name, str) or not source_name:
                raise WorkspaceError(f"repositories.{name}.path must be a non-empty string")
            if not isinstance(base, str) or not base:
                raise WorkspaceError(f"repositories.{name}.base must be a non-empty string")
            source = self._site_path(source_name)
            if not source.is_dir():
                raise WorkspaceError(f"repository directory is missing: {source_name}")
            self._git(("rev-parse", "--git-dir"), source)
            result.append((name, source, base))
        return result

    def _remote(self, source: Path) -> tuple[str, str]:
        remotes = self._git(("remote",), source).splitlines()
        if len(remotes) != 1:
            raise WorkspaceError(
                f"source repository {source.relative_to(self.site)} must have exactly one remote; "
                f"found {len(remotes)}"
            )
        name = remotes[0]
        # Remote URLs are operational values. Keep them intact internally; only
        # diagnostics and serialized events may receive sanitized values.
        fetch_url = self._git_raw(("remote", "get-url", name), source)
        push_url = self._git_raw(("remote", "get-url", "--push", name), source)
        if fetch_url != push_url:
            raise WorkspaceError(
                f"source repository {source.relative_to(self.site)} remote {name!r} has "
                "different fetch and push URLs"
            )
        return name, fetch_url

    def _require_workspace_containment(self, workspace: Path, repository: Path) -> None:
        workspace_root = self.workspace_root.resolve()
        resolved_workspace = workspace.resolve()
        resolved_repository = repository.resolve()
        try:
            resolved_workspace.relative_to(workspace_root)
            resolved_repository.relative_to(resolved_workspace)
        except ValueError as error:
            raise WorkspaceError(
                f"repository clone escapes its Issue workspace: {repository}"
            ) from error
        if resolved_workspace != workspace.absolute() or resolved_repository != repository.absolute():
            raise WorkspaceError(
                f"repository clone path must not use symlinks: {repository}"
            )

    def _require_independent_clone(self, workspace: Path, repository: Path) -> None:
        self._require_workspace_containment(workspace, repository)
        if not repository.is_dir():
            raise WorkspaceError(f"repository clone is missing: {repository}")
        git_directory = repository / ".git"
        if not git_directory.is_dir() or git_directory.is_symlink():
            raise WorkspaceError(
                f"existing repository has no independent .git directory: {repository}"
            )
        objects_directory = git_directory / "objects"
        if not objects_directory.is_dir() or objects_directory.is_symlink():
            raise WorkspaceError(
                f"existing repository has no independent Git object directory: {repository}"
            )
        if (objects_directory / "info" / "alternates").exists():
            raise WorkspaceError(
                f"existing repository uses Git object alternates: {repository}"
            )

    def _record(self, name: str, source: Path, repository: Path, base_revision: str) -> dict[str, str]:
        branch = self._git(("branch", "--show-current"), repository)
        head = self._git(("rev-parse", "HEAD"), repository)
        remote_name, remote_url = self._remote(repository)
        return {
            "name": name,
            "source": source.relative_to(self.site).as_posix(),
            "path": repository.relative_to(self.site).as_posix(),
            "branch": branch,
            "head": head,
            "base_revision": base_revision,
            "remote": remote_name,
            "remote_url": event_remote_url(remote_url, self.secrets),
        }

    def create(self, issue: str, selected: Sequence[str]) -> dict[str, Any]:
        workspace_id = self.workspace_id(issue)
        workspace = self.workspace_root / workspace_id
        repositories = self.selected_repositories(selected)
        preflight: list[tuple[str, Path, str, str, Path, str, str]] = []
        any_created = False
        for name, source, base in repositories:
            branch = f"{self.branch_prefix}/{workspace_id}"
            target = workspace / name
            self._require_workspace_containment(workspace, target)
            base_revision = self._git(("rev-parse", base), source)
            remote_name, remote_url = self._remote(source)
            if target.exists():
                self._require_independent_clone(workspace, target)
                actual_branch = self._git(("branch", "--show-current"), target)
                if actual_branch != branch:
                    raise WorkspaceError(
                        f"existing repository {target} uses {actual_branch!r}, expected {branch!r}"
                    )
                actual_remote = self._remote(target)
                if actual_remote != (remote_name, remote_url):
                    raise WorkspaceError(
                        f"existing repository {target} remote is {actual_remote!r}, "
                        f"expected {(remote_name, remote_url)!r}"
                    )
                ancestor = subprocess.run(
                    ["git", "-C", str(target), "merge-base", "--is-ancestor", base_revision, "HEAD"],
                    check=False, env=self.environment,
                )
                if ancestor.returncode != 0:
                    raise WorkspaceError(f"existing repository {target} is not based on {base_revision}")
                preflight.append(
                    (name, source, branch, base_revision, target, remote_name, remote_url)
                )
                continue
            preflight.append(
                (name, source, branch, base_revision, target, remote_name, remote_url)
            )

        records: list[dict[str, str]] = []
        for name, source, branch, base_revision, target, remote_name, remote_url in preflight:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary_remote = "daik-source"
                self._git(
                    (
                        "clone",
                        "--no-hardlinks",
                        "--origin",
                        temporary_remote,
                        str(source),
                        str(target),
                    ),
                    source,
                )
                self._git(("checkout", "-b", branch, base_revision), target)
                self._git(("remote", "remove", temporary_remote), target)
                self._git(("remote", "add", remote_name, remote_url), target)
                any_created = True
            records.append(self._record(name, source, target, base_revision))
        return event(
            "workspace.prepared" if any_created else "workspace.reused",
            issue,
            {
                "workspace_id": workspace_id,
                "path": workspace.relative_to(self.site).as_posix(),
                "repositories": records,
            },
        )

    def inspect(self, issue: str, selected: Sequence[str] = ()) -> dict[str, Any]:
        workspace_id = self.workspace_id(issue)
        workspace = self.workspace_root / workspace_id
        records: list[dict[str, str]] = []
        for name, source, base in self.selected_repositories(selected):
            target = workspace / name
            self._require_independent_clone(workspace, target)
            records.append(self._record(name, source, target, self._git(("rev-parse", base), source)))
        return event(
            "workspace.inspected",
            issue,
            {
                "workspace_id": workspace_id,
                "path": workspace.relative_to(self.site).as_posix(),
                "repositories": records,
            },
        )

    def list(self) -> list[dict[str, Any]]:
        if not self.workspace_root.is_dir():
            return []
        return [
            {
                "workspace_id": child.name,
                "path": child.relative_to(self.site).as_posix(),
                "repositories": sorted(item.name for item in child.iterdir() if item.is_dir()),
            }
            for child in sorted(self.workspace_root.iterdir())
            if child.is_dir()
        ]

    def reconcile(self, issue: str, expected: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        actual = self.inspect(issue)
        expected_data = expected.get("data")
        differences: list[str] = []
        if expected.get("schema") != "daik.issue-event.v1" or not isinstance(expected_data, dict):
            raise WorkspaceError("expected event does not use daik.issue-event.v1")
        expected_repositories = {
            item.get("name"): item
            for item in expected_data.get("repositories", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        observations: list[str] = []
        for item in actual["data"]["repositories"]:
            recorded = expected_repositories.pop(item["name"], None)
            if recorded is None:
                differences.append(f"{item['name']}: missing from recorded event")
                continue
            for key in ("source", "path", "branch", "base_revision", "remote", "remote_url"):
                if recorded.get(key) != item[key]:
                    differences.append(
                        f"{item['name']}.{key}: recorded {recorded.get(key)!r}, actual {item[key]!r}"
                    )
            if recorded.get("head") != item["head"]:
                observations.append(
                    f"{item['name']}.head advanced from {recorded.get('head')!r} to {item['head']!r}"
                )
        differences.extend(f"{name}: recorded repository is not configured" for name in expected_repositories)
        result = event(
            "workspace.reconciled",
            issue,
            {
                **actual["data"],
                "compatible": not differences,
                "differences": differences,
                "observations": observations,
            },
        )
        return result, not differences

    def remove(self, issue: str, selected: Sequence[str], wet_run: bool) -> dict[str, Any]:
        workspace_id = self.workspace_id(issue)
        workspace = self.workspace_root / workspace_id
        removed: list[dict[str, str]] = []
        for name, source, _base in self.selected_repositories(selected):
            target = workspace / name
            if not target.exists():
                continue
            self._require_independent_clone(workspace, target)
            branch = self._git(("branch", "--show-current"), target)
            removed.append(
                {
                    "name": name,
                    "path": target.relative_to(self.site).as_posix(),
                    "branch": branch,
                }
            )
            if wet_run:
                shutil.rmtree(target)
        if wet_run and workspace.is_dir() and not any(workspace.iterdir()):
            workspace.rmdir()
        return event(
            "workspace.removed" if wet_run else "workspace.remove-preview",
            issue,
            {"workspace_id": workspace_id, "repositories": removed},
        )


def handoff_event(
    issue: str,
    from_role: str,
    to_role: str,
    phase: str,
    summary: str,
    commits: Sequence[str],
    validation: Sequence[str],
    decisions: Sequence[str],
    risks: Sequence[str],
    next_actions: Sequence[str],
) -> dict[str, Any]:
    return event(
        "handoff",
        issue,
        {
            "from_role": from_role,
            "to_role": to_role,
            "phase": phase,
            "summary": summary,
            "commits": list(commits),
            "validation": list(validation),
            "decisions": list(decisions),
            "risks": list(risks),
            "next_actions": list(next_actions),
        },
    )


def dump_event(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)

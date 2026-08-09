"""Git worktree management with issue-tracker event output."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Sequence


class WorkspaceError(RuntimeError):
    pass


def run_git(arguments: Sequence[str], repository: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise WorkspaceError(detail)
    return result.stdout.strip()


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
        workspace = config.get("workspace")
        if not isinstance(workspace, dict):
            raise WorkspaceError("workspace configuration must be a mapping")
        root_name = workspace.get("root")
        if not isinstance(root_name, str) or not root_name:
            raise WorkspaceError("workspace.root must be a non-empty string")
        self.workspace_root = self._site_path(root_name)
        prefix = workspace.get("branch_prefix", "daik")
        if not isinstance(prefix, str) or not prefix or "/" in prefix:
            raise WorkspaceError("workspace.branch_prefix must be a non-empty path component")
        self.branch_prefix = prefix
        repositories = config.get("repositories")
        if not isinstance(repositories, dict) or not repositories:
            raise WorkspaceError("no repositories are configured")
        self.repositories = repositories

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
            run_git(("rev-parse", "--git-dir"), source)
            result.append((name, source, base))
        return result

    def _record(self, name: str, source: Path, worktree: Path, base_revision: str) -> dict[str, str]:
        branch = run_git(("branch", "--show-current"), worktree)
        head = run_git(("rev-parse", "HEAD"), worktree)
        return {
            "name": name,
            "source": source.relative_to(self.site).as_posix(),
            "worktree": worktree.relative_to(self.site).as_posix(),
            "branch": branch,
            "head": head,
            "base_revision": base_revision,
        }

    def create(self, issue: str, selected: Sequence[str]) -> dict[str, Any]:
        workspace_id = self.workspace_id(issue)
        workspace = self.workspace_root / workspace_id
        repositories = self.selected_repositories(selected)
        preflight: list[tuple[str, Path, str, str, Path, bool]] = []
        any_created = False
        for name, source, base in repositories:
            branch = f"{self.branch_prefix}/{workspace_id}"
            target = workspace / name
            base_revision = run_git(("rev-parse", base), source)
            if target.exists():
                if not target.is_dir():
                    raise WorkspaceError(f"worktree target is not a directory: {target}")
                actual_branch = run_git(("branch", "--show-current"), target)
                if actual_branch != branch:
                    raise WorkspaceError(
                        f"existing worktree {target} uses {actual_branch!r}, expected {branch!r}"
                    )
                preflight.append((name, source, branch, base_revision, target, False))
                continue
            branch_exists = subprocess.run(
                ["git", "-C", str(source), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
                check=False,
            ).returncode == 0
            preflight.append((name, source, branch, base_revision, target, not branch_exists))

        records: list[dict[str, str]] = []
        for name, source, branch, base_revision, target, create_branch in preflight:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                arguments = ["worktree", "add"]
                if create_branch:
                    arguments.extend(("-b", branch, str(target), base_revision))
                else:
                    arguments.extend((str(target), branch))
                run_git(arguments, source)
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
            if not target.is_dir():
                raise WorkspaceError(f"worktree is missing: {target.relative_to(self.site)}")
            records.append(self._record(name, source, target, run_git(("rev-parse", base), source)))
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
            for key in ("source", "worktree", "branch"):
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
            branch = run_git(("branch", "--show-current"), target)
            removed.append(
                {
                    "name": name,
                    "worktree": target.relative_to(self.site).as_posix(),
                    "branch": branch,
                }
            )
            if wet_run:
                run_git(("worktree", "remove", str(target)), source)
        if wet_run and workspace.is_dir() and not any(workspace.iterdir()):
            workspace.rmdir()
        return event(
            "workspace.removed" if wet_run else "workspace.remove-preview",
            issue,
            {"workspace_id": workspace_id, "repositories": removed, "branches_retained": True},
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
    checks: list[dict[str, str]] = []
    for value in validation:
        if "=" not in value:
            raise WorkspaceError("validation must use COMMAND=RESULT form")
        command, result = value.split("=", 1)
        checks.append({"command": command, "result": result})
    return event(
        "handoff",
        issue,
        {
            "from_role": from_role,
            "to_role": to_role,
            "phase": phase,
            "summary": summary,
            "commits": list(commits),
            "validation": checks,
            "decisions": list(decisions),
            "risks": list(risks),
            "next_actions": list(next_actions),
        },
    )


def dump_event(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)

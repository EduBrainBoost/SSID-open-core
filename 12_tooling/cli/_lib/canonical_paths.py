from __future__ import annotations

import re
from pathlib import Path

_PATH_SERIALIZED_EXPORT_PATTERN = re.compile(
    r"^[A-Za-z]--Users-.*[REDACTED-PRIVATE-REPO]-SSID-Arbeitsbereich-Github-(SSID|SSID-EMS)(-.+)?$",
    re.IGNORECASE,
)


def _normalize(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def canonical_repo_roots(repo_root: str | Path | None = None) -> tuple[Path, ...]:
    current_repo_root = _normalize(repo_root or Path(__file__).resolve().parents[3])
    sibling_ems_root = _normalize(current_repo_root.parent / "SSID-EMS")
    return (current_repo_root, sibling_ems_root)


def _matching_canonical_root(path: Path, repo_root: str | Path | None = None) -> Path | None:
    for root in canonical_repo_roots(repo_root):
        try:
            path.relative_to(root)
            return root
        except ValueError:
            continue
    return None


def _path_serialized_export_root(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if _PATH_SERIALIZED_EXPORT_PATTERN.match(candidate.name):
            return candidate
    return None


def classify_path(path: str | Path, repo_root: str | Path | None = None) -> str:
    resolved = _normalize(path)

    if _matching_canonical_root(resolved, repo_root):
        return "CANONICAL_REPO"

    normalized = str(resolved).replace("\\", "/").lower()
    if "/documents/github/ssid" in normalized or "/documents/github/ssid-ems" in normalized:
        return "DUPLICATE_REPO"

    if "/.claude/projects/" in normalized or _path_serialized_export_root(resolved):
        return "DRIVE_ARTIFACT_DUPLICATE"

    if "/ssid_evidence/" in normalized:
        return "EVIDENCE_DUPLICATE"

    if "/backups/" in normalized or normalized.endswith("/backup"):
        return "BACKUP_DUPLICATE"

    if "/.ssid-system/" in normalized:
        return "WORKSPACE_META"

    return "CONTAMINATED_ROOT"


def ensure_canonical_repo_root(
    path: str | Path,
    *,
    expected_repo_name: str | None = None,
    repo_root: str | Path | None = None,
) -> Path:
    resolved = _normalize(path)
    matching_root = _matching_canonical_root(resolved, repo_root)
    if matching_root is None or resolved != matching_root:
        raise ValueError(
            f"Repo path must be one of the canonical repo roots, got {resolved} "
            f"({classify_path(resolved, repo_root=repo_root)})"
        )
    if expected_repo_name and resolved.name.lower() != expected_repo_name.lower():
        raise ValueError(f"Repo path {resolved} does not match expected repo name {expected_repo_name}")
    return resolved


def ensure_canonical_write_path(
    path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> Path:
    resolved = _normalize(path)
    matching_root = _matching_canonical_root(resolved, repo_root)
    if matching_root is None:
        raise ValueError(
            f"Write path must stay inside canonical repos, got {resolved} "
            f"({classify_path(resolved, repo_root=repo_root)})"
        )
    if _path_serialized_export_root(resolved):
        raise ValueError(f"Write path rejected inside path-serialized export root: {resolved}")
    return resolved

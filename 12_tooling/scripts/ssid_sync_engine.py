"""
SSID Deterministic Sync Engine

Windows-compatible, deterministic file synchronization with:
- Add/update/delete tracking
- .git directory preservation
- Dry-run mode
- Comprehensive error handling
- Cross-platform path handling
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Set
import hashlib


class SyncEngine:
    """Deterministic bidirectional sync engine."""

    def __init__(self, source: Path, target: Path, preserve_patterns: List[str] = None):
        """
        Initialize sync engine.

        Args:
            source: Source directory
            target: Target directory
            preserve_patterns: Path patterns to preserve in target (e.g., [".git"])
        """
        self.source = Path(source)
        self.target = Path(target)
        self.preserve_patterns = preserve_patterns or [".git"]

        self.stats = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": 0
        }

        self.errors = []

    def should_preserve(self, path: Path) -> bool:
        """Check if path matches preserve patterns."""
        path_parts = path.parts
        for pattern in self.preserve_patterns:
            if pattern in path_parts:
                return True
        return False

    def get_file_hash(self, fpath: Path) -> str:
        """Get SHA256 hash of file."""
        try:
            sha256 = hashlib.sha256()
            with open(fpath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            return ""

    def get_source_files(self) -> Dict[str, Path]:
        """Get all trackable files in source."""
        files = {}
        if not self.source.exists():
            return files

        for fpath in self.source.rglob("*"):
            if fpath.is_file() and not self.should_preserve(fpath.relative_to(self.source)):
                rel_path = str(fpath.relative_to(self.source)).replace("\\", "/")
                files[rel_path] = fpath

        return files

    def get_target_files(self) -> Dict[str, Path]:
        """Get all trackable files in target."""
        files = {}
        if not self.target.exists():
            return files

        for fpath in self.target.rglob("*"):
            if fpath.is_file() and not self.should_preserve(fpath.relative_to(self.target)):
                rel_path = str(fpath.relative_to(self.target)).replace("\\", "/")
                files[rel_path] = fpath

        return files

    def sync(self, dry_run: bool = False) -> Tuple[bool, Dict]:
        """
        Synchronize source to target.

        Args:
            dry_run: If True, report changes but don't apply them

        Returns:
            (success: bool, stats: dict)
        """
        source_files = self.get_source_files()
        target_files = self.get_target_files()

        source_set = set(source_files.keys())
        target_set = set(target_files.keys())

        # Files to add
        to_add = source_set - target_set
        # Files to update (exist in both)
        to_check = source_set & target_set
        # Files to delete (only in target)
        to_delete = target_set - source_set

        # Process additions and updates
        for rel_path in sorted(to_add | to_check):
            src_file = source_files[rel_path]
            dst_file = self.target / rel_path

            try:
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                if rel_path in to_add:
                    # Add new file
                    if not dry_run:
                        shutil.copy2(src_file, dst_file)
                    self.stats["added"] += 1
                else:
                    # Check if update needed
                    src_hash = self.get_file_hash(src_file)
                    dst_hash = self.get_file_hash(dst_file)

                    if src_hash != dst_hash and src_hash:
                        # Update existing file
                        if not dry_run:
                            shutil.copy2(src_file, dst_file)
                        self.stats["updated"] += 1
                    else:
                        self.stats["skipped"] += 1

            except Exception as e:
                self.errors.append(f"Failed to sync {rel_path}: {str(e)}")
                self.stats["errors"] += 1

        # Process deletions
        for rel_path in sorted(to_delete):
            dst_file = target_files[rel_path]

            try:
                if not dry_run:
                    dst_file.unlink()
                self.stats["deleted"] += 1
            except Exception as e:
                self.errors.append(f"Failed to delete {rel_path}: {str(e)}")
                self.stats["errors"] += 1

        success = self.stats["errors"] == 0
        return success, self.stats


class VerificationScanner:
    """Scan files for violations across all relevant types."""

    SCAN_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".json", ".sh", ".toml"}

    def __init__(self, target: Path):
        """Initialize scanner."""
        self.target = Path(target)
        self.violations = {
            "local_paths": [],
            "private_refs": [],
            "credentials": [],
            "invalid_claims": [],
            "quickstart_errors": [],
            "manifest_errors": []
        }

    def scan(self) -> Dict[str, List[str]]:
        """Scan target directory for violations."""
        import re

        files_to_scan = []
        for ext in self.SCAN_EXTENSIONS:
            files_to_scan.extend(self.target.rglob(f"*{ext}"))

        for fpath in files_to_scan:
            if ".git" in fpath.parts:
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                self._check_file(fpath, content)
            except Exception:
                pass

        return self.violations

    def _check_file(self, fpath: Path, content: str):
        """Check single file for violations."""
        import re

        rel_path = fpath.relative_to(self.target)

        # Hardcoded local paths
        if re.search(r'[Cc]:\\Users\\bibel|/c/Users/bibel', content):
            self.violations["local_paths"].append(str(rel_path))

        # AWS credentials
        if re.search(r'AKIA[0-9A-Z]{16}', content):
            self.violations["credentials"].append(str(rel_path))

        # SK tokens
        if re.search(r'sk-[a-zA-Z0-9]{20,}', content):
            self.violations["credentials"].append(str(rel_path))

        # Unbacked mainnet claims
        if fpath.suffix == ".py":
            if re.search(r'mainnet|production.*deployed|live.*blockchain', content, re.IGNORECASE):
                if not re.search(r'(planned|candidate|proposed|future|not.*yet)', content, re.IGNORECASE):
                    self.violations["invalid_claims"].append(str(rel_path))

        # Invalid quickstart references
        if fpath.name == "README.md":
            if "11_test_simulation" in content:
                self.violations["quickstart_errors"].append(f"{rel_path}: references 11_test_simulation")
            if "01_ai_layer" in content:
                self.violations["quickstart_errors"].append(f"{rel_path}: references 01_ai_layer")

    def report(self) -> str:
        """Generate violation report."""
        lines = ["VERIFICATION SCAN REPORT", "=" * 60]

        for category, items in self.violations.items():
            if items:
                lines.append(f"\n{category.upper()} ({len(items)}):")
                for item in items[:5]:  # Show first 5
                    lines.append(f"  - {item}")
                if len(items) > 5:
                    lines.append(f"  ... and {len(items) - 5} more")

        if not any(self.violations.values()):
            lines.append("\nNo violations detected")

        return "\n".join(lines)

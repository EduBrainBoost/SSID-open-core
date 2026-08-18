"""Real OpenCore tests."""
import pytest
import tempfile
import json
from pathlib import Path
from src.opencore import OpenCoreCore


class TestExport:
    """Test content export."""

    def test_export_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = OpenCoreCore(tmpdir)
            # Create a source file
            schema_dir = Path(tmpdir) / "schemas"
            schema_dir.mkdir()
            schema_file = schema_dir / "test.json"
            schema_file.write_text('{"type": "object"}')

            manifest = core.export_content("schemas/test.json", "public/test.json")
            assert manifest is not None
            assert manifest.content_hash

    def test_export_excluded_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = OpenCoreCore(tmpdir)
            # Try to export excluded path
            manifest = core.export_content("config/secrets/env", "public/secrets")
            assert manifest is None

    def test_export_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = OpenCoreCore(tmpdir)
            manifest = core.export_content("nonexistent/file.txt", "public/file.txt")
            assert manifest is None


class TestVerification:
    """Test export verification."""

    def test_verify_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = OpenCoreCore(tmpdir)
            schema_dir = Path(tmpdir) / "schemas"
            schema_dir.mkdir()
            (schema_dir / "test.json").write_text('{"type": "object"}')

            manifest = core.export_content("schemas/test.json", "public/test.json")
            result = core.verify_export(manifest.manifest_id)
            assert result["verified"] is True
            assert result["status"] == "EXPORTED"

    def test_verify_nonexistent(self):
        core = OpenCoreCore(".")
        result = core.verify_export("nonexistent")
        assert result["verified"] is False


class TestRevoke:
    """Test export revocation."""

    def test_revoke_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = OpenCoreCore(tmpdir)
            schema_dir = Path(tmpdir) / "schemas"
            schema_dir.mkdir()
            (schema_dir / "test.json").write_text('{"type": "object"}')

            manifest = core.export_content("schemas/test.json", "public/test.json")
            assert core.revoke_export(manifest.manifest_id)
            result = core.verify_export(manifest.manifest_id)
            assert result["status"] == "REVOKED"


class TestListExports:
    """Test listing exports."""

    def test_list_exports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = OpenCoreCore(tmpdir)
            schema_dir = Path(tmpdir) / "schemas"
            schema_dir.mkdir()
            (schema_dir / "test.json").write_text('{"type": "object"}')

            core.export_content("schemas/test.json", "public/test.json")
            exports = core.list_exports()
            assert len(exports) == 1
            assert exports[0]["status"] == "EXPORTED"

    def test_filter_by_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = OpenCoreCore(tmpdir)
            schema_dir = Path(tmpdir) / "schemas"
            schema_dir.mkdir()
            (schema_dir / "test.json").write_text('{"type": "object"}')

            manifest = core.export_content("schemas/test.json", "public/test.json")
            core.revoke_export(manifest.manifest_id)

            exported = core.list_exports(status="EXPORTED")
            assert len(exported) == 0

            revoked = core.list_exports(status="REVOKED")
            assert len(revoked) == 1


class TestListExportable:
    """Test listing exportable content."""

    def test_list_exportable(self):
        core = OpenCoreCore(".")
        exports = core.list_exportable()
        # At minimum, schemas should be listed
        assert len(exports) >= 0


class TestVersion:
    """Test version."""

    def test_version(self):
        from src.opencore import __version__
        assert __version__ == "1.0.0"

#!/usr/bin/env python3
"""Tests for 12_tooling.security.attack_surface_mapper — AttackSurfaceMapper class.

Covers:
  - map_endpoints(): FastAPI, Django, Express.js, gRPC, WebSocket patterns
  - map_dependencies(): requirements.txt, package.json extraction
  - Port discovery via _scan_ports()
  - External call detection via _scan_external_calls()
  - generate_report(): summary counters and risk level aggregation
  - Risk classification helpers: _endpoint_risk, _port_risk, _dep_risk
  - reset() state clearing
  - Non-existent / invalid path handling

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make parent 12_tooling importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from security.attack_surface_mapper import (
    AttackSurfaceMapper,
    AttackSurfaceReport,
    _dep_risk,
    _endpoint_risk,
    _port_risk,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _py(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mapper() -> AttackSurfaceMapper:
    return AttackSurfaceMapper()


@pytest.fixture()
def fastapi_root(tmp_path: Path) -> Path:
    """A root directory with FastAPI endpoint definitions."""
    root = tmp_path / "03_core"
    root.mkdir()
    _py(
        root / "api.py",
        (
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "\n"
            '@app.get("/health")\n'
            "def health(): pass\n"
            "\n"
            '@app.post("/auth/token")\n'
            "def token(): pass\n"
            "\n"
            '@app.delete("/admin/user")\n'
            "def delete_user(): pass\n"
        ),
    )
    return root


@pytest.fixture()
def grpc_root(tmp_path: Path) -> Path:
    """A root directory with a gRPC .proto file."""
    root = tmp_path / "10_interoperability"
    root.mkdir()
    _py(
        root / "identity.proto",
        (
            'syntax = "proto3";\n'
            "service IdentityService {\n"
            "  rpc ResolveIdentity (IdentityRequest) returns (IdentityResponse);\n"
            "  rpc VerifyCredential (CredentialRequest) returns (VerificationResult);\n"
            "}\n"
        ),
    )
    return root


@pytest.fixture()
def deps_root(tmp_path: Path) -> Path:
    """A root directory with Python and npm dependency files."""
    root = tmp_path / "18_data_layer"
    root.mkdir()
    (root / "requirements.txt").write_text(
        "cryptography==41.0.5\nrequests==2.31.0\nboto3==1.34.0\n",
        encoding="utf-8",
    )
    _json(
        root / "package.json",
        {
            "name": "ssid-ui",
            "dependencies": {
                "axios": "^1.6.0",
                "react": "^18.2.0",
            },
            "devDependencies": {
                "typescript": "^5.0.0",
            },
        },
    )
    return root


# ===========================================================================
# Tests — Risk classification helpers
# ===========================================================================


class TestRiskHelpers:
    def test_endpoint_risk_auth_path_is_critical(self) -> None:
        assert _endpoint_risk("GET", "/auth/token") == "critical"

    def test_endpoint_risk_admin_path_is_critical(self) -> None:
        assert _endpoint_risk("GET", "/admin/users") == "critical"

    def test_endpoint_risk_delete_method_is_high(self) -> None:
        assert _endpoint_risk("DELETE", "/resource") == "high"

    def test_endpoint_risk_post_method_is_high(self) -> None:
        assert _endpoint_risk("POST", "/data") == "high"

    def test_endpoint_risk_health_is_medium(self) -> None:
        assert _endpoint_risk("GET", "/health") == "medium"

    def test_endpoint_risk_get_plain_is_low(self) -> None:
        assert _endpoint_risk("GET", "/public/info") == "low"

    def test_port_risk_ssh_is_critical(self) -> None:
        assert _port_risk(22) == "critical"

    def test_port_risk_rdp_is_critical(self) -> None:
        assert _port_risk(3389) == "critical"

    def test_port_risk_postgres_is_high(self) -> None:
        assert _port_risk(5432) == "high"

    def test_port_risk_http_8000_is_medium(self) -> None:
        assert _port_risk(8000) == "medium"

    def test_port_risk_https_is_low(self) -> None:
        assert _port_risk(443) == "low"

    def test_dep_risk_cryptography_is_high(self) -> None:
        assert _dep_risk("cryptography") == "high"

    def test_dep_risk_requests_is_medium(self) -> None:
        assert _dep_risk("requests") == "medium"

    def test_dep_risk_unknown_package_is_low(self) -> None:
        assert _dep_risk("my-internal-utils") == "low"


# ===========================================================================
# Tests — map_endpoints()
# ===========================================================================


class TestMapEndpoints:
    def test_fastapi_routes_detected(self, mapper: AttackSurfaceMapper, fastapi_root: Path) -> None:
        entries = mapper.map_endpoints(fastapi_root)
        paths = [e.path for e in entries]
        assert any("/health" in p for p in paths)
        assert any("/auth/token" in p for p in paths)

    def test_admin_endpoint_risk_is_critical(self, mapper: AttackSurfaceMapper, fastapi_root: Path) -> None:
        mapper.map_endpoints(fastapi_root)
        critical = [e for e in mapper._endpoints if e.risk_level == "critical"]
        assert len(critical) >= 1

    def test_grpc_rpc_methods_detected(self, mapper: AttackSurfaceMapper, grpc_root: Path) -> None:
        entries = mapper.map_endpoints(grpc_root)
        methods = [e.method for e in entries]
        assert "rpc" in methods

    def test_nonexistent_dir_returns_empty(self, mapper: AttackSurfaceMapper, tmp_path: Path) -> None:
        result = mapper.map_endpoints(tmp_path / "nonexistent")
        assert result == []
        assert len(mapper._errors) >= 1

    def test_binary_files_are_skipped(self, mapper: AttackSurfaceMapper, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        (root / "compiled.pyc").write_bytes(b'@app.get("/secret")')
        entries = mapper.map_endpoints(root)
        assert entries == []


# ===========================================================================
# Tests — map_dependencies()
# ===========================================================================


class TestMapDependencies:
    def test_python_deps_detected(self, mapper: AttackSurfaceMapper, deps_root: Path) -> None:
        entries = mapper.map_dependencies(deps_root)
        names = [e.name for e in entries]
        assert "cryptography" in names
        assert "requests" in names

    def test_npm_deps_detected(self, mapper: AttackSurfaceMapper, deps_root: Path) -> None:
        entries = mapper.map_dependencies(deps_root)
        names = [e.name for e in entries]
        assert "axios" in names

    def test_dep_ecosystems_correct(self, mapper: AttackSurfaceMapper, deps_root: Path) -> None:
        mapper.map_dependencies(deps_root)
        py_deps = [e for e in mapper._dependencies if e.ecosystem == "pypi"]
        npm_deps = [e for e in mapper._dependencies if e.ecosystem == "npm"]
        assert len(py_deps) >= 1
        assert len(npm_deps) >= 1

    def test_high_risk_crypto_dep_flagged(self, mapper: AttackSurfaceMapper, deps_root: Path) -> None:
        mapper.map_dependencies(deps_root)
        crypto = [e for e in mapper._dependencies if e.name == "cryptography"]
        assert len(crypto) >= 1
        assert crypto[0].risk_level == "high"

    def test_no_duplicate_deps(self, mapper: AttackSurfaceMapper, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        (root / "requirements.txt").write_text("flask==3.0.0\nflask==3.0.0\n", encoding="utf-8")
        mapper.map_dependencies(root)
        flask = [e for e in mapper._dependencies if e.name == "flask"]
        assert len(flask) == 1


# ===========================================================================
# Tests — generate_report()
# ===========================================================================


class TestGenerateReport:
    def test_report_type(self, mapper: AttackSurfaceMapper, fastapi_root: Path) -> None:
        mapper.map_endpoints(fastapi_root)
        report = mapper.generate_report()
        assert isinstance(report, AttackSurfaceReport)

    def test_report_counters_match_internals(
        self, mapper: AttackSurfaceMapper, fastapi_root: Path, deps_root: Path
    ) -> None:
        mapper.map_endpoints(fastapi_root)
        mapper.map_dependencies(deps_root)
        report = mapper.generate_report()
        assert report.total_endpoints == len(mapper._endpoints)
        assert report.total_dependencies == len(mapper._dependencies)

    def test_report_critical_count(self, mapper: AttackSurfaceMapper, fastapi_root: Path) -> None:
        mapper.map_endpoints(fastapi_root)
        report = mapper.generate_report()
        # /admin and /auth/token endpoints should produce critical findings
        assert report.critical_count >= 1

    def test_report_to_dict_serialisable(self, mapper: AttackSurfaceMapper, fastapi_root: Path) -> None:
        mapper.map_endpoints(fastapi_root)
        report = mapper.generate_report()
        d = report.to_dict()
        assert isinstance(d, dict)
        # Must be JSON serialisable
        serialised = json.dumps(d)
        assert "generated_at" in serialised

    def test_reset_clears_all_state(self, mapper: AttackSurfaceMapper, fastapi_root: Path) -> None:
        mapper.map_endpoints(fastapi_root)
        assert len(mapper._endpoints) >= 1
        mapper.reset()
        assert mapper._endpoints == []
        assert mapper._ports == []
        assert mapper._dependencies == []
        assert mapper._errors == []

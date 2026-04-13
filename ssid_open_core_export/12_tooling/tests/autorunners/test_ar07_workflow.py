from pathlib import Path

import yaml

WF_PATH = Path(".github/workflows/forbidden_extensions.yml")


def test_workflow_file_exists():
    assert WF_PATH.exists()


def test_workflow_yaml_valid():
    wf = yaml.safe_load(WF_PATH.read_text())
    assert wf is not None


def test_workflow_triggers_on_push_and_pr():
    wf = yaml.safe_load(WF_PATH.read_text())
    assert "push" in wf["on"]
    assert "pull_request" in wf["on"]


def test_workflow_calls_forbidden_ext_script():
    content = WF_PATH.read_text()
    assert "forbidden_ext_check.py" in content


def test_workflow_fails_on_violation():
    content = WF_PATH.read_text()
    assert "continue-on-error: false" not in content

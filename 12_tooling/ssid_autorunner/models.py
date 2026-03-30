from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re

VALID_AR_IDS = {f"AR-{i:02d}" for i in range(1, 11)}

class StatusCode(str, Enum):
    PASS = "PASS"
    FAIL_POLICY = "FAIL_POLICY"
    FAIL_SOT = "FAIL_SOT"
    FAIL_QA = "FAIL_QA"
    FAIL_DUPLICATE = "FAIL_DUPLICATE"
    FAIL_SCOPE = "FAIL_SCOPE"
    FAIL_FORBIDDEN = "FAIL_FORBIDDEN"
    FAIL_FRESHNESS = "FAIL_FRESHNESS"
    FAIL_DORA = "FAIL_DORA"
    FAIL_SHARD = "FAIL_SHARD"
    ERROR = "ERROR"

class ScopeLock(BaseModel):
    allowed_paths: List[str] = Field(default_factory=list)
    forbidden_paths: List[str] = Field(default_factory=list)

class AgentTask(BaseModel):
    agent_id: str
    model: str = Field(pattern="^(opus|sonnet|haiku)$")
    max_tokens: int = 4096

class AutoRunnerPayload(BaseModel):
    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    autorunner_id: str
    trigger: str = Field(pattern="^(push|cron|pr|manual)$")
    repo: str
    branch: str = "main"
    commit_sha: str
    scope_lock: ScopeLock = Field(default_factory=ScopeLock)
    agent_task: Optional[AgentTask] = None
    opa_input_path: Optional[str] = None
    context: dict = Field(default_factory=dict)

    @field_validator("autorunner_id")
    @classmethod
    def validate_ar_id(cls, v):
        if v not in VALID_AR_IDS:
            raise ValueError(f"autorunner_id must be one of {VALID_AR_IDS}")
        return v

    @field_validator("commit_sha")
    @classmethod
    def validate_sha(cls, v):
        if not re.match(r"^[0-9a-f]{40}$", v):
            raise ValueError("commit_sha must be 40-char lowercase hex")
        return v

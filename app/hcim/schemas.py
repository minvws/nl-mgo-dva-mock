from enum import Enum
from typing import List

from pydantic import BaseModel


class Severity(str, Enum):
    ERROR = "error"


class Code(str, Enum):
    NOT_FOUND = "not-found"
    NOT_SUPPORTED = "not-supported"


class OperationOutcomeIssue(BaseModel):
    severity: Severity
    code: Code
    diagnostics: str


class OperationOutcome(BaseModel):
    resourceType: str = "OperationOutcome"
    issue: List[OperationOutcomeIssue]

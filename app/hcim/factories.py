from .schemas import Code, OperationOutcome, OperationOutcomeIssue, Severity


class OperationOutcomeFactory:
    @staticmethod
    def with_issue(
        severity: Severity, code: Code, diagnostics: str
    ) -> OperationOutcome:
        return OperationOutcome(
            issue=[
                OperationOutcomeIssue(
                    severity=severity, code=code, diagnostics=diagnostics
                ),
            ],
        )

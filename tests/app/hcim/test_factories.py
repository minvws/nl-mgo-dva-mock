from faker import Faker

from app.hcim.factories import OperationOutcomeFactory
from app.hcim.schemas import Code, OperationOutcome, Severity


class TestOperationOutcomeFactory:
    def test_with_issue(self, faker: Faker) -> None:
        severity: Severity = faker.random_element(Severity)

        code: Code = faker.random_element(Code)
        diagnostics: str = faker.sentence()

        operation_outcome = OperationOutcomeFactory.with_issue(
            severity=severity, code=code, diagnostics=diagnostics
        )

        assert isinstance(operation_outcome, OperationOutcome)
        assert len(operation_outcome.issue) == 1

        operation_outcome_issue = operation_outcome.issue[0]
        assert operation_outcome_issue.severity is severity
        assert operation_outcome_issue.code is code
        assert operation_outcome_issue.diagnostics == diagnostics

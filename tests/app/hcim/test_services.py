import pytest

from app.hcim.services import FhirVersionAcceptHeaderMatcher


class TestFhirVersionAcceptHeaderMatcher:
    def setup_method(self) -> None:
        self.matcher = FhirVersionAcceptHeaderMatcher()

    @pytest.mark.parametrize(
        "header, expected_version, expected_result",
        [
            # Valid MIME types with correct fhirVersion parameter
            ("application/fhir+json; fhirVersion=4.0", "4.0", True),
            ("application/json+fhir; fhirVersion=4.0", "4.0", True),
            # Valid MIME types with incorrect fhirVersion parameter
            ("application/fhir+json; fhirVersion=4.0", "3.0", False),
            ("application/json+fhir; fhirVersion=4.0", "3.0", False),
            # Invalid MIME types
            ("application/fhir+xml; fhirVersion=4.0", "4.0", False),
            ("application/xml+fhir; fhirVersion=4.0", "4.0", False),
            ("text/plain; fhirVersion=4.0", "4.0", False),
            # Missing fhirVersion parameter
            ("application/fhir+json; someOtherParam=4.0", "4.0", False),
            ("application/json+fhir; someOtherParam=4.0", "4.0", False),
        ],
    )
    def test_fhir_version_matches(
        self, header: str, expected_version: str, expected_result: bool
    ) -> None:
        assert (
            self.matcher.fhir_version_matches(header, expected_version)
            == expected_result
        )

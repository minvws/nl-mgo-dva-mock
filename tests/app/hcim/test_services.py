import pytest

from app.hcim.matchers import FhirVersionAcceptHeaderMatcher


class TestFhirVersionAcceptHeaderMatcher:
    def setup_method(self) -> None:
        self.matcher = FhirVersionAcceptHeaderMatcher()

    @pytest.mark.parametrize(
        "header, expected_version, expected_result",
        [
            ("application/fhir+json; fhirVersion=4.0", "4.0", True),
            ("application/json+fhir; fhirVersion=4.0", "4.0", True),
            ("application/fhir+json; fhirVersion=4.0", "3.0", False),
            ("application/json+fhir; fhirVersion=4.0", "3.0", False),
            ("application/fhir+xml; fhirVersion=4.0", "4.0", False),
            ("application/xml+fhir; fhirVersion=4.0", "4.0", False),
            ("text/plain; fhirVersion=4.0", "4.0", False),
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

    def test_fhir_version_matches_with_none_header(self) -> None:
        """Test that None header returns False."""
        assert self.matcher.fhir_version_matches(None, "4.0") is False

    def test_fhir_version_matches_with_three_part_version(self) -> None:
        """Test matching with three-part version numbers."""
        assert (
            self.matcher.fhir_version_matches(
                "application/fhir+json; fhirVersion=4.0.1", "4.0.1"
            )
            is True
        )

    def test_fhir_version_matches_with_whitespace_in_header(self) -> None:
        """Test matching with whitespace around the fhirVersion parameter."""
        assert (
            self.matcher.fhir_version_matches(
                "application/fhir+json; fhirVersion = 4.0", "4.0"
            )
            is False
        )

    def test_fhir_version_matches_with_charset(self) -> None:
        """Test matching with charset parameter."""
        assert (
            self.matcher.fhir_version_matches(
                "application/fhir+json; charset=utf-8; fhirVersion=4.0", "4.0"
            )
            is True
        )

    def test_fhir_version_matches_legacy_format_with_version_3(self) -> None:
        """Test legacy format with version 3.0."""
        assert (
            self.matcher.fhir_version_matches(
                "application/json+fhir; fhirVersion=3.0", "3.0"
            )
            is True
        )

    def test_fhir_version_matches_case_sensitive_mime_type(self) -> None:
        """Test that MIME type matching is case-sensitive."""
        assert (
            self.matcher.fhir_version_matches(
                "Application/Fhir+Json; fhirVersion=4.0", "4.0"
            )
            is False
        )

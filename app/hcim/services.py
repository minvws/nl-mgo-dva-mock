import re


class FhirVersionAcceptHeaderMatcher:
    def fhir_version_matches(
        self, header_from_request: str, expected_version: str
    ) -> bool:
        """
        Check if the FHIR version in the request header matches what we expect.

        According to the FHIR spec, we support the following MIME types:
        - Primary format (FHIR STU3 onwards): 'application/fhir+json; fhirVersion=X.X'
        - Legacy format (DSTU2 to STU3): 'application/json+fhir; fhirVersion=X.X'

        Args:
            header_from_request: The Accept header from the request
            expected_version: The version we're checking against

        Returns:
            True if versions match, False otherwise
        """
        accepted_mime_types = [
            "application/fhir+json",  # Current official MIME type (STU3+)
            "application/json+fhir",  # Legacy MIME type (DSTU2-STU3)
        ]

        if not any(
            header_from_request.startswith(mime_type)
            for mime_type in accepted_mime_types
        ):
            return False

        pattern = re.compile(r"fhirVersion=(\d+\.\d+(?:\.\d+)?)")
        match = pattern.search(header_from_request)

        if not match:
            return False

        return match.group(1) == expected_version

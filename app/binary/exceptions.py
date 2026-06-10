class BinaryError(Exception):
    """Base exception for binary domain errors."""


class BinaryResourceNotFoundError(BinaryError):
    """Raised when a binary resource file cannot be found."""


class BinaryInvalidResourceError(BinaryError):
    """Raised when a binary resource is malformed for the requested representation."""


class InvalidBinaryPayloadError(BinaryInvalidResourceError):
    """Raised when a Binary payload field is present but not base64 string content."""

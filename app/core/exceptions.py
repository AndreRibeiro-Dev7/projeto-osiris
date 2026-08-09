"""Application exceptions independent from HTTP transport."""


class ResourceNotFoundError(Exception):
    """Raised when a requested domain resource does not exist."""


class DuplicateResourceError(Exception):
    """Raised when a unique business rule would be violated."""

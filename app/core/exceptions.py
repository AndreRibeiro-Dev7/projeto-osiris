"""Application exceptions independent from HTTP transport."""


class ResourceNotFoundError(Exception):
    """Raised when a requested domain resource does not exist."""


class DuplicateResourceError(Exception):
    """Raised when a unique business rule would be violated."""


class SchedulingConflictError(Exception):
    """Raised when a barber already has an overlapping appointment."""


class InvalidSchedulingReferenceError(Exception):
    """Raised when an appointment references a resource from another business."""


class InactiveBarberError(Exception):
    """Raised when attempting to schedule time with an inactive barber."""

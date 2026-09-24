"""Application exceptions independent from HTTP transport."""


class ResourceNotFoundError(Exception):
    """Raised when a requested domain resource does not exist."""


class DuplicateResourceError(Exception):
    """Raised when a unique business rule would be violated."""


class InvalidCredentialsError(Exception):
    """Raised when a sensitive action receives an incorrect current password."""


class SchedulingConflictError(Exception):
    """Raised when a barber already has an overlapping appointment."""


class InvalidSchedulingReferenceError(Exception):
    """Raised when an appointment references a resource from another business."""


class InactiveBarberError(Exception):
    """Raised when attempting to schedule time with an inactive barber."""


class InvalidAppointmentStatusTransitionError(Exception):
    """Raised when an appointment cannot transition to the requested status."""


class LoyaltyRewardUnavailableError(Exception):
    """Raised when a customer has no loyalty reward available to redeem."""


class MissingAIConfigurationError(Exception):
    """Raised when the AI provider is not configured for runtime use."""


class AIProviderError(Exception):
    """Raised when the configured AI provider cannot generate a response."""

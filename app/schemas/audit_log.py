"""Activity history API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_email: str
    actor_role: str
    actor_is_primary_owner: bool
    area: str
    description: str
    created_at: datetime

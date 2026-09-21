from datetime import date
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class BusinessClosureCreate(BaseModel):
    closure_date: date
    reason: str = Field(min_length=2, max_length=200)
class BusinessClosureResponse(BusinessClosureCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID

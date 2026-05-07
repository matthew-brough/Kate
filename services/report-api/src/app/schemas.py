import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ReportStatus


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    status: ReportStatus
    result: str | None
    created_at: datetime
    updated_at: datetime

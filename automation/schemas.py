from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl


class TaskRead(BaseModel):
    id: int
    issue_number: int
    issue_title: str
    issue_body: Optional[str]
    issue_url: Optional[HttpUrl]
    issue_repo: str
    status: str
    devin_session_id: Optional[str]
    devin_session_url: Optional[HttpUrl]
    pr_url: Optional[HttpUrl]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        orm_mode = True

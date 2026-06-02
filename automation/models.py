from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime
from automation.db import Base


class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    issue_number = Column(Integer, nullable=False, index=True)
    issue_title = Column(String(512), nullable=False)
    issue_body = Column(Text, nullable=True)
    issue_url = Column(String(1024), nullable=True)
    issue_repo = Column(String(256), nullable=False)

    status = Column(String(32), default=TaskStatus.queued.value, nullable=False)
    devin_session_id = Column(String(128), nullable=True)
    devin_session_url = Column(String(1024), nullable=True)
    pr_url = Column(String(1024), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

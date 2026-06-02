import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from automation.config import settings

logger = logging.getLogger("automation.db")
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    logger.info("Initializing database and ensuring tables exist")
    from automation.models import Task

    Base.metadata.create_all(bind=engine)

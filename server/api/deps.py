from collections.abc import Generator

from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    from planner_core.database.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

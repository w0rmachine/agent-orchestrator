"""Database engine and session management."""
from collections.abc import Generator
from sqlmodel import Session, create_engine

from backend.config import settings

# Create engine with connection pooling
engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)


def get_session() -> Generator[Session, None, None]:
    """Get database session."""
    with Session(engine) as session:
        yield session

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from . import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,      # test connections before checkout (catches stale connections)
    pool_recycle=1800,       # recycle connections after 30 min to avoid server-side timeouts
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

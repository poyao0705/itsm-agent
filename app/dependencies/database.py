# db injectino script
from sqlmodel import Session
from app.db.database import engine

def get_db():
    with Session(engine) as session:
        yield session
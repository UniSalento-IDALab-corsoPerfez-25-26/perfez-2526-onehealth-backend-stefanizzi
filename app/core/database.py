"""Connessione configurata dall'ambiente locale, senza credenziali nei sorgenti."""
from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,sessionmaker

load_dotenv(Path(__file__).resolve().parents[2]/'.env',override=False)
DATABASE_URL=os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('Impostare DATABASE_URL nell’ambiente o nel file .env della radice del progetto. Consultare .env.example.')
engine=create_engine(DATABASE_URL,echo=False,pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
class Base(DeclarativeBase):
    pass

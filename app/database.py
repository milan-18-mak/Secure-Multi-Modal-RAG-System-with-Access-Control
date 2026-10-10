"""SQLite persistence for identities, source records, and retrievable chunks."""
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from passlib.context import CryptContext
from app.models import User, UserCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DATABASE_PATH = os.getenv("DATABASE_URL", "sqlite:///data/app.db").replace("sqlite:///", "")

@contextmanager
def get_db_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH); conn.row_factory = sqlite3.Row
    try:
        yield conn; conn.commit()
    finally: conn.close()

def get_db_path() -> str: return DATABASE_PATH

def init_db() -> None:
    with get_db_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, department TEXT NOT NULL, salary INTEGER NOT NULL, email TEXT NOT NULL, access_group TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY AUTOINCREMENT, source_key TEXT UNIQUE NOT NULL, source_name TEXT NOT NULL, source_type TEXT NOT NULL, access_groups TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, source_key TEXT NOT NULL REFERENCES sources(source_key), content TEXT NOT NULL, embedding_json TEXT NOT NULL, page INTEGER, row_id TEXT, modality TEXT NOT NULL, chunk_ordinal INTEGER NOT NULL, checksum TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chunk_access (chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE, access_group TEXT NOT NULL, PRIMARY KEY (chunk_id, access_group));
        CREATE INDEX IF NOT EXISTS idx_chunk_access_group ON chunk_access(access_group, chunk_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_key);
        """)

def verify_password(plain_password: str, hashed_password: str) -> bool: return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password: str) -> str: return pwd_context.hash(password)

def create_user(user: UserCreate) -> User:
    hashed = get_password_hash(user.password)
    with get_db_connection() as conn:
        cur = conn.execute("INSERT INTO users(username, hashed_password, role) VALUES (?, ?, ?)", (user.username, hashed, user.role))
        return User(id=cur.lastrowid, username=user.username, role=user.role, hashed_password=hashed)

def get_user_by_username(username: str) -> Optional[User]:
    with get_db_connection() as conn: row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return User(**dict(row)) if row else None

def authenticate_user(username: str, password: str) -> Optional[User]:
    user = get_user_by_username(username)
    return user if user and verify_password(password, user.hashed_password) else None

def seed_employees() -> None:
    users = [("admin", "admin123", "admin"), ("hr", "hr123", "hr"), ("engineering", "engineering123", "engineering"), ("finance", "finance123", "finance")]
    employees = [("E101", "Amit", "HR", 45000, "amit@company.com", "hr"), ("E102", "Rahul", "Engineering", 65000, "rahul@company.com", "engineering"), ("E103", "Neha", "Finance", 70000, "neha@company.com", "finance")]
    with get_db_connection() as conn:
        for username, password, role in users:
            if not conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone(): conn.execute("INSERT INTO users(username,hashed_password,role) VALUES (?, ?, ?)", (username, get_password_hash(password), role))
        conn.executemany("INSERT OR IGNORE INTO employees(employee_id,name,department,salary,email,access_group) VALUES (?, ?, ?, ?, ?, ?)", employees)

def employee_rows() -> List[Dict[str, Any]]:
    with get_db_connection() as conn: return [dict(r) for r in conn.execute("SELECT * FROM employees ORDER BY employee_id")]

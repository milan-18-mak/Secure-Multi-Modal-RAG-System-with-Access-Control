from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class User(BaseModel):
    id: int
    username: str
    role: str
    hashed_password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    username: str
    role: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None


class ChatRequest(BaseModel):
    message: str


class Citation(BaseModel):
    source: str
    page: Optional[int] = None
    source_type: Optional[str] = None
    row_id: Optional[str] = None


class RetrievedSource(BaseModel):
    source: str
    source_type: str
    page: Optional[int] = None
    row_id: Optional[str] = None
    access_groups: List[str]


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    retrieved_sources: List[RetrievedSource]


class IngestRequest(BaseModel):
    source_type: str
    source_path: Optional[str] = None
    access_groups: List[str]


class SourceInfo(BaseModel):
    source: str
    source_type: str
    access_groups: List[str]
    chunk_count: int


class SecureSearchResult(BaseModel):
    text: str
    metadata: dict
    distance: float
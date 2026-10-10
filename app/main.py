from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List
import os

from app.database import init_db, seed_employees, authenticate_user
from app.auth import create_access_token, verify_token, TokenData
from app.models import Token, ChatRequest, ChatResponse, SourceInfo, UserLogin
from app.generation import generate_answer
from app.ingestion import get_all_sources, run_full_ingestion
from app.authorization import get_allowed_access_groups

app = FastAPI(title="Secure Multi-Modal RAG Chatbot", version="2.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

@app.on_event("startup")
async def startup_event():
    init_db()
    seed_employees()
    run_full_ingestion()


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception
    return token_data


async def get_current_user_optional(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        return await get_current_user(token)
    except HTTPException:
        return None


@app.post("/api/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"user_id": user.id, "username": user.username, "role": user.role}
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        role=user.role
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: TokenData = Depends(get_current_user)):
    response = await generate_answer(request.message, current_user.role)
    return response


@app.post("/api/ingest")
async def ingest_data(current_user: TokenData = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can trigger ingestion")
    
    total_chunks = run_full_ingestion()
    return {"message": f"Ingestion complete. Total chunks: {total_chunks}"}


@app.get("/api/sources", response_model=List[SourceInfo])
async def get_sources(current_user: TokenData = Depends(get_current_user)):
    sources = get_all_sources()
    allowed_groups = get_allowed_access_groups(current_user.role)
    
    filtered_sources = []
    for source in sources:
        if any(group in allowed_groups for group in source.get("access_groups", [])):
            filtered_sources.append(SourceInfo(
                source=source["source"],
                source_type=source["source_type"],
                access_groups=source["access_groups"],
                chunk_count=source["chunk_count"]
            ))
    
    return filtered_sources


@app.get("/api/user/me")
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    allowed_groups = get_allowed_access_groups(current_user.role)
    all_groups = ["admin", "hr", "engineering", "finance"]
    blocked_groups = [g for g in all_groups if g not in allowed_groups]
    
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
        "allowed_groups": allowed_groups,
        "blocked_groups": blocked_groups
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

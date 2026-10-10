"""Grounded Gemini generation with citation allow-list validation."""
import os
import re
from typing import Dict, List
from app.citations import format_citation
from app.models import ChatResponse, RetrievedSource
from app.retrieval import build_context, build_inline_citation, format_retrieved_sources, secure_search
from app.ingestion import gemini_configured

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
REFUSAL = "I could not find sufficient authorized information."
SYSTEM_PROMPT = """You are a secure retrieval assistant. Answer ONLY from AUTHORIZED CONTEXT.
Write a helpful, direct, conversational answer in one to three short sentences—like a polished AI chatbot, not a document dump. Every factual sentence must end with one exact source citation copied from the context.
Never invent facts, citations, sources, or access information. If context cannot answer, reply exactly:
I could not find sufficient authorized information."""

def _allowed_citations(chunks: List[Dict]) -> set[str]: return {build_inline_citation(chunk["metadata"]) for chunk in chunks}
def _answer_with_gemini(query: str, context: str) -> str:
    if not gemini_configured(): return ""
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        gemini_model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)
        response = gemini_model.generate_content(f"AUTHORIZED CONTEXT:\n{context}\n\nQUESTION: {query}", generation_config={"temperature": 0.0, "max_output_tokens": 700})
        return response.text.strip()
    except Exception: return ""

def _valid_answer(answer: str, allowed: set[str]) -> bool:
    citations = set(re.findall(r"\[Source:[^\]]+\]", answer))
    return bool(citations) and citations.issubset(allowed)

def _context_covers(query: str, chunks: List[Dict]) -> bool:
    """Reject semantic near-matches when a requested entity/fact is not in evidence."""
    stop = {"what", "who", "when", "where", "why", "how", "quickly", "time", "is", "the", "a", "an", "of", "for", "to", "in", "on", "and", "does", "do", "are", "please", "tell", "me"}
    def stem(word: str) -> str:
        word = word.lower()
        for suffix in ("gement", "ments", "ment", "ities", "ity", "ized", "ised", "ing", "ed", "es", "s", "ly"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[:-len(suffix)]
                break
        return word.rstrip("e")
    terms = [stem(word) for word in re.findall(r"[A-Za-z0-9]+", query) if word.lower() not in stop]
    evidence_words = [stem(word) for word in re.findall(r"[A-Za-z0-9]+", " ".join(chunk["text"] for chunk in chunks))]
    def matches(term: str, item: str) -> bool:
        if term == item:
            return True
        # Partial matching is only for meaningful stems such as
        # acknowledgement/acknowledged, never one-letter filler words.
        return len(term) >= 4 and len(item) >= 4 and (term in item or item in term)
    return bool(terms) and all(any(matches(term, item) for item in evidence_words) for term in terms)

def _extractive_fallback(query: str, chunks: List[Dict]) -> str:
    """Short, readable grounded answer if the Gemini request is unavailable."""
    ignored = {"what", "who", "when", "where", "why", "how", "is", "the", "a", "an", "of", "for", "to", "in", "on", "and", "does", "do", "are"}
    terms = {word.lower() for word in re.findall(r"[A-Za-z0-9]+", query) if word.lower() not in ignored}
    candidates = []
    for chunk in chunks:
        # Line boundaries preserve clean database fields; sentence boundaries
        # produce compact PDF/OCR answers.
        for part in re.split(r"[\n.!?]+", chunk["text"]):
            text = part.strip()
            if text:
                score = sum(term in text.lower() for term in terms)
                candidates.append((score, text, chunk["metadata"]))
    _, text, metadata = max(candidates, key=lambda item: item[0])
    return f"{text}. {build_inline_citation(metadata)}"

async def generate_answer(query: str, user_role: str) -> ChatResponse:
    chunks = secure_search(query, user_role, n_results=5)
    if not chunks or not _context_covers(query, chunks): return ChatResponse(answer=REFUSAL, citations=[], retrieved_sources=[])
    context, allowed = build_context(chunks), _allowed_citations(chunks)
    answer = _answer_with_gemini(query, context)
    if not _valid_answer(answer, allowed): answer = _extractive_fallback(query, chunks)
    sources = format_retrieved_sources(chunks)
    citations = [format_citation(chunk["metadata"]) for chunk in chunks if build_inline_citation(chunk["metadata"]) in answer]
    unique = {(c.source,c.page,c.row_id): c for c in citations}
    return ChatResponse(answer=answer, citations=list(unique.values()), retrieved_sources=[RetrievedSource(**source) for source in sources])

def generate_answer_sync(query: str, user_role: str) -> ChatResponse:
    import asyncio
    return asyncio.run(generate_answer(query, user_role))

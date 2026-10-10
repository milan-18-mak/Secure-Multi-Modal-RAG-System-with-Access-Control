import re
from typing import List, Dict, Optional
from app.models import Citation, RetrievedSource


def format_citation(metadata: dict) -> Citation:
    source = metadata.get("source", "Unknown")
    source_type = metadata.get("source_type", "unknown")
    page = metadata.get("page")
    row_id = metadata.get("row_id")
    
    return Citation(
        source=source,
        page=page,
        source_type=source_type,
        row_id=row_id
    )


def extract_citations_from_response(response: str) -> List[Citation]:
    citations = []
    pattern = r'\[Source:\s*([^,\]]+)(?:,\s*Page\s*(\d+))?(?:,\s*Row\s*([^\]]+))?\]'
    matches = re.findall(pattern, response)
    
    for match in matches:
        source = match[0].strip()
        page = int(match[1]) if match[1] else None
        row_id = match[2].strip() if match[2] else None
        citations.append(Citation(source=source, page=page, row_id=row_id))
    
    return citations


def validate_citations(response: str, retrieved_sources: List[RetrievedSource]) -> bool:
    response_citations = extract_citations_from_response(response)
    
    if not response_citations:
        return True
    
    available_sources = set()
    for src in retrieved_sources:
        key = (src.source, src.page, src.row_id)
        available_sources.add(key)
    
    for citation in response_citations:
        key = (citation.source, citation.page, citation.row_id)
        if key not in available_sources:
            return False
    
    return True


def build_citation_string(metadata: dict) -> str:
    source = metadata.get("source", "Unknown")
    source_type = metadata.get("source_type", "unknown")
    page = metadata.get("page")
    row_id = metadata.get("row_id")
    
    if source_type == "pdf":
        return f"[Source: {source}, Page {page}]"
    elif source_type == "image":
        return f"[Source: {source}, Page {page}]"
    elif source_type == "database":
        return f"[Source: {source} database, Row {row_id}]"
    else:
        return f"[Source: {source}]"


def format_retrieved_sources(retrieved_chunks: List[dict]) -> List[RetrievedSource]:
    sources = []
    seen = set()
    
    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "Unknown")
        source_type = metadata.get("source_type", "unknown")
        page = metadata.get("page")
        row_id = metadata.get("row_id")
        access_groups = metadata.get("access_groups", [])
        
        key = (source, source_type, page, row_id)
        if key not in seen:
            seen.add(key)
            sources.append(RetrievedSource(
                source=source,
                source_type=source_type,
                page=page,
                row_id=row_id,
                access_groups=access_groups if isinstance(access_groups, list) else []
            ))
    
    return sources
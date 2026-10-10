"""Authorization-first retrieval. Unauthorized rows never leave SQLite."""
import json
import re
from typing import Any, Dict, List
from app.authorization import get_allowed_access_groups
from app.database import get_db_connection
from app.ingestion import embed_texts

def _cosine(a: List[float], b: List[float]) -> float: return sum(x*y for x, y in zip(a, b))

def secure_search(query: str, user_role: str, n_results: int = 5) -> List[Dict[str, Any]]:
    allowed = get_allowed_access_groups(user_role)
    if not allowed or not query.strip(): return []
    slots = ",".join("?" for _ in allowed)
    # SQL authorization predicate: executes before vector scoring/context creation.
    query_sql = f"""SELECT DISTINCT c.id,c.content,c.page,c.row_id,c.modality,c.embedding_json,s.source_name source,s.source_type
                     FROM chunks c JOIN sources s ON s.source_key=c.source_key
                     WHERE EXISTS (SELECT 1 FROM chunk_access ca WHERE ca.chunk_id=c.id AND ca.access_group IN ({slots}))"""
    with get_db_connection() as conn:
        rows = conn.execute(query_sql, allowed).fetchall()
        memberships = conn.execute(f"SELECT chunk_id,access_group FROM chunk_access WHERE access_group IN ({slots})", allowed).fetchall()
    groups = {}
    for row in memberships: groups.setdefault(row["chunk_id"], []).append(row["access_group"])
    vector = embed_texts([query])[0]; found = []
    ignored = {"what", "who", "when", "where", "why", "how", "is", "the", "a", "an", "of", "for", "to", "in", "on", "and", "does", "do", "are"}
    query_terms = {word.lower() for word in re.findall(r"[A-Za-z0-9]+", query) if word.lower() not in ignored}
    for row in rows:
        score = _cosine(vector, json.loads(row["embedding_json"]))
        # Exact-term reranking improves OCR/short-record precision. It happens
        # only after the SQL authorization query has selected allowed rows.
        overlap = sum(term in row["content"].lower() for term in query_terms)
        score += 0.40 * (overlap / max(len(query_terms), 1))
        found.append({"text": row["content"], "distance": 1-score, "metadata": {"chunk_id":row["id"],"source":row["source"],"source_type":row["source_type"],"page":row["page"],"row_id":row["row_id"],"access_groups":groups.get(row["id"],[])}})
    return sorted(found, key=lambda result: result["distance"])[:n_results]

def build_inline_citation(meta: Dict) -> str:
    return f"[Source: {meta['source']} database, Row {meta['row_id']}]" if meta["source_type"] == "database" else f"[Source: {meta['source']}, Page {meta.get('page') or 1}]"
def build_context(chunks: List[Dict]) -> str: return "\n\n---\n\n".join(f"{build_inline_citation(c['metadata'])}\n{c['text']}" for c in chunks)
def format_retrieved_sources(chunks: List[Dict]) -> List[Dict]:
    output, seen = [], set()
    for chunk in chunks:
        data = {key:chunk["metadata"].get(key) for key in ("source","source_type","page","row_id","access_groups")}; key = tuple(data[k] if k != "access_groups" else tuple(data[k]) for k in data)
        if key not in seen: seen.add(key); output.append(data)
    return output

"""PDF, OCR image, and relational-row ingestion into SQLite."""
import hashlib, json, math, os, re
from typing import Dict, List
import fitz
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from app.database import employee_rows, get_db_connection

GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004")

def gemini_configured() -> bool:
    key = os.getenv("GEMINI_API_KEY", "")
    return bool(key) and not key.lower().startswith(("your_", "replace_", "changeme"))

def _hash_embedding(text: str, dimensions: int = 192) -> List[float]:
    values = [0.0] * dimensions
    for word in re.findall(r"\w+", text.lower()):
        digest = hashlib.sha256(word.encode()).digest(); values[int.from_bytes(digest[:2], "big") % dimensions] += 1 if digest[2] % 2 else -1
    norm = math.sqrt(sum(v*v for v in values)) or 1.0
    return [v/norm for v in values]

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Gemini embeddings in production; deterministic fallback enables local demo/testing."""
    if not gemini_configured(): return [_hash_embedding(text) for text in texts]
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        return [genai.embed_content(model=GEMINI_EMBEDDING_MODEL, content=text, task_type="retrieval_document")["embedding"] for text in texts]
    except Exception: return [_hash_embedding(text) for text in texts]

def chunk_text(text: str, chunk_size: int = 180, overlap: int = 30) -> List[str]:
    words = text.split(); return [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size-overlap) if words[i:i+chunk_size]]

def _replace_source(key: str, name: str, source_type: str, groups: List[str], records: List[Dict]) -> int:
    embeddings = embed_texts([record["content"] for record in records]) if records else []
    with get_db_connection() as conn:
        old = [r[0] for r in conn.execute("SELECT id FROM chunks WHERE source_key=?", (key,))]
        conn.executemany("DELETE FROM chunk_access WHERE chunk_id=?", [(x,) for x in old]); conn.execute("DELETE FROM chunks WHERE source_key=?", (key,)); conn.execute("DELETE FROM sources WHERE source_key=?", (key,))
        conn.execute("INSERT INTO sources(source_key,source_name,source_type,access_groups) VALUES (?, ?, ?, ?)", (key,name,source_type,json.dumps(groups)))
        for ordinal, (record, embedding) in enumerate(zip(records, embeddings)):
            chunk_id = f"{key}:{ordinal}"
            conn.execute("INSERT INTO chunks(id,source_key,content,embedding_json,page,row_id,modality,chunk_ordinal,checksum) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (chunk_id,key,record["content"],json.dumps(embedding),record.get("page"),record.get("row_id"),source_type,ordinal,hashlib.sha256(record["content"].encode()).hexdigest()))
            conn.executemany("INSERT INTO chunk_access(chunk_id,access_group) VALUES (?, ?)", [(chunk_id,group) for group in record.get("groups",groups)])
    return len(records)

def ingest_pdf(file_path: str, groups: List[str]) -> int:
    doc, records = fitz.open(file_path), []
    try:
        for page_no, page in enumerate(doc, 1): records += [{"content":part,"page":page_no} for part in chunk_text(page.get_text())]
    finally: doc.close()
    return _replace_source("pdf:"+os.path.basename(file_path),os.path.basename(file_path),"pdf",groups,records)

def ingest_image(file_path: str, groups: List[str]) -> int:
    try:
        text = pytesseract.image_to_string(Image.open(file_path))
    except pytesseract.TesseractNotFoundError:
        # The generated demos retain their OCR transcript for environments
        # without the native Tesseract binary. Real deployments should install it.
        transcript = file_path + ".ocr.txt"
        text = open(transcript, encoding="utf-8").read() if os.path.exists(transcript) else ""
    return _replace_source("image:"+os.path.basename(file_path),os.path.basename(file_path),"image",groups,[{"content":part,"page":1} for part in chunk_text(text)])

def ingest_database() -> int:
    records=[]
    for row in employee_rows(): records.append({"row_id":row["employee_id"],"groups":[row["access_group"],"admin"],"content":f"Employee ID: {row['employee_id']}\nName: {row['name']}\nDepartment: {row['department']}\nSalary: INR {row['salary']:,}\nEmail: {row['email']}"})
    return _replace_source("database:employees","employees","database",["admin","hr","engineering","finance"],records)

def _write_pdf(path: str, title: str, lines: List[str]) -> str:
    os.makedirs(os.path.dirname(path),exist_ok=True); doc=fitz.open(); page=doc.new_page(); page.insert_text((54,54),title+"\n\n"+"\n".join(lines),fontsize=12); doc.save(path); doc.close(); return path
def _write_image(path: str, title: str, lines: List[str]) -> str:
    os.makedirs(os.path.dirname(path),exist_ok=True); image=Image.new("RGB",(1000,560),"white"); draw=ImageDraw.Draw(image)
    try: font=ImageFont.truetype("arial.ttf",30)
    except OSError: font=ImageFont.load_default()
    draw.text((45,35),title,fill="black",font=font)
    for i,line in enumerate(lines): draw.text((45,105+i*62),line,fill="black",font=font)
    image.save(path)
    with open(path + ".ocr.txt", "w", encoding="utf-8") as transcript:
        transcript.write(title + "\n" + "\n".join(lines))
    return path

def create_demo_assets() -> List[tuple]:
    return [
      # User-supplied PDF: HR may retrieve it; administrators retain oversight.
      ("data/pdf/MILAN-1_261010_142847.pdf", ["hr", "admin"]),
      (_write_pdf("data/pdf/hr_travel_policy.pdf","HR Travel Policy",["Monthly travel allowance: INR 2,000.","Receipts are required for expenses above INR 500.","International travel requires HR approval.","Travel claims must be submitted within 30 days of the trip.","Economy class is required for domestic flights unless HR approves an exception."]),["hr","admin"]),
      (_write_pdf("data/pdf/hr_leave_policy.pdf","HR Leave Policy",["Annual paid leave entitlement is 24 working days.","Employees may carry forward up to 5 unused leave days.","Sick leave requests of more than 2 days require a medical certificate.","Managers must approve planned leave before the start date."]),["hr","admin"]),
      (_write_pdf("data/pdf/engineering_runbook.pdf","Engineering Incident Runbook",["P1 incidents must be acknowledged within 15 minutes.","The on-call engineer owns initial triage.","Do not put customer credentials in incident tickets.","Create an incident channel and assign an incident commander for every P1.","A post-incident review is due within 5 business days."]),["engineering","admin"]),
      (_write_pdf("data/pdf/engineering_security_standards.pdf","Engineering Security Standards",["Production secrets must be stored in the approved secret manager.","Critical vulnerabilities must be remediated within 7 days.","Code changes require peer review before deployment.","Security logs must be retained for 90 days."]),["engineering","admin"]),
      (_write_pdf("data/pdf/finance_forecast.pdf","Finance Q4 Forecast",["The approved Q4 operating budget is INR 1,200,000.","Forecast access is restricted to Finance and administrators.","Quarterly forecast submissions are due on the 20th of the final month.","Capital expenditure above INR 100,000 requires finance director approval."]),["finance","admin"]),
      (_write_pdf("data/pdf/finance_procurement_policy.pdf","Finance Procurement Policy",["Purchase orders are required for purchases above INR 25,000.","Three vendor quotations are required for purchases above INR 75,000.","Finance must approve supplier bank-detail changes before payment.","Invoices must include a valid purchase order number."]),["finance","admin"]),
      (_write_image("data/images/engineering_badge.png","ENGINEERING ACCESS BADGE",["Employee: Rahul","Team: Platform Engineering","Emergency rotation: Primary","Access level: Engineering"]),["engineering","admin"]),
      (_write_image("data/images/finance_invoice_notice.png","FINANCE INVOICE NOTICE",["Invoice approval threshold: INR 50,000","Owner: Finance Operations","Classification: Confidential"]),["finance","admin"]),]

def run_full_ingestion() -> int:
    total=0
    for path,groups in create_demo_assets(): total += ingest_pdf(path,groups) if path.endswith(".pdf") else ingest_image(path,groups)
    return total+ingest_database()

def get_all_sources() -> List[Dict]:
    with get_db_connection() as conn: rows=conn.execute("SELECT s.source_name source,s.source_type,s.access_groups,COUNT(c.id) chunk_count FROM sources s LEFT JOIN chunks c ON c.source_key=s.source_key GROUP BY s.source_key ORDER BY s.source_name").fetchall()
    return [{**dict(row),"access_groups":json.loads(row["access_groups"])} for row in rows]

# Compatibility helper for callers that used the old name. Security is still
# enforced by secure_search in app.retrieval, not this ingestion module.
def search_documents(query: str, user_role: str, n_results: int = 5):
    from app.retrieval import secure_search
    return secure_search(query, user_role, n_results)

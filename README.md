# Secure AI chatbot: multimodal RAG with access control

This is a browser-based AI chatbot. Users authenticate, ask natural-language questions in the chat UI, and Gemini generates an answer from only the documents and database rows they are allowed to retrieve.

## Security model

PDFs, OCR text from images, and SQLite employee records become chunks in a unified SQLite index. Each chunk has its own source location and access-group rows. `secure_search()` applies a parameterized SQLite `EXISTS` access predicate before vectors are scored, before content is returned, and before any context reaches Gemini. This protects both whole documents and individual employee records.

Gemini (`genai.GenerativeModel("gemini-3.8-flash")`) receives only authorized context. Its citations must exactly match a retrieved page or row; otherwise the answer is rejected and replaced by a cited extractive response. Missing evidence produces a refusal rather than a guess.

## Included chat data

- HR travel policy, engineering incident runbook, finance forecast (PDF)
- Engineering badge and finance invoice notice (OCR images)
- Employee SQLite rows with row-level groups

## Run

1. Set `GEMINI_API_KEY` in `.env`.
2. Run `pip install -r requirements.txt`.
3. Run `python run.py` and open `http://localhost:8000`.

Demo accounts: `admin/admin123`, `hr/hr123`, `engineering/engineering123`, `finance/finance123`.

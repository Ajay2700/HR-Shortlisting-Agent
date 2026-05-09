# HR Resume Shortlisting Agent

Production-ready AI shortlisting platform for HR teams.

It combines a modern React UI, a FastAPI backend, and a LangGraph pipeline to parse resumes, score candidates with transparent criteria, and generate recruiter-friendly ranked shortlists.

## Why This Project

- Reduce manual screening time for large applicant pools
- Keep scoring transparent and auditable
- Enable HR override while preserving traceability
- Remain resilient with fallback parsing/scoring when LLM calls fail

## Features


<img width="1908" height="1078" alt="Screenshot 2026-05-09 150035" src="https://github.com/user-attachments/assets/61c4db54-9d9b-4bb9-8cd2-19064cb13645" />
<img width="1909" height="1037" alt="Screenshot 2026-05-09 150143" src="https://github.com/user-attachments/assets/8987a5db-2033-42df-8e87-00dd5789aa15" />


- Parse Job Description from text / TXT / PDF / DOCX
- Parse resumes from PDF/DOCX + LinkedIn profile JSON
- Score each candidate on 5 weighted dimensions
- Rank candidates and generate downloadable HTML report
- Human override endpoint and UI workflow
- Structured API errors (`VALIDATION_ERROR`, `PARSE_ERROR`, `QUOTA_EXCEEDED`, etc.)
- Security layer: input sanitization, PII masking, output validation, audit logging

## Screenshots

### Results Dashboard

![Results Dashboard](assets/screenshots/results-dashboard.png)

### Audit Trail Dashboard

![Audit Trail Dashboard](assets/screenshots/audit-dashboard.png)

## Current Architecture

- `frontend/` — React + Vite premium UI
- `api_server.py` — FastAPI backend REST API
- `agent/` — LangGraph nodes (JD parse → profile extraction → scoring → ranking → report)
- `core/` — LLM service, document parser, embeddings, LinkedIn parser
- `security/` — sanitizer, validator, audit logger
- `models/` — Pydantic schemas

## Tech Stack

- Frontend: React + Vite
- Backend: FastAPI
- Workflow Orchestration: LangGraph
- LLM: OpenAI (`gpt-4o-mini` by default)
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- Parsing: PyMuPDF + python-docx
- Validation: Pydantic
- Security: custom sanitizer + PII masker + validator + audit logger

## API Endpoints

- `GET /health` — health and model status
- `POST /run` — run full pipeline with uploaded files
- `POST /samples/run` — run using bundled sample LinkedIn profiles
- `GET /samples/jd` — fetch sample JD
- `POST /override` — apply HR override to candidate score
- `GET /audit` — fetch session audit logs

## Quick Start

### 1) Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key

### 2) Setup

```bash
cd hr-shortlisting-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

### 3) Configure environment

Copy `.env.example` to `.env` and set:

```env
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4o-mini
```

### 4) Run

Terminal 1 (backend):
```bash
python -m uvicorn api_server:app --reload --port 8000
```

Terminal 2 (frontend):
```bash
cd frontend
npm run dev
```

Open UI at:
- `http://localhost:5173` (or next available port shown by Vite)

## Usage Flow

1. Paste/upload Job Description
2. Upload resumes and/or LinkedIn JSON
3. Run shortlisting pipeline
4. Review ranked candidates and dimension-level scores
5. Apply HR override if needed
6. Download HTML report and audit logs

## Scoring Rubric

Each candidate is evaluated on:

- Skills Match — 30%
- Experience Relevance — 25%
- Education & Certifications — 15%
- Project / Portfolio — 20%
- Communication Quality — 10%

Recommendation thresholds:
- `>= 8.0` → `STRONG HIRE`
- `>= 6.5` → `HIRE`
- `>= 4.5` → `MAYBE`
- `< 4.5` → `NO HIRE`

## Fallback Behavior

If LLM calls fail (quota/rate-limit/network), the system falls back to deterministic parsing/scoring:

- Section-aware resume parsing (`SUMMARY`, `PROJECTS`, `EDUCATION`, etc.)
- Project extraction with technology parsing
- Heuristic rubric scoring

This ensures the pipeline still completes and produces a report.

## Security & Reliability

- Input sanitization against prompt injection
- PII masking before LLM calls
- Schema validation with Pydantic
- Structured API errors for UI clarity
- Audit trail for all critical actions and overrides

## Industry Readiness Highlights

- Clear API contract with machine-readable error codes
- Defensive file validation and parsing guards
- Resume parser hardened for noisy PDF text extraction
- Deterministic fallback scoring path to avoid pipeline outages
- Human override + audit trail for compliance workflows
- Modular architecture suitable for integration into ATS/HRMS systems

## Project Structure

```text
hr-shortlisting-agent/
├── api_server.py
├── app.py
├── config.py
├── requirements.txt
├── frontend/
│   ├── src/
│   └── package.json
├── agent/
├── core/
├── models/
├── security/
├── sample_data/
├── output/
└── logs/
```

## Notes

- `app.py` (Streamlit) is kept as legacy UI; React + FastAPI is the primary path.
- Add `.env` to git ignore and never commit secrets.

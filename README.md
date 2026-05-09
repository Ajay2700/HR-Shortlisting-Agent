# HR Resume Shortlisting Agent

Production-style AI shortlisting pipeline with:
- React dashboard
- FastAPI backend
- LangGraph workflow
- OpenAI scoring + local embeddings
- Heuristic fallbacks when LLM is unavailable
- Audit trail and human score override support

## Features

- Parse Job Description from text / TXT / PDF / DOCX
- Parse resumes from PDF/DOCX + LinkedIn profile JSON
- Score each candidate on 5 weighted dimensions
- Rank candidates and generate downloadable HTML report
- Human override endpoint and UI workflow
- Structured API errors (`VALIDATION_ERROR`, `PARSE_ERROR`, `QUOTA_EXCEEDED`, etc.)
- Security layer: input sanitization, PII masking, output validation, audit logging

## Current Architecture

- `frontend/` — React + Vite premium UI
- `api_server.py` — FastAPI backend REST API
- `agent/` — LangGraph nodes (JD parse → profile extraction → scoring → ranking → report)
- `core/` — LLM service, document parser, embeddings, LinkedIn parser
- `security/` — sanitizer, validator, audit logger
- `models/` — Pydantic schemas

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

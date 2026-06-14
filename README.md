# Ejar Contract Explainer — Week 1 (extraction layer)

Upload a Saudi Ejar tenancy contract (PDF or images, multi-page) and get its structured
data back. Runs a **free local open-source model** for your testing and **Anthropic** in
production — switch with one env var. Stateless: nothing is written to disk or a database,
and document content is never logged.

## Layout
    app/
      models.py                 # Pydantic schema (extraction + insight layers)
      prompts.py                # extraction instructions
      imaging.py                # PDF / images -> page PNGs (PyMuPDF)
      extractors/
        base.py                 # VisionExtractor interface
        ollama_extractor.py     # local, free  (Qwen2.5-VL via Ollama)
        anthropic_extractor.py  # production    (Claude, tool-forced schema)
        factory.py              # picks provider from EXTRACTOR_PROVIDER
      main.py                   # FastAPI: POST /api/extract  (+ serves frontend/)
    frontend/index.html         # bilingual AR/EN, RTL, upload + result view

## Setup
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env

## Run locally with a FREE open-source model (your testing)
1. Install Ollama: https://ollama.com  (needs a GPU or a decent amount of RAM)
2. Pull a vision model good at Arabic documents:
       ollama pull qwen2.5vl
3. In .env:  EXTRACTOR_PROVIDER=ollama
4. Start:
       uvicorn app.main:app --reload
   Open http://localhost:8000  ->  upload a (redacted) contract.

Tip: large multi-page contracts can exceed a small local model's context. If extraction
degrades, lower the page count or render at a lower DPI in imaging.py. The page-by-page
+ merge strategy is a clean week-2 upgrade.

## Switch to Anthropic for production
In .env:
    EXTRACTOR_PROVIDER=anthropic
    ANTHROPIC_API_KEY=sk-ant-...        # set on the host, never commit
    ANTHROPIC_MODEL=claude-sonnet-4-6
No code change — the factory handles it.

## Deploy (free tiers)
- Backend: Dockerize and deploy to Fly.io / Render / Railway. Set the env vars there.
  Minimal Dockerfile:
      FROM python:3.12-slim
      WORKDIR /srv
      COPY requirements.txt . && RUN pip install --no-cache-dir -r requirements.txt
      COPY . .
      CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8080"]
- Frontend is served by FastAPI, so one service ships both. (You can split it to Vercel later.)
- For PDPL: when it serves real documents, host in a Saudi/region cloud and confirm the
  Anthropic data-retention terms before launch.

## Privacy posture (already built in)
- Stateless: no file or extracted PII persisted.
- Prompt instructs the model to null out names / IDs / emails / phones / addresses.
- No document content in logs (only provider + latency).
- Frontend asks the user to redact before upload, and offers a sample to try with no upload.

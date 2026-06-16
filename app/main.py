import logging
import os
import time
from pathlib import Path
from typing import List

from dotenv import load_dotenv
# Load .env from the project root (one level above this file), regardless of CWD.
_DOTENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_DOTENV)

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.extractors.factory import get_extractor
from app.imaging import file_to_page_images
from app.insights import derive_insights
from app.models import ContractAnalysis

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ejar")

app = FastAPI(title="Ejar Contract Explainer")

MAX_PAGES = 12
MAX_BYTES = 25 * 1024 * 1024


@app.on_event("startup")
async def _startup():
    log.info(".env found at %s: %s", _DOTENV, _DOTENV.exists())
    log.info("Active extractor provider: %s", os.getenv("EXTRACTOR_PROVIDER", "ollama"))
    if os.getenv("EXTRACTOR_PROVIDER") == "anthropic":
        log.info("ANTHROPIC_API_KEY set: %s", bool(os.getenv("ANTHROPIC_API_KEY")))


@app.get("/api/health")
async def health():
    return {"ok": True, "provider": os.getenv("EXTRACTOR_PROVIDER", "ollama")}


@app.post("/api/extract")
async def extract(files: List[UploadFile] = File(...)):
    pages: List[bytes] = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "A file is too large.")
        pages.extend(file_to_page_images(f.filename or "upload", data))
    if not pages:
        raise HTTPException(400, "No readable pages found.")
    if len(pages) > MAX_PAGES:
        raise HTTPException(413, f"Too many pages (max {MAX_PAGES}).")

    extractor = get_extractor()
    started = time.time()
    try:
        # Run the (blocking) model call in a worker thread so it never freezes
        # the server's event loop.
        contract = await run_in_threadpool(extractor.extract, pages)
    except Exception as e:
        log.error("extraction failed via %s: %s", extractor.name, type(e).__name__)
        raise HTTPException(502, "Could not read the contract. Try clearer images.")

    log.info("ok via %s in %.1fs over %d page(s)", extractor.name, time.time() - started, len(pages))
    analysis = ContractAnalysis(extracted=contract, insights=derive_insights(contract))
    return JSONResponse(analysis.model_dump(mode="json"))


# Serve the frontend (registered after API routes so /api/* wins).
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

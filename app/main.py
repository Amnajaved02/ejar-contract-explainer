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
# Cap pages sent to the model. Ejar data lives in the first few pages; later
# pages are boilerplate obligations the extractor doesn't use. Bounds latency/cost.
MAX_EXTRACT_PAGES = int(os.getenv("MAX_EXTRACT_PAGES", "5"))

# Safety net: map known Arabic field values to English (the model is also asked to
# output English, but this guarantees the common standard-template values).
AR_EN = {
    "جديد": "New", "تجديد": "Renewal",
    "الرياض": "Riyadh", "جدة": "Jeddah", "جده": "Jeddah", "الدمام": "Dammam",
    "مكة": "Mecca", "مكة المكرمة": "Mecca", "المدينة": "Medina", "المدينة المنورة": "Medina",
    "الخبر": "Khobar", "الطائف": "Taif", "تبوك": "Tabuk", "أبها": "Abha",
    "عمارة": "Apartment building", "شقة": "Apartment", "فيلا": "Villa",
    "دور": "Floor unit", "استوديو": "Studio", "أرض": "Land", "محل": "Shop",
    "سكن عائلات": "Family residence", "سكن عزاب": "Bachelor housing",
    "سكني": "Residential", "تجاري": "Commercial", "سكن عائلي": "Family residence",
    "نصف سنوي": "Semi-annual", "سنوي": "Annual", "ربع سنوي": "Quarterly", "شهري": "Monthly",
    "هوية وطنية": "National ID", "هوية مقيم": "Resident ID (Iqama)",
    "صك ملكية ورقي": "Paper title deed", "صك إلكتروني": "Electronic title deed",
}


def _en(v):
    return AR_EN.get(v.strip(), v) if isinstance(v, str) else v


def normalize_to_english(c) -> None:
    """Map known Arabic values on the extracted contract to English, in place."""
    c.contract_type = _en(c.contract_type)
    c.sealing_location = _en(c.sealing_location)
    if c.property:
        c.property.property_type = _en(c.property.property_type)
        c.property.property_usage = _en(c.property.property_usage)
        c.property.unit_type = _en(c.property.unit_type)
    if c.financials:
        c.financials.payment_cycle = _en(c.financials.payment_cycle)


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
    sent = pages[:MAX_EXTRACT_PAGES]
    started = time.time()
    try:
        # Run the (blocking) model call in a worker thread so it never freezes
        # the server's event loop.
        contract = await run_in_threadpool(extractor.extract, sent)
    except Exception as e:
        log.error("extraction failed via %s: %s", extractor.name, type(e).__name__)
        raise HTTPException(502, "Could not read the contract. Try clearer images.")

    log.info("ok via %s in %.1fs over %d of %d page(s) (cap=%d)",
             extractor.name, time.time() - started, len(sent), len(pages), MAX_EXTRACT_PAGES)
    normalize_to_english(contract)
    analysis = ContractAnalysis(extracted=contract, insights=derive_insights(contract))
    return JSONResponse(analysis.model_dump(mode="json"))


# Serve the frontend (registered after API routes so /api/* wins).
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

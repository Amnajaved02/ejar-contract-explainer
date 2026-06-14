# Contributing

Thanks for your interest! This project turns Saudi Ejar tenancy contracts into
structured, plain-language summaries.

## Dev setup
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env          # EXTRACTOR_PROVIDER=ollama for free local runs
    uvicorn app.main:app --reload

## Ground rules
- **Never commit real contracts, personal data, or API keys.** Put test files in
  `samples/` or `private/` (both git-ignored).
- Keep the pipeline **stateless** — no persisting document content, no logging it.
- New model backends go in `app/extractors/` implementing `VisionExtractor`.

## Pull requests
Keep them focused, describe the change, and note how you tested it.

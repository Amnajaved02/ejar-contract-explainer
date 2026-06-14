import base64
import json
import os
import urllib.request
from typing import List

from app.extractors.base import VisionExtractor
from app.models import EjarContract
from app.prompts import EXTRACTION_INSTRUCTIONS


class OllamaExtractor(VisionExtractor):
    """Runs a local open-source vision model via Ollama. No API cost."""

    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5vl")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def extract(self, page_images: List[bytes]) -> EjarContract:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": EXTRACTION_INSTRUCTIONS,
                    "images": [base64.b64encode(i).decode() for i in page_images],
                }
            ],
            "stream": False,
            "format": EjarContract.model_json_schema(),  # Ollama structured output
            "options": {"temperature": 0},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=900) as r:
            data = json.loads(r.read())
        return EjarContract.model_validate_json(data["message"]["content"])

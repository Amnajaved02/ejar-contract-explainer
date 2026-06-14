import base64
import os
from typing import List

from app.extractors.base import VisionExtractor
from app.models import EjarContract
from app.prompts import EXTRACTION_INSTRUCTIONS


class AnthropicExtractor(VisionExtractor):
    name = "anthropic"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    def extract(self, page_images: List[bytes]) -> EjarContract:
        import anthropic  # lazy import so local runs don't need the SDK

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(img).decode(),
                },
            }
            for img in page_images
        ]
        content.append({"type": "text", "text": EXTRACTION_INSTRUCTIONS})

        tool = {
            "name": "return_contract",
            "description": "Return the extracted Ejar contract as structured data.",
            "input_schema": EjarContract.model_json_schema(),
        }
        resp = client.messages.create(
            model=self.model,
            max_tokens=4096,
            tools=[tool],
            tool_choice={"type": "tool", "name": "return_contract"},
            messages=[{"role": "user", "content": content}],
        )
        for block in resp.content:
            if block.type == "tool_use":
                return EjarContract.model_validate(block.input)
        raise ValueError("Model returned no structured output")

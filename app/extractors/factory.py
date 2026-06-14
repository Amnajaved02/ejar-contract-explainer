import os
from app.extractors.base import VisionExtractor


def get_extractor() -> VisionExtractor:
    provider = os.getenv("EXTRACTOR_PROVIDER", "ollama").lower()
    if provider == "anthropic":
        from app.extractors.anthropic_extractor import AnthropicExtractor
        return AnthropicExtractor()
    if provider == "ollama":
        from app.extractors.ollama_extractor import OllamaExtractor
        return OllamaExtractor()
    raise ValueError(f"Unknown EXTRACTOR_PROVIDER: {provider!r}")

from abc import ABC, abstractmethod
from typing import List
from app.models import EjarContract


class VisionExtractor(ABC):
    name: str = "base"

    @abstractmethod
    def extract(self, page_images: List[bytes]) -> EjarContract:
        """Take a list of page PNG bytes, return a validated EjarContract."""
        raise NotImplementedError

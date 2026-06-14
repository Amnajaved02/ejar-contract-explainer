from typing import List
import fitz  # PyMuPDF


def file_to_page_images(filename: str, data: bytes, dpi: int = 150) -> List[bytes]:
    if filename.lower().endswith(".pdf"):
        return pdf_to_images(data, dpi)
    return [data]  # already an image (png/jpg)


def pdf_to_images(pdf_bytes: bytes, dpi: int = 150) -> List[bytes]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [page.get_pixmap(dpi=dpi).tobytes("png") for page in doc]
    finally:
        doc.close()

import io
import os
import re

from pypdf import PdfReader

MAX_MB = int(os.getenv("UPLOAD_MAX_MB", "10"))
MAX_BYTES = MAX_MB * 1024 * 1024
MAX_PAGES = 300
ALLOWED = {".pdf", ".txt", ".md"}
UNIT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n\s*\n")


class IngestError(ValueError):
    """Raised when an uploaded document can't be used."""


def clean(text):
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_units(text, size):
    for unit in UNIT_SPLIT.split(text):
        unit = unit.strip()
        while len(unit) > size:
            cut = unit.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            yield unit[:cut].strip()
            unit = unit[cut:].strip()
        if unit:
            yield unit


def chunk_text(text, size=900, overlap=150):
    """Split text into passages of about `size` characters that overlap slightly."""
    chunks, current, length = [], [], 0
    for unit in split_units(clean(text), size):
        if current and length + len(unit) + 1 > size:
            chunks.append(" ".join(current))
            tail, used = [], 0
            for prev in reversed(current):
                if used + len(prev) > overlap:
                    break
                tail.insert(0, prev)
                used += len(prev) + 1
            current, length = tail, used
        current.append(unit)
        length += len(unit) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def extract_pages(raw, ext):
    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise IngestError("This PDF is password protected.")
            if len(reader.pages) > MAX_PAGES:
                raise IngestError(f"This PDF has too many pages (max {MAX_PAGES}).")
            pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        except IngestError:
            raise
        except Exception as exc:
            raise IngestError("This PDF could not be read.") from exc
    else:
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        pages = [(None, text)]
    if not any(text.strip() for _, text in pages):
        raise IngestError("No text found. Scanned PDFs need OCR, which is not included yet.")
    return pages


def ingest(raw, ext):
    """Return (page_count, character_count, [(page, passage), ...])."""
    pages = extract_pages(raw, ext)
    chunks = [(page, passage) for page, text in pages for passage in chunk_text(text)]
    return len(pages), sum(len(text) for _, text in pages), chunks
import re
import uuid
from pathlib import Path
from typing import List, Tuple
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi

from pypdf import PdfReader
from docx import Document as DocxDocument

from ..config import UPLOAD_DIR


def fetch_url_text(url: str) -> Tuple[str, str]:
    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return title, text


def fetch_youtube_transcript(url: str) -> Tuple[str, str]:
    vid = _extract_video_id(url)
    if not vid:
        raise ValueError("Invalid YouTube URL")
    transcript = YouTubeTranscriptApi.get_transcript(vid)
    text = " ".join(t["text"] for t in transcript)
    title = f"YouTube: {vid}"
    return title, text


def _extract_video_id(url: str) -> str:
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    if len(url) == 11 and re.match(r"^[A-Za-z0-9_-]{11}$", url):
        return url
    return ""


def parse_document(path: Path) -> List[Tuple[str, int, int, str]]:
    """Return list of (section, page_start, page_end, text) blocks."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix in (".docx",):
        return _parse_docx(path)
    # plain text / markdown
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [("Document", 1, 1, text)]


def _parse_pdf(path: Path):
    reader = PdfReader(str(path))
    blocks = []
    for i, page in enumerate(reader.pages, start=1):
        txt = page.extract_text() or ""
        txt = _clean(txt)
        if txt.strip():
            blocks.append(("Page %d" % i, i, i, txt))
    return blocks


def _parse_docx(path: Path):
    doc = DocxDocument(str(path))
    paras = [p.text for p in doc.paragraphs if p.text.strip()]
    # group into one block (simple); headings could split
    text = "\n".join(paras)
    return [("Document", 1, 1, _clean(text))]


def _clean(text: str) -> str:
    text = text.replace("\r", "\n")
    # remove hyphenation at line breaks
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # collapse spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> List[str]:
    """Sentence-aware chunking by approximate token count (whitespace tokens)."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = []
    cur_len = 0
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        toks = len(s.split())
        if cur_len + toks > max_tokens and current:
            chunks.append(" ".join(current))
            # overlap: keep last `overlap` tokens worth of sentences
            if overlap > 0:
                tail = []
                tail_len = 0
                for sent in reversed(current):
                    if tail_len + len(sent.split()) > overlap:
                        break
                    tail.insert(0, sent)
                    tail_len += len(sent.split())
                current = tail
                cur_len = tail_len
            else:
                current = []
                cur_len = 0
        current.append(s)
        cur_len += toks
    if current:
        chunks.append(" ".join(current))
    # fallback: if no chunks, split by tokens
    if not chunks:
        words = text.split()
        for i in range(0, len(words), max_tokens):
            chunks.append(" ".join(words[i:i + max_tokens]))
    return [c for c in chunks if c.strip()]


def make_chunks_from_blocks(blocks):
    out = []
    idx = 0
    for section, ps, pe, text in blocks:
        for c in chunk_text(text):
            out.append({"section": section, "page_start": ps, "page_end": pe, "text": c, "order_index": idx})
            idx += 1
    return out

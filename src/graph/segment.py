import re
from dataclasses import dataclass
from typing import Optional

LIST_MARKER_RE = re.compile(r"^(?:(\d+)[.)]|[-*•])(?:\s+|$)")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass
class Segment:
    text: str  # cleaned: list marker and ** removed
    start: int  # span in the original generation string
    end: int
    list_marker: Optional[int]
    is_header: bool


def _make_segment(generation: str, start: int, end: int) -> Optional[Segment]:
    raw = generation[start:end]
    content_start = start + (len(raw) - len(raw.lstrip()))
    content = generation[content_start:end]

    list_marker = None
    m = LIST_MARKER_RE.match(content)
    if m:
        list_marker = int(m.group(1)) if m.group(1) else None
        content_start += m.end()
        content = generation[content_start:end]

    content_end = content_start + len(content.rstrip())
    text = generation[content_start:content_end].replace("**", "").strip()

    is_header = False
    if text.startswith("#"):
        text = text.lstrip("#").strip()
        is_header = True
    elif text.endswith(":") and "=" not in text:
        is_header = True

    if not any(c.isalnum() for c in text):
        return None
    return Segment(text, content_start, content_end, list_marker, is_header)


def _split_sentences(generation: str, seg: Segment) -> list:
    pieces = []
    cursor = seg.start
    for m in SENTENCE_SPLIT_RE.finditer(generation, seg.start, seg.end):
        pieces.append((cursor, m.start()))
        cursor = m.end()
    pieces.append((cursor, seg.end))

    out = []
    for i, (s, e) in enumerate(pieces):
        piece = _make_segment(generation, s, e)
        if piece is None:
            continue
        if i == 0:
            piece.list_marker = seg.list_marker
        out.append(piece)
    return out


def segment_generation(generation: str) -> list:
    """Split a model answer into reasoning steps, one per line (or sentence for single-paragraph answers)."""
    segments = []
    for m in re.finditer(r"[^\n]+", generation):
        seg = _make_segment(generation, m.start(), m.end())
        if seg is not None:
            segments.append(seg)

    if len(segments) == 1 and not segments[0].is_header:
        segments = _split_sentences(generation, segments[0])
    return segments

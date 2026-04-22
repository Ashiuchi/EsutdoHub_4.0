import logging
from typing import List

logger = logging.getLogger(__name__)


class MarkdownChunker:
    """Splits markdown content into overlapping chunks, preferring heading boundaries."""

    def __init__(self, chunk_size: int = 15000, overlap: int = 1000):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        lines = text.splitlines(keepends=True)
        chunks: List[str] = []
        current_lines: List[str] = []
        current_len = 0

        for line in lines:
            line_len = len(line)

            # Flush when adding this line would exceed chunk_size and we have content
            if current_len + line_len > self.chunk_size and current_lines:
                chunk_text = "".join(current_lines)
                chunks.append(chunk_text)

                # Seed next chunk with overlap tail
                tail = chunk_text[-self.overlap:] if self.overlap else ""
                current_lines = [tail] if tail else []
                current_len = len(tail)

            current_lines.append(line)
            current_len += line_len

        if current_lines:
            chunks.append("".join(current_lines))

        logger.info(f"MarkdownChunker: {len(text)} chars → {len(chunks)} chunks (size={self.chunk_size}, overlap={self.overlap})")
        return chunks

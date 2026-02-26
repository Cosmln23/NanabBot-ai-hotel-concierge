"""
Utility for splitting long messages into chunks that fit within messaging platform limits.
"""

import logging
import time
from typing import Callable, List

logger = logging.getLogger(__name__)

# Platform message limits
WHATSAPP_MAX_LENGTH = 4096
LINE_MAX_LENGTH = 5000
DEFAULT_CHUNK_DELAY = 0.5  # seconds between chunks


def split_message(text: str, max_length: int = WHATSAPP_MAX_LENGTH) -> List[str]:
    """
    Split a long message into multiple parts that fit within the max_length limit.

    Tries to split at the last newline or space for better readability.
    If no suitable split point is found, forces a hard cut at max_length.

    Args:
        text: The message text to split
        max_length: Maximum length per chunk (default: 4096 for WhatsApp)

    Returns:
        List of message chunks
    """
    if not text:
        return []

    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to find a good split point (newline first, then space)
        split_pos = remaining.rfind("\n", 0, max_length)
        if split_pos <= 0:
            split_pos = remaining.rfind(" ", 0, max_length)
        if split_pos <= 0:
            # No good split point found, force cut at max_length
            split_pos = max_length

        chunk = remaining[:split_pos].rstrip()
        if chunk:  # Only add non-empty chunks
            chunks.append(chunk)
        remaining = remaining[split_pos:].lstrip()

    if len(chunks) > 1:
        logger.info("Message split into %d chunks (original length: %d)", len(chunks), len(text))

    return chunks


def send_chunked_message(
    text: str,
    send_fn: Callable[[str], bool],
    max_length: int = WHATSAPP_MAX_LENGTH,
    delay: float = DEFAULT_CHUNK_DELAY,
) -> bool:
    """
    Split a message and send each chunk using the provided send function.

    Args:
        text: The message text to send
        send_fn: Function that sends a single message chunk, returns True on success
        max_length: Maximum length per chunk
        delay: Delay in seconds between chunks (to avoid rate limiting)

    Returns:
        True if all chunks were sent successfully, False otherwise
    """
    chunks = split_message(text, max_length)

    if not chunks:
        return True

    success = True
    for i, chunk in enumerate(chunks):
        if i > 0 and delay > 0:
            time.sleep(delay)

        if not send_fn(chunk):
            logger.error("Failed to send chunk %d/%d", i + 1, len(chunks))
            success = False

    return success

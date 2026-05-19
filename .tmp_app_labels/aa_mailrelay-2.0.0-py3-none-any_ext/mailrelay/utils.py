"""Utility functions for Mail Relay."""

from typing import List


def chunks_by_lines(full_text: str, max_lengths: int) -> List[str]:
    """Converts text into chunks not exceeding max_lengths and split by newline."""
    parts = []
    partial_text = ""
    for line in full_text.splitlines(keepends=True):
        if len(partial_text + line) > max_lengths:
            parts.append(partial_text)
            partial_text = ""
        partial_text += line
    if partial_text:
        parts.append(partial_text)
    return parts

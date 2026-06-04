"""Synthetic moonmining extraction IDs used by emu_moons_test_invoices."""

TEST_MM_ID_BASE = 8_100_000
TEST_MM_ID_SPAN = 100_000


def is_test_extraction(extraction) -> bool:
    mm_id = int(getattr(extraction, "moonmining_extraction_id", 0) or 0)
    return TEST_MM_ID_BASE <= mm_id < TEST_MM_ID_BASE + TEST_MM_ID_SPAN

"""Skill point calculations."""

from __future__ import annotations


def cumulative_skill_sp(level: int, rank: int) -> int:
    if level <= 0 or rank <= 0:
        return 0
    total = 0.0
    for n in range(1, level + 1):
        if n == 1:
            total += 250 * rank
        else:
            total += 250 * rank * (2 ** ((2 * n - 3) / 2))
    return round(total)


def max_skill_sp(rank: int) -> int:
    return cumulative_skill_sp(5, rank)

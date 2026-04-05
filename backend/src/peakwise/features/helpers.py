"""Shared numerical helpers for feature engineering."""

from __future__ import annotations


def rolling_avg(values: list[float | None], window: int) -> float | None:
    """Compute the average of the last *window* non-None values.

    Returns ``None`` if there are no valid values in the window.
    """
    valid = [v for v in values[-window:] if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def rolling_sum(values: list[float | None], window: int) -> float:
    """Sum the last *window* non-None values (0 for None entries)."""
    return sum(v for v in values[-window:] if v is not None)


def linear_slope(values: list[float | None]) -> float | None:
    """Compute the ordinary least-squares slope over an ordered sequence.

    ``None`` entries are skipped.  Returns ``None`` when fewer than 2 valid
    points exist.
    """
    points: list[tuple[float, float]] = []
    for i, v in enumerate(values):
        if v is not None:
            points.append((float(i), v))
    if len(points) < 2:
        return None
    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_xx = sum(p[0] ** 2 for p in points)
    denom = n * sum_xx - sum_x**2
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


def consistency_score(values: list[float | None], window: int) -> float | None:
    """Score based on standard deviation: lower variance → higher score.

    score = max(0, 100 − std_dev × 10)

    Returns ``None`` if fewer than 2 valid values in the window.
    """
    valid = [v for v in values[-window:] if v is not None]
    if len(valid) < 2:
        return None
    mean = sum(valid) / len(valid)
    variance = sum((v - mean) ** 2 for v in valid) / len(valid)
    std = variance**0.5
    return max(0.0, 100.0 - std * 10.0)

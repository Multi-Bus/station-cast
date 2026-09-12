"""Congestion grading for estimated wait counts W(s,t) (S2, issue #12).

Converts W into a three-tier label (여유/보통/혼잡) by comparing it to each
stop's 포용인원(physical capacity) rather than a fixed headcount, since
stop size varies across the corridor and a fixed threshold would grade a
small stop as chronically 혼잡 and a large one as chronically 여유:

- W / capacity <= 0.5 -> 여유
- W / capacity <= 1.0 -> 보통
- W / capacity > 1.0  -> 혼잡

포용인원 isn't available from open data, so the team field-surveyed each
stop's 승차대(platform structure) count and set capacity at 10 people per
platform (see ingest/stop_capacity.py, where 포용인원 = 10 * 승차대개수).
The ratio thresholds above are that per-platform rule translated directly:
up to 5 people per platform is 여유, up to 10 is 보통, more is 혼잡.
"""

GRADES = ("여유", "보통", "혼잡")

SPARE_RATIO = 0.5
NORMAL_RATIO = 1.0


def grade_wait(w: float, capacity: float) -> str:
    """Grade a single W value against a stop's capacity.

    capacity must be positive -- a zero or negative capacity makes the
    ratio undefined, not just an edge case to silently clamp.
    """
    if capacity <= 0:
        raise ValueError(f"capacity must be positive, got {capacity}")

    ratio = w / capacity
    if ratio <= SPARE_RATIO:
        return "여유"
    if ratio <= NORMAL_RATIO:
        return "보통"
    return "혼잡"

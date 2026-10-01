"""Wall-clock budgeting for local and story fixed-step simulation."""


def offline_frame_dt(elapsed_ms: float) -> float:
    """Catch up at low render FPS; cap long pauses at 250 ms.

    Physics still runs at its original fixed 120 Hz. The cap prevents a long
    window drag/suspend from creating an unbounded catch-up loop.
    """
    return min(max(elapsed_ms, 0.0) / 1000.0, 0.25)

"""Pure decoder-readiness policy for playbackCore Take/Cue operations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessDecision:
    state: str
    reason: str
    required_frames: int


def assess_decoder_readiness(
    *,
    opened,
    opening,
    open_failed,
    decode_errors,
    fully_pre_read,
    num_pre_read_frames,
    requested_pre_read_frames,
    movie_length_frames,
    minimum_start_frames=1,
    elapsed_seconds,
    timeout_seconds,
):
    """Return READY, WAITING, or ERROR without depending on TouchDesigner."""
    requested = max(0, int(requested_pre_read_frames or 0))
    available = max(0, int(num_pre_read_frames or 0))
    length = max(0, int(movie_length_frames or 0))
    minimum = max(1, int(minimum_start_frames or 1))
    cache_target = min(requested, length) if length > 0 else requested
    required = min(cache_target, minimum)

    if open_failed:
        return ReadinessDecision('ERROR', 'Movie failed to open', required)
    if decode_errors:
        return ReadinessDecision(
            'ERROR',
            'Movie decoder reported errors',
            required,
        )
    if opened:
        if requested == 0:
            return ReadinessDecision('READY', 'Movie is open', 0)
        if fully_pre_read:
            return ReadinessDecision(
                'READY',
                'Movie pre-read cache is full',
                required,
            )
        if required > 0 and available >= required:
            return ReadinessDecision(
                'READY',
                'Minimum decoded start frames are available',
                required,
            )

    if elapsed_seconds >= timeout_seconds:
        detail = (
            'Movie load timed out after {:.1f}s '
            '(open={}, opening={}, pre-read={}/{})'
        ).format(
            elapsed_seconds,
            int(bool(opened)),
            int(bool(opening)),
            available,
            required,
        )
        return ReadinessDecision('ERROR', detail, required)

    return ReadinessDecision('WAITING', 'Waiting for decoder', required)

"""Typed non-visual perception events.

This module owns the lightweight event schema used by gameplay systems to
describe sound and scent emissions. It intentionally does not propagate sound
or scent fields, and it does not play audio. Production propagation remains in
``pathfinding.perception_systems``; audio playback remains in
``game.systems.sound``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pathfinding.perception_systems import FlowType


@dataclass(slots=True)
class NoiseEvent:
    """Pending sound/noise event consumed by production perception fields.

    Attributes
    ----------
    x, y:
        Source tile for the emitted noise.
    intensity:
        Debug/radius-map intensity and gameplay loudness hint. Production flow
        propagation currently uses the loudest queued event as its flow source.
    flow_type:
        Pathfinding flow semantics for the noise field. This is deliberately a
        gameplay/perception concept, not an audio-playback concept.
    source_id:
        Optional entity or object ID that produced the sound.
    cause:
        Optional stable cause string, such as ``"movement"``, ``"combat"``, or
        ``"door"``. Consumers should not parse localized message text.
    lifetime:
        Optional queue lifetime in turns. A value of 0 means the event is
        consumed on the next perception-field update.
    """

    x: int
    y: int
    intensity: float
    flow_type: FlowType = FlowType.REAL_NOISE
    source_id: int | None = None
    cause: str | None = None
    lifetime: int = 0


@dataclass(slots=True)
class ScentEvent:
    """Pending scent event consumed by production scent fields."""

    x: int
    y: int
    intensity: float = 5.0
    source_id: int | None = None
    cause: str | None = None


PendingNoiseEvent = NoiseEvent | tuple[int, int, float]
PendingScentEvent = ScentEvent | tuple[int, int, float]


def event_xy_intensity(
    event: PendingNoiseEvent | PendingScentEvent,
) -> tuple[int, int, float]:
    """Return the common ``(x, y, intensity)`` view for typed or legacy events."""
    if isinstance(event, tuple):
        return int(event[0]), int(event[1]), float(event[2])
    return int(event.x), int(event.y), float(event.intensity)


def noise_event_flow_type(event: PendingNoiseEvent) -> FlowType:
    """Return the flow type for a typed noise event or the legacy default."""
    if isinstance(event, NoiseEvent):
        return event.flow_type
    return FlowType.REAL_NOISE

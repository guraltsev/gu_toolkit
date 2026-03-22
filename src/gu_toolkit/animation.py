"""Parameter animation helpers for notebook controls.

The animation system is intentionally small and widget-friendly:

- a shared clock drives active animations at a fixed cadence,
- each control owns a lightweight :class:`AnimationController`,
- values are quantized to admissible slider values before being applied.

The controller keeps an internal continuous value so animation remains smooth
when the displayed control value is discretized by slider ``step``.
"""

from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

AnimationMode = Literal[">>", ">", "<>"]

DEFAULT_ANIMATION_HZ = 60.0
DEFAULT_ANIMATION_TIME = 5.0
_VALID_ANIMATION_MODES = (">>", ">", "<>")
_EPS = 1e-12


class AnimationClockLike(Protocol):
    """Minimal clock protocol used by :class:`AnimationController`."""

    def subscribe(self, callback: Callable[[float], None]) -> None:
        """Register a callback that receives the current monotonic time."""

    def unsubscribe(self, callback: Callable[[float], None]) -> None:
        """Unregister a previously registered callback."""


class AnimationTarget(Protocol):
    """Control contract required by :class:`AnimationController`."""

    @property
    def value(self) -> float:
        """Current control value."""

    @value.setter
    def value(self, value: float) -> None:
        """Apply a new control value."""

    @property
    def min(self) -> float:
        """Lower bound of the control."""

    @property
    def max(self) -> float:
        """Upper bound of the control."""

    @property
    def step(self) -> float:
        """Step size used by the control."""


@dataclass(frozen=True)
class AnimationDomain:
    """Numeric domain used for animation quantization and wrapping."""

    min: float
    max: float
    step: float

    @property
    def span(self) -> float:
        """Return the non-negative numeric span of the domain."""
        return max(0.0, self.max - self.min)


def _validate_mode(mode: str) -> AnimationMode:
    if mode not in _VALID_ANIMATION_MODES:
        raise ValueError(
            f"animation_mode must be one of {_VALID_ANIMATION_MODES}, got {mode!r}."
        )
    return mode  # type: ignore[return-value]


def _coerce_domain(target: AnimationTarget) -> AnimationDomain:
    min_value = float(target.min)
    max_value = float(target.max)
    if max_value < min_value:
        min_value, max_value = max_value, min_value

    step_value = abs(float(target.step))
    if not math.isfinite(step_value) or step_value <= _EPS:
        step_value = max_value - min_value
        if step_value <= _EPS:
            step_value = 1.0

    return AnimationDomain(min=min_value, max=max_value, step=step_value)


def _is_close(a: float, b: float, *, step: float | None = None) -> bool:
    abs_tol = _EPS
    if step is not None and math.isfinite(step):
        abs_tol = max(abs_tol, abs(step) * 1e-12)
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=abs_tol)


def _admissible_candidates(value: float, domain: AnimationDomain) -> tuple[float, ...]:
    """Return nearby admissible values for quantization.

    The admissible set follows the slider grid ``min + n * step`` and always
    includes the exact range endpoints. Including ``max`` makes terminal modes
    such as ``">"`` reach the configured end cleanly even when ``step`` does
    not divide the range exactly.
    """
    lo = domain.min
    hi = domain.max
    step = domain.step

    if hi - lo <= _EPS:
        return (lo,)

    if not math.isfinite(value):
        value = lo

    offset = (value - lo) / step
    lower = math.floor(offset)
    upper = math.ceil(offset)

    candidates = {lo, hi}
    for index in (lower - 1, lower, upper, upper + 1):
        candidate = lo + float(index) * step
        if lo - _EPS <= candidate <= hi + _EPS:
            candidates.add(min(max(candidate, lo), hi))

    return tuple(sorted(candidates))


def quantize_to_admissible(
    value: float,
    domain: AnimationDomain,
    *,
    direction: float = 0.0,
) -> float:
    """Return the closest slider-compatible value for ``value``.

    Ties are broken in the direction of motion so forward animations remain
    monotone when the internal value lands exactly between two admissible
    slider values.
    """
    candidates = _admissible_candidates(value, domain)
    if len(candidates) == 1:
        return candidates[0]

    best_distance = min(abs(candidate - value) for candidate in candidates)
    nearest = [
        candidate
        for candidate in candidates
        if _is_close(abs(candidate - value), best_distance)
    ]
    if len(nearest) == 1:
        return nearest[0]
    if direction > 0:
        return max(nearest)
    if direction < 0:
        return min(nearest)
    return min(nearest, key=lambda candidate: (abs(candidate - value), candidate))


class AnimationClock:
    """Shared cadence source for active parameter animations."""

    def __init__(
        self,
        *,
        frequency_hz: float = DEFAULT_ANIMATION_HZ,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be > 0")
        self._frequency_hz = float(frequency_hz)
        self._interval_s = 1.0 / self._frequency_hz
        self._time_source = time_source
        self._lock = threading.Lock()
        self._timer: object | None = None
        self._subscribers: set[Callable[[float], None]] = set()

    @property
    def frequency_hz(self) -> float:
        """Configured clock frequency."""
        return self._frequency_hz

    def subscribe(self, callback: Callable[[float], None]) -> None:
        """Register a callback and start the cadence if needed."""
        with self._lock:
            self._subscribers.add(callback)
            if self._timer is None:
                self._schedule_next_locked()

    def unsubscribe(self, callback: Callable[[float], None]) -> None:
        """Remove a callback from the active cadence."""
        with self._lock:
            self._subscribers.discard(callback)

    def _schedule_next_locked(self) -> None:
        delay_s = self._interval_s
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            timer = threading.Timer(delay_s, self._on_tick)
            timer.daemon = True
            self._timer = timer
            timer.start()
            return

        self._timer = loop.call_later(delay_s, self._on_tick)

    def _on_tick(self) -> None:
        with self._lock:
            self._timer = None
            subscribers = tuple(self._subscribers)

        if not subscribers:
            return

        now = self._time_source()
        for callback in subscribers:
            try:
                callback(now)
            except Exception:  # pragma: no cover - defensive callback boundary
                logging.getLogger(__name__).exception("Animation clock callback failed")

        with self._lock:
            if self._subscribers and self._timer is None:
                self._schedule_next_locked()


_DEFAULT_CLOCK: AnimationClock | None = None


def get_default_animation_clock() -> AnimationClock:
    """Return the process-wide default animation clock."""
    global _DEFAULT_CLOCK
    if _DEFAULT_CLOCK is None:
        _DEFAULT_CLOCK = AnimationClock()
    return _DEFAULT_CLOCK


class AnimationController:
    """Widget-bound animation controller for a single parameter.

    Parameters
    ----------
    target : AnimationTarget
        Control to animate. The controller reads ``value``/``min``/``max``/
        ``step`` and writes new values back through ``target.value``.
    clock : AnimationClockLike, optional
        Cadence source. Defaults to the shared 60 Hz clock.
    time_source : callable, optional
        Monotonic time provider. Defaults to :func:`time.monotonic`.
    animation_time : float, optional
        Seconds needed to traverse the current full range once.
    animation_mode : {">>", ">", "<>"}, optional
        Forward loop, forward stop, or bounce.
    state_change_callback : callable, optional
        Invoked when running state changes.
    """

    def __init__(
        self,
        target: AnimationTarget,
        *,
        clock: AnimationClockLike | None = None,
        time_source: Callable[[], float] = time.monotonic,
        animation_time: float = DEFAULT_ANIMATION_TIME,
        animation_mode: AnimationMode = ">>",
        state_change_callback: Callable[[bool], None] | None = None,
    ) -> None:
        self._target = target
        self._clock = clock if clock is not None else get_default_animation_clock()
        self._time_source = time_source
        self._state_change_callback = state_change_callback

        self._animation_time = DEFAULT_ANIMATION_TIME
        self._animation_mode: AnimationMode = ">>"
        self._running = False
        self._internal_value = float(target.value)
        self._direction = 1.0
        self._last_tick: float | None = None
        self._applying_animation = False

        self.animation_time = animation_time
        self.animation_mode = animation_mode

    @property
    def animation_time(self) -> float:
        """Seconds needed to traverse the current numeric range once."""
        return self._animation_time

    @animation_time.setter
    def animation_time(self, seconds: float) -> None:
        seconds_value = float(seconds)
        if not math.isfinite(seconds_value) or seconds_value <= 0:
            raise ValueError("animation_time must be a finite number > 0")
        self._animation_time = seconds_value

    @property
    def animation_mode(self) -> AnimationMode:
        """Current animation mode token."""
        return self._animation_mode

    @animation_mode.setter
    def animation_mode(self, mode: str) -> None:
        validated = _validate_mode(mode)
        self._animation_mode = validated
        if validated in (">", ">>"):
            self._direction = 1.0

    @property
    def running(self) -> bool:
        """Whether the controller is currently subscribed to the clock."""
        return self._running

    def start(self) -> None:
        """Start animating from the current internal value."""
        if self._running:
            return
        self._internal_value = float(self._target.value)
        if self._animation_mode in (">", ">>"):
            self._direction = 1.0
        elif _is_close(self._internal_value, float(self._target.max)):
            self._direction = -1.0
        elif _is_close(self._internal_value, float(self._target.min)):
            self._direction = 1.0

        self._apply_discrete_value(quantize_to_admissible(
            self._internal_value,
            _coerce_domain(self._target),
            direction=self._direction,
        ))
        self._last_tick = self._time_source()
        self._running = True
        self._clock.subscribe(self._on_clock_tick)
        self._emit_state_change()

    def stop(self) -> None:
        """Stop animating and unsubscribe from the clock."""
        if not self._running:
            return
        self._clock.unsubscribe(self._on_clock_tick)
        self._running = False
        self._last_tick = None
        self._emit_state_change()

    def toggle(self) -> None:
        """Toggle between running and paused states."""
        if self._running:
            self.stop()
            return
        self.start()

    def handle_value_change(self, new_value: float) -> None:
        """Sync the internal animation state from an external value edit."""
        if self._applying_animation:
            return
        self._internal_value = float(new_value)

    def handle_domain_change(self) -> None:
        """Adapt the animation to a changed slider range or step.

        The internal value is preserved while it stays inside the numeric range.
        The displayed value is always re-quantized so the parameter remains
        compatible with the current ``min``/``max``/``step`` configuration.
        """
        domain = _coerce_domain(self._target)
        if self._internal_value < domain.min or self._internal_value > domain.max:
            self._internal_value = quantize_to_admissible(
                self._internal_value,
                domain,
                direction=self._direction,
            )
        discrete = quantize_to_admissible(
            self._internal_value,
            domain,
            direction=self._direction,
        )
        self._apply_discrete_value(discrete)

    def _emit_state_change(self) -> None:
        callback = self._state_change_callback
        if callback is None:
            return
        callback(self._running)

    def _on_clock_tick(self, now: float) -> None:
        if not self._running:
            return
        if self._last_tick is None:
            self._last_tick = now
            return

        elapsed_s = max(0.0, float(now) - float(self._last_tick))
        self._last_tick = float(now)
        self._advance_by(elapsed_s)

    def _advance_by(self, elapsed_s: float) -> None:
        if elapsed_s <= 0:
            return

        domain = _coerce_domain(self._target)
        span = domain.span
        if span <= _EPS:
            self._apply_discrete_value(domain.min)
            return

        distance = (span / self._animation_time) * elapsed_s
        new_internal = self._internal_value
        reached_terminal = False

        if self._animation_mode == ">>":
            offset = (self._internal_value - domain.min + distance) % span
            new_internal = domain.min + offset
            self._direction = 1.0
        elif self._animation_mode == ">":
            new_internal = min(domain.max, self._internal_value + distance)
            self._direction = 1.0
            reached_terminal = _is_close(new_internal, domain.max)
        else:
            phase = self._bounce_phase(domain)
            cycle = 2.0 * span
            phase = (phase + distance) % cycle
            if _is_close(phase, span):
                new_internal = domain.max
                self._direction = -1.0
            elif phase < span:
                new_internal = domain.min + phase
                self._direction = 1.0
            else:
                new_internal = domain.max - (phase - span)
                self._direction = -1.0

        self._internal_value = new_internal
        discrete = quantize_to_admissible(
            self._internal_value,
            domain,
            direction=self._direction,
        )
        self._apply_discrete_value(discrete)

        if reached_terminal:
            self.stop()

    def _bounce_phase(self, domain: AnimationDomain) -> float:
        span = domain.span
        if self._direction >= 0:
            return max(0.0, min(span, self._internal_value - domain.min))
        return span + max(0.0, min(span, domain.max - self._internal_value))

    def _apply_discrete_value(self, value: float) -> None:
        current = float(self._target.value)
        step = float(self._target.step)
        if _is_close(current, value, step=step):
            return

        self._applying_animation = True
        try:
            self._target.value = float(value)
        finally:
            self._applying_animation = False

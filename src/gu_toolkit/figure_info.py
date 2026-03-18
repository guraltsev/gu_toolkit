"""Info section manager for figure sidebars.

The *Info section* is the optional sidebar region used for explanatory text,
small computed summaries, and arbitrary notebook output associated with a
figure. Two lanes are supported:

- raw :class:`ipywidgets.Output` widgets created via :meth:`get_output`, and
- simple *info cards* created via :meth:`set_simple_card`.

An *info card* is a small rich-text block composed of static string segments,
dynamic callable segments, or a mixture of both. Cards may be global or scoped
to a specific view. A view-scoped card is shown only while that view is the
active one.
"""

from __future__ import annotations

import html
import re
import time
import traceback
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import ipywidgets as widgets
from IPython.display import display

from .debouncing import QueuedDebouncer
from .FigureSnapshot import InfoCardSnapshot

# SECTION: InfoPanelManager (The Model for Info) [id: InfoPanelManager]
# =============================================================================


class InfoPanelManager:
    """Own the figure sidebar's Info section.

    ``InfoPanelManager`` is the advanced API behind :meth:`Figure.info`.
    It manages both raw output widgets and simple info cards, keeps track of the
    active view for view-scoped cards, and produces immutable info-card
    snapshots for serialization.
    """

    _ID_REGEX = re.compile(r"^info:(\d+)$")
    _SIMPLE_ID_REGEX = re.compile(r"^info(\d+)$")

    @dataclass(frozen=True)
    class InfoChangeContext:
        """Update metadata for dynamic info segment evaluations."""

        reason: str
        trigger: Any = None
        t: float = 0.0
        seq: int = 0

    @dataclass
    class _StaticSegment:
        text: str
        widget: widgets.HTMLMath

    @dataclass
    class _DynamicSegment:
        fn: Callable[[Any, InfoPanelManager.InfoChangeContext], str]
        widget: widgets.HTMLMath
        last_text: str | None = None

    @dataclass
    class _SimpleInfoCard:
        id: Hashable
        output: widgets.Output
        container: widgets.VBox
        segments: list[
            InfoPanelManager._StaticSegment | InfoPanelManager._DynamicSegment
        ]
        debouncer: QueuedDebouncer
        pending_ctx: InfoPanelManager.InfoChangeContext | None = None
        view_id: str | None = None

    def __init__(self, layout_box: widgets.Box) -> None:
        """Initialize the info panel manager.

        Parameters
        ----------
        layout_box : ipywidgets.Box
            Container where info outputs will be added.

        Returns
        -------
        None

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP

        Notes
        -----
        Use :meth:`get_output` to create outputs lazily as content is needed.
        """
        self._outputs: dict[Hashable, widgets.Output] = {}
        self._components: dict[Hashable, Any] = {}
        self._layout_box = layout_box
        self._counter = 0
        self._simple_cards: dict[Hashable, InfoPanelManager._SimpleInfoCard] = {}
        self._simple_counter = 0
        self._update_seq = 0
        self._active_view_id: str | None = None
        self._layout_change_callback: Callable[[str], Any] | None = None

    def bind_layout_change_callback(
        self, callback: Callable[[str], Any] | None
    ) -> None:
        """Bind a figure-owned callback notified when info widgets change.

        Parameters
        ----------
        callback : callable or None
            Invoked with a short reason string when the info panel structure
            changes in a way that can affect figure layout, such as creating the
            first raw output widget.
        """
        self._layout_change_callback = callback

    def _notify_layout_change(self, reason: str) -> None:
        callback = self._layout_change_callback
        if callback is not None:
            callback(reason)

    def get_output(
        self, id: Hashable | None = None, **layout_kwargs: Any
    ) -> widgets.Output:
        """
        Get or create an Info Output widget.

        Parameters
        ----------
        id : hashable, optional
            Unique identifier for the output. If omitted, a new ID is generated.
        **layout_kwargs : Any
            Keyword arguments forwarded to ``ipywidgets.Layout``.

        Returns
        -------
        ipywidgets.Output
            Output widget associated with the ID.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> out = panel.get_output("info:1")  # doctest: +SKIP

        Notes
        -----
        IDs are stored on the widget as ``out.id`` for convenience.
        """
        if id is None:
            self._counter += 1
            id = f"info:{self._counter}"

        if id in self._outputs:
            out = self._outputs[id]
            if layout_kwargs:
                out.layout = widgets.Layout(**layout_kwargs)
            return out

        # Validate ID if string (avoids collision with auto-generated IDs)
        if isinstance(id, str):
            m = self._ID_REGEX.match(id)
            if m:
                self._counter = max(self._counter, int(m.group(1)))

        out = widgets.Output(layout=widgets.Layout(**layout_kwargs))
        out.id = id

        self._outputs[id] = out
        self._layout_box.children += (out,)
        self._notify_layout_change("output_created")
        return out

    def add_component(self, id: Hashable, component_inst: Any) -> None:
        """Register an info component instance.

        Parameters
        ----------
        id : hashable
            Unique identifier for the component.
        component_inst : Any
            Component instance to store.

        Returns
        -------
        None

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.add_component("demo", object())  # doctest: +SKIP

        See Also
        --------
        get_component : Retrieve a registered component.
        """
        self._components[id] = component_inst

    def get_component(self, id: Hashable) -> Any:
        """Retrieve a previously registered info component.

        Parameters
        ----------
        id : hashable
            Component identifier.

        Returns
        -------
        Any
            The registered component instance.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.add_component("demo", object())  # doctest: +SKIP
        >>> panel.get_component("demo")  # doctest: +SKIP

        See Also
        --------
        add_component : Register a component instance.
        """
        return self._components[id]

    @property
    def has_info(self) -> bool:
        """Whether the figure has any Info-section content.

        Returns
        -------
        bool
            ``True`` if at least one output has been created.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.has_info
        False

        See Also
        --------
        get_output : Create an output widget in the info panel.

        Notes
        -----
        This is a global section-level flag. View-scoped cards still count as
        info content even when they are hidden for the currently active view.
        """
        return len(self._outputs) > 0

    @property
    def outputs(self) -> Mapping[Hashable, widgets.Output]:
        """Read-only mapping of lazily created info outputs.

        Notes
        -----
        This property intentionally returns a read-only mapping to avoid
        external code mutating the manager's internal registry.
        Use :meth:`get_output` to create and retrieve outputs.
        """
        return MappingProxyType(self._outputs)

    def set_simple_card(
        self,
        spec: str | Callable | Sequence[str | Callable],
        id: Hashable | None = None,
        *,
        view: str | None = None,
    ) -> Hashable:
        """Create or replace a simple rich-text info card.

        Parameters
        ----------
        spec:
            Static string content, one dynamic callable, or a sequence mixing
            both. Dynamic callables receive ``(figure, context)``.
        id:
            Optional stable identifier used for replacement.
        view:
            Optional view id. When provided, the card is only visible while
            that view is active.

        Returns
        -------
        Hashable
            The card identifier.
        """
        if id is None:
            id = self._next_simple_id()
        elif isinstance(id, str):
            m = self._SIMPLE_ID_REGEX.match(id)
            if m:
                self._simple_counter = max(self._simple_counter, int(m.group(1)) + 1)

        out = self.get_output(id=id)

        normalized = self._normalize_spec(spec)
        card = self._simple_cards.get(id)
        if card is None:
            container = widgets.VBox(layout=widgets.Layout(gap="6px"))
            card = self._SimpleInfoCard(
                id=id,
                output=out,
                container=container,
                segments=[],
                debouncer=QueuedDebouncer(
                    lambda card_id=id: self._run_card_update(card_id),
                    execute_every_ms=33,
                    drop_overflow=True,
                ),
            )
            self._simple_cards[id] = card

        card.view_id = view
        self._rebuild_simple_card(card, normalized)
        self._apply_card_visibility(card)
        return id

    def _apply_card_visibility(self, card: _SimpleInfoCard) -> None:
        visible = card.view_id is None or card.view_id == self._active_view_id
        card.output.layout.display = "block" if visible else "none"

    def set_active_view(self, view_id: str) -> None:
        """Update which view-scoped cards are visible in the sidebar."""
        self._active_view_id = str(view_id)
        for card in self._simple_cards.values():
            self._apply_card_visibility(card)

    def _next_simple_id(self) -> str:
        while True:
            id = f"info{self._simple_counter}"
            self._simple_counter += 1
            if id not in self._outputs:
                return id

    def schedule_info_update(self, reason: str, trigger: Any = None) -> None:
        """Queue updates for all simple cards with a shared reason payload."""
        if not self._simple_cards:
            return

        self._update_seq += 1
        ctx = self.InfoChangeContext(
            reason=reason, trigger=trigger, t=time.time(), seq=self._update_seq
        )
        for card in self._simple_cards.values():
            card.pending_ctx = ctx
            card.debouncer()

    def _normalize_spec(
        self, spec: str | Callable | Sequence[str | Callable]
    ) -> list[str | Callable]:
        if isinstance(spec, str) or callable(spec):
            return [spec]
        if isinstance(spec, Sequence) and not isinstance(spec, (str, bytes)):
            values = list(spec)
            for idx, value in enumerate(values):
                if not isinstance(value, str) and not callable(value):
                    raise TypeError(
                        f"Info spec element at index {idx} must be a str or callable; got {type(value).__name__}"
                    )
            return values
        raise TypeError(
            f"Info spec must be a str, callable, or sequence of these; got {type(spec).__name__}"
        )

    def _rebuild_simple_card(
        self, card: _SimpleInfoCard, normalized: list[str | Callable]
    ) -> None:
        segment_widgets: list[widgets.HTMLMath] = []
        segments: list[
            InfoPanelManager._StaticSegment | InfoPanelManager._DynamicSegment
        ] = []
        for part in normalized:
            if isinstance(part, str):
                widget = widgets.HTMLMath(
                    value=part, layout=widgets.Layout(margin="0px")
                )
                segments.append(self._StaticSegment(text=part, widget=widget))
            else:
                widget = widgets.HTMLMath(value="", layout=widgets.Layout(margin="0px"))
                segments.append(
                    self._DynamicSegment(fn=part, widget=widget, last_text=None)
                )
            segment_widgets.append(widget)

        card.segments = segments
        card.pending_ctx = self.InfoChangeContext(
            reason="manual", trigger=None, t=time.time(), seq=self._update_seq
        )
        card.container.children = tuple(segment_widgets)

        with card.output:
            card.output.clear_output(wait=True)
            display(card.container)

        card.debouncer()

    def _run_card_update(self, card_id: Hashable) -> None:
        card = self._simple_cards.get(card_id)
        if card is None:
            return

        ctx = card.pending_ctx or self.InfoChangeContext(
            reason="manual", trigger=None, t=time.time(), seq=self._update_seq
        )
        for seg in card.segments:
            if isinstance(seg, self._StaticSegment):
                continue
            try:
                text = seg.fn(self._figure_owner, ctx)
                if text is None:
                    text = ""
                elif not isinstance(text, str):
                    text = str(text)
            except Exception as exc:
                text = self._format_segment_error(exc)
            if text != seg.last_text:
                seg.widget.value = text
                seg.last_text = text

    def _format_segment_error(self, exc: Exception) -> str:
        lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        payload = "".join(lines)
        capped = "\n".join(payload.splitlines()[:20])
        safe = html.escape(capped)
        return (
            '<pre style="max-height: 12em; overflow:auto; white-space: pre-wrap; margin:0;">'
            f"{safe}"
            "</pre>"
        )

    @property
    def _figure_owner(self) -> Any:
        owner = getattr(self, "__figure_owner", None)
        if owner is None:
            raise RuntimeError("InfoPanelManager owner figure not set")
        return owner

    def bind_figure(self, fig: Any) -> None:
        """Bind the owning figure used when dynamic card callables run."""
        setattr(self, "__figure_owner", fig)

    def snapshot(self) -> tuple[InfoCardSnapshot, ...]:
        """Return immutable snapshots of all simple info cards.

        Static text segments are captured verbatim. Dynamic callable segments
        are stored as the placeholder string ``"<dynamic>"`` because the
        callable implementation itself is not serialized.
        """
        results: list[InfoCardSnapshot] = []
        for card in self._simple_cards.values():
            segs: list[str] = []
            for seg in card.segments:
                if isinstance(seg, self._StaticSegment):
                    segs.append(seg.text)
                else:
                    segs.append("<dynamic>")
            results.append(
                InfoCardSnapshot(id=card.id, segments=tuple(segs), view_id=card.view_id)
            )
        return tuple(results)


# =============================================================================

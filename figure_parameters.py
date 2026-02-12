"""Parameter manager for Figure."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, Dict, Iterator, Optional, Sequence, Tuple, Union

import ipywidgets as widgets
import sympy as sp
from sympy.core.symbol import Symbol

from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .ParameterSnapshot import ParameterSnapshot
from .Slider import FloatSlider

# SECTION: ParameterManager (The Model for Parameters) [id: ParameterManager]
# =============================================================================

class ParameterManager(Mapping[Symbol, ParamRef]):
    """
    Manages the collection of parameter sliders and change hooks.

    Responsibilities:
    - Creating and reusing parameter controls.
    - Storing parameter refs.
    - Executing hooks when parameters change.
    - Acts like a dictionary so `fig.parameters[sym]` works.

    Design Note:
    ------------
    By centralizing parameter logic here, we decouple the "state" of the math
    from the "rendering" of the figure.
    """

    def __init__(self, render_callback: Callable[[str, ParamEvent], None], layout_box: widgets.Box, modal_host: Optional[widgets.Box] = None) -> None:
        """Initialize the manager with a render callback and layout container.

        Parameters
        ----------
        render_callback : callable
            Function invoked when parameters change. Signature: ``(reason, event)``.
        layout_box : ipywidgets.Box
            Container where slider widgets will be added.
        modal_host : ipywidgets.Box, optional
            Host container used by controls that support full-layout modal overlays.

        Returns
        -------
        None

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP

        Notes
        -----
        ``render_callback`` is invoked by :meth:`_on_param_change` whenever any
        parameter value updates.
        """
        self._refs: Dict[Symbol, ParamRef] = {}
        self._controls: List[Any] = []
        self._hooks: Dict[Hashable, Callable[[ParamEvent], Any]] = {}
        self._hook_counter: int = 0
        self._render_callback = render_callback
        self._layout_box = layout_box # The VBox where sliders live
        self._modal_host = modal_host

    def parameter(self, symbols: Union[Symbol, Sequence[Symbol]], *, control: Optional[Any] = None, **control_kwargs: Any):
        """
        Create or reuse parameter references for the given symbols.

        Parameters
        ----------
        symbols : sympy.Symbol or sequence[sympy.Symbol]
            Parameter symbol(s) to ensure.
        control : Any, optional
            Optional control instance (or compatible) to use. When provided, the
            control must implement ``make_refs`` and return a mapping for the
            requested symbol(s).
        **control_kwargs :
            Control configuration (min, max, value, step). These are applied to
            the resulting :class:`ParamRef` objects.

        Returns
        -------
        ParamRef or dict[Symbol, ParamRef]
            ParamRef for a single symbol, or mapping for multiple symbols.

        Examples
        --------
        Create a single slider and fetch its ref:

        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = mgr.parameter(a, min=-2, max=2)  # doctest: +SKIP
        >>> ref.symbol  # doctest: +SKIP
        a

        Notes
        -----
        For custom controls, pass ``control`` with a ``make_refs`` method that
        returns a ``{Symbol: ParamRef}`` mapping.
        """
        if isinstance(symbols, Symbol):
            symbols = [symbols]
            single = True
        else:
            symbols = list(symbols)
            single = False

        existing = [s for s in symbols if s in self._refs]
        missing = [s for s in symbols if s not in self._refs]

        if control is not None and existing:
            for symbol in existing:
                if self._refs[symbol].widget is not control:
                    raise ValueError(f"Symbol {symbol} is already bound to a different control.")

        defaults = {'value': 0.0, 'min': -1.0, 'max': 1.0, 'step': 0.01}

        if control is None:
            for symbol in missing:
                config = {**defaults, **control_kwargs}
                new_control = FloatSlider(
                    description=f"${sp.latex(symbol)}$",
                    value=float(config['value']),
                    min=float(config['min']),
                    max=float(config['max']),
                    step=float(config['step'])
                )
                self._attach_modal_host(new_control)
                refs = new_control.make_refs([symbol])
                if symbol not in refs:
                    raise KeyError(f"Control did not provide a ref for symbol {symbol}.")
                ref = refs[symbol]
                ref.observe(self._on_param_change)
                self._refs[symbol] = ref
                if new_control not in self._controls:
                    self._controls.append(new_control)
                    self._layout_box.children += (new_control,)
        elif missing:
            self._attach_modal_host(control)
            refs = control.make_refs(missing)
            for symbol in missing:
                if symbol not in refs:
                    raise KeyError(f"Control did not provide a ref for symbol {symbol}.")
                ref = refs[symbol]
                ref.observe(self._on_param_change)
                self._refs[symbol] = ref
            if control not in self._controls:
                self._controls.append(control)
                self._layout_box.children += (control,)

        for symbol in symbols:
            ref = self._refs[symbol]
            for name, value in control_kwargs.items():
                setattr(ref, name, value)

        if single:
            return self._refs[symbols[0]]
        return {symbol: self._refs[symbol] for symbol in symbols}

    def _attach_modal_host(self, control: Any) -> None:
        """Attach modal host to controls that support it.

        Parameters
        ----------
        control : Any
            Candidate control widget.

        Returns
        -------
        None
            Applies host binding when supported.
        """
        if self._modal_host is None:
            return
        attach_fn = getattr(control, "set_modal_host", None)
        if callable(attach_fn):
            attach_fn(self._modal_host)

    def snapshot(self, *, full: bool = False) -> Dict[Symbol, Any] | ParameterSnapshot:
        """Return parameter values or a full immutable metadata snapshot.

        Parameters
        ----------
        full : bool, default=False
            If False, return a detached ``dict[Symbol, value]``.
            If True, return a full :class:`ParameterSnapshot` including metadata.
        """
        entries: Dict[Symbol, Dict[str, Any]] = {}
        for symbol, ref in self._refs.items():
            entry: Dict[str, Any] = {"value": ref.value}
            caps = list(ref.capabilities)
            entry["capabilities"] = caps
            for name in caps:
                entry[name] = getattr(ref, name)
            entries[symbol] = entry

        snapshot = ParameterSnapshot(entries)
        if full:
            return snapshot
        return snapshot.value_map()

    @property
    def has_params(self) -> bool:
        """Whether any parameters have been created.

        Returns
        -------
        bool
            ``True`` if at least one slider exists.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> mgr.has_params
        False

        See Also
        --------
        parameter : Create or reuse parameter controls.
        """
        return len(self._refs) > 0

    def add_hook(self, callback: Callable[[Optional[ParamEvent]], Any], hook_id: Optional[Hashable] = None) -> Hashable:
        """
        Register a parameter change hook.
        
        Parameters
        ----------
        callback: Callable
            The function to call (signature: (event)).
        hook_id: Hashable, optional
            Optional unique identifier.
        Returns
        -------
        Hashable
            The hook ID.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> hook_id = mgr.add_hook(lambda *_: None)  # doctest: +SKIP

        Notes
        -----
        Hooks are called after :class:`Figure` re-renders on parameter
        updates.
        """
        if hook_id is None:
            self._hook_counter += 1
            hook_id = f"hook:{self._hook_counter}"
        self._hooks[hook_id] = callback
        
        return hook_id

    def fire_hook(self, hook_id: Hashable, event: Optional[ParamEvent]) -> None:
        """Fire a specific hook with a ParamEvent.

        Parameters
        ----------
        hook_id : hashable
            Identifier for the hook to invoke.
        event : ParamEvent or None
            Event payload to forward to the callback.

        Returns
        -------
        None

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> hook_id = mgr.add_hook(lambda *_: None)  # doctest: +SKIP
        >>> mgr.fire_hook(hook_id, None)  # doctest: +SKIP

        Notes
        -----
        Use :meth:`add_hook` to register callbacks before firing them.
        """
        callback = self._hooks.get(hook_id)
        if callback is None:
            return
        callback(event)

    def _on_param_change(self, event: ParamEvent) -> None:
        """Handle parameter changes by triggering the render callback.

        Parameters
        ----------
        event : ParamEvent
            Parameter change payload.

        Returns
        -------
        None
        """
        self._render_callback("param_change", event)
    
    def get_hooks(self) -> Dict[Hashable, Callable]:
        """Return a copy of the registered hook dictionary.

        Returns
        -------
        dict
            Mapping of hook IDs to callbacks.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> isinstance(mgr.get_hooks(), dict)
        True

        Notes
        -----
        The returned mapping is a shallow copy; mutating it will not affect
        internal registrations.
        """
        return self._hooks.copy()

    # --- Dict-like Interface for Backward Compatibility ---
    # This allows `fig.parameters[symbol]` to work in user hooks.
    
    def __getitem__(self, key: Symbol) -> ParamRef:
        """Return the param ref for the given symbol.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.

        Returns
        -------
        ParamRef
            Ref associated with the symbol.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.parameter(a)  # doctest: +SKIP
        >>> mgr[a]  # doctest: +SKIP

        See Also
        --------
        get : Safe lookup with a default.
        """
        return self._refs[key]
    
    def __contains__(self, key: Symbol) -> bool:
        """Check if a slider exists for a symbol.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.

        Returns
        -------
        bool
            ``True`` if the symbol is present.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> a in mgr
        False

        See Also
        --------
        has_params : Determine whether any parameters exist.
        """
        return key in self._refs
    
    def items(self) -> Iterator[Tuple[Symbol, ParamRef]]:
        """Iterate over ``(Symbol, ParamRef)`` pairs.

        Returns
        -------
        iterator
            Iterator over the internal ref mapping.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.items())
        []

        Notes
        -----
        This mirrors the behavior of ``dict.items`` for compatibility.
        """
        return self._refs.items()
    
    def keys(self) -> Iterator[Symbol]:
        """Iterate over parameter symbols.

        Returns
        -------
        iterator
            Iterator over parameter symbols.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.keys())
        []

        See Also
        --------
        values : Iterate over parameter references.
        """
        return self._refs.keys()
    
    def values(self) -> Iterator[ParamRef]:
        """Iterate over param refs.

        Returns
        -------
        iterator
            Iterator over param refs.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.values())
        []

        See Also
        --------
        keys : Iterate over parameter symbols.
        """
        return self._refs.values()
    
    def get(self, key: Symbol, default: Any = None) -> Any:
        """Return a param ref if present; otherwise return a default.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.
        default : Any, optional
            Default value returned if no slider exists.

        Returns
        -------
        Any
            Param ref or the default value.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.get(a) is None
        True

        Notes
        -----
        This mirrors ``dict.get`` semantics for compatibility.
        """
        return self._refs.get(key, default)

    def __iter__(self) -> Iterator[Symbol]:
        """Iterate over parameter symbols.

        Returns
        -------
        iterator
            Iterator over parameter symbols.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(iter(mgr))
        []
        """
        return iter(self._refs)

    def __len__(self) -> int:
        """Return the number of stored parameter refs.

        Returns
        -------
        int
            Number of parameter refs in the manager.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> len(mgr)
        0
        """
        return len(self._refs)

    def widget(self, symbol: Symbol) -> Any:
        """Return the widget/control for a symbol.

        Parameters
        ----------
        symbol : sympy.Symbol
            Parameter symbol.

        Returns
        -------
        Any
            The underlying widget/control instance.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.parameter(a)  # doctest: +SKIP
        >>> mgr.widget(a)  # doctest: +SKIP

        See Also
        --------
        __getitem__ : Retrieve the :class:`ParamRef` for a symbol.
        """
        return self._refs[symbol].widget

    def widgets(self) -> List[Any]:
        """Return unique widgets/controls suitable for display.

        Returns
        -------
        list
            Unique control instances created by the manager.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> mgr.widgets()  # doctest: +SKIP
        []

        Notes
        -----
        Use this when you need to manually lay out controls outside the default
        sidebar.
        """
        return list(self._controls)


# =============================================================================

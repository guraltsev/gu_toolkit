"""Notebook-friendly symbolic-math prelude and convenience exports.

Provides SymPy/NumPy/Pandas shortcuts, indexed symbol and function families,
and infix relation operators tuned for discoverable notebook use.
"""

from __future__ import annotations

__all__=[]
# --- The deliberate classroom prelude ---
import sympy as sp
__all__+=["sp"]
from sympy import *
__all__+= list(getattr(sp, "__all__", []))

import numpy as np
__all__+=["np"]



import pandas as pd
__all__+=["pd"]

# print("__all__ (from prelude):",__all__)
import sympy as sp

class SymbolFamily(sp.Symbol):
    """
    A SymPy Symbol that creates indexed children via [].
    Inherits from sp.Symbol, so all math (x**2, diff, etc.) works natively.
    """
    def __new__(cls, name, **kwargs):
        """Create a family root symbol with cached indexed children support."""
        # Create the actual SymPy Symbol
        obj = super().__new__(cls, name, **kwargs)
        
        # Attach our family-specific attributes to the new instance
        # We use distinct names (e.g., _family_cache) to avoid colliding with SymPy internals
        obj._family_cache = {}
        obj._family_kwargs = kwargs
        return obj

    def __getitem__(self, k):
        """Return a cached indexed child symbol, creating it on first access."""
        if not isinstance(k, tuple):
            k = (k,)
            
        if k not in self._family_cache:
            sub = ",".join(map(str, k))
            child_name = f"{self.name}_{sub}"
            # Create a standard Symbol for the child
            self._family_cache[k] = sp.Symbol(child_name, **self._family_kwargs)
            
        return self._family_cache[k]

class FunctionFamily:
    """
    A wrapper for SymPy Functions (e.g., f(x)).
    SymPy Functions are complex to subclass directly, so this proxy 
    is the standard way to handle them.
    """
    def __init__(self, name, **kwargs):
        """Initialize a function-family wrapper around a base SymPy Function."""
        self.name = name
        self._kwargs = kwargs
        # Create the base function (e.g. f)
        self._base = sp.Function(name, **kwargs)
        self._cache = {}

    def __getitem__(self, k):
        """Return an indexed child function (for example ``f[1]`` -> ``f_1``)."""
        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._cache:
            sub = ",".join(map(str, k))
            # Create a new Function for the child (e.g. f_1)
            self._cache[k] = sp.Function(f"{self.name}_{sub}", **self._kwargs)
        return self._cache[k]

    def __call__(self, *args):
        """Call the base symbolic function with positional arguments."""
        # Allows f(x) to work
        return self._base(*args)
    
    def _sympy_(self):
        """Return the underlying SymPy function for SymPy coercion."""
        # Allows SymPy to recognize this object
        return self._base
    
    def __str__(self):
        """Return the string form of the wrapped base function."""
        return str(self._base)
    
    def __repr__(self):
        """Return a representation matching the wrapped SymPy function."""
        return repr(self._base)

__all__ += ["SymbolFamily", "FunctionFamily"]

# -----------------------
# Roman (lowercase)
# -----------------------
for _ch in "abcdefghijklmnopqrstuvwxyz":
    globals()[_ch] = SymbolFamily(_ch)

# conventional function letters
for _ch in "fgh":
    globals()[_ch] = FunctionFamily(_ch)

# conventional integer indices (as in your original snippet)
for _ch in "klmnij":
    globals()[_ch] = SymbolFamily(_ch, integer=True)

__all__ += list("abcdefghijklmnopqrstuvwxyz")

# -----------------------
# Roman (uppercase)
# -----------------------
for _ch in "ABCDEFGHIJKLOPQRSTUVWXYZ":
    globals()[_ch] = SymbolFamily(_ch)

for _ch in "MN":
    globals()[_ch] = SymbolFamily(_ch, integer=True)

# conventional function letters
for _ch in "FGH":
    globals()[_ch] = FunctionFamily(_ch)

__all__ += list("ABCDEFGHJKLMNOPQRSTUVWXYZ")

# -----------------------
# Greek (lowercase): SymPy canonical names (not LaTeX macros)
# -----------------------
alpha = SymbolFamily("alpha")
beta = SymbolFamily("beta")
gamma = SymbolFamily("gamma")
delta = SymbolFamily("delta")

epsilon = SymbolFamily("epsilon")
varepsilon = SymbolFamily("varepsilon")

zeta = SymbolFamily("zeta")
eta = SymbolFamily("eta")

theta = SymbolFamily("theta")
vartheta = SymbolFamily("vartheta")

kappa = SymbolFamily("kappa")
lam = SymbolFamily("lambda")  # "lambda" is a Python keyword
mu = SymbolFamily("mu")
nu = SymbolFamily("nu")
xi = SymbolFamily("xi")

rho = SymbolFamily("rho")

sigma = SymbolFamily("sigma")
varsigma = SymbolFamily("varsigma")
tau = SymbolFamily("tau")

phi = SymbolFamily("phi")
varphi = SymbolFamily("varphi")

chi = SymbolFamily("chi")
psi = SymbolFamily("psi")
omega = SymbolFamily("omega")

__all__ += [
    "alpha","beta","gamma","delta",
    "epsilon","varepsilon",
    "zeta","eta",
    "theta","vartheta",
    "kappa","lam","mu","nu","xi","rho",
    "sigma","varsigma","tau",
    "phi","varphi",
    "chi","psi","omega",
]

del _ch





class Infix:
    """Generic infix operator used as: a |OP| b."""
    __slots__ = ("func",)

    def __init__(self, func):
        """Store the binary callable implementing the infix operation."""
        self.func = func

    def __ror__(self, left):
        """Capture the left operand during ``a |op`` parsing."""
        return _InfixPartial(self.func, left)


class _InfixPartial:
    """Intermediate state object used to complete ``a |op| b`` expressions."""
    __slots__ = ("func", "left")

    def __init__(self, func, left):
        """Persist partial infix state until the right operand arrives."""
        self.func = func
        self.left = left

    def __or__(self, right):
        """Apply the infix callable to the captured operands."""
        return self.func(self.left, right)

eq = Infix(sp.Eq)
lt = Infix(sp.Lt)
le = Infix(sp.Le)
gt = Infix(sp.Gt)
ge = Infix(sp.Ge)
__all__+=["Infix", "eq", "lt", "le", "gt", "ge"]

## Demo:
# x, y = sp.symbols("x y")
# expr1 = x + 1
# expr2 = 2*y

# print(expr1 | eq | expr2)      # Eq(x + 1, 2*y)
# print((x**2) | eq | (y**2))    # Eq(x**2, y**2)


from IPython.display import Latex 
__all__+=["Latex"]

from pprint import pprint
__all__+=["pprint"]


def NIntegrate(expr, var_and_limits, binding=None):
    """Numerically integrate a symbolic or numeric 1D function.

    Parameters
    ----------
    expr:
        One of:

        - a SymPy expression,
        - a :class:`numpify.NumpifiedFunction`,
        - a :class:`numpify.BoundNumpifiedFunction`,
        - or a plain numeric callable ``f(x)``.
    var_and_limits:
        Tuple ``(x, a, b)`` where ``a``/``b`` are scalar bounds (including
        ``sympy.oo``/``-sympy.oo``). For plain numeric callables, ``x`` is
        ignored and only ``(a, b)`` are used.
    binding:
        Optional parameter source when ``expr`` needs extra arguments:

        - ``dict[Symbol, value]`` for explicit bindings,
        - ``SmartFigure`` for live figure-backed bindings,
        - ``None`` to use the current figure context when needed.

    Returns
    -------
    float
        Numeric integral value computed with ``scipy.integrate.quad``.
    """
    try:
        x, a, b = var_and_limits
    except Exception as exc:  # pragma: no cover - defensive shape validation
        raise TypeError("NIntegrate expects limits as a tuple: (x, a, b)") from exc

    try:
        from .numpify import (
            BoundNumpifiedFunction as _BoundNumpifiedFunction,
            NumpifiedFunction as _NumpifiedFunction,
            numpify_cached as _numpify_cached,
        )
        from .SmartFigure import current_figure as _current_figure
    except ImportError:
        from numpify import (
            BoundNumpifiedFunction as _BoundNumpifiedFunction,
            NumpifiedFunction as _NumpifiedFunction,
            numpify_cached as _numpify_cached,
        )
        from SmartFigure import current_figure as _current_figure

    from scipy.integrate import quad

    def _to_quad_limit(v):
        if v == sp.oo:
            return np.inf
        if v == -sp.oo:
            return -np.inf
        return float(sp.N(v))

    def _resolve_symbolic_callable(symbolic_expr, symbol):
        required_symbols = tuple(sorted((sp.sympify(symbolic_expr).free_symbols - {symbol}), key=lambda s: s.name))
        if not required_symbols:
            return _numpify_cached(symbolic_expr, args=symbol)

        if binding is None:
            fig = _current_figure(required=True)
            value_map = {sym: fig.parameters[sym].value for sym in required_symbols}
        elif isinstance(binding, dict):
            missing = [sym for sym in required_symbols if sym not in binding]
            if missing:
                names = ", ".join(sym.name for sym in missing)
                raise ValueError(f"binding is missing values for: {names}")
            value_map = {sym: binding[sym] for sym in required_symbols}
        elif hasattr(binding, "params"):
            value_map = {sym: binding.params[sym].value for sym in required_symbols}
        elif hasattr(binding, "parameters"):
            value_map = {sym: binding.parameters[sym].value for sym in required_symbols}
        else:
            raise TypeError(
                "binding must be dict[Symbol, value], SmartFigure-like provider, or None"
            )

        compiled = _numpify_cached(symbolic_expr, args=(symbol, *required_symbols))
        bound = compiled.bind(value_map)
        return bound

    if isinstance(expr, _BoundNumpifiedFunction):
        f = expr
    elif isinstance(expr, _NumpifiedFunction):
        if not expr.args:
            raise TypeError("NIntegrate requires an x argument for numpified functions")
        if len(expr.args) == 1:
            f = expr
        else:
            if binding is None:
                f = expr.bind(_current_figure(required=True))
            else:
                f = expr.bind(binding)
    elif isinstance(expr, sp.Basic):
        if not isinstance(x, sp.Symbol):
            raise TypeError(f"NIntegrate expects x to be a sympy Symbol for symbolic expressions, got {type(x)}")
        f = _resolve_symbolic_callable(expr, x)
    elif callable(expr):
        import inspect

        signature = inspect.signature(expr)
        positional = [
            param for param in signature.parameters.values()
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        required = [param for param in positional if param.default is inspect._empty]

        if len(required) <= 1:
            f = expr
        else:
            missing_count = len(required) - 1

            def _map_from_dict(source):
                values = []
                missing_names = []
                for param in required[1:]:
                    name = param.name
                    sym = sp.Symbol(name)
                    if name in source:
                        values.append(source[name])
                    elif sym in source:
                        values.append(source[sym])
                    else:
                        missing_names.append(name)
                if missing_names:
                    raise ValueError(
                        "binding is missing values for callable parameters: " + ", ".join(missing_names)
                    )
                return values

            if binding is None:
                fig = _current_figure(required=True)
                value_list = []
                missing_names = []
                for param in required[1:]:
                    sym = sp.Symbol(param.name)
                    if sym in fig.parameters:
                        value_list.append(fig.parameters[sym].value)
                    else:
                        missing_names.append(param.name)
                if missing_names:
                    raise ValueError(
                        "current figure is missing callable parameters: " + ", ".join(missing_names)
                    )
            elif isinstance(binding, dict):
                value_list = _map_from_dict(binding)
            elif hasattr(binding, "params"):
                value_list = []
                missing_names = []
                for param in required[1:]:
                    sym = sp.Symbol(param.name)
                    if sym in binding.params:
                        value_list.append(binding.params[sym].value)
                    else:
                        missing_names.append(param.name)
                if missing_names:
                    raise ValueError(
                        "binding provider is missing callable parameters: " + ", ".join(missing_names)
                    )
            elif hasattr(binding, "parameters"):
                value_list = []
                missing_names = []
                for param in required[1:]:
                    sym = sp.Symbol(param.name)
                    if sym in binding.parameters:
                        value_list.append(binding.parameters[sym].value)
                    else:
                        missing_names.append(param.name)
                if missing_names:
                    raise ValueError(
                        "binding provider is missing callable parameters: " + ", ".join(missing_names)
                    )
            else:
                raise TypeError(
                    "binding must be dict, SmartFigure-like provider, or None for callable expr"
                )

            if len(value_list) < missing_count:
                raise ValueError(
                    f"binding did not satisfy callable parameters: expected {missing_count}, got {len(value_list)}"
                )

            def f(t):
                return expr(t, *value_list)
    else:
        raise TypeError(f"Unsupported expr type for NIntegrate: {type(expr)}")

    def _integrand(t):
        return float(np.asarray(f(t)))

    value, _error = quad(_integrand, _to_quad_limit(a), _to_quad_limit(b))
    return value


__all__ += ["NIntegrate"]

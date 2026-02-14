"""Notebook-friendly symbolic-math prelude and convenience exports.

This module is intentionally focused on setting up an exploratory namespace
(NumPy/SymPy shortcuts, symbol/function families, and convenience operators).
Higher-level numeric helpers are implemented in ``prelude_extensions`` and
re-exported here for notebook ergonomics.
"""

from __future__ import annotations

__all__ = []

# --- core math namespace ---
import sympy as sp
__all__ += ["sp"]
from sympy import *
__all__ += list(getattr(sp, "__all__", []))

import numpy as np
__all__ += ["np"]

try:
    import pandas as pd
except ModuleNotFoundError:  # Optional dependency in lean environments.
    pd = None
else:
    __all__ += ["pd"]

# --- prelude extensions (moved out for maintainability) ---
try:
    from .prelude_extensions import (
        FunctionFamily,
        Infix,
        NIntegrate,
        NReal_Fourier_Series,
        SymbolFamily,
        eq,
        ge,
        gt,
        le,
        lt,
        play,
    )
except ImportError:  # pragma: no cover
    from prelude_extensions import (
        FunctionFamily,
        Infix,
        NIntegrate,
        NReal_Fourier_Series,
        SymbolFamily,
        eq,
        ge,
        gt,
        le,
        lt,
        play,
    )

__all__ += [
    "SymbolFamily",
    "FunctionFamily",
    "Infix",
    "eq",
    "lt",
    "le",
    "gt",
    "ge",
    "NIntegrate",
    "NReal_Fourier_Series",
    "play",
]

# -----------------------
# Roman (lowercase)
# -----------------------
for _ch in "abcdefghijklmnopqrstuvwxyz":
    globals()[_ch] = SymbolFamily(_ch)

# conventional function letters
for _ch in "fgh":
    globals()[_ch] = FunctionFamily(_ch)

# conventional integer indices
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

for _ch in "FGH":
    globals()[_ch] = FunctionFamily(_ch)

__all__ += list("ABCDEFGHJKLMNOPQRSTUVWXYZ")

# -----------------------
# Greek (lowercase): SymPy canonical names
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
lam = SymbolFamily("lambda")
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
    "alpha", "beta", "gamma", "delta",
    "epsilon", "varepsilon",
    "zeta", "eta",
    "theta", "vartheta",
    "kappa", "lam", "mu", "nu", "xi", "rho",
    "sigma", "varsigma", "tau",
    "phi", "varphi",
    "chi", "psi", "omega",
]

del _ch

from IPython.display import HTML, Latex, display
__all__ += ["HTML", "Latex", "display"]

from pprint import pprint
__all__ += ["pprint"]

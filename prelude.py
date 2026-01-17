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


class SymbolFamily:
    def __init__(self, name: str, cls=None,**kwargs):
        self.name = name
        self._kwargs = kwargs
        self._base = sp.Symbol(name, **self._kwargs)
        self._cache = {}

        if cls is None or cls is sp.Symbol:
            self._factory = lambda s: sp.Symbol(s, **self._kwargs)
        elif cls is sp.Function:
            self._factory = lambda s: sp.Function(s, **self._kwargs)
        else:
            raise TypeError(
                f"Unsupported cls={cls!r}. Use cls=sp.Symbol (default) or cls=sp.Function."
            )


    def _sympy_(self):
        # lets SymPy convert `a` to Symbol('a') when needed
        return self._base

    def __getitem__(self, k):
        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._cache:
            sub = ",".join(map(str, k))
            self._cache[k] = sp.Symbol(f"{self.name}_{sub}", **self._kwargs)
        return self._cache[k]

    # Optional: make printing in plain Python show `a`
    def __repr__(self):
        return repr(self._base)

    def __str__(self):
        return str(self._base)
    
__all__+=["SymbolFamily"]
a = SymbolFamily('a')
b = SymbolFamily('b')
c = SymbolFamily('c')


x = SymbolFamily('x')
y = SymbolFamily('y')
z = SymbolFamily('z')
t = SymbolFamily('t')
__all__+=["a","b","c","x","y","z","t"]


k = SymbolFamily("k", integer=True)
l = SymbolFamily("l", integer=True)
m = SymbolFamily("m", integer=True)
n = SymbolFamily("n", integer=True)
__all__+=["k","l","m","n"]

f=SymbolFamily("f",cls=sp.Function)
g=SymbolFamily("g",cls=sp.Function)
h=SymbolFamily("h",cls=sp.Function)
__all__+=["f","g","h"]




from IPython.display import Latex 
__all__+=["Latex"]


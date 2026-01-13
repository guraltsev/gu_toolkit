"""
NamedFunction: Dynamic SymPy Function Generation
===================================================

This module provides the `NamedFunction` decorator to convert standard Python 
functions or classes into full-fledged SymPy Function classes with enhanced documentation.
"""
__gu_exports__ = ['NamedFunction']
__gu_priority__ = 200
__gu_enabled__ = True


import inspect
import textwrap
import sys
from typing import Any, Callable, Optional, Type, Union, Tuple

import sympy as sp
import numpy as np

__all__ = ["NamedFunction"]

# Common Greek letters to avoid wrapping in \mathrm
_GREEK_LETTERS = {
    'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'iota', 'kappa', 
    'lambda', 'mu', 'nu', 'xi', 'omicron', 'pi', 'rho', 'sigma', 'tau', 'upsilon', 
    'phi', 'chi', 'psi', 'omega', 'Gamma', 'Delta', 'Theta', 'Lambda', 'Xi', 'Pi', 
    'Sigma', 'Upsilon', 'Phi', 'Psi', 'Omega'
}

# --- Metaclass Fix for Signature ---
# SymPy's FunctionClass has a read-only __signature__ property.
# We must derive a new metaclass to override it.
class _SignedFunctionMeta(type(sp.Function)):
    """
    A custom metaclass that inherits from SymPy's FunctionClass.
    It overrides __signature__ to allow us to inject the real function signature
    so that inspect.signature(MyFunction) works correctly.
    """
    @property
    def __signature__(cls):
        return getattr(cls, '_custom_signature', None)


def NamedFunction(obj: Union[Callable, Type]) -> Type[sp.Function]:
    """
    Decorator that converts a Python function OR a class into a dynamic SymPy Function class.
    
    Mode 1: Function Decorator
    --------------------------
    Used when the symbolic definition is sufficient, or when no specific numerical 
    implementation is required.
    
    >>> @NamedFunction
    ... def F(x):
    ...     return x * 2

    Mode 2: Class Decorator
    -----------------------
    Used when you need to provide a specific, vectorized numerical implementation 
    (e.g., for performance or opaque functions) alongside the symbolic definition.
    
    The class MUST define exactly two methods:
    1. `symbolic(self, *args)`: Returns SymPy expression or None.
    2. `numeric(self, *args)`: Returns NumPy array.
    """
    if inspect.isclass(obj):
        return _handle_class_decoration(obj)
    elif callable(obj):
        return _handle_function_decoration(obj)
    else:
        raise TypeError(f"@NamedFunction must decorate a function or a class, not {type(obj)}")


def _generate_enhanced_docstring(original_doc: Optional[str], 
                                 expansion_str: str, 
                                 latex_str: str,
                                 has_custom_numeric: bool) -> str:
    """
    Helper to build a rich docstring compatible with standard help parsers (Google/NumPy style).
    It places the original docstring first, followed by a 'NamedFunction notes' section containing 
    the dynamic properties.
    """
    doc = []
    
    # 1. User Documentation (Primary)
    if original_doc:
        doc.append(inspect.cleandoc(original_doc))
    else:
        doc.append("No user documentation provided.")

    # 2. Notes Section (recognized by SmartHelp as a specific card)
    doc.append("\n## NamedFunction notes\n")
    doc.append("\n-----\n")
    
    # Numerical Status
    doc.append("- **Numerical Implementation**:\n")
    if has_custom_numeric:
        doc.append("    PRESENT. This function has a dedicated `f_numpy` method for fast vectorized execution.")
    else:
        doc.append("    ABSENT. No custom implementation provided; falls back to SymPy's `lambdify`.")

    # Symbolic Status
    doc.append("- **Symbolic Expansion**:\n")
    doc.append("    To view the underlying symbolic definition programmatically, apply the rewrite method:")
    doc.append("    ```python")
    doc.append("    expr.rewrite(\"expand_definition\")")
    doc.append("    ```")

    # Definition Display
    doc.append("- **Current Definition**:\n")
    doc.append(f"    {expansion_str}\n")
    
    # LaTeX Display
    if latex_str:
        doc.append(f"    $ {latex_str} $")

    return "\n".join(doc)


def _get_smart_latex_symbol(name: str) -> sp.Symbol:
    """
    Creates a SymPy symbol with smart LaTeX formatting.
    - Standard Greek letters are left alone (\alpha).
    - Single letters are left alone (x).
    - Multi-letter words are wrapped in \\mathrm{word}.
    - Handles subscripts (x_val -> \\mathrm{x}_{val}).
    """
    if not name:
        return sp.Symbol(name)

    # Check for subscripts
    if '_' in name:
        parts = name.split('_', 1)
        head, sub = parts[0], parts[1]
    else:
        head, sub = name, None

    # Process Head
    if len(head) > 1 and head not in _GREEK_LETTERS:
        tex_head = f"\\mathrm{{{head}}}"
    else:
        # If it's greek, SymPy handles it automatically if we don't specify latex_name
        # But if we specify latex_name for the whole thing (to handle subscript), we need the backslash
        tex_head = f"\\{head}" if head in _GREEK_LETTERS else head

    # Reassemble
    if sub:
        tex = f"{tex_head}_{{{sub}}}"
    else:
        tex = tex_head

    return sp.Symbol(name, latex_name=tex)


def _compute_symbolic_representation(func: Callable, 
                                     nargs: int, 
                                     func_name: str,
                                     is_method: bool = False) -> Tuple[str, str]:
    """
    Generates generic symbols (using actual argument names if possible), 
    calls the function, and returns the string and LaTeX representation of the result.
    """
    # 1. Inspect signature to get meaningful symbol names
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        
        # Skip 'self' if it's a method
        start_idx = 1 if is_method else 0
        
        if len(params) > start_idx:
            # Use the actual argument names from the definition
            sym_names = [p.name for p in params[start_idx:]]
            # Handle *args if present
            if any(p.kind == p.VAR_POSITIONAL for p in params):
                syms = tuple(_get_smart_latex_symbol(f'x_{i}') for i in range(nargs))
            else:
                syms = tuple(_get_smart_latex_symbol(name) for name in sym_names)
        else:
            # Fallback if signature extraction fails or is empty
            if nargs == 1:
                syms = (_get_smart_latex_symbol('x'),)
            elif nargs == 2:
                syms = (_get_smart_latex_symbol('x'), _get_smart_latex_symbol('y'))
            else:
                syms = tuple(_get_smart_latex_symbol(f'arg_{i}') for i in range(nargs))
    except Exception:
         syms = tuple(_get_smart_latex_symbol(f'arg_{i}') for i in range(nargs))

    # 2. Call the function to get the expression
    try:
        if is_method:
            # We pass a Dummy object as 'self'
            dummy_self = sp.Dummy("self")
            result = func(dummy_self, *syms)
        else:
            result = f"{func(*syms)}"
            
        if result == "None":
            return "`None` (Opaque function)",""
        
        # 3. Format the result
        # String representation
        args_str = ", ".join(str(s) for s in syms)
        str_repr = f"`{func_name}({args_str}) = {result}`"
        
        # LaTeX representation
        # Display as func_name(args) = rhs
        latex_rhs = sp.latex(result)
        latex_args = ", ".join(sp.latex(s) for s in syms)
        
        # Format the function name itself for LaTeX
        if len(func_name) > 1 and func_name not in _GREEK_LETTERS:
            latex_func_name = f"\\mathrm{{{func_name}}}"
        elif func_name in _GREEK_LETTERS:
            latex_func_name = f"\\{func_name}"
        else:
            latex_func_name = func_name
            
        latex_repr = f"{latex_func_name}({latex_args}) = {latex_rhs}"
        
        return str_repr, latex_repr
        
    except Exception as e:
        return f"Could not expand definition automatically.\nError: {e}", ""


def _handle_function_decoration(func: Callable) -> Type[sp.Function]:
    """Logic for decorating a standalone function."""
    
    sig = inspect.signature(func)
    nargs = len(sig.parameters)
    
    # Define the rewrite hook
    def _eval_rewrite_as_expand_definition(self, *args, **kwargs):
        result = func(*args)
        if result is None or result == self:
            return self
        return result

    # Define the evalf hook
    def _eval_evalf(self, prec):
        rewritten = self.rewrite("expand_definition")
        if rewritten == self:
            return self
        return rewritten.evalf(prec)

    # Check if custom numpy function was attached prior to decoration
    has_numpy = hasattr(func, "f_numpy")

    # Compute symbolic expansion string
    expansion_str, latex_str = _compute_symbolic_representation(
        func, nargs, func_name=func.__name__, is_method=False
    )

    # Generate enhanced docstring
    new_doc = _generate_enhanced_docstring(
        original_doc=func.__doc__,
        expansion_str=expansion_str,
        latex_str=latex_str,
        has_custom_numeric=has_numpy
    )

    class_dict = {
        "nargs": nargs,
        "_eval_rewrite_as_expand_definition": _eval_rewrite_as_expand_definition,
        "_eval_evalf": _eval_evalf,
        "__module__": func.__module__,
        "__doc__": new_doc,
        "_original_func": staticmethod(func),
        "f_numpy": getattr(func, "f_numpy", None)
    }

    # Create the class using our custom metaclass to support signature overriding
    NewClass = _SignedFunctionMeta(func.__name__, (sp.Function,), class_dict)
    
    # Store the signature on the class for the metaclass property to find
    NewClass._custom_signature = sig
    
    return NewClass


def _handle_class_decoration(cls: Type) -> Type[sp.Function]:
    """Logic for decorating a class definition containing symbolic and numeric specs."""
    
    # 1. Validation
    if not hasattr(cls, 'symbolic') or not hasattr(cls, 'numeric'):
        raise ValueError(
            f"Class {cls.__name__} decorated with @NamedFunction must define "
            "both 'symbolic' and 'numeric' methods."
        )

    symbolic_func = getattr(cls, 'symbolic')
    numeric_func = getattr(cls, 'numeric')

    sig_sym = inspect.signature(symbolic_func)
    sig_num = inspect.signature(numeric_func)
    
    if len(sig_sym.parameters) != len(sig_num.parameters):
        raise ValueError(
            f"Signature mismatch in {cls.__name__}: 'symbolic' takes {len(sig_sym.parameters)} args "
            f"but 'numeric' takes {len(sig_num.parameters)} args."
        )

    nargs = len(sig_sym.parameters) - 1
    if nargs < 0:
        raise ValueError(f"{cls.__name__}.symbolic must accept at least 'self'.")

    # 2. Define the rewrite hook
    def _eval_rewrite_as_expand_definition(self, *args, **kwargs):
        result = symbolic_func(self, *args)
        if result is None:
            return self
        if result == self:
            return self
        return result

    # 3. Define the evalf hook
    def _eval_evalf(self, prec):
        rewritten = self.rewrite("expand_definition")
        if rewritten == self:
            return self
        return rewritten.evalf(prec)

    # 4. Define the static numeric implementation
    @staticmethod
    def f_numpy_impl(*args):
        return numeric_func(None, *args)

    # 5. Compute symbolic expansion string
    # We pass is_method=True so it handles the 'self' argument
    expansion_str, latex_str = _compute_symbolic_representation(
        symbolic_func, nargs, func_name=cls.__name__, is_method=True
    )

    # 6. Generate enhanced docstring
    new_doc = _generate_enhanced_docstring(
        original_doc=cls.__doc__,
        expansion_str=expansion_str,
        latex_str=latex_str,
        has_custom_numeric=True
    )

    class_dict = {
        "nargs": nargs,
        "_eval_rewrite_as_expand_definition": _eval_rewrite_as_expand_definition,
        "_eval_evalf": _eval_evalf,
        "__module__": cls.__module__,
        "__doc__": new_doc,
        "f_numpy": f_numpy_impl,
        "_original_class": cls
    }
    
    # Create the class using our custom metaclass
    NewClass = _SignedFunctionMeta(cls.__name__, (sp.Function,), class_dict)
    
    # Fix the signature. We extract it from the 'symbolic' method,
    # stripping the 'self' parameter to match the resulting Function usage.
    params = list(sig_sym.parameters.values())
    new_params = params[1:] # Skip self
    new_sig = sig_sym.replace(parameters=new_params)
    
    # Store the signature on the class
    NewClass._custom_signature = new_sig

    return NewClass


if __name__ == "__main__":
    # Small demo to verify the docstring output
    print("--- Test: Function Mode Docstring ---")
    @NamedFunction
    def Square(x_val):
        """Returns the square of x_val."""
        return x_val**2 + 1
        
    print(Square.__doc__)
    print(f"Signature: {inspect.signature(Square)}")
    
    print("\n\n--- Test: Class Mode Docstring ---")
    @NamedFunction
    class AdvancedSin:
        """
        A custom sine function.
        It behaves like normal sine symbolically but wraps numpy for arrays.
        """
        def symbolic(self, theta_rad):
            # Using 'theta' to test variable name extraction
            return sp.sin(theta_rad) / theta_rad
            
        def numeric(self, theta_rad):
            return np.sin(theta_rad) / theta_rad
            
    print(AdvancedSin.__doc__)
    print(f"Signature: {inspect.signature(AdvancedSin)}")

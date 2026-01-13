"""
SmartException.py: The Intelligent Error Coach
=================================================
A pluggable exception handler using a hierarchical diagnosis framework.
It detects errors ranging from generic input issues to specific typos
and logic gaps, prioritizing the most helpful diagnosis.

Features:
- Hierarchical Diagnosis: Generic -> Specific -> Very Specific
- Fuzzy Matching: Detects typos (e.g., 'integrat' vs 'integrate')
- Case Sensitivity: Detects 'X' vs 'x'
- Modern Support: Utilizes Python 3.10+ error attributes
- Dark Mode Safe: High-contrast, opaque UI cards
- Markdown Support: Explanations and Hints render Markdown
"""
__gu_exports__ = ["GuideError"]
__gu_priority__ = 200
__gu_enabled=True
__all__=["GuideError"]


import sys
import traceback
import html
import re
import difflib
from typing import List, Dict, Any, Tuple, Optional
from ipywidgets import Button, VBox, HBox, Output, Layout, HTML
from IPython.display import display

# Try importing markdown for rich text support
try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


# --- 1. The Custom "Teachable" Exception ---
class GuideError(Exception):
    """
    Raise this exception for 100% confidence feedback.
    Example: raise GuideError("Don't do that!", hint="Do this instead.")
    """
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


# --- 2. The Diagnosis Framework ---

class Diagnosis:
    """
    Abstract Base Class for all error diagnoses.
    
    To add a new heuristic, inherit from this class and override:
      1. _check_condition: returns a confidence score (0.0 - 1.0).
      2. _generate_info: returns (Title, Explanation, Hint).
    """
    
    def run(self, etype, evalue, tb, code, user_ns) -> Optional[Dict[str, Any]]:
        """
        Public execution method. 
        Runs the check and returns the result dict if confidence > 0.
        """
        try:
            self._reset_state()
            confidence = self._check_condition(etype, evalue, tb, code, user_ns)
            if confidence > 0:
                title, expl, hint = self._generate_info(evalue, code, user_ns)
                return {
                    "confidence": confidence,
                    "title": title,
                    "explanation": expl,
                    "hint": hint
                }
        except Exception:
            # Diagnostics must never crash the handler
            return None
        return None

    def _reset_state(self):
        """Optional hook to clear state between runs."""
        pass

    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        """
        Analyze the exception.
        Returns: Float between 0.0 (no match) and 1.0 (certainty).
        """
        return 0.0

    def _generate_info(self, evalue, code, user_ns) -> Tuple[str, str, str]:
        """
        Construct the feedback.
        Returns: (Title, Explanation, Hint)
        """
        return ("Unknown Issue", "No explanation available.", "")


# Registry List
_DIAGNOSIS_CLASSES: List[Diagnosis] = []

def register_diagnosis(cls):
    """Decorator to register a Diagnosis class."""
    _DIAGNOSIS_CLASSES.append(cls())
    return cls


# --- 3. The Logic Core (Modernized) ---

def _analyze_exception(etype, evalue, tb) -> List[dict]:
    # 1. Filter Traceback to find user's line
    # We ignore standard library paths and our own internal files
    IGNORED_FILES = {
        "gu_SmartFigure.py", "gu_numpify.py", "gu_NamedSympyFunction.py", 
        "gu_SmartException.py", "gu_doc.py", "gu_context.py"
    }
    
    records = traceback.extract_tb(tb)
    user_frame = None
    
    # A. Search for the last valid user frame
    for frame in reversed(records):
        filename = frame.filename
        if "site-packages" in filename or "dist-packages" in filename: continue
        if any(ign in filename for ign in IGNORED_FILES): continue
        user_frame = frame
        break
    
    if not user_frame and records:
        user_frame = records[-1] # Fallback

    # 2. Extract Code and Caret Location
    code_line = ""
    caret_string = ""
    lineno = "?"
    
    def make_carets(start, end):
        if start is None: return ""
        end = end or (start + 1)
        length = max(1, end - start)
        return " " * start + "^" * length

    try:
        # Case A: SyntaxErrors (The info is on the exception object)
        if isinstance(evalue, SyntaxError) and evalue.text:
            code_line = evalue.text.rstrip('\n')
            lineno = evalue.lineno
            # SyntaxError offsets are 1-based
            offset = (evalue.offset or 1) - 1
            end_offset = (evalue.end_offset or offset + 1) - 1
            caret_string = make_carets(offset, end_offset)

        # Case B: Runtime Errors (The info is in the frame, Python 3.11+)
        elif user_frame:
            code_line = user_frame.line or ""
            lineno = user_frame.lineno
            # FrameSummary offsets are 0-based
            col = getattr(user_frame, 'colno', None)
            end_col = getattr(user_frame, 'end_colno', None)
            caret_string = make_carets(col, end_col)
            
        # 3. Handle Indentation (Strip leading whitespace for display, sync carets)
        if code_line:
            stripped_code = code_line.lstrip()
            indent_len = len(code_line) - len(stripped_code)
            
            # Update code to display
            code_line = stripped_code
            
            # Shift carets left by the same amount
            if len(caret_string) > indent_len:
                caret_string = caret_string[indent_len:]
            else:
                caret_string = "" # Carets pointed to the whitespace we stripped

    except Exception:
        pass

    # 3. Get User Namespace
    try:
        from IPython import get_ipython
        ip = get_ipython()
        user_ns = ip.user_ns if ip else {}
    except (ImportError, AttributeError):
        user_ns = {}

    candidates = []

    # A. Explicit GuideError
    if isinstance(evalue, GuideError):
        candidates.append({
            "confidence": 1.0,
            "title": "Guidance",
            "explanation": str(evalue),
            "hint": evalue.hint,
            "line": code_line,
            "caret": caret_string,
            "lineno": lineno
        })
        return candidates

    # B. Run Framework Heuristics
    for diagnoser in _DIAGNOSIS_CLASSES:
        result = diagnoser.run(etype, evalue, tb, code_line, user_ns)
        if result:
            result['line'] = code_line
            result['caret'] = caret_string
            result['lineno'] = lineno
            candidates.append(result)

    # C. Default Fallback
    candidates.append({
        "confidence": 0.0,
        "title": f"Exception: {etype.__name__}",
        "explanation": f"An error occurred: {html.escape(str(evalue))}",
        "hint": "Check the Details below.",
        "line": code_line,
        "caret": caret_string,
        "lineno": lineno
    })

    candidates.sort(key=lambda x: x['confidence'], reverse=True)
    return candidates


# --- 4. Pluggable Heuristics (Hierarchy) ---

@register_diagnosis
class InputIncomplete(Diagnosis):
    """
    Detects when code ends prematurely (missing closing paren/bracket/quote).
    """
    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        # Check 1: IPython specific incomplete input
        if etype.__name__ == "_IncompleteInputError":
            return 0.99
        # Check 2: Standard SyntaxError EOF
        if isinstance(evalue, SyntaxError) and "unexpected EOF" in str(evalue):
            return 0.95
        return 0.0

    def _generate_info(self, evalue, code, user_ns):
        return (
            "Missing Closing Symbol",
            "Python reached the end of your code but was expecting more. This almost always means you have an unclosed parenthesis `(`, bracket `[`, curly brace `{`, or string quote.",
            "Check the end of the highlighted block for a missing `)` or `]`."
        )

@register_diagnosis
class InputIssue(Diagnosis):
    """
    ROOT CATEGORY: Checks if the error occurred directly in the user's cell.
    """
    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        depth = 0
        curr = tb
        first_frame = None
        while curr:
            if depth == 0: first_frame = curr.tb_frame
            depth += 1
            curr = curr.tb_next
        
        # In IPython, depth 2 usually means: Level 1 shell -> Level 2 user cell
        if depth == 2 and first_frame:
            fname = first_frame.f_code.co_filename
            if "interactiveshell.py" in fname:
                return 0.1 # Baseline for user error
        return 0.0

    def _generate_info(self, evalue, code, user_ns):
        return (
            "Input Issue",
            "The execution stopped directly in your cell code. This is usually due to a typo or syntax mismatch.",
            "Review the highlighted line."
        )

@register_diagnosis
class InputNameError(InputIssue):
    """
    SPECIFIC CATEGORY: Input Issues that are specifically NameErrors.
    """
    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        parent_conf = super()._check_condition(etype, evalue, tb, code, user_ns)
        if parent_conf == 0.0: return 0.0
            
        if isinstance(evalue, NameError):
            return 0.25
        return 0.0

    def _generate_info(self, evalue, code, user_ns):
        return (
            "Undefined Variable",
            f"Python cannot find the variable definition. **{html.escape(str(evalue))}**.",
            "Did you define it in a previous cell?"
        )

@register_diagnosis
class InputCaseTypo(InputNameError):
    """
    HIGHLY SPECIFIC: NameErrors caused by capitalization (e.g., 'X' vs 'x').
    """
    def _reset_state(self):
        self.missing_name = None
        self.suggestion = None

    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        if super()._check_condition(etype, evalue, tb, code, user_ns) == 0.0:
            return 0.0

        # Robust Name Extraction (Python 3.10+ support)
        if hasattr(evalue, 'name'):
            missing = evalue.name
        else:
            match = re.search(r"name '(\w+)' is not defined", str(evalue))
            if not match: return 0.0
            missing = match.group(1)
        
        # Check case-insensitive match
        # Optimize: Filter user_ns to avoid iterating over huge modules
        candidates = [k for k in user_ns.keys() if not k.startswith('_')]
        missing_lower = missing.lower()
        
        for cand in candidates:
            if cand.lower() == missing_lower:
                self.missing_name = missing
                self.suggestion = cand
                return 0.95 # Very high confidence
            
        return 0.0

    def _generate_info(self, evalue, code, user_ns):
        return (
            "Capitalization Error",
            f"You typed `{self.missing_name}`, but defined `{self.suggestion}`.",
            f"Python is case-sensitive. Change it to `{self.suggestion}`."
        )

@register_diagnosis
class InputFuzzyTypo(InputNameError):
    """
    HIGHLY SPECIFIC: NameErrors caused by typos (e.g., 'integrat' vs 'integrate').
    Uses difflib for fuzzy matching.
    """
    def _reset_state(self):
        self.missing_name = None
        self.suggestion = None

    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        if super()._check_condition(etype, evalue, tb, code, user_ns) == 0.0:
            return 0.0

        if hasattr(evalue, 'name'):
            missing = evalue.name
        else:
            match = re.search(r"name '(\w+)' is not defined", str(evalue))
            if not match: return 0.0
            missing = match.group(1)

        # Fuzzy match
        candidates = [k for k in user_ns.keys() if not k.startswith('_')]
        matches = difflib.get_close_matches(missing, candidates, n=1, cutoff=0.7)
        
        if matches:
            self.missing_name = missing
            self.suggestion = matches[0]
            # Lower confidence than exact case match so CaseMatch wins if both are valid
            return 0.60 
            
        return 0.0

    def _generate_info(self, evalue, code, user_ns):
        return (
            "Possible Typo",
            f"Variable `{self.missing_name}` is not defined.",
            f"Did you mean `{self.suggestion}`?"
        )


@register_diagnosis
class DictKeyError(Diagnosis):
    """
    Diagnoses KeyErrors, offering "Did you mean?" suggestions 
    by inspecting the dictionary keys for typos or case mismatches.
    """
    def _reset_state(self):
        self.missing_key = None
        self.suggestion = None
        self.dict_name = None
        self.issue_type = "missing" # 'missing', 'case', 'typo'

    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        if not isinstance(evalue, KeyError):
            return 0.0
        
        # Extract the raw key from the exception args
        # KeyError('foo') -> args[0] is 'foo'
        if not evalue.args: return 0.5
        raw_key = evalue.args[0]
        self.missing_key = raw_key

        # Attempt to find the dictionary variable name in the code line
        # Regex looks for: variable_name[
        match = re.search(r"([a-zA-Z_]\w*)\s*\[", code)
        
        if match:
            name = match.group(1)
            # Ensure the variable exists in user namespace and is dict-like
            if name in user_ns and hasattr(user_ns[name], "keys"):
                self.dict_name = name
                # Get actual keys safely
                try:
                    keys = list(user_ns[name].keys())
                except Exception:
                    keys = []
                
                # 1. Check for Case Sensitivity (Strings only)
                if isinstance(raw_key, str):
                    for k in keys:
                        if isinstance(k, str) and k.lower() == raw_key.lower():
                            self.suggestion = k
                            self.issue_type = "case"
                            return 0.95 # High confidence

                # 2. Check for Fuzzy Typos (String conversion)
                # We map string representations back to original keys for the suggestion
                str_keys_map = {str(k): k for k in keys}
                str_raw = str(raw_key)
                
                matches = difflib.get_close_matches(str_raw, str_keys_map.keys(), n=1, cutoff=0.6)
                
                if matches:
                    self.suggestion = str_keys_map[matches[0]]
                    self.issue_type = "typo"
                    return 0.85 # Good confidence
        
        # 3. Generic KeyError (Code line didn't reveal a dict variable or no matches found)
        return 0.5

    def _generate_info(self, evalue, code, user_ns):
        # Format keys with quotes if strings, otherwise standard repr
        key_disp = repr(self.missing_key)
        
        if self.issue_type == "case":
            sug_disp = repr(self.suggestion)
            return (
                "Key Capitalization Error",
                f"The key `{key_disp}` was not found in `{self.dict_name}`.",
                f"Did you mean `{sug_disp}`? Dictionary keys are case-sensitive."
            )
        elif self.issue_type == "typo":
            sug_disp = repr(self.suggestion)
            return (
                "Key Typo",
                f"The key `{key_disp}` was not found in `{self.dict_name}`.",
                f"Did you mean `{sug_disp}`?"
            )
        else:
            # Generic
            context = f" in `{self.dict_name}`" if self.dict_name else ""
            return (
                "Missing Key",
                f"The key `{key_disp}` does not exist{context}.",
                "Check the available keys or use `.get()` to handle missing values."
            )

# --- 5. Math Specific Heuristics ---

@register_diagnosis
class MathSyntaxCaret(Diagnosis):
    """Detects usage of ^ for power."""
    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        if "^" in code and "unsupported operand" in str(evalue):
            return 0.9
        return 0.0

    def _generate_info(self, evalue, code, user_ns):
        return (
            "Syntax: Powers",
            "It looks like you used `^` for power.",
            "Use `**` instead (e.g. `x**2`)."
        )

@register_diagnosis
class MathSyntaxImplicitMult(Diagnosis):
    """Detects 2x instead of 2*x."""
    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        if isinstance(evalue, SyntaxError) and re.search(r"\d[a-zA-Z]", code):
            return 0.85
        return 0.0

    def _generate_info(self, evalue, code, user_ns):
        return (
            "Syntax: Multiplication",
            "It looks like you wrote something like `2x`.",
            "Python requires the star for multiplication: `2*x`."
        )

@register_diagnosis
class MissingImport(Diagnosis):
    """Detects missing common math functions."""
    def _reset_state(self):
        self.missing_name = None

    def _check_condition(self, etype, evalue, tb, code, user_ns) -> float:
        if isinstance(evalue, NameError):
            if hasattr(evalue, 'name'):
                name = evalue.name
            else:
                match = re.search(r"name '(\w+)' is not defined", str(evalue))
                name = match.group(1) if match else None

            if name in ['sin', 'cos', 'tan', 'exp', 'log', 'sqrt', 'pi', 'inf']:
                self.missing_name = name
                return 0.95
        return 0.0

    def _generate_info(self, evalue, code, user_ns):
        return (
            "Missing Prefix",
            f"Python doesn't know `{self.missing_name}` directly.",
            f"Try `sp.{self.missing_name}` or `np.{self.missing_name}`."
        )


# --- 6. The UI Renderer (Dark Mode Safe) ---

def smart_exception_handler(shell, etype, evalue, tb, tb_offset=None):
    
    candidates = _analyze_exception(etype, evalue, tb)
    
    # UI Containers
    out_card = Output()
    nav_container = HBox(layout=Layout(margin='5px 0 10px 0', flex_flow='row wrap', align_items='baseline'))
    
    state = {'current_idx': 0}

    def render_view():
        idx = state['current_idx']
        data = candidates[idx]
        
        with out_card:
            out_card.clear_output()
            _render_html_card(data)
            
        buttons = []
        if len(candidates) > 1:
            label = HTML('<span style="color:#666; margin-right:8px; font-size:0.9em;">Or maybe:</span>')
            buttons.append(label)
            
            for i, cand in enumerate(candidates):
                is_active = (i == idx)
                
                # Active: Subtle highlight
                if is_active:
                    bg_color = "#E1F5FE" # Light Blue
                    text_weight = "bold"
                    border_val = "1px solid #B3E5FC"
                else:
                    bg_color = "transparent"
                    text_weight = "normal"
                    border_val = "1px solid transparent"

                b = Button(
                    description=cand['title'], 
                    layout=Layout(width='auto', height='28px', border=border_val, margin='0 2px'),
                    style={'button_color': bg_color, 'font_weight': text_weight},
                    tooltip=f"Switch to diagnosis: {cand['title']}"
                )
                
                def on_click(btn, target_i=i):
                    state['current_idx'] = target_i
                    render_view()
                    
                b.on_click(on_click)
                buttons.append(b)
                
        nav_container.children = tuple(buttons)

    render_view()

    # Debug Section (Bottom)
    out_debug = Output(layout={'display': 'none', 'border': '1px solid #ddd', 'padding': '10px', 'margin_top': '5px', 'background_color': '#f9f9f9'})
    with out_debug:
        traceback.print_exception(etype, evalue, tb)
    
    btn_debug = Button(
        description="▶ Details",
        layout=Layout(width='auto', border='none', margin='0', padding='0', height='auto'),
        style={'button_color': 'transparent', 'text_color': '#555', 'font_weight': 'normal'},
        tooltip="Show technical details (Collapsed)"
    )
    
    def toggle_debug(b):
        if out_debug.layout.display == 'none':
            out_debug.layout.display = 'block'
            b.description = "▼ Details"
        else:
            out_debug.layout.display = 'none'
            b.description = "▶ Details"
            
    btn_debug.on_click(toggle_debug)

    display(out_card)
    display(nav_container)
    display(VBox([btn_debug, out_debug], layout=Layout(align_items='flex-start', margin='0')))

def _render_html_card(data):
    """Renders the HTML for the currently selected diagnosis."""
    conf = data['confidence']
    
    # Accessible Color Palette
    if conf == 1.0:
        border = "#0277BD"
        bg = "#E1F5FE"
        icon = "🎓"
    elif conf > 0.4:
        border = "#FF8F00"
        bg = "#FFF8E1"
        icon = "💡"
    elif conf > 0.05:
        border = "#616161"
        bg = "#F5F5F5"
        icon = "⚠️"
    else:
        border = "#D32F2F"
        bg = "#FFEBEE"
        icon = "❌"

    # Prepare caret HTML
    caret_html = ""
    if data.get('caret'):
        caret_html = f'<div style="color: #D32F2F; font-weight:bold;">{html.escape(data["caret"])}</div>'

    # Markdown Parsing
    # We use markdown to convert the text to HTML, fallback to raw if not available
    expl_text = data['explanation']
    hint_text = data['hint']

    if HAS_MARKDOWN:
        try:
            # extensions can be added here if needed, e.g., 'fenced_code'
            expl_html = markdown.markdown(expl_text)
            hint_html = markdown.markdown(hint_text)
        except Exception:
            expl_html = expl_text
            hint_html = hint_text
    else:
        expl_html = expl_text
        hint_html = hint_text

    # Dark Mode Safe Style: Opaque white container with shadow
    # Note: We use <div> for explanation and hint because markdown might return <p> tags
    # and nesting <p><p>...</p></p> is invalid.
    html_content = f"""
    <div style="
        background-color: {bg}; 
        color: #212121;
        border-left: 5px solid {border}; 
        padding: 12px 16px; 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 5px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h4 style="margin: 0; color: #212121; font-size: 1.1em; font-weight: 600;">
                <span role="img">{icon}</span> {data['title']}
            </h4>
            <span style="font-size: 0.85em; color: #555;" title="Confidence Score">
                Match: {int(conf*100)}%
            </span>
        </div>
        
        <div style="margin: 0 0 10px 0; font-size: 1em; line-height: 1.5; color: #212121;">
            {expl_html}
        </div>
        
        <div style="
            background-color: #FFFFFF; 
            color: #333333;
            padding: 8px 10px; 
            border: 1px solid #ddd; 
            font-family: 'Menlo', 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            margin-bottom: 8px;
            border-radius: 2px;
            overflow-x: auto;
        ">
            <div style="margin-bottom: 2px; color: #666; user-select: none; font-size: 0.8em;">Line {data['lineno']}:</div> 
            <div style="white-space: pre; line-height: 1.2;">{html.escape(data['line'])}</div>
            <div style="white-space: pre; line-height: 1.2;">{caret_html}</div>
        </div>
        
        <div style="color: #004D40; font-weight: 600; font-size: 0.95em; display: flex; align-items: baseline;">
            <span style="margin-right: 5px;" aria-hidden="true">➥</span>
            <div>{hint_html}</div>
        </div>
    </div>
    
    <style>
        /* Remove excessive margins from markdown paragraphs inside the card */
        .smart-exception-card p {{ margin: 0 0 5px 0; }}
        .smart-exception-card code {{ 
            background-color: rgba(255,255,255,0.5); 
            padding: 2px 4px; 
            border-radius: 3px; 
            font-family: monospace; 
        }}
    </style>
    """
    display(HTML(html_content))   


def activate(verbose):
    """Hooks the exception handler and help system into IPython."""
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if not ip: return
        ip.set_custom_exc((Exception,), smart_exception_handler)
        if verbose:
            print("✅ Smart Exception Handler Activated.")
    except ImportError:
        pass

def deactivate(verbose):
    """Restores default exception handling."""
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip:
            ip.set_custom_exc((Exception,), None)
            if verbose:
                print("Smart Exception Handler Deactivated.")
    except:
        pass


def _setup(ctx):
    """Initial setup function."""
    verbose=ctx.get("verbose")
    activate(verbose)
    if verbose:
        print("✅ Smart Exception Handler Activated.")
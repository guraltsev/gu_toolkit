"""Private MathLive-backed widget backend used by semantic input wrappers.

The public notebook-facing widgets should prefer :class:`ExpressionInput` and
:class:`IdentifierInput` from :mod:`gu_toolkit.mathlive.inputs`. This module keeps
MathLive isolated as an implementation detail while still exposing
``MathLiveField`` for compatibility with existing tests and internal imports.
"""

from __future__ import annotations

import traitlets

from .._widget_stubs import anywidget, widgets


class MathLiveField(anywidget.AnyWidget):
    """Low-level AnyWidget wrapper around a MathLive field with synced transport traits used by higher-level semantic widgets.
    
    Full API
    --------
    ``MathLiveField(*args: object, **kwargs: object)``
    
    Important synced traits include ``value``, ``math_json``, ``transport_source_value``,
    ``semantic_context``, ``inline_shortcuts``, ``menu_items``, ``transport_valid``,
    and ``transport_errors``.
    
    Parameters
    ----------
    *args : object
        Positional arguments forwarded to ``anywidget.AnyWidget``.
    
    **kwargs : object
        Keyword arguments forwarded to ``anywidget.AnyWidget``. In practice callers most often set synced traits such as ``value``, ``placeholder``, ``aria_label``, ``field_role``, ``math_json``, or ``read_only``.
    
    Returns
    -------
    MathLiveField
        AnyWidget instance with synced traits such as ``value``, ``math_json``, ``transport_source_value``, ``semantic_context``, and ``transport_errors`` that a frontend MathLive field can bind to.
    
    Optional arguments
    ------------------
    - ``**kwargs``: forwarded to ``anywidget.AnyWidget`` and may initialize synced traits such as ``value``, ``placeholder``, ``aria_label``, ``field_role``, ``math_json``, or ``read_only``.
    - The constructor also installs the shared ``gu-control`` / ``gu-control-math`` CSS classes and a full-width widget layout.
    
    Architecture note
    -----------------
    This class lives in ``gu_toolkit.mathlive.widget``, the low-level AnyWidget backend. Higher-level notebook code should usually start from ``IdentifierInput`` or ``ExpressionInput`` and let them manage context synchronization on top of this transport surface.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.mathlive.widget import MathLiveField
    
        field = MathLiveField(placeholder="Enter an expression")
    
    Discovery-oriented use::
    
        from gu_toolkit.mathlive.widget import MathLiveField
    
        help(MathLiveField)
        dir(MathLiveField())
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_mathlive_inputs.py`` and ``tests/semantic_math/test_expression_context.py``.
    """

    value = traitlets.Unicode("").tag(sync=True)
    placeholder = traitlets.Unicode("").tag(sync=True)
    aria_label = traitlets.Unicode("Mathematical input").tag(sync=True)
    read_only = traitlets.Bool(False).tag(sync=True)
    smart_mode = traitlets.Bool(False).tag(sync=True)
    field_role = traitlets.Unicode("math").tag(sync=True)
    math_json = traitlets.Any(default_value=None, allow_none=True).tag(sync=True)
    transport_valid = traitlets.Bool(True).tag(sync=True)
    transport_errors = traitlets.List(default_value=[]).tag(sync=True)
    transport_source_value = traitlets.Unicode("").tag(sync=True)
    semantic_context = traitlets.Dict(default_value={}).tag(sync=True)
    inline_shortcuts = traitlets.Dict(default_value={}).tag(sync=True)
    menu_items = traitlets.List(default_value=[]).tag(sync=True)
    known_identifiers = traitlets.List(default_value=[]).tag(sync=True)
    known_functions = traitlets.List(default_value=[]).tag(sync=True)

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.layout = widgets.Layout(width="100%", min_width="0", max_width="100%")
        add_class = getattr(self, "add_class", None)
        if callable(add_class):
            add_class("gu-control")
            add_class("gu-control-math")

    _esm = r"""
    let mathliveReady = null;
    let computeEngineReady = null;

    function ensureMathLive() {
      if (!mathliveReady) {
        mathliveReady = import("https://esm.run/mathlive");
      }
      return mathliveReady;
    }

    function ensureComputeEngine() {
      if (!computeEngineReady) {
        computeEngineReady = import("https://esm.run/@cortex-js/compute-engine");
      }
      return computeEngineReady;
    }

    function setCommonState(node, model) {
      if (!node) return;
      const placeholder = model.get("placeholder") || "";
      const ariaLabel = model.get("aria_label") || placeholder || "Mathematical input";
      const readOnly = !!model.get("read_only");
      if (node instanceof HTMLElement) {
        node.setAttribute("aria-label", ariaLabel);
        node.style.display = "block";
        node.style.width = "100%";
        node.style.maxWidth = "100%";
        node.style.boxSizing = "border-box";
        node.style.minWidth = "0";
        node.style.overflow = "hidden";
        if (node.tagName && node.tagName.toLowerCase() === "math-field") {
          node.style.fontSize = "var(--gu-math-font-size, 18px)";
          node.style.lineHeight = "1.05";
        }
        node.dataset.guReadOnly = readOnly ? "true" : "false";
      }
      if ("placeholder" in node) node.placeholder = placeholder;
      if ("readOnly" in node) node.readOnly = readOnly;
      if ("disabled" in node) node.disabled = false;
    }

    function isMathField(node) {
      return !!(node && node.tagName && node.tagName.toLowerCase() === "math-field");
    }

    function jsonStableStringify(value) {
      try {
        return JSON.stringify(value);
      } catch (_error) {
        return String(value);
      }
    }

    function cloneJson(value) {
      if (value === undefined) return null;
      if (value === null) return null;
      try {
        return JSON.parse(JSON.stringify(value));
      } catch (_error) {
        return null;
      }
    }

    function isHoldHead(value) {
      if (value === "Hold") return true;
      if (value && typeof value === "object" && !Array.isArray(value)) {
        const keys = Object.keys(value);
        return keys.length === 1 && keys[0] === "sym" && value.sym === "Hold";
      }
      return Array.isArray(value) && value.length === 1 && isHoldHead(value[0]);
    }

    function isEmptyMathJsonPayload(value) {
      if (value === undefined || value === null) return true;
      if (typeof value === "string") {
        const text = value.trim();
        return text === "" || text === "Nothing";
      }
      if (Array.isArray(value)) {
        if (value.length === 0) return true;
        if (value.length === 1) return isEmptyMathJsonPayload(value[0]);
        if (isHoldHead(value[0]) && value.length === 2) {
          return isEmptyMathJsonPayload(value[1]);
        }
        return false;
      }
      if (typeof value === "object") {
        const keys = Object.keys(value);
        if (keys.length === 0) return true;
        if (keys.length === 1 && keys[0] === "sym") return isEmptyMathJsonPayload(value.sym);
        if (keys.length === 1 && keys[0] === "num") return isEmptyMathJsonPayload(value.num);
        if (Object.prototype.hasOwnProperty.call(value, "fn")) {
          const args = Array.isArray(value.args) ? value.args : [];
          if (args.length === 0) return isEmptyMathJsonPayload(value.fn);
          if (args.length === 1 && isHoldHead(value.fn)) {
            return isEmptyMathJsonPayload(args[0]);
          }
        }
      }
      return false;
    }

    function normalizeMathJsonPayload(value) {
      const cloned = cloneJson(value);
      return isEmptyMathJsonPayload(cloned) ? null : cloned;
    }

    function valuesEqual(lhs, rhs) {
      if (lhs === rhs) return true;
      return jsonStableStringify(lhs) === jsonStableStringify(rhs);
    }

    function formatTransportError(error) {
      if (error == null) return "Unknown MathLive transport error.";
      if (typeof error === "string") return error;
      if (error instanceof Error && typeof error.message === "string") return error.message;
      if (typeof error.latex === "string" && error.latex) return error.latex;
      if (typeof error.message === "string" && error.message) return error.message;
      return jsonStableStringify(error);
    }

    function fallbackIdentifierLatex(name) {
      if (!name) return "";
      if (name.length === 1) return name;
      return `\\mathrm{${String(name).replaceAll("_", "\\_")}}`;
    }

    function fallbackFunctionHeadLatex(name) {
      if (!name) return "";
      if (name.length === 1) return name;
      return `\\operatorname{${String(name).replaceAll("_", "\\_")}}`;
    }

    function buildFallbackManifest(model) {
      const shortcuts = model.get("inline_shortcuts") || {};
      const symbolNames = Array.from(new Set(model.get("known_identifiers") || []));
      const functionNames = Array.from(new Set(model.get("known_functions") || []));
      return {
        version: 1,
        fieldRole: model.get("field_role") || "math",
        symbols: symbolNames.map((name) => ({
          name,
          latex: Object.prototype.hasOwnProperty.call(shortcuts, name)
            ? shortcuts[name]
            : fallbackIdentifierLatex(name),
        })),
        functions: functionNames.map((name) => {
          const latexHead = Object.prototype.hasOwnProperty.call(shortcuts, name)
            ? shortcuts[name]
            : fallbackFunctionHeadLatex(name);
          return {
            name,
            latexHead,
            template: `${latexHead}(#0)`,
          };
        }),
      };
    }

    function getSemanticContext(model) {
      const manifest = model.get("semantic_context");
      if (
        manifest &&
        typeof manifest === "object" &&
        (Array.isArray(manifest.symbols) || Array.isArray(manifest.functions))
      ) {
        return manifest;
      }
      return buildFallbackManifest(model);
    }

    function semanticEntries(model, kind) {
      const manifest = getSemanticContext(model);
      const raw = manifest && Array.isArray(manifest[kind]) ? manifest[kind] : [];
      return raw.filter((item) => item && typeof item === "object");
    }

    function semanticSymbolByName(model, name) {
      return semanticEntries(model, "symbols").find((item) => item.name === name) || null;
    }

    function semanticFunctionByName(model, name) {
      return semanticEntries(model, "functions").find((item) => item.name === name) || null;
    }

    function applyValue(node, value) {
      const next = value || "";
      if (!node) return;
      if (node.tagName && node.tagName.toLowerCase() === "math-field") {
        if (node.value !== next) {
          try {
            node.setValue(next, { silenceNotifications: true });
          } catch (_error) {
            node.value = next;
          }
        }
        return;
      }
      if (node.value !== next) node.value = next;
    }

    function applyMathJson(node, model) {
      if (!isMathField(node)) return false;
      const payload = model.get("math_json");
      if (payload === null || payload === undefined) return false;
      const ce = node.computeEngine || null;
      if (!ce || typeof ce.box !== "function") return false;
      try {
        const current = expressionSnapshot(node).math_json;
        if (valuesEqual(current, payload)) return false;
      } catch (_error) {
        // Ignore comparison failures and try to serialize the payload below.
      }
      try {
        const boxed = ce.box(payload);
        const latex = boxed && typeof boxed.latex === "string" ? boxed.latex : "";
        if (!latex) return false;
        applyValue(node, latex);
        return true;
      } catch (_error) {
        return false;
      }
    }

    function shouldWrapShortcut(symbol, model) {
      if (!symbol) return false;
      const identifiers = new Set(model.get("known_identifiers") || []);
      const functions = new Set(model.get("known_functions") || []);
      return identifiers.has(symbol) || functions.has(symbol);
    }

    function latexForShortcut(symbol, model) {
      const shortcuts = model.get("inline_shortcuts") || {};
      if (Object.prototype.hasOwnProperty.call(shortcuts, symbol)) {
        return shortcuts[symbol] || "";
      }
      const fnEntry = semanticFunctionByName(model, symbol);
      if (fnEntry && typeof fnEntry.latexHead === "string") {
        return fnEntry.latexHead;
      }
      const symEntry = semanticSymbolByName(model, symbol);
      if (symEntry && typeof symEntry.latex === "string") {
        return symEntry.latex;
      }
      if (!shouldWrapShortcut(symbol, model)) return "";
      if (symbol.length === 1) return symbol;
      const functions = new Set(model.get("known_functions") || []);
      if (functions.has(symbol)) return fallbackFunctionHeadLatex(symbol);
      return fallbackIdentifierLatex(symbol);
    }

    function buildSemanticMenuItems(model) {
      const explicitItems = Array.isArray(model.get("menu_items")) ? model.get("menu_items") : [];
      const sourceItems = explicitItems.length
        ? explicitItems
        : [
            ...semanticEntries(model, "symbols").map((entry) => ({
              kind: "symbol",
              id: `symbol:${entry.name}`,
              name: entry.name,
              label: entry.name,
              latex: entry.latex || fallbackIdentifierLatex(entry.name),
            })),
            ...semanticEntries(model, "functions").map((entry) => ({
              kind: "function",
              id: `function:${entry.name}`,
              name: entry.name,
              label: entry.name,
              latex: entry.latexHead || fallbackFunctionHeadLatex(entry.name),
              template:
                entry.template ||
                `${entry.latexHead || fallbackFunctionHeadLatex(entry.name)}(#0)`,
            })),
          ];
      if (!sourceItems.length) return null;

      const symbolItems = [];
      const functionItems = [];
      for (const item of sourceItems) {
        const label = item.label || item.name || item.id || "Insert";
        const kind = item.kind || "symbol";
        if (kind === "function") {
          functionItems.push({
            label,
            id: item.id || `function:${label}`,
            onMenuSelect: (mf) => {
              const template = item.template || `${item.latex || label}(#0)`;
              mf.executeCommand(["insert", template, { selectionMode: "placeholder" }]);
            },
          });
        } else {
          symbolItems.push({
            label,
            id: item.id || `symbol:${label}`,
            onMenuSelect: (mf) => {
              const latex = item.latex || label;
              mf.executeCommand(["insert", latex]);
            },
          });
        }
      }

      const menu = [];
      if (symbolItems.length) {
        menu.push({ label: "Insert Symbol", id: "gu-insert-symbol", submenu: symbolItems });
      }
      if (functionItems.length) {
        menu.push({ label: "Insert Function", id: "gu-insert-function", submenu: functionItems });
      }
      return menu;
    }

    function safeDeclareFunction(ce, name) {
      if (!ce || typeof ce.declare !== "function" || !name) return;
      try {
        ce.declare(name, "function");
      } catch (_error) {
        // Re-declaration is fine when the field context changes repeatedly.
      }
    }

    function buildSymbolDictionaryEntry(entry) {
      const record = {
        name: entry.name,
        kind: "symbol",
        serialize: () => entry.latex || fallbackIdentifierLatex(entry.name),
      };
      if (entry.triggerKind === "symbol" && entry.trigger) {
        record.symbolTrigger = entry.trigger;
      } else if (entry.triggerKind === "latex" && entry.trigger) {
        record.latexTrigger = entry.trigger;
      }
      return record;
    }

    function buildFunctionDictionaryEntry(entry) {
      const latexHead = entry.latexHead || fallbackFunctionHeadLatex(entry.name);
      const record = {
        name: entry.name,
        kind: "function",
        serialize: (serializer, expr) => {
          if (serializer && typeof serializer.wrapArguments === "function") {
            return latexHead + serializer.wrapArguments(expr);
          }
          return latexHead;
        },
      };
      if (entry.triggerKind === "symbol" && entry.trigger) {
        record.symbolTrigger = entry.trigger;
      } else if (entry.triggerKind === "latex" && entry.trigger) {
        record.latexTrigger = entry.trigger;
      }
      return record;
    }

    function buildComputeEngine(node, model) {
      const runtime = node.__guRuntime || {};
      const ComputeEngine = runtime.ComputeEngine || null;
      if (!ComputeEngine) return null;

      const manifest = getSemanticContext(model);
      const ce = new ComputeEngine();
      const customEntries = [];

      for (const entry of semanticEntries(model, "symbols")) {
        customEntries.push(buildSymbolDictionaryEntry(entry));
      }
      for (const entry of semanticEntries(model, "functions")) {
        safeDeclareFunction(ce, entry.name);
        customEntries.push(buildFunctionDictionaryEntry(entry));
      }

      if (Array.isArray(ce.latexDictionary)) {
        ce.latexDictionary = [...ce.latexDictionary, ...customEntries];
      } else {
        ce.latexDictionary = customEntries;
      }
      ce.__guManifest = manifest;
      return ce;
    }

    function applyTransportContext(node, model) {
      if (!isMathField(node)) return;
      const manifest = getSemanticContext(model);
      const signature = jsonStableStringify(manifest);
      if (node.__guTransportSignature === signature && node.computeEngine) {
        return;
      }
      node.__guTransportSignature = signature;
      const ce = buildComputeEngine(node, model);
      if (ce) {
        node.computeEngine = ce;
      }
    }

    function expressionSnapshot(node) {
      const latex = typeof node.value === "string" ? node.value : "";
      if (!isMathField(node)) {
        return {
          value: latex,
          math_json: null,
          transport_valid: true,
          transport_errors: [],
          transport_source_value: latex,
        };
      }
      try {
        const expr = node.expression;
        if (!expr) {
          return {
            value: latex,
            math_json: null,
            transport_valid: true,
            transport_errors: [],
            transport_source_value: latex,
          };
        }
        const errors = Array.isArray(expr.errors)
          ? expr.errors.map((error) => formatTransportError(error))
          : [];
        return {
          value: latex,
          math_json: normalizeMathJsonPayload(expr.json),
          transport_valid: expr.isValid !== false && errors.length === 0,
          transport_errors: errors,
          transport_source_value: latex,
        };
      } catch (error) {
        return {
          value: latex,
          math_json: null,
          transport_valid: false,
          transport_errors: [formatTransportError(error)],
          transport_source_value: latex,
        };
      }
    }

    function commitTransport(node, model) {
      const snapshot = expressionSnapshot(node);
      let dirty = false;
      for (const key of Object.keys(snapshot)) {
        if (!valuesEqual(model.get(key), snapshot[key])) {
          model.set(key, snapshot[key]);
          dirty = true;
        }
      }
      if (dirty) {
        model.save_changes();
      }
    }

    function bindValueBridge(node, model) {
      const commit = () => {
        commitTransport(node, model);
      };
      node.addEventListener("input", commit);
      node.addEventListener("change", commit);
      return () => {
        node.removeEventListener("input", commit);
        node.removeEventListener("change", commit);
      };
    }

    function primeMathFieldLifecycle(node, onMount) {
      if (!isMathField(node)) {
        node.__guMounted = true;
        onMount();
        return () => {};
      }

      node.__guMounted = false;
      node.__guPendingSemantic = false;
      const handleMount = () => {
        node.__guMounted = true;
        onMount();
      };
      node.addEventListener("mount", handleMount, { once: true });
      return () => node.removeEventListener("mount", handleMount);
    }

    function applySemanticState(node, model) {
      if (!isMathField(node)) return;
      if (!node.__guMounted) {
        node.__guPendingSemantic = true;
        return;
      }

      node.smartFence = true;
      node.smartMode = !!model.get("smart_mode");

      if (node.__guBaseInlineShortcuts === undefined) {
        node.__guBaseInlineShortcuts = { ...(node.inlineShortcuts || {}) };
      }
      const shortcuts = model.get("inline_shortcuts") || {};
      node.inlineShortcuts = { ...node.__guBaseInlineShortcuts, ...shortcuts };
      node.onInlineShortcut = (_sender, symbol) => latexForShortcut(symbol, model);

      if (node.__guBaseMenuItems === undefined) {
        node.__guBaseMenuItems = Array.isArray(node.menuItems) ? [...node.menuItems] : [];
      }
      const menu = buildSemanticMenuItems(model);
      node.menuItems = menu || node.__guBaseMenuItems;
      node.__guPendingSemantic = false;
    }

    async function buildMathField(model) {
      await ensureMathLive();
      const field = document.createElement("math-field");
      field.setAttribute("math-virtual-keyboard-policy", "auto");
      field.setAttribute("virtual-keyboard-mode", "manual");
      field.smartFence = true;
      field.smartMode = !!model.get("smart_mode");
      try {
        const computeEngineModule = await ensureComputeEngine();
        field.__guRuntime = {
          ComputeEngine:
            computeEngineModule.ComputeEngine ||
            (computeEngineModule.default && computeEngineModule.default.ComputeEngine) ||
            computeEngineModule.default ||
            null,
        };
      } catch (_error) {
        field.__guRuntime = { ComputeEngine: null };
      }
      return field;
    }

    function buildTextarea() {
      const field = document.createElement("textarea");
      field.rows = 1;
      field.spellcheck = false;
      field.style.resize = "vertical";
      return field;
    }

    export default {
      async render({ model, el }) {
        el.innerHTML = "";
        el.style.width = "100%";
        el.style.minWidth = "0";
        el.style.maxWidth = "100%";
        el.style.overflow = "hidden";

        let input = null;
        try {
          input = await buildMathField(model);
        } catch (_error) {
          input = buildTextarea();
        }

        const cleanupBridge = bindValueBridge(input, model);
        const syncFromModel = () => {
          setCommonState(input, model);
          applyTransportContext(input, model);
          if (!applyMathJson(input, model)) {
            applyValue(input, model.get("value"));
          }
          applySemanticState(input, model);
          commitTransport(input, model);
        };

        const onValue = () => {
          applyTransportContext(input, model);
          applyValue(input, model.get("value"));
          commitTransport(input, model);
        };
        const onMathJson = () => {
          applyTransportContext(input, model);
          applyMathJson(input, model);
          applySemanticState(input, model);
          commitTransport(input, model);
        };
        const onPlaceholder = () => setCommonState(input, model);
        const onReadOnly = () => setCommonState(input, model);
        const onSemantic = () => {
          applyTransportContext(input, model);
          applySemanticState(input, model);
          commitTransport(input, model);
        };
        model.on("change:value", onValue);
        model.on("change:math_json", onMathJson);
        model.on("change:placeholder", onPlaceholder);
        model.on("change:aria_label", onPlaceholder);
        model.on("change:read_only", onReadOnly);
        model.on("change:smart_mode", onSemantic);
        model.on("change:field_role", onSemantic);
        model.on("change:semantic_context", onSemantic);
        model.on("change:inline_shortcuts", onSemantic);
        model.on("change:menu_items", onSemantic);
        model.on("change:known_identifiers", onSemantic);
        model.on("change:known_functions", onSemantic);

        const cleanupMount = primeMathFieldLifecycle(input, () => {
          if (input.__guPendingSemantic) {
            applySemanticState(input, model);
          }
          commitTransport(input, model);
        });

        el.appendChild(input);
        syncFromModel();

        return () => {
          cleanupBridge();
          cleanupMount();
          model.off("change:value", onValue);
          model.off("change:math_json", onMathJson);
          model.off("change:placeholder", onPlaceholder);
          model.off("change:aria_label", onPlaceholder);
          model.off("change:read_only", onReadOnly);
          model.off("change:smart_mode", onSemantic);
          model.off("change:field_role", onSemantic);
          model.off("change:semantic_context", onSemantic);
          model.off("change:inline_shortcuts", onSemantic);
          model.off("change:menu_items", onSemantic);
          model.off("change:known_identifiers", onSemantic);
          model.off("change:known_functions", onSemantic);
        };
      },
    };
    """


__all__ = ["MathLiveField"]

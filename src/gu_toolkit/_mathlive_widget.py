"""Small MathLive-backed widget wrappers used by notebook editors.

Purpose
-------
The toolkit mostly relies on standard ipywidgets, but expression entry benefits
from a real mathematical editor. This module provides :class:`MathLiveField`, a
thin ``anywidget`` wrapper around MathLive's ``<math-field>`` custom element.

Architecture
------------
The widget deliberately keeps the Python surface tiny:

- ``value`` stores the current LaTeX string,
- ``placeholder`` and ``aria_label`` describe the field,
- ``read_only`` controls editability.

Frontend code loads MathLive from the ESM CDN recommended by the official docs
and falls back to a plain ``<textarea>`` if the import is unavailable. That
keeps notebook usage resilient without introducing a JavaScript build step.

Discoverability
---------------
See :mod:`gu_toolkit.figure_plot_editor` for the plot-composer dialog that uses
this widget.
"""

from __future__ import annotations

import traitlets

from ._widget_stubs import anywidget


class MathLiveField(anywidget.AnyWidget):
    """Editable LaTeX-backed math input widget.

    The widget exposes a single synchronized ``value`` trait containing the
    current LaTeX content. In browsers where MathLive cannot be loaded, it
    degrades to a simple textarea so the surrounding editor remains functional.

    Examples
    --------
    The widget is typically embedded inside higher-level dialogs instead of
    being used directly:

    >>> from gu_toolkit._mathlive_widget import MathLiveField  # doctest: +SKIP
    >>> field = MathLiveField(value=r"x^2", placeholder="Expression")  # doctest: +SKIP
    >>> field.value  # doctest: +SKIP
    'x^2'
    """

    value = traitlets.Unicode("").tag(sync=True)
    placeholder = traitlets.Unicode("").tag(sync=True)
    aria_label = traitlets.Unicode("Mathematical input").tag(sync=True)
    read_only = traitlets.Bool(False).tag(sync=True)

    _esm = r"""
    let mathliveReady = null;

    function ensureMathLive() {
      if (!mathliveReady) {
        mathliveReady = import("https://esm.run/mathlive");
      }
      return mathliveReady;
    }

    function setCommonState(node, model) {
      if (!node) return;
      const placeholder = model.get("placeholder") || "";
      const ariaLabel = model.get("aria_label") || placeholder || "Mathematical input";
      const readOnly = !!model.get("read_only");
      if (node instanceof HTMLElement) {
        node.setAttribute("aria-label", ariaLabel);
        node.style.width = "100%";
        node.style.boxSizing = "border-box";
        node.style.minHeight = "38px";
        node.style.border = "1px solid rgba(15, 23, 42, 0.16)";
        node.style.borderRadius = "8px";
        node.style.padding = "6px 10px";
        node.style.background = readOnly ? "rgba(15, 23, 42, 0.04)" : "white";
      }
      if ("placeholder" in node) node.placeholder = placeholder;
      if ("readOnly" in node) node.readOnly = readOnly;
      if ("disabled" in node) node.disabled = false;
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

    function bindValueBridge(node, model) {
      const commit = () => {
        const next = typeof node.value === "string" ? node.value : "";
        if (model.get("value") === next) return;
        model.set("value", next);
        model.save_changes();
      };
      node.addEventListener("input", commit);
      node.addEventListener("change", commit);
      return () => {
        node.removeEventListener("input", commit);
        node.removeEventListener("change", commit);
      };
    }

    async function buildMathField() {
      await ensureMathLive();
      const field = document.createElement("math-field");
      field.setAttribute("math-virtual-keyboard-policy", "auto");
      field.setAttribute("virtual-keyboard-mode", "manual");
      field.smartFence = true;
      field.smartMode = true;
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

        let input = null;
        try {
          input = await buildMathField();
        } catch (_error) {
          input = buildTextarea();
        }

        const cleanupBridge = bindValueBridge(input, model);
        const syncFromModel = () => {
          setCommonState(input, model);
          applyValue(input, model.get("value"));
        };
        syncFromModel();

        const onValue = () => applyValue(input, model.get("value"));
        const onPlaceholder = () => setCommonState(input, model);
        const onReadOnly = () => setCommonState(input, model);
        model.on("change:value", onValue);
        model.on("change:placeholder", onPlaceholder);
        model.on("change:aria_label", onPlaceholder);
        model.on("change:read_only", onReadOnly);

        el.appendChild(input);

        return () => {
          cleanupBridge();
          model.off("change:value", onValue);
          model.off("change:placeholder", onPlaceholder);
          model.off("change:aria_label", onPlaceholder);
          model.off("change:read_only", onReadOnly);
        };
      },
    };
    """


__all__ = ["MathLiveField"]

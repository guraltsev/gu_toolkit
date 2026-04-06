const MATHLIVE_MODULE_URL = "https://esm.run/mathlive@0.109.0";
const MATHLIVE_FONTS_URL = "https://cdn.jsdelivr.net/npm/mathlive@0.109.0/fonts";
const BOOTSTRAP_KEY = "__gu_toolkit_mathlive_bootstrap_v2";
const IDENTIFIER_PATTERN = /^[A-Za-z][A-Za-z0-9]*$/;

function getBootstrap() {
  if (!globalThis[BOOTSTRAP_KEY]) {
    globalThis[BOOTSTRAP_KEY] = {
      modulePromise: null,
      async ensureMathLive() {
        if (!this.modulePromise) {
          this.modulePromise = import(MATHLIVE_MODULE_URL).then(async (mathlive) => {
            const MathfieldElement = mathlive?.MathfieldElement;
            if (!MathfieldElement) {
              throw new Error("MathLive module did not expose MathfieldElement.");
            }

            MathfieldElement.fontsDirectory = MATHLIVE_FONTS_URL;
            MathfieldElement.soundsDirectory = null;
            MathfieldElement.plonkSound = null;

            await customElements.whenDefined("math-field");
            return { MathfieldElement };
          });
        }
        return this.modulePromise;
      },
    };
  }
  return globalThis[BOOTSTRAP_KEY];
}

function normalizeString(value) {
  return typeof value === "string" ? value : "";
}

function normalizeContextNames(value) {
  return Array.isArray(value)
    ? value.filter((item) => typeof item === "string")
    : [];
}

function normalizePolicy(value) {
  return value === "context_or_new" ? "context_or_new" : "context_only";
}

function setMathfieldValue(field, value) {
  const next = normalizeString(value);
  if (field.value === next) {
    return;
  }

  if (typeof field.setValue === "function") {
    field.setValue(next, { silenceNotifications: true });
    return;
  }

  field.value = next;
}

function classifyIdentifierCandidate(candidate, contextNames, contextPolicy) {
  const text = normalizeString(candidate);

  if (text === "") {
    return {
      accepted: true,
      normalized: "",
      state: "empty",
    };
  }

  if (!IDENTIFIER_PATTERN.test(text)) {
    return {
      accepted: false,
      normalized: text,
      state: "invalid-shape",
    };
  }

  if (contextPolicy === "context_only" && !contextNames.includes(text)) {
    return {
      accepted: false,
      normalized: text,
      state: "not-in-context",
    };
  }

  if (contextNames.includes(text)) {
    return {
      accepted: true,
      normalized: text,
      state: "accepted-context",
    };
  }

  return {
    accepted: true,
    normalized: text,
    state: "accepted-new",
  };
}

function updateRootState(root, classification) {
  root.classList.toggle("is-empty", classification.state === "empty");
  root.classList.toggle(
    "is-accepted",
    classification.accepted && classification.state !== "empty",
  );
  root.classList.toggle("is-invalid", !classification.accepted);
}

function createEditMenuItem(field, id, label, command) {
  return {
    id,
    label,
    onMenuSelect: () => {
      field.executeCommand(command);
      field.focus();
    },
  };
}

function createContextMenuItem(name, onPick) {
  return {
    id: `context-name-${name}`,
    label: name,
    onMenuSelect: () => onPick(name),
  };
}

function createIdentifierMenu(field, contextNames, onPick) {
  const menuItems = [];

  if (contextNames.length > 0) {
    menuItems.push({
      id: "context-names",
      label: "Context names",
      submenu: contextNames.map((name) => createContextMenuItem(name, onPick)),
    });
    menuItems.push({ type: "divider" });
  }

  menuItems.push(
    createEditMenuItem(field, "undo", "Undo", "undo"),
    createEditMenuItem(field, "redo", "Redo", "redo"),
    { type: "divider" },
    createEditMenuItem(field, "cut", "Cut", "cutToClipboard"),
    createEditMenuItem(field, "copy", "Copy", "copyToClipboard"),
    createEditMenuItem(field, "paste", "Paste", "pasteFromClipboard"),
    { type: "divider" },
    createEditMenuItem(field, "select-all", "Select all", "selectAll"),
  );

  return menuItems;
}

function isMenuShortcut(event) {
  return event.code === "Space" || event.key === " " || event.key === "Spacebar";
}

function handleIdentifierKeydown(event) {
  const isBareAltShortcut = event.altKey && !event.ctrlKey && !event.metaKey;
  if (isBareAltShortcut && !isMenuShortcut(event)) {
    event.preventDefault();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
      return;
    }
    event.stopPropagation();
  }
}

async function appendAndWaitForMount(host, field) {
  let mounted = false;
  const mountPromise = new Promise((resolve) => {
    const handleMount = () => {
      mounted = true;
      resolve();
    };
    field.addEventListener("mount", handleMount, { once: true });
  });

  host.appendChild(field);

  await Promise.race([
    mountPromise,
    new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          resolve();
        });
      });
    }),
  ]);

  if (!mounted) {
    await Promise.resolve();
  }
}

function applyIdentifierFieldConfiguration(field) {
  field.defaultMode = "math";
  field.inlineShortcuts = {};
  field.mathVirtualKeyboardPolicy = "manual";
  field.popoverPolicy = "off";
  field.scriptDepth = 0;
  field.smartFence = false;
  field.smartMode = false;
  field.smartSuperscript = false;
}

export default async function () {
  const { MathfieldElement } = await getBootstrap().ensureMathLive();

  return {
    async render({ model, el }) {
      el.classList.add("gu-identifier-input-root");
      el.replaceChildren();

      let contextNames = normalizeContextNames(model.get("context_names"));
      let contextPolicy = normalizePolicy(model.get("context_policy"));
      let committedValue = normalizeString(model.get("value"));

      const field = new MathfieldElement();
      field.setAttribute("aria-label", "Identifier input");
      setMathfieldValue(field, committedValue);
      await appendAndWaitForMount(el, field);
      applyIdentifierFieldConfiguration(field);

      const refreshUi = (candidate) => {
        const classification = classifyIdentifierCandidate(
          candidate,
          contextNames,
          contextPolicy,
        );
        updateRootState(el, classification);
        field.setAttribute("aria-invalid", classification.accepted ? "false" : "true");
        return classification;
      };

      const applyAcceptedValue = (nextValue) => {
        committedValue = normalizeString(nextValue);
        setMathfieldValue(field, committedValue);
        const classification = refreshUi(committedValue);
        if (classification.accepted && model.get("value") !== committedValue) {
          model.set("value", committedValue);
          model.save_changes();
        }
        field.focus();
      };

      const refreshMenu = () => {
        field.menuItems = createIdentifierMenu(field, contextNames, applyAcceptedValue);
      };

      const syncAcceptedValueFromField = () => {
        const classification = refreshUi(field.value);
        if (!classification.accepted) {
          return;
        }

        committedValue = classification.normalized;
        if (model.get("value") === committedValue) {
          return;
        }

        model.set("value", committedValue);
        model.save_changes();
      };

      const handleModelValueChange = () => {
        committedValue = normalizeString(model.get("value"));
        setMathfieldValue(field, committedValue);
        refreshUi(committedValue);
      };

      const handleContextNamesChange = () => {
        contextNames = normalizeContextNames(model.get("context_names"));
        refreshMenu();
        refreshUi(field.value);
      };

      const handleContextPolicyChange = () => {
        contextPolicy = normalizePolicy(model.get("context_policy"));
        refreshUi(field.value);
      };

      field.addEventListener("input", syncAcceptedValueFromField);
      field.addEventListener("change", syncAcceptedValueFromField);
      field.addEventListener("keydown", handleIdentifierKeydown, true);
      if (typeof model.on === "function") {
        model.on("change:value", handleModelValueChange);
        model.on("change:context_names", handleContextNamesChange);
        model.on("change:context_policy", handleContextPolicyChange);
      }

      refreshMenu();
      refreshUi(committedValue);

      return () => {
        field.removeEventListener("input", syncAcceptedValueFromField);
        field.removeEventListener("change", syncAcceptedValueFromField);
        field.removeEventListener("keydown", handleIdentifierKeydown, true);
        if (typeof model.off === "function") {
          model.off("change:value", handleModelValueChange);
          model.off("change:context_names", handleContextNamesChange);
          model.off("change:context_policy", handleContextPolicyChange);
        }
      };
    },
  };
}

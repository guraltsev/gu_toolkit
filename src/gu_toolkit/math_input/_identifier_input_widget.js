const MATHLIVE_MODULE_URL = "https://esm.run/mathlive@0.109.0";
const BOOTSTRAP_KEY = "__gu_toolkit_mathlive_bootstrap_v1";
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
            MathfieldElement.fontsDirectory = "";
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
      status: "empty",
      message:
        contextPolicy === "context_only"
          ? "The field is blank. Pick one of the provided names or type one of them exactly."
          : "The field is blank. Pick a suggested name or type a new plain identifier.",
    };
  }

  if (!IDENTIFIER_PATTERN.test(text)) {
    return {
      accepted: false,
      normalized: text,
      status: "invalid-shape",
      message:
        "Only plain identifiers are accepted here: start with a letter, then use letters or digits only.",
    };
  }

  if (contextPolicy === "context_only" && !contextNames.includes(text)) {
    return {
      accepted: false,
      normalized: text,
      status: "not-in-context",
      message:
        "This field is using context_only policy, so the name must come from the provided context list.",
    };
  }

  if (contextNames.includes(text)) {
    return {
      accepted: true,
      normalized: text,
      status: "accepted-context",
      message: "Accepted. This name is in the provided context.",
    };
  }

  return {
    accepted: true,
    normalized: text,
    status: "accepted-new",
    message:
      "Accepted. This name is not in the provided context, but context_or_new policy allows a new plain identifier.",
  };
}

function matchesPrefix(candidate, contextName) {
  const text = normalizeString(candidate);
  if (text === "") {
    return true;
  }
  return contextName.startsWith(text);
}

function updateRootState(root, classification) {
  root.classList.toggle("is-invalid", !classification.accepted);
  root.classList.toggle("is-accepted", classification.accepted);
}

function renderSuggestions(container, contextNames, draftValue, onPick) {
  container.replaceChildren();

  if (contextNames.length === 0) {
    const empty = document.createElement("div");
    empty.className = "gu-identifier-empty-suggestions";
    empty.textContent = "No context names were provided for this field in Phase 2.";
    container.appendChild(empty);
    return;
  }

  const matching = contextNames.filter((name) => matchesPrefix(draftValue, name));
  const namesToRender = matching.length > 0 ? matching : contextNames;

  for (const name of namesToRender) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "gu-identifier-suggestion";
    button.textContent = name;
    button.addEventListener("click", () => onPick(name));
    container.appendChild(button);
  }
}

function createIdentifierMenu(field) {
  const commandItem = (id, label, command) => ({
    id,
    label,
    onMenuSelect: () => {
      field.executeCommand(command);
      field.focus();
    },
  });

  return [
    commandItem("undo", "Undo", "undo"),
    commandItem("redo", "Redo", "redo"),
    { type: "divider" },
    commandItem("cut", "Cut", "cutToClipboard"),
    commandItem("copy", "Copy", "copyToClipboard"),
    commandItem("paste", "Paste", "pasteFromClipboard"),
    { type: "divider" },
    commandItem("select-all", "Select all", "selectAll"),
  ];
}

function filterIdentifierKeybindings(field) {
  if (!Array.isArray(field.keybindings)) {
    return;
  }
  field.keybindings = field.keybindings.filter((binding) => {
    const key = String(binding?.key ?? "").toLowerCase();
    return !key.includes("alt") && !key.includes("option");
  });
}

async function appendAndWaitForMount(host, field) {
  let settled = false;
  const done = () => {
    settled = true;
  };
  const mountPromise = new Promise((resolve) => {
    const handleMount = () => {
      field.removeEventListener("mount", handleMount);
      if (!settled) {
        done();
        resolve();
      }
    };
    field.addEventListener("mount", handleMount, { once: true });
  });

  host.appendChild(field);

  await Promise.race([
    mountPromise,
    new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (!settled) {
            done();
          }
          resolve();
        });
      });
    }),
  ]);
}

export default async function () {
  await getBootstrap().ensureMathLive();

  return {
    async render({ model, el }) {
      el.classList.add("gu-identifier-input-root");
      el.replaceChildren();

      let contextNames = normalizeContextNames(model.get("context_names"));
      let contextPolicy = normalizePolicy(model.get("context_policy"));
      let committedValue = normalizeString(model.get("value"));
      let draftValue = committedValue;

      const frame = document.createElement("div");
      frame.className = "gu-identifier-input-frame";

      const field = document.createElement("math-field");
      field.setAttribute("aria-label", "Identifier input");
      field.defaultMode = "math";
      field.smartFence = false;
      field.smartMode = false;
      field.mathVirtualKeyboardPolicy = "manual";
      field.popoverPolicy = "off";
      setMathfieldValue(field, committedValue);

      const meta = document.createElement("div");
      meta.className = "gu-identifier-meta";

      const fieldHost = document.createElement("div");
      fieldHost.className = "gu-identifier-field-host";

      const status = document.createElement("div");
      status.className = "gu-identifier-status";

      const suggestionsLabel = document.createElement("div");
      suggestionsLabel.className = "gu-identifier-suggestions-label";
      suggestionsLabel.textContent = "Suggested context names";

      const suggestions = document.createElement("div");
      suggestions.className = "gu-identifier-suggestions";

      frame.appendChild(meta);
      frame.appendChild(fieldHost);
      frame.appendChild(status);
      frame.appendChild(suggestionsLabel);
      frame.appendChild(suggestions);
      el.appendChild(frame);

      await appendAndWaitForMount(fieldHost, field);

      field.inlineShortcuts = {};
      filterIdentifierKeybindings(field);
      field.menuItems = createIdentifierMenu(field);

      const refreshUi = (candidate) => {
        draftValue = normalizeString(candidate);
        const classification = classifyIdentifierCandidate(
          draftValue,
          contextNames,
          contextPolicy,
        );
        updateRootState(el, classification);
        meta.textContent = `Policy: ${contextPolicy}. Contract: empty or [A-Za-z][A-Za-z0-9]*.`;
        status.textContent = classification.message;
        status.dataset.state = classification.accepted ? "accepted" : "invalid";
        renderSuggestions(suggestions, contextNames, draftValue, (pickedName) => {
          const picked = classifyIdentifierCandidate(
            pickedName,
            contextNames,
            contextPolicy,
          );
          committedValue = picked.normalized;
          draftValue = picked.normalized;
          setMathfieldValue(field, committedValue);
          if (model.get("value") !== committedValue) {
            model.set("value", committedValue);
            model.save_changes();
          }
          refreshUi(committedValue);
        });
        return classification;
      };

      const revertToCommittedValue = () => {
        draftValue = committedValue;
        setMathfieldValue(field, committedValue);
        refreshUi(committedValue);
      };

      const handleInput = () => {
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

      const handleChange = () => {
        const classification = classifyIdentifierCandidate(
          field.value,
          contextNames,
          contextPolicy,
        );
        if (!classification.accepted) {
          revertToCommittedValue();
          return;
        }
        committedValue = classification.normalized;
        setMathfieldValue(field, committedValue);
        refreshUi(committedValue);
      };

      const handleKeydown = (event) => {
        if (event.altKey && !event.ctrlKey && !event.metaKey) {
          event.preventDefault();
        }
      };

      const handleBlur = () => {
        const classification = classifyIdentifierCandidate(
          field.value,
          contextNames,
          contextPolicy,
        );
        if (!classification.accepted) {
          revertToCommittedValue();
        }
      };

      const handleModelValueChange = () => {
        committedValue = normalizeString(model.get("value"));
        draftValue = committedValue;
        setMathfieldValue(field, committedValue);
        refreshUi(committedValue);
      };

      const handleContextNamesChange = () => {
        contextNames = normalizeContextNames(model.get("context_names"));
        refreshUi(field.value);
      };

      const handleContextPolicyChange = () => {
        contextPolicy = normalizePolicy(model.get("context_policy"));
        refreshUi(field.value);
      };

      field.addEventListener("input", handleInput);
      field.addEventListener("change", handleChange);
      field.addEventListener("keydown", handleKeydown);
      field.addEventListener("focusout", handleBlur);
      if (typeof model.on === "function") {
        model.on("change:value", handleModelValueChange);
        model.on("change:context_names", handleContextNamesChange);
        model.on("change:context_policy", handleContextPolicyChange);
      }

      refreshUi(committedValue);

      return () => {
        field.removeEventListener("input", handleInput);
        field.removeEventListener("change", handleChange);
        field.removeEventListener("keydown", handleKeydown);
        field.removeEventListener("focusout", handleBlur);
        if (typeof model.off === "function") {
          model.off("change:value", handleModelValueChange);
          model.off("change:context_names", handleContextNamesChange);
          model.off("change:context_policy", handleContextPolicyChange);
        }
      };
    },
  };
}

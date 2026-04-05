const MATHLIVE_MODULE_URL = "https://esm.run/mathlive";

function normalizeValue(value) {
  return typeof value === "string" ? value : "";
}

function setMathfieldValue(field, value) {
  const next = normalizeValue(value);
  if (field.value === next) {
    return;
  }

  if (typeof field.setValue === "function") {
    field.setValue(next, { silenceNotifications: true });
    return;
  }

  field.value = next;
}

export default async function () {
  await import(MATHLIVE_MODULE_URL);
  await customElements.whenDefined("math-field");

  return {
    render({ model, el }) {
      el.classList.add("gu-math-input-root");
      el.replaceChildren();

      const field = document.createElement("math-field");
      field.setAttribute("aria-label", "Math input");
      setMathfieldValue(field, model.get("value"));

      const handleInput = () => {
        const next = normalizeValue(field.value);
        if (model.get("value") === next) {
          return;
        }
        model.set("value", next);
        model.save_changes();
      };

      const handleModelChange = () => {
        setMathfieldValue(field, model.get("value"));
      };

      field.addEventListener("input", handleInput);
      if (typeof model.on === "function") {
        model.on("change:value", handleModelChange);
      }

      el.appendChild(field);

      return () => {
        field.removeEventListener("input", handleInput);
        if (typeof model.off === "function") {
          model.off("change:value", handleModelChange);
        }
      };
    },
  };
}

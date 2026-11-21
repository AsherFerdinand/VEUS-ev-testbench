// This versioned session preference is set only by a deliberate confirmation.
const key = "veus.model-assumptions.v1";
let memory = false;
export function acknowledged() {
  try {
    return sessionStorage.getItem(key) === "confirmed";
  } catch {
    return memory;
  }
}
export function confirmAssumptions(value) {
  memory = value;
  try {
    value
      ? sessionStorage.setItem(key, "confirmed")
      : sessionStorage.removeItem(key);
  } catch {
    /* Mounted controls retain consent. */
  }
}

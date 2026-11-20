// One bounded local library. Geometry and engineering results are not duplicated here.
export const state = {
  design: null,
  evaluation: null,
  library: [],
  activeId: null,
  dirty: false,
  storageError: null,
  loaded: false,
};
const KEY = "veus.design-library.v2",
  LIMIT = 16,
  BYTES = 180000;
function shape(d) {
  return (
    d &&
    d.schema_version === 2 &&
    d.classification === "illustrative" &&
    typeof d.name === "string" &&
    d.name.length <= 100 &&
    [
      "battery",
      "motor",
      "inverter",
      "body",
      "charging",
      "dcdc",
      "gearbox",
      "operating_point",
      "assumptions",
    ].every((k) => d[k] && typeof d[k] === "object" && !Array.isArray(d[k]))
  );
}
export function loadLibrary() {
  if (state.loaded) return;
  state.loaded = true;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return;
    if (new TextEncoder().encode(raw).length > BYTES)
      throw Error("Stored library exceeds its 180 KB bound");
    const value = JSON.parse(raw);
    if (
      value.schema_version !== 1 ||
      !Array.isArray(value.records) ||
      value.records.length > LIMIT ||
      !value.records.every(
        (r) =>
          typeof r.id === "string" &&
          /^[A-Za-z0-9_-]{1,80}$/.test(r.id) &&
          shape(r.design),
      ) ||
      new Set(value.records.map((r) => r.id)).size !== value.records.length
    )
      throw Error("Stored design library is invalid");
    state.library = value.records;
    state.activeId = value.active_id;
    const record = state.library.find((r) => r.id === state.activeId);
    if (!record && state.activeId !== null)
      throw Error("Stored active design is missing");
    state.design = record ? structuredClone(record.design) : null;
  } catch (e) {
    state.library = [];
    state.activeId = null;
    state.design = null;
    state.storageError = e.message + "; stored data was not changed.";
  }
}
export function persist(records, activeId) {
  if (records.length > LIMIT)
    throw Error(
      "Library is limited to 16 designs. Export or delete an unused design first.",
    );
  const raw = JSON.stringify({
    schema_version: 1,
    active_id: activeId,
    records,
  });
  if (new TextEncoder().encode(raw).length > BYTES)
    throw Error("Library exceeds 180 KB");
  if (state.storageError)
    throw Error(
      state.storageError + " Reset the library explicitly before replacing it.",
    );
  try {
    localStorage.setItem(KEY, raw);
  } catch {
    throw Error(
      "Browser storage is unavailable or full. Export JSON to keep your design; library was not changed.",
    );
  }
  state.library = records;
  state.activeId = activeId;
  window.dispatchEvent(new Event("veus:design"));
}
export function resetLibrary() {
  localStorage.removeItem(KEY);
  state.storageError = null;
  state.library = [];
  state.activeId = null;
  state.design = null;
  state.evaluation = null;
  window.dispatchEvent(new Event("veus:design"));
}
export function newId() {
  return crypto.randomUUID
    ? crypto.randomUUID()
    : "design-" +
        Date.now().toString(36) +
        "-" +
        Math.random().toString(36).slice(2);
}

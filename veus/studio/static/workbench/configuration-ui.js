import { state } from "./design-state.js";
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const fmt = (v) =>
  Number.isFinite(v)
    ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : "Unavailable";
export function simplifyConfiguration(root, { evaluate, changed }) {
  root.refocusLife?.abort();
  const life = (root.refocusLife = new AbortController()),
    $ = (id) => root.querySelector("#" + id);
  root.querySelector(".page-heading").remove();
  root.querySelector(".preset-action").hidden = true;
  root.querySelector(".library-toolbar label").firstChild.textContent =
    "Load Vehicle";
  $("design-save").textContent = "Save Vehicle";
  $("design-export").textContent = "Export Configuration (.json)";
  for (const id of ["design-new", "design-duplicate"])
    root.querySelector(".library-more div").append($(id));
  $("studio-appearance")
    .closest("label")
    .prepend(document.createTextNode("Advanced visual-only override · "));
  const advanced = document.createElement("details");
  advanced.id = "advanced-configuration";
  advanced.innerHTML =
    "<summary>Advanced Configuration · components, limits & appearance</summary>";
  const layout = root.querySelector(".studio-layout");
  layout.before(advanced);
  advanced.append(layout);
  const drawing = layout.querySelector(".drawing-panel");
  advanced.append(drawing.querySelector(".studio-view-controls"));
  drawing.remove();
  const analysis = document.createElement("details");
  analysis.id = "advanced-analysis";
  analysis.innerHTML =
    "<summary>Advanced Analysis · comparisons, sensitivity, cost & calculations</summary>";
  advanced.before(analysis);
  for (const node of [
    ...root.querySelectorAll(
      "#engineering-insights,#controlled-analysis,.studio-evidence",
    ),
  ])
    analysis.append(node);
  const basic = document.createElement("section");
  basic.id = "basic-configuration";
  basic.innerHTML = `<div class="basic-grid"><label>Vehicle type<output>${esc(state.design.name)}</output></label><label>Usable battery capacity · kWh<input id="basic-capacity" type="number" min="1" max="${state.design.battery.gross_capacity_kwh}" step="any" value="${state.design.battery.usable_capacity_kwh}"></label><label>Continuous motor power · kW<input id="basic-power" type="number" min="1" step="any" value="${state.design.motor.rated_power_kw}"></label><label>Total vehicle mass · kg<input id="basic-mass" type="number" min="1" step="any"></label><label>Drag coefficient · dimensionless<input id="basic-drag" type="number" min=".01" max="1" step="any" value="${state.design.body.drag_coefficient}"></label><label>Selected powertrain model<select id="basic-model"><option value="">Legacy constant efficiency</option><option value="illustrative_map">Illustrative operating-point map</option></select></label></div><p class="quiet">Capacity stays within declared gross capacity. Mass edits adjust residual body mass while component masses remain explicit. Advanced Configuration retains all detailed bounds.</p><a class="primary run-configuration" href="/?workspace=simulation">Run Simulation →</a><p>Configuration JSON is a reproducible vehicle model, not measurement data. The Lab receives this active configuration automatically. The selected loss model is a run option preserved in simulation exports; vehicle JSON keeps its compatible format.</p><div id="configuration-results" class="analysis-metrics" aria-live="polite"></div>`;
  root.querySelector(".vehicle-preset-selection").after(basic);
  basic.querySelector(".run-configuration").onclick = (event) => {
    for (const field of basic.querySelectorAll("input"))
      if (!field.reportValidity()) {
        event.preventDefault();
        return;
      }
  };
  basic.insertBefore(
    $("configuration-status"),
    basic.querySelector(".run-configuration"),
  );
  const masses = () => {
    const values = [
      "battery",
      "motor",
      "inverter",
      "charging",
      "dcdc",
      "gearbox",
    ].map((k) => state.design[k].mass_kg);
    return values.every(Number.isFinite)
      ? values.reduce((a, b) => a + b, 0)
      : NaN;
  };
  $("basic-mass").value =
    state.design.body.mass_excluding_components_kg + masses();
  $("basic-model").value = state.powertrainModel || "";
  $("basic-model").onchange = () => {
    state.powertrainModel = $("basic-model").value;
    window.dispatchEvent(new Event("veus:design"));
  };
  for (const [id, group, key] of [
    ["basic-capacity", "battery", "usable_capacity_kwh"],
    ["basic-power", "motor", "rated_power_kw"],
    ["basic-drag", "body", "drag_coefficient"],
    ["basic-mass", "body", "mass_excluding_components_kg"],
  ])
    $(id).onchange = async () => {
      if (!$(id).reportValidity()) return;
      state.design[group][key] =
        $(id).valueAsNumber - (id === "basic-mass" ? masses() : 0);
      if (group in state.design.component_ids)
        state.design.component_ids[group] = "custom";
      state.dirty = true;
      changed();
      await evaluate();
      for (const n of root.querySelectorAll("[data-field]"))
        n.value = state.design[n.dataset.group][n.dataset.field] ?? "";
      const record = $("component-record");
      if (record)
        record.value =
          state.design.component_ids[$("design-group").value] || "custom";
    };
  function results() {
    if (!state.design || !root.isConnected) return;
    basic.querySelector("output").textContent = state.design.name;
    for (const [id, value] of [
      ["basic-capacity", state.design.battery.usable_capacity_kwh],
      ["basic-power", state.design.motor.rated_power_kw],
      ["basic-drag", state.design.body.drag_coefficient],
      ["basic-mass", state.design.body.mass_excluding_components_kg + masses()],
    ])
      if (document.activeElement !== $(id)) $(id).value = value;
    const same = (r) =>
      r &&
      JSON.stringify(r.request?.vehicle) === JSON.stringify(state.design) &&
      (r.request?.efficiency_model || "") === (state.powertrainModel || "");
    const run = same(state.lastSimulation) ? state.lastSimulation : null,
      insight = same(state.lastInsights) ? state.lastInsights : null;
    $("configuration-results").innerHTML =
      [
        [
          "Energy consumption",
          run?.summary.consumption_kwh_100km,
          "kWh/100 km",
        ],
        [
          "Cycle-equivalent range",
          insight?.metrics.cycle_equivalent_range_km.value,
          "km",
        ],
        ["Battery SOC", run ? run.summary.final_soc * 100 : null, "%"],
      ]
        .map(
          ([n, v, u]) =>
            `<div><span>${n}</span><strong>${fmt(v)} <small>${u}</small></strong></div>`,
        )
        .join("") +
      '<p class="quiet">Only matching computed snapshots are shown. Range requires an eligible full-cycle Insights calculation under Advanced Analysis. Predictions are not measured or certified results.</p>';
  }
  results();
  window.addEventListener("veus:run", results, { signal: life.signal });
  window.addEventListener("veus:design", results, { signal: life.signal });
}

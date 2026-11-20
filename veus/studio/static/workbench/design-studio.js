import { anatomySVG, updateSchematic } from "./schematic.js";
import {
  state,
  loadLibrary,
  persist,
  resetLibrary,
  newId,
} from "./design-state.js";
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const names = {
  battery: "Battery system",
  motor: "Traction motor",
  inverter: "Inverter",
  body: "Body & wheels",
  charging: "Charging",
  dcdc: "DC/DC converter",
  gearbox: "Reduction gearbox",
  operating_point: "Electrical / torque operating point",
  assumptions: "Model assumptions",
};
const componentId = {
  battery: "battery",
  motor: "motor",
  inverter: "inverter",
  body: null,
  charging: "charger",
  dcdc: "dcdc",
  gearbox: "gearbox",
  operating_point: "inverter",
  assumptions: null,
};
const essentials = {
  battery: [
    "chemistry",
    "usable_capacity_kwh",
    "gross_capacity_kwh",
    "nominal_voltage_v",
    "mass_kg",
  ],
  motor: [
    "topology",
    "rated_power_kw",
    "peak_power_kw",
    "rated_torque_nm",
    "peak_torque_nm",
  ],
  inverter: [
    "technology",
    "continuous_power_kw",
    "peak_power_kw",
    "maximum_dc_voltage_v",
  ],
  body: [
    "mass_excluding_components_kg",
    "drag_coefficient",
    "frontal_area_m2",
    "wheel_radius_m",
  ],
  charging: ["maximum_ac_kw", "maximum_dc_kw", "maximum_dc_voltage_v"],
  dcdc: ["rated_power_kw", "output_voltage_v", "mass_kg"],
  gearbox: ["reduction_ratio", "mechanical_efficiency", "mass_kg"],
  operating_point: ["dc_voltage_v", "dc_power_kw", "motor_torque_nm"],
  assumptions: ["initial_soc", "friction_coefficient", "grade_percent"],
};
const enums = {
  chemistry: ["unspecified", "LFP", "NMC"],
  topology: ["unspecified", "PMSM", "induction"],
  technology: ["unspecified", "silicon", "SiC"],
};
const unit = {
  kg: "kg",
  kwh: "kWh",
  kw: "kW",
  v: "V",
  a: "A",
  nm: "N·m",
  rpm: "rpm",
  m: "m",
  m2: "m²",
  ohm: "Ω",
  s: "s",
  percent: "%",
  m3: "kg/m³",
};
const label = (k) =>
  k === "mass_excluding_components_kg"
    ? "Body mass, excluding listed components · kg"
    : k === "mechanical_efficiency"
      ? "Gearbox efficiency assumption · fraction"
      : k === "efficiency_assumption"
        ? "Efficiency assumption · fraction"
        : k
            .replace(/_/g, " ")
            .replace(
              /\b(kwh|kw|kg|v|a|nm|rpm|ohm|m2|m3|s|percent)$/,
              (v) => "· " + unit[v],
            );
const acknowledgementLabels = {
  illustrative_parameters:
    "These are representative assumptions, not a calibrated production vehicle.",
  constant_efficiency:
    "Use explicitly assumed constant motor and inverter efficiencies.",
  constant_ocv:
    "Use a fixed open-circuit-voltage and resistance battery model.",
  longitudinal_only:
    "Forward longitudinal dynamics only; no steering, lateral dynamics or slip model.",
  unmodelled_thermal_charging:
    "No thermal, ageing, charging-curve or coupled experiment prediction.",
};
const statusText = (s) => String(s || "unknown").replaceAll("_", " ");
async function request(path, value, signal) {
  const r = await fetch("/api/workbench/v2/" + path, {
    ...(value === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(value),
        }),
    signal,
  });
  const data = await r.json();
  if (!r.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
let cataloguePromise;
const catalogue = () =>
  (cataloguePromise ||= request("catalogue").catch((e) => {
    cataloguePromise = null;
    throw e;
  }));
function exportJSON(value) {
  const a = document.createElement("a");
  a.download = "veus-vehicle-design-v2.json";
  a.href = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
const fmt = (v) =>
  v === null || v === undefined
    ? "Unavailable"
    : typeof v === "number"
      ? Number(v.toFixed(4)).toLocaleString()
      : String(v);
export async function mountStudio(root, { content, header, notice }) {
  if (!document.getElementById("studio-css")) {
    const css = document.createElement("link");
    css.id = "studio-css";
    css.rel = "stylesheet";
    css.href = "/static/workbench/design-studio.css";
    document.head.append(css);
  }
  loadLibrary();
  let alive = true,
    timer = null,
    generation = 0,
    controller = null,
    group = "battery",
    comparison = null;
  const cat = await catalogue();
  if (!root.isConnected) return () => {};
  if (!state.design) state.design = await request("design");
  const find = (id) => root.querySelector("#" + id);
  const connected = () => alive && root.isConnected;
  function syncLabel() {
    window.dispatchEvent(new Event("veus:design"));
  }
  function shell() {
    root.innerHTML =
      header(
        "03 / CONFIGURATION → EVIDENCE → MODEL",
        "Design a system. Know its limits.",
        "Representative components, explicit assumptions and checked specifications. Save a baseline before changing a design.",
        "FUNCTIONAL DESIGN STUDIO",
      ) +
      `
 <div class="library-toolbar"><label>Local design library<select id="library-select"><option value="">Unsaved design</option>${state.library.map((r) => `<option value="${esc(r.id)}" ${r.id === state.activeId ? "selected" : ""}>${esc(r.design.name)}</option>`).join("")}</select></label><label class="design-title">Active design<input id="design-name" maxlength="100" value="${esc(state.design.name)}"></label><button id="design-save" class="primary">Save design</button><button id="design-new">New</button><button id="design-duplicate">Duplicate</button><details class="library-more"><summary>Files & library</summary><div><button id="design-export">Export JSON</button><label>Import JSON<input id="design-import" type="file" accept=".json"></label><button id="design-delete">Delete saved design…</button><button id="library-reset">Reset library…</button></div></details></div>
 <p class="library-note" id="library-status">${state.storageError ? esc(state.storageError) : "Local browser storage · up to 16 designs / 180 KB · export JSON for a portable backup."}</p>
 <div class="design-layout studio-layout"><div><div class="drawing-panel"><div class="drawing-toolbar"><span class="drawing-id">ACTIVE VEHICLE / ${esc(state.design.catalogue_version)}</span><div class="studio-view-controls"><label>Body<select id="studio-body"><option value="cutaway">Cutaway</option><option value="transparent">Transparent</option><option value="opaque">Complete body</option></select></label><label><input id="studio-annotations" type="checkbox" checked> Annotations</label></div></div><div id="design-schematic">${anatomySVG(content.components, true, { selected: componentId[group], body: "cutaway" })}</div><p id="anatomy-tooltip" aria-live="polite">Select a component or subsystem to inspect its configuration.</p><div class="drawing-footer"><span>Original conceptual vehicle · not production geometry</span><span>Illustrative components / no performance inferred from labels</span></div></div><div id="specifications" class="specification-strip" aria-live="polite"></div><div class="studio-evidence"><details id="compatibility-details" open><summary>Engineering compatibility <span id="compatibility-status"></span></summary><div id="compatibility-checks"></div></details><details><summary>Equations, inputs & assumptions</summary><div id="calculation-details"></div></details><details><summary>Prepare for the retained physics model</summary><div id="adapter-panel"></div></details><details id="comparison-details"><summary>Baseline versus modified specifications</summary><label>Saved baseline<select id="comparison-baseline"><option value="">Choose a saved design</option>${state.library.map((r) => `<option value="${esc(r.id)}">${esc(r.design.name)}</option>`).join("")}</select></label><button id="compare-designs">Compare with active design</button><div id="design-comparison"></div></details></div></div>
 <aside class="design-form studio-editor"><label>Subsystem<select id="design-group">${Object.entries(
   names,
 )
   .map(
     ([k, n]) =>
       `<option value="${k}" ${k === group ? "selected" : ""}>${n}</option>`,
   )
   .join(
     "",
   )}</select></label><div id="component-editor"></div><p id="configuration-status" class="configuration-status" role="status">Checking current design…</p><button id="design-check" type="button">Check specifications</button><details><summary>Catalogue evidence & classification</summary><div id="catalogue-evidence"></div></details></aside></div>`;
    editor();
    bind();
    updateSchematic(root.querySelector(".anatomy-svg"), {
      selected: componentId[group],
      body: "cutaway",
    });
    if (
      state.evaluation &&
      JSON.stringify(state.evaluation.design) === JSON.stringify(state.design)
    ) {
      renderResults(state.evaluation);
      find("configuration-status").textContent =
        "Checked · " + statusText(state.evaluation.compatibility_status);
    } else evaluation();
  }
  function invalidateComparison() {
    comparison = null;
    const node = find("design-comparison");
    if (node)
      node.textContent =
        "Design changed; compare again to refresh specifications.";
  }
  function editor() {
    const value = state.design[group],
      records = cat.components.filter((c) => c.kind === group);
    find("component-editor").innerHTML =
      `<h2>${names[group]}</h2>${records.length ? `<label>Representative component<select id="component-record"><option value="custom">Custom / edited values</option>${records.map((r) => `<option value="${esc(r.id)}" ${state.design.component_ids[group] === r.id ? "selected" : ""}>${esc(r.label)}</option>`).join("")}</select></label><p class="quiet">Illustrative engineering examples, not manufacturer specifications. Selecting a component changes its declared parameters.</p>` : ""}<div class="field-grid">${essentials[group].map(field).join("")}</div><details class="advanced-fields"><summary>Advanced limits, masses & assumptions</summary><div class="field-grid">${Object.keys(
        value,
      )
        .filter((k) => !essentials[group].includes(k))
        .map(field)
        .join(
          "",
        )}</div></details><p class="quiet">Blank optional values remain unknown. Compatibility checks are not electrical, thermal or safety certification.</p>`;
    if (find("component-record"))
      find("component-record").onchange = (e) => {
        const record = records.find((r) => r.id === e.target.value);
        if (!record) return;
        state.design[group] = { ...state.design[group], ...record.parameters };
        state.design.component_ids[group] = record.id;
        state.dirty = true;
        invalidateComparison();
        editor();
        evaluation();
      };
    find("component-editor").oninput = (e) => {
      const k = e.target.dataset.field;
      if (!k) return;
      state.design[group][k] =
        e.target.tagName === "SELECT"
          ? e.target.value
          : e.target.value === ""
            ? null
            : e.target.valueAsNumber;
      if (group in state.design.component_ids) {
        state.design.component_ids[group] = "custom";
        const menu = find("component-record");
        if (menu && menu.value !== "custom") {
          menu.value = "custom";
          evidence();
        }
      }
      state.dirty = true;
      invalidateComparison();
      clearTimeout(timer);
      find("configuration-status").textContent =
        "Unvalidated edits; checking after input settles…";
      timer = setTimeout(evaluation, 250);
    };
    evidence();
  }
  function field(k) {
    const v = state.design[group][k],
      options = enums[k];
    return `<label>${esc(label(k))}${options ? `<select data-field="${esc(k)}" data-group="${group}">${options.map((x) => `<option ${x === v ? "selected" : ""}>${x}</option>`).join("")}</select>` : typeof v === "string" ? `<input value="${esc(v)}" disabled>` : `<input data-field="${esc(k)}" data-group="${group}" type="number" step="any" value="${esc(v ?? "")}" placeholder="unknown">`}</label>`;
  }
  function evidence() {
    const rec = cat.components.find(
      (r) => r.id === state.design.component_ids[group],
    );
    find("catalogue-evidence").innerHTML = rec
      ? `<p class="quiet">${esc(rec.label)} · ${esc(rec.technology)} · ${esc(rec.classification || "illustrative")}</p>${Object.entries(
          rec.parameter_metadata,
        )
          .map(([k, m]) => {
            const s = cat.sources.find((s) => s.id === m.source_id);
            return `<p class="quiet"><strong>${esc(label(k))}</strong> · ${esc(m.unit)} · ${esc(m.classification)}<br>${esc(m.operating_conditions)}<br>Uncertainty: ${esc(m.uncertainty ?? "Not quantified")}${s ? `<br><a href="${esc(s.url || s.source_url || "#")}">${esc(s.title || s.id)}</a>` : ""}</p>`;
          })
          .join("")}`
      : '<p class="quiet">Custom resolved values. Catalogue identity no longer describes these fields. Check all units and assumptions; original resolved values remain in exported design JSON.</p>';
  }
  async function evaluation() {
    clearTimeout(timer);
    const current = ++generation;
    controller?.abort();
    controller = new AbortController();
    state.evaluation = null;
    find("design-save").disabled = true;
    find("configuration-status").textContent =
      "Checking declared limits and supported calculations…";
    try {
      const result = await request("evaluate", state.design, controller.signal);
      if (!connected() || current !== generation) return;
      state.design = structuredClone(result.design);
      state.evaluation = result;
      find("design-save").disabled = false;
      find("configuration-status").textContent =
        "Checked · " +
        statusText(result.compatibility_status) +
        " · not physical validation";
      renderResults(result);
      syncLabel();
    } catch (e) {
      if (!connected() || current !== generation || e.name === "AbortError")
        return;
      find("configuration-status").textContent =
        "Invalid configuration: " + e.message;
      find("specifications").textContent =
        "Specifications unavailable for invalid inputs.";
      find("calculation-details").textContent =
        "Correct invalid inputs before inspecting calculations.";
      find("compatibility-status").textContent = "· invalid input";
      find("compatibility-checks").textContent =
        "Correct structural errors before evaluating compatibility.";
      find("adapter-panel").textContent = "Unavailable: invalid configuration.";
    }
  }
  function renderResults(r) {
    const specs = r.specifications;
    find("specifications").innerHTML = [
      "total_mass_kg",
      "usable_nominal_capacity_ah",
      "peak_power_to_weight_kw_per_tonne",
      "drag_area_m2",
    ]
      .map(
        (k) =>
          `<div><span>${esc(k.replaceAll("_", " "))}</span><strong>${fmt(specs[k]?.value)} <small>${esc(specs[k]?.unit || "")}</small></strong></div>`,
      )
      .join("");
    find("compatibility-status").textContent =
      "· " + statusText(r.compatibility_status);
    find("compatibility-checks").innerHTML = r.checks
      .map(
        (c) =>
          `<div class="compatibility-row" data-status="${esc(c.status)}"><span>${esc(statusText(c.status))}</span><p>${esc(c.explanation || c.message || c.id)}</p></div>`,
      )
      .join("");
    find("calculation-details").innerHTML = Object.entries(specs)
      .map(
        ([k, s]) =>
          `<section class="calculation-row"><h3>${esc(k.replaceAll("_", " "))} · ${fmt(s.value)} ${esc(s.unit)}</h3><code>${esc(s.equation)}</code><p class="quiet">${esc(s.unavailable_reason || "")}${esc(Array.isArray(s.assumptions) ? s.assumptions.join(" ") : s.assumptions || "")}</p><pre>${esc(JSON.stringify(s.inputs, null, 2))}</pre></section>`,
      )
      .join("");
    const ready = r.simulation_readiness;
    find("adapter-panel").innerHTML =
      `<p>${esc(statusText(ready.status))}</p>${ready.missing_inputs?.length ? `<p class="quiet">Missing inputs: ${esc(ready.missing_inputs.join(", "))}</p>` : ""}${ready.blocking_checks?.length ? `<p class="quiet">Blocking checks: ${esc(ready.blocking_checks.join(", "))}</p>` : ""}<p class="quiet">Explicit parameter mapping to the retained longitudinal and energy models. Preparing does not execute a simulation.</p>${(ready.required_acknowledgements || []).map((x) => `<label class="acknowledgement"><input type="checkbox" data-ack="${esc(typeof x === "string" ? x : x.id)}"> ${esc(typeof x === "string" ? acknowledgementLabels[x] || x.replaceAll("_", " ") : x.description || x.label || x.id)}</label>`).join("")}<button id="prepare-adapter" ${ready.status !== "requires_acknowledgement" ? "disabled" : ""}>Prepare model configuration</button><pre id="adapter-result"></pre>`;
    find("prepare-adapter").onclick = async () => {
      try {
        const ack = [...root.querySelectorAll("[data-ack]:checked")].map(
          (x) => x.dataset.ack,
        );
        const result = await request("adapter", {
          design: state.design,
          acknowledgements: ack,
        });
        if (connected())
          find("adapter-result").textContent = JSON.stringify(result, null, 2);
      } catch (e) {
        if (connected()) find("adapter-result").textContent = e.message;
      }
    };
  }
  async function checked() {
    await evaluation();
    if (!state.evaluation)
      throw Error("Correct invalid configuration before saving.");
    return structuredClone(state.design);
  }
  function bind() {
    find("design-group").onchange = (e) => {
      group = e.target.value;
      editor();
      updateSchematic(root.querySelector(".anatomy-svg"), {
        selected: componentId[group],
      });
    };
    const svg = root.querySelector(".anatomy-svg");
    for (const g of svg.querySelectorAll("[data-component]")) {
      const choose = () => {
        const kind =
          Object.entries(componentId).find(
            ([k, id]) => id === g.dataset.component,
          )?.[0] ||
          {
            bms: "assumptions",
            thermal: "assumptions",
            port: "charging",
            aux: "dcdc",
          }[g.dataset.component];
        if (kind) {
          group = kind;
          find("design-group").value = kind;
          editor();
        }
        updateSchematic(svg, { selected: g.dataset.component });
      };
      g.onclick = choose;
      g.onkeydown = (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          choose();
        }
      };
      g.onfocus = g.onmouseenter = () => {
        find("anatomy-tooltip").textContent =
          content.components.find((c) => c.id === g.dataset.component)
            ?.function || g.dataset.component;
      };
    }
    svg.onclick = (e) => {
      const marker = e.target.closest("[data-component-link]");
      if (marker) {
        const node = svg.querySelector(
          `[data-component="${marker.dataset.componentLink}"]`,
        );
        node?.dispatchEvent(new Event("click"));
      }
    };
    find("studio-body").onchange = (e) =>
      updateSchematic(svg, { body: e.target.value });
    find("studio-annotations").onchange = (e) =>
      updateSchematic(svg, { annotations: e.target.checked });
    find("design-name").oninput = (e) => {
      state.design.name = e.target.value;
      state.dirty = true;
      invalidateComparison();
      syncLabel();
    };
    find("design-check").onclick = evaluation;
    find("design-save").onclick = async () => {
      try {
        const d = await checked(),
          id = state.activeId || newId(),
          records = state.library.filter((r) => r.id !== id);
        records.push({ id, design: d });
        persist(records, id);
        state.dirty = false;
        shell();
        notice("Design saved locally. Export JSON for a portable copy.");
      } catch (e) {
        notice(e.message);
      }
    };
    find("design-new").onclick = async () => {
      if (
        state.dirty &&
        !confirm("Discard unsaved edits and create a new design?")
      )
        return;
      state.design = await request("design");
      state.activeId = null;
      state.dirty = false;
      shell();
      syncLabel();
    };
    find("design-duplicate").onclick = async () => {
      try {
        const d = await checked();
        d.name = d.name.slice(0, 90) + " · copy";
        const id = newId();
        persist([...state.library, { id, design: d }], id);
        state.design = structuredClone(d);
        state.dirty = false;
        shell();
        syncLabel();
      } catch (e) {
        notice(e.message);
      }
    };
    find("design-delete").onclick = async () => {
      try {
        if (!state.activeId) return notice("This design has not been saved.");
        if (!confirm("Delete this saved design from this browser?")) return;
        const records = state.library.filter((r) => r.id !== state.activeId);
        persist(records, records[0]?.id || null);
        state.design = records[0]
          ? structuredClone(records[0].design)
          : await request("design");
        state.evaluation = null;
        state.dirty = false;
        shell();
        syncLabel();
      } catch (e) {
        notice(e.message);
      }
    };
    find("library-reset").onclick = async () => {
      if (
        !confirm(
          "Delete the entire local design library? Export your designs first.",
        )
      )
        return;
      try {
        resetLibrary();
        state.design = await request("design");
        state.evaluation = null;
        state.dirty = false;
        shell();
        syncLabel();
      } catch (e) {
        notice(e.message);
      }
    };
    find("library-select").onchange = async (e) => {
      const record = state.library.find((r) => r.id === e.target.value);
      if (!record) return;
      if (
        state.dirty &&
        !confirm("Discard unsaved edits and open the saved design?")
      )
        return;
      try {
        const r = await request("evaluate", record.design);
        persist(state.library, record.id);
        state.design = r.design;
        state.dirty = false;
        shell();
        syncLabel();
      } catch (e) {
        notice("Saved record rejected: " + e.message);
      }
    };
    find("design-export").onclick = async () => {
      try {
        exportJSON(await checked());
      } catch (e) {
        notice(e.message);
      }
    };
    find("design-import").onchange = async (e) => {
      try {
        const f = e.target.files[0];
        if (!f) return;
        if (f.size > 64000) throw Error("Import is limited to 64 KB");
        let d = JSON.parse(await f.text());
        if (d.schema_version === 1) d = (await request("migrate", d)).design;
        const result = await request("evaluate", d);
        state.design = result.design;
        state.activeId = null;
        state.dirty = true;
        shell();
        notice("Valid design imported; review and save to persist it.");
      } catch (e) {
        notice("Import rejected: " + e.message);
      }
    };
    find("compare-designs").onclick = async () => {
      const record = state.library.find(
        (r) => r.id === find("comparison-baseline").value,
      );
      if (!record) return notice("Choose a saved baseline first.");
      try {
        comparison = await request("compare", {
          baseline: record.design,
          modified: state.design,
        });
        if (!connected()) return;
        find("design-comparison").innerHTML =
          `<p class="quiet">Saved baseline ${esc(record.design.name)} versus active ${esc(state.design.name)}. Specifications only; no simulated outcomes.</p><table><thead><tr><th>Quantity</th><th>Baseline</th><th>Modified</th><th>Difference</th><th>Unit</th></tr></thead><tbody>${comparison.differences.map((d) => `<tr><td>${esc(d.key.replaceAll("_", " "))}</td><td>${fmt(d.baseline)}</td><td>${fmt(d.modified)}</td><td>${fmt(d.delta)}</td><td>${esc(d.unit)}</td></tr>`).join("")}</tbody></table><h3>Changed declared parameters</h3><table><thead><tr><th>Parameter</th><th>Baseline</th><th>Modified</th><th>Unit</th></tr></thead><tbody>${comparison.changed_parameters.map((d) => `<tr><td>${esc(d.key)}</td><td>${esc(fmt(d.baseline))}</td><td>${esc(fmt(d.modified))}</td><td>${esc(d.unit)}</td></tr>`).join("")}</tbody></table>`;
      } catch (e) {
        notice(e.message);
      }
    };
  }
  shell();
  syncLabel();
  return () => {
    alive = false;
    clearTimeout(timer);
    controller?.abort();
  };
}

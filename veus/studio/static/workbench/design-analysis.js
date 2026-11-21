import { state } from "./design-state.js";
import { esc, fmt, bars, post, download } from "./engineering-insights.js";
const ACKS = [
  "illustrative_parameters",
  "constant_efficiency",
  "constant_ocv",
  "longitudinal_only",
  "unmodelled_thermal_charging",
];
export function mountAnalysis(root) {
  const life = new AbortController();
  let controller = null,
    last = null;
  const $ = (id) => root.querySelector("#" + id);
  const options = () =>
    '<option value="active">Current active draft</option>' +
    state.library
      .map((r) => `<option value="${esc(r.id)}">${esc(r.design.name)}</option>`)
      .join("");
  root.innerHTML = `<details id="analysis-panel"><summary>Compare Designs · controlled comparisons and sensitivity</summary><p class="quiet">Matched complete profiles and continuous-rating acceleration. No optimizer; failures remain visible. Saved records are never edited by studies.</p><form id="analysis-form" class="analysis-form"><label>Study<select id="analysis-kind"><option value="compare">Baseline versus modified</option><option value="sensitivity">Single-parameter sensitivity</option><option value="battery_size">Battery capacity with explicit pack mass</option></select></label><label>Baseline<select id="analysis-baseline">${options()}</select></label><label id="analysis-modified-label">Modified<select id="analysis-modified">${options()}</select></label><label>Matched profile<select id="analysis-profile"><option value="urban">Illustrative urban</option><option value="motorway">Illustrative motorway</option><option value="udds">FASTSim UDDS</option><option value="hwfet">FASTSim HWFET</option></select></label><label id="analysis-parameter-label" hidden>Single parameter<select id="analysis-parameter"><option value="body.drag_coefficient">Drag coefficient</option><option value="body.mass_excluding_components_kg">Residual body mass · kg</option><option value="body.frontal_area_m2">Frontal area · m²</option><option value="body.rolling_resistance_coefficient">Rolling coefficient</option><option value="battery.usable_capacity_kwh">Usable energy · kWh (others fixed)</option><option value="motor.rated_power_kw">Continuous motor rating · kW</option></select></label><label id="analysis-values-label" hidden>2–5 values, comma separated<input id="analysis-values" value=".22,.25,.3"></label><label id="analysis-mass-label" hidden>Explicit pack mass / usable energy · kg/kWh<input id="analysis-mass" type="number" step="any" min=".1" max="40" value="7"></label><label class="analysis-ack"><input id="analysis-ack" type="checkbox" required>I acknowledge illustrative parameters, constant OCV/efficiencies, longitudinal-only motion and unmodelled thermal/charging behaviour. Battery mass scaling is an explicit user assumption, not physical pack design.</label><button id="analysis-run">Run bounded study</button></form><p id="analysis-status" role="status">No controlled study executed.</p><div id="analysis-results"></div><div id="analysis-chart"></div><div class="lab-export"><button data-analysis-format="json" disabled>JSON</button><button data-analysis-format="csv" disabled>CSV</button><button data-analysis-format="html" disabled>HTML report</button></div></details>`;
  function changed() {
    if (last)
      $("analysis-status").textContent =
        "Inputs or active design changed. Displayed study is frozen; run again to update.";
  }
  window.addEventListener("veus:design", changed, { signal: life.signal });
  $("analysis-kind").onchange = () => {
    const kind = $("analysis-kind").value;
    $("analysis-modified-label").hidden = kind !== "compare";
    $("analysis-values-label").hidden = kind === "compare";
    $("analysis-parameter-label").hidden = kind !== "sensitivity";
    $("analysis-mass-label").hidden = kind !== "battery_size";
    if (kind === "battery_size") $("analysis-values").value = "50,70,90";
    changed();
  };
  const snapshot = (id) =>
    structuredClone(
      id === "active"
        ? state.design
        : state.library.find((r) => r.id === id)?.design,
    );
  $("analysis-form").onsubmit = async (e) => {
    e.preventDefault();
    controller?.abort();
    controller = new AbortController();
    $("analysis-run").disabled = true;
    $("analysis-status").textContent = "Executing matched bounded runs…";
    try {
      const kind = $("analysis-kind").value,
        req = {
          kind,
          baseline: snapshot($("analysis-baseline").value),
          modified:
            kind === "compare" ? snapshot($("analysis-modified").value) : null,
          conditions: {
            acknowledgements: ACKS,
            profile_id: $("analysis-profile").value,
            dt_s: 0.2,
            acceleration_duration_s: 30,
          },
          parameter: $("analysis-parameter").value,
          values:
            kind === "compare"
              ? []
              : $("analysis-values")
                  .value.split(",")
                  .map((v) => Number(v.trim())),
          battery_mass_kg_per_usable_kwh:
            kind === "battery_size" ? Number($("analysis-mass").value) : null,
        };
      const r = await post("design-analysis", req, controller.signal);
      last = r;
      window.VEUSDesignAnalysis = r;
      $("analysis-results").innerHTML =
        `<p><strong>${r.matched_conditions ? "Matched scenario conditions" : "Conditions differ — no controlled differences reported"}</strong></p>${r.warnings.map((w) => `<p>${esc(w)}</p>`).join("")}<table class="analysis-table"><thead><tr><th>Point</th><th>Value</th><th>Mass kg</th><th>Usable kWh</th><th>Continuous / peak kW</th><th>kWh/100 km</th><th>Equivalent km</th><th>Acceleration s</th><th>Status / limits</th></tr></thead><tbody>${r.rows
          .map((row) => {
            const a = row.analysis,
              m = a?.metrics;
            return `<tr><td>${esc(row.name)}</td><td>${fmt(row.parameter_value)}</td><td>${fmt(m?.total_vehicle_mass_kg.value)}</td><td>${fmt(m?.usable_battery_capacity_kwh.value)}</td><td>${fmt(m?.continuous_motor_power_kw.value)} / ${fmt(m?.peak_motor_power_kw.value)}</td><td>${fmt(m?.modelled_consumption_kwh_100km.value)}</td><td>${fmt(m?.cycle_equivalent_range_km.value)}</td><td>${fmt(m?.modelled_acceleration_time_s.value)}</td><td>${esc(row.status)} ${esc(row.error || a?.cycle.eligibility.reasons.join("; ") || Object.keys(a?.acceleration.limit_duration_s || {}).join(", "))}</td></tr>`;
          })
          .join(
            "",
          )}</tbody></table><details><summary>Absolute / percentage differences, changed fields and exact snapshots</summary><pre>${esc(JSON.stringify(r, null, 2))}</pre></details>`;
      $("analysis-chart").innerHTML = bars(
        r.rows.map((row) => ({
          name: row.name,
          consumption:
            row.analysis?.metrics.modelled_consumption_kwh_100km.value,
        })),
        "consumption",
        "Stored-energy sensitivity",
        "kWh/100 km",
      );
      for (const button of root.querySelectorAll("[data-analysis-format]"))
        button.disabled = false;
      $("analysis-status").textContent =
        "Completed. Inconclusive points remain in the evidence.";
    } catch (error) {
      if (error.name !== "AbortError")
        $("analysis-status").textContent = "Unavailable: " + error.message;
    } finally {
      if (!life.signal.aborted) $("analysis-run").disabled = false;
    }
  };
  for (const button of root.querySelectorAll("[data-analysis-format]"))
    button.onclick = async () => {
      try {
        const r = await post(
          "design-analysis/export",
          { result: last, format: button.dataset.analysisFormat },
          life.signal,
        );
        download(r.filename, r.content, r.media_type);
      } catch (error) {
        $("analysis-status").textContent =
          "Export unavailable: " + error.message;
      }
    };
  return () => {
    life.abort();
    controller?.abort();
    delete window.VEUSDesignAnalysis;
  };
}

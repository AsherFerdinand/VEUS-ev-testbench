import { acknowledged, confirmAssumptions } from "./assumptions.js";
// Click-driven, bounded model analyses. Every numerical quantity comes from Python.
import { state } from "./design-state.js";
const ACKS = [
  "illustrative_parameters",
  "constant_efficiency",
  "constant_ocv",
  "longitudinal_only",
  "unmodelled_thermal_charging",
];
export const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const fmt = (v) =>
  typeof v === "number" && Number.isFinite(v)
    ? v.toLocaleString(undefined, { maximumFractionDigits: 3 })
    : v == null
      ? "Unavailable"
      : String(v);
export function download(name, content, type = "application/json") {
  const a = document.createElement("a"),
    url = URL.createObjectURL(new Blob([content], { type }));
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function bars(rows, key, label, unit) {
  const vals = rows.map((r) => r[key]).filter(Number.isFinite),
    max = Math.max(1, ...vals);
  return `<article class="analysis-chart"><h4>${esc(label)} / ${esc(unit)}</h4>${rows.map((r) => `<div><span>${esc(r.name)}</span><i style="width:${Number.isFinite(r[key]) ? (Math.max(0, r[key]) / max) * 45 : 0}%"></i><b>${fmt(r[key])} ${esc(unit)}</b></div>`).join("")}</article>`;
}
export async function post(path, body, signal) {
  const r = await fetch("/api/workbench/v2/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  const value = await r.json();
  if (!r.ok)
    throw Error(
      typeof value.detail === "string"
        ? value.detail
        : JSON.stringify(value.detail),
    );
  return value;
}
export function mountInsights(root) {
  const life = new AbortController();
  let controller = null,
    last = null;
  const $ = (id) => root.querySelector("#" + id);
  root.innerHTML = `<details id="insights-panel"><summary>Engineering Insights · cycle energy, range and daily cost</summary><p class="quiet">Numerical model estimates, not certified or real-world range. Run the same complete profile for meaningful comparisons.</p><form id="insights-form" class="analysis-form"><label>Driving profile<select id="insights-profile"><option value="urban">Illustrative urban</option><option value="motorway">Illustrative motorway</option><option value="udds">FASTSim UDDS reference</option><option value="hwfet">FASTSim HWFET reference</option></select></label><label>Daily distance · km<input id="insights-distance" type="number" min="0" max="1000" step="any" value="40" required></label><label>User tariff · €/kWh<input id="insights-tariff" type="number" min="0" max="10" step="any" value=".30" required></label><label>Optional charging efficiency · 0–1<input id="insights-efficiency" type="number" min=".01" max="1" step="any" placeholder="Unknown"></label><label>Driving days / month<input id="insights-days" type="number" min="0" max="31" value="20" required></label><label>Acceleration target · km/h<input id="insights-target" type="number" min="1" max="250" value="100" required></label><label class="analysis-ack"><input id="insights-ack" type="checkbox" required>I acknowledge illustrative inputs, constant OCV/efficiencies, longitudinal motion only and unmodelled thermal/charging dynamics. Distance/tariff/days are editable user assumptions.</label><button id="insights-run">Evaluate active design</button><button id="insights-presets" type="button">Compare three default presets</button></form><p id="insights-status" role="status">No analysis executed.</p><div id="insights-result"></div><div id="insights-charts" class="analysis-charts"></div><button id="insights-export" disabled>Export analysis JSON</button></details>`;
  $("insights-ack").checked = acknowledged();
  $("insights-ack").addEventListener(
    "change",
    () => confirmAssumptions($("insights-ack").checked),
    { signal: life.signal },
  );
  function request(vehicle = state.design) {
    return {
      ...(state.powertrainModel
        ? { efficiency_model: state.powertrainModel }
        : {}),
      vehicle: structuredClone(vehicle),
      acknowledgements: ACKS,
      profile_id: $("insights-profile").value,
      daily_distance_km: Number($("insights-distance").value),
      tariff_eur_kwh: Number($("insights-tariff").value),
      charging_efficiency:
        $("insights-efficiency").value === ""
          ? null
          : Number($("insights-efficiency").value),
      driving_days: Number($("insights-days").value),
      acceleration_target_ms: Number($("insights-target").value) / 3.6,
      acceleration_duration_s: 30,
      dt_s: 0.2,
    };
  }
  function changed() {
    if (last)
      $("insights-status").textContent =
        "Active design or assumptions may differ. Displayed evidence remains the frozen completed analysis; evaluate again to update.";
  }
  window.addEventListener("veus:design", changed, { signal: life.signal });
  root.addEventListener("change", changed, { signal: life.signal });
  function view(value) {
    last = value;
    $("insights-export").disabled = false;
    const labels = {
      modelled_consumption_kwh_100km: "Stored-energy consumption",
      cycle_equivalent_range_km: "Cycle-equivalent range",
      daily_battery_energy_kwh: "Daily battery energy",
      daily_grid_energy_kwh: "Daily grid energy",
      daily_electricity_cost_eur: "Daily grid electricity cost",
      daily_battery_energy_cost_eur: "Daily battery-energy cost",
      modelled_acceleration_time_s: "Time to target speed",
      acceleration_final_speed_ms: "Achieved acceleration final speed",
    };
    $("insights-result").innerHTML =
      `<p><strong>${esc(value.request.vehicle.name)}</strong> · ${esc(value.request.profile_id)} · continuous ratings / frozen model result</p><div class="analysis-metrics">${Object.entries(
        labels,
      )
        .map(([key, label]) => {
          const m = value.metrics[key];
          return `<div><span>${esc(label)}</span><strong>${fmt(m?.value)} <small>${esc(m?.unit)}</small></strong>${m?.reason ? `<p class="quiet">${esc(m.reason)}</p>` : ""}</div>`;
        })
        .join(
          "",
        )}</div><p class="quiet">${esc(value.cycle.eligibility.reasons.join(" "))} Range is a modelled full-usable-energy cycle equivalent, not certified or real-world range.</p><details><summary>Exact assumptions, quantities and reproduction</summary><pre>${esc(JSON.stringify(value, null, 2))}</pre></details>`;
    root.dataset.resultHash = value.insights_sha256;
  }
  async function execute(all = false) {
    if (!$("insights-form").reportValidity()) return;
    controller?.abort();
    controller = new AbortController();
    $("insights-run").disabled = true;
    $("insights-presets").disabled = true;
    $("insights-status").textContent =
      "Running bounded continuous-rating analyses…";
    try {
      if (all) {
        const data = await (
            await fetch("/api/workbench/v2/presets", {
              signal: controller.signal,
            })
          ).json(),
          results = [];
        for (const p of data.presets)
          results.push({
            name: p.name,
            value: await post("insights", request(p.design), controller.signal),
          });
        last = {
          classification:
            "Same user assumptions; default presets, not customized designs",
          results,
        };
        $("insights-result").textContent =
          "Three default presets evaluated under identical profile and daily assumptions.";
        $("insights-export").disabled = false;
        $("insights-charts").innerHTML =
          bars(
            results.map((r) => ({
              name: r.name.split(" — ")[0],
              consumption: r.value.metrics.modelled_consumption_kwh_100km.value,
            })),
            "consumption",
            "Cycle stored-energy consumption",
            "kWh/100 km",
          ) +
          bars(
            results.map((r) => ({
              name: r.name.split(" — ")[0],
              energy: r.value.metrics.daily_battery_energy_kwh.value,
            })),
            "energy",
            "Daily battery energy",
            "kWh",
          ) +
          bars(
            results.map((r) => ({
              name: r.name.split(" — ")[0],
              acceleration: r.value.metrics.modelled_acceleration_time_s.value,
            })),
            "acceleration",
            "Acceleration time to requested speed",
            "s",
          ) +
          `<table class="analysis-table"><tr><th>Default</th><th>Cycle-equivalent km</th><th>Daily € / basis</th></tr>${results.map((r) => `<tr><td>${esc(r.name)}</td><td>${fmt(r.value.metrics.cycle_equivalent_range_km.value)}</td><td>${fmt(r.value.metrics.daily_electricity_cost_eur.value ?? r.value.metrics.daily_battery_energy_cost_eur.value)} / ${r.value.metrics.daily_electricity_cost_eur.value == null ? "battery-energy proxy" : "grid-energy estimate"}</td></tr>`).join("")}</table>`;
        window.VEUSInsights = last;
      } else {
        const result = await post("insights", request(), controller.signal);
        view(result);
        window.VEUSInsights = result;
        state.lastInsights = result;
        window.dispatchEvent(new Event("veus:run"));
      }
      $("insights-status").textContent =
        "Completed; frozen evidence. Changing the saved design never relabels these results.";
    } catch (e) {
      if (e.name !== "AbortError")
        $("insights-status").textContent = "Unavailable: " + e.message;
    } finally {
      if (!life.signal.aborted) {
        $("insights-run").disabled = false;
        $("insights-presets").disabled = false;
      }
    }
  }
  $("insights-form").addEventListener(
    "submit",
    (e) => {
      e.preventDefault();
      execute();
    },
    { signal: life.signal },
  );
  $("insights-presets").addEventListener("click", () => execute(true), {
    signal: life.signal,
  });
  $("insights-export").addEventListener(
    "click",
    () =>
      download("veus-engineering-insights.json", JSON.stringify(last, null, 2)),
    { signal: life.signal },
  );
  return () => {
    controller?.abort();
    life.abort();
    delete window.VEUSInsights;
  };
}

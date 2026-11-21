import { state } from "./design-state.js";
import { acknowledged } from "./assumptions.js";
import { fmt } from "./engineering-insights.js";
const ACKS = [
  "illustrative_parameters",
  "constant_efficiency",
  "constant_ocv",
  "longitudinal_only",
  "unmodelled_thermal_charging",
];
export function mountLearning(root) {
  const life = new AbortController();
  let request;
  root.innerHTML =
    '<div class="learning-grid">' +
    [
      [
        "drag",
        "Why does motorway driving consume more?",
        "Speed · km/h",
        40,
        140,
        80,
      ],
      [
        "mass",
        "More battery energy, more vehicle mass",
        "Usable capacity · kWh",
        40,
        100,
        60,
      ],
      [
        "regen",
        "Where does braking energy go?",
        "Initial speed · km/h",
        30,
        100,
        60,
      ],
    ]
      .map(
        ([id, title, label, min, max, value]) =>
          `<article><h2>${title}</h2><svg viewBox="0 0 320 80" role="img" aria-label="${title}"><path d="M35 48l20-22h75l25 22h40v14H25V48Z" fill="#8db0c1"/><circle cx="65" cy="64" r="10" fill="#223c4c"/><circle cx="150" cy="64" r="10" fill="#223c4c"/><path id="learn-arrow-${id}" d="M215 45h60m-12-10l12 10-12 10" stroke="#5da99c" stroke-width="5" fill="none"/></svg><label>${label}<input id="learn-${id}" type="range" min="${min}" max="${max}" value="${value}"><output id="learn-value-${id}">${value}</output></label><p>${id === "drag" ? "F_drag = ½ρCdAv²; road power grows with speed. Arrow is illustrative, not a force scale." : id === "mass" ? "Bounded battery-size study: explicit 5 kg per usable kWh; baseline keeps its existing pack mass. Gross/usable ratio retained." : "Wheels → gearbox → motor/inverter → battery; charge/torque limits leave friction-brake work."}</p><button data-learn="${id}">Evaluate with existing model</button><p id="learn-result-${id}" role="status">No calculation performed.</p></article>`,
      )
      .join("") +
    "</div>";
  for (const input of root.querySelectorAll("input"))
    input.oninput = () =>
      (root.querySelector(
        "#" + input.id.replace("learn-", "learn-value-"),
      ).textContent = input.value);
  for (const button of root.querySelectorAll("[data-learn]"))
    button.onclick = async () => {
      const id = button.dataset.learn,
        out = root.querySelector("#learn-result-" + id),
        value = Number(root.querySelector("#learn-" + id).value);
      if (!state.design) {
        out.textContent = "Configure a vehicle in Vehicle Architecture first.";
        return;
      }
      if (!acknowledged()) {
        out.textContent =
          "Confirm model limitations once in Simulation Lab before executing these illustrative experiments.";
        return;
      }
      request?.abort();
      request = new AbortController();
      button.disabled = true;
      out.textContent = "Computing a bounded illustrative experiment…";
      try {
        const vehicle = structuredClone(state.design);
        let path, body;
        if (id === "mass") {
          path = "/api/workbench/v2/design-analysis";
          body = {
            kind: "battery_size",
            baseline: vehicle,
            conditions: {
              acknowledgements: ACKS,
              profile_id: "urban",
              dt_s: 0.2,
              ...(state.powertrainModel
                ? { efficiency_model: state.powertrainModel }
                : {}),
            },
            values: [value, value + 5],
            battery_mass_kg_per_usable_kwh: 5,
          };
        } else {
          path = "/api/lab/run";
          body = {
            schema_version: 1,
            vehicle,
            acknowledgements: ACKS,
            ...(state.powertrainModel
              ? { efficiency_model: state.powertrainModel }
              : {}),
            experiment: {
              kind: id === "drag" ? "constant_speed" : "braking",
              mode: id === "drag" ? "prescribed" : "predictive",
              duration_s: 10,
              dt_s: 0.1,
              initial_speed_ms: value / 3.6,
              target_speed_ms: value / 3.6,
              grade_percent: 0,
              brake_deceleration_ms2: 4,
              regen_enabled: true,
            },
          };
        }
        const response = await fetch(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: request.signal,
        });
        const r = await response.json();
        if (!response.ok)
          throw Error(
            typeof r.detail === "string" ? r.detail : JSON.stringify(r.detail),
          );
        if (life.signal.aborted) return;
        if (id === "mass")
          out.textContent =
            r.rows
              .map(
                (row) =>
                  `${row.parameter_value == null ? "Baseline " + fmt(row.design.battery.usable_capacity_kwh) : fmt(row.parameter_value)} kWh: ${fmt(row.analysis?.metrics.modelled_consumption_kwh_100km.value)} kWh/100 km; ${fmt(row.analysis?.metrics.cycle_equivalent_range_km.value)} km`,
              )
              .join(" · ") +
            ". Model predictions; identifiability is not physical validation.";
        else {
          const s = r.summary;
          out.textContent =
            id === "drag"
              ? `Aero road work ${fmt(s.aerodynamic_work_kwh)} kWh over ${fmt(s.distance_m)} m; terminal consumption ${fmt(s.consumption_kwh_100km)} kWh/100 km.`
              : `Recovered ${fmt(s.energy_recovered_kwh)} kWh; friction-brake work ${fmt(s.friction_energy_kwh)} kWh. Not all kinetic energy returns to the battery.`;
          root
            .querySelector("#learn-arrow-" + id)
            .setAttribute(
              "transform",
              `translate(215 0) scale(${Math.min(1.4, 0.4 + value / 140)} 1) translate(-215 0)`,
            );
        }
      } catch (e) {
        if (e.name !== "AbortError" && !life.signal.aborted)
          out.textContent = "Unavailable: " + e.message;
      } finally {
        if (!life.signal.aborted) button.disabled = false;
      }
    };
  return () => {
    life.abort();
    request?.abort();
  };
}

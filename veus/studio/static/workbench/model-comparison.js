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
    ? v.toLocaleString(undefined, { maximumFractionDigits: 3 })
    : "Unavailable";
export function mountModelComparison(root, lab) {
  let request = null,
    result = null;
  const life = new AbortController(),
    $ = (id) => root.querySelector("#" + id);
  root.innerHTML = `<details><summary>Constant versus mapped motor efficiency · same design / same cycle</summary><p class="quiet">Illustrative map assumptions change predicted losses, not the hardware. No extrapolation outside the documented operating region.</p><label>Complete reference profile<select id="motor-map-profile"><option value="urban">Illustrative urban</option><option value="motorway">Illustrative motorway</option><option value="udds">FASTSim UDDS</option><option value="hwfet">FASTSim HWFET</option></select></label><button id="motor-map-compare">Compare powertrain assumptions</button><p id="motor-map-status" role="status">No model comparison executed.</p><div id="motor-map-result"></div></details>`;
  $("motor-map-compare").onclick = async () => {
    const a = [...lab.querySelectorAll(".lab-ack:checked")].map((e) => e.value);
    if (a.length !== 5) {
      lab.querySelector("#lab-config").open = true;
      lab.querySelector("#lab-assumptions").open = true;
      $("motor-map-status").textContent =
        "Acknowledge all Lab model assumptions first.";
      return;
    }
    request?.abort();
    request = new AbortController();
    $("motor-map-status").textContent =
      "Running identical full-cycle continuous-rating comparisons…";
    $("motor-map-compare").disabled = true;
    try {
      const response = await fetch("/api/workbench/v2/powertrain-comparison", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle: structuredClone(state.design),
          acknowledgements: a,
          profile_id: $("motor-map-profile").value,
        }),
        signal: request.signal,
      });
      const r = await response.json();
      if (!response.ok)
        throw Error(
          typeof r.detail === "string" ? r.detail : JSON.stringify(r.detail),
        );
      result = r;
      window.VEUSMotorComparison = r;
      const keys = [
        ["modelled_consumption_kwh_100km", "Stored consumption", "kWh/100 km"],
        ["cycle_equivalent_range_km", "Cycle-equivalent range", "km"],
        ["modelled_acceleration_time_s", "Time to target", "s"],
      ];
      $("motor-map-result").innerHTML =
        `<p>${esc(r.request.vehicle.name)} · frozen ${esc(r.request.profile_id)} · ${esc(r.interpretation)}</p><table class="analysis-table"><tr><th>Quantity</th><th>Constant</th><th>Mapped</th><th>Unit</th></tr>${keys.map(([k, n, u]) => `<tr><td>${n}</td><td>${fmt(r.legacy.metrics[k].value)}</td><td>${fmt(r.mapped.metrics[k].value)}</td><td>${u}</td></tr>`).join("")}<tr><td>Cycle conversion loss</td><td>${fmt(r.legacy.cycle.summary.conversion_loss_kwh)}</td><td>${fmt(r.mapped.cycle.summary.conversion_loss_kwh)}</td><td>kWh</td></tr></table><div id="motor-operating-points"></div><details><summary>Map operating points, efficiencies, provenance and model requests</summary><pre>${esc(JSON.stringify(r, null, 2))}</pre></details><button id="motor-map-export">Export frozen comparison JSON</button>`;
      const rows = r.mapped.cycle.preview_trace,
        points = rows.filter(
          (v) =>
            Number.isFinite(v.motor_rpm) &&
            Number.isFinite(v.motor_torque_nm) &&
            Number.isFinite(v.motor_efficiency),
        );
      $("motor-operating-points").innerHTML = points.length
        ? `<p>Selected supported-map operating points · preview only; unavailable points remain in the report</p><svg viewBox="0 0 500 180" role="img" aria-label="Motor rpm versus signed shaft torque Nm"><path d="M35 10v140h450" fill="none" stroke="currentColor"/>${points.map((v) => `<circle cx="${35 + (v.motor_rpm / r.request.vehicle.motor.maximum_speed_rpm) * 450}" cy="${80 - (v.motor_torque_nm / r.request.vehicle.motor.rated_torque_nm) * 60}" r="2" fill="${v.motor_torque_nm < 0 ? "#45b6ce" : "#6c9f7e"}"/>`).join("")}<text x="40" y="175" font-size="10">0 → configured maximum rpm; torque ± continuous Nm</text></svg>`
        : "<p>Operating points retained in the frozen report.</p>";
      $("motor-map-export").onclick = () => {
        const url = URL.createObjectURL(
            new Blob([JSON.stringify(result, null, 2)], {
              type: "application/json",
            }),
          ),
          a = document.createElement("a");
        a.href = url;
        a.download = "veus-powertrain-comparison.json";
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      };
      $("motor-map-status").textContent =
        "Completed. Same inputs, different loss model; physical validation INCONCLUSIVE.";
    } catch (e) {
      if (e.name !== "AbortError")
        $("motor-map-status").textContent = "Unavailable: " + e.message;
    } finally {
      if (!life.signal.aborted) $("motor-map-compare").disabled = false;
    }
  };
  return () => {
    life.abort();
    request?.abort();
    delete window.VEUSMotorComparison;
  };
}

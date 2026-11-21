import { state } from "./design-state.js";
import { acknowledged, confirmAssumptions } from "./assumptions.js";
export function simplifyLab(root) {
  const $ = (id) => root.querySelector("#" + id);
  $("lab-config").querySelector("summary").firstChild.textContent =
    "Advanced Simulation Settings ";
  $("lab-run").childNodes[0].textContent = "Run Simulation ";
  $("lab-profile-mode").textContent = "Driving Cycles";
  root
    .querySelector(".lab-selection")
    .prepend($("lab-vehicle").closest("label"));
  const row = document.createElement("div");
  row.className = "lab-simple-controls";
  row.innerHTML =
    '<label>Driving cycle<select id="lab-simple-cycle"><option value="">Use selected scenario</option><option value="urban">Urban · illustrative</option><option value="motorway">Highway · illustrative</option><option value="custom">Custom / sourced driving data…</option></select></label><label class="lab-check"><input type="checkbox" id="model-ack">I acknowledge model limitations — illustrative simulation; not physically validated.</label>';
  root.querySelector(".lab-config-row").before(row);
  $("lab-assumptions").querySelector("summary").textContent =
    "Model Assumptions · technical details & individual flags";
  const flags = [...root.querySelectorAll(".lab-ack")];
  $("model-ack").checked = acknowledged();
  if (acknowledged()) for (const f of flags) f.checked = true;
  $("model-ack").onchange = () => {
    for (const f of flags) f.checked = $("model-ack").checked;
    confirmAssumptions($("model-ack").checked);
  };
  for (const f of flags)
    f.addEventListener("change", () => {
      $("model-ack").checked = flags.every((x) => x.checked);
      confirmAssumptions($("model-ack").checked);
    });
  $("lab-efficiency-model").value = state.powertrainModel || "";
  $("lab-efficiency-model").addEventListener(
    "change",
    () => (state.powertrainModel = $("lab-efficiency-model").value),
  );
  $("lab-simple-cycle").onchange = () => {
    const v = $("lab-simple-cycle").value;
    if (!v) return;
    $("lab-kind").value = "profile";
    $("lab-kind").dispatchEvent(new Event("change"));
    if (v === "custom") {
      $("lab-config").open = true;
      $("lab-import-data").open = true;
      return;
    }
    $("lab-profile").value = v;
    $("lab-profile").dispatchEvent(new Event("change"));
    $("lab-dt").value = ".2";
    $("lab-config").open = false;
  };
}
export function labSummary(root, value) {
  let p = root.querySelector("#lab-primary-results");
  if (!p) {
    p = document.createElement("p");
    p.id = "lab-primary-results";
    p.setAttribute("role", "status");
    root.querySelector(".lab-instrument").prepend(p);
  }
  const s = value.summary,
    n = (x) => (Number.isFinite(x) ? x.toFixed(2) : "Unavailable"),
    bad =
      (s.requested_motion_infeasible_duration_s ||
        s.requested_infeasible_duration_s ||
        0) > 0;
  p.textContent = `${bad ? "Requested cycle INFEASIBLE; showing achieved movement. " : "Computed achieved result. "}Distance ${n(s.distance_m / 1000)} km · terminal consumption ${n(s.consumption_kwh_100km)} kWh/100 km · final SOC ${n(s.final_soc * 100)}%. Constraints and provenance below.`;
}

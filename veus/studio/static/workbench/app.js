import { icon, anatomySVG, updateSchematic } from "./schematic.js";
import { state, loadLibrary } from "./design-state.js";
const $ = (id) => document.getElementById(id);
const esc = (v) =>
  String(v).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const workspaces = [
  ["anatomy", "EV Anatomy", "UNDERSTAND"],
  ["challenges", "EV Challenges", "ASK BETTER QUESTIONS"],
  ["design", "Design Studio", "DEFINE THE SYSTEM"],
  ["simulation", "Simulation Lab", "REPEAT THE EXPERIMENT"],
  ["measurements", "Measurements", "FOLLOW THE EVIDENCE"],
];
let content,
  catalogue,
  selectedComponent = "battery",
  anatomyMode = "placement",
  flowMode = "propulsion",
  challenge = "range",
  active = "anatomy";
let studioCleanup = null;
const vehicleOptions = {
  annotations: true,
  body: "cutaway",
  view: "complete",
  selected: null,
  flow: null,
};
const sourceLinks = (ids) =>
  `<div class="source-links">${ids
    .map((id) => {
      const s = content.sources.find((s) => s.id === id);
      return `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)} ↗</a>`;
    })
    .join("")}</div>`;
const header = (eyebrow, title, description, status) =>
  `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><span class="badge">${status}</span></div>`;
function notice(message) {
  $("notice").textContent = message;
  $("notice").classList.add("visible");
  clearTimeout(notice.timer);
  notice.timer = setTimeout(
    () => $("notice").classList.remove("visible"),
    7000,
  );
}
async function get(url) {
  const r = await fetch(url);
  if (!r.ok) throw Error(`Cannot load ${url} (${r.status})`);
  return r.json();
}
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $("theme-toggle").setAttribute(
    "aria-label",
    `Switch to ${theme === "dark" ? "light" : "dark"} theme`,
  );
  $("theme-toggle").querySelector("span").textContent =
    theme === "dark" ? "Light" : "Dark";
}
try {
  applyTheme(
    localStorage.getItem("veus.workbench.theme") ||
      (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light"),
  );
} catch {
  applyTheme("light");
}
$("theme-toggle").onclick = () => {
  const theme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(theme);
  try {
    localStorage.setItem("veus.workbench.theme", theme);
  } catch {
    notice("Theme changed for this visit; browser storage is unavailable.");
  }
};
$("workspace-tabs").innerHTML = workspaces
  .map(
    ([key, name, tag], i) =>
      `<button id="tab-${key}" class="workspace-tab" data-key="${key}" role="tab" aria-controls="workspace-panel" aria-selected="false" tabindex="-1">${icon(key)}<span><small>0${i + 1} / ${tag}</small><strong>${name}</strong></span></button>`,
  )
  .join("");
for (const button of document.querySelectorAll(".workspace-tab")) {
  button.onclick = () => navigate(button.dataset.key);
  button.onkeydown = (e) => {
    const i = workspaces.findIndex((w) => w[0] === button.dataset.key);
    let n;
    if (e.key === "ArrowRight") n = (i + 1) % workspaces.length;
    else if (e.key === "ArrowLeft")
      n = (i + workspaces.length - 1) % workspaces.length;
    else if (e.key === "Home") n = 0;
    else if (e.key === "End") n = workspaces.length - 1;
    else return;
    e.preventDefault();
    navigate(workspaces[n][0]);
    $("tab-" + workspaces[n][0]).focus();
  };
}
function navigate(key, update = true) {
  if (!content) return;
  if (key === "optimization") {
    key = "design";
    history.replaceState({}, "", "/?workspace=design");
    notice("Design comparisons are now in Design Studio.");
  }
  if (!workspaces.some((w) => w[0] === key)) key = "anatomy";
  studioCleanup?.();
  studioCleanup = null;
  active = key;
  document.body.dataset.workspace = key;
  for (const b of document.querySelectorAll(".workspace-tab")) {
    const selected = b.dataset.key === key;
    b.setAttribute("aria-selected", selected);
    b.tabIndex = selected ? 0 : -1;
  }
  if (update) history.pushState({}, "", `/?workspace=${key}`);
  $("workspace-host").innerHTML =
    `<section id="workspace-panel" role="tabpanel" aria-labelledby="tab-${key}"></section>`;
  ({
    anatomy: renderAnatomy,
    challenges: renderChallenges,
    design: renderDesign,
    simulation: renderSimulation,
    measurements: renderMeasurements,
  })[key]();
  scrollTo(0, 0);
}
window.addEventListener("popstate", () =>
  navigate(new URLSearchParams(location.search).get("workspace"), false),
);
function renderAnatomy() {
  $("workspace-panel").innerHTML =
    header(
      "01 / SYSTEMS & ENERGY PATHS",
      "Understand the whole vehicle.",
      "Ten connected systems. Start with a component, then follow the energy through the vehicle.",
      "INTERACTIVE SCHEMATIC",
    ) +
    `
 <div class="anatomy-layout"><div><div class="drawing-panel"><div class="drawing-toolbar"><span class="drawing-id">FIG. 01 / ELECTRIC VEHICLE ARCHITECTURE</span><div class="segmented" aria-label="Schematic view"><button id="placement-view" aria-pressed="${anatomyMode === "placement"}">Component placement</button><button id="flow-view" aria-pressed="${anatomyMode === "flow"}">Energy paths</button></div></div><div id="schematic-slot"></div><p id="anatomy-tooltip" aria-live="polite">Hover or focus a numbered component. Select to inspect its engineering role.</p><div class="drawing-footer"><span>Original schematic · illustrative component locations</span><span>No manufacturer-specific layout</span></div></div><div class="below-drawing"><div class="note-panel"><h3>Understand the relationships.</h3><p>Energy storage, power conversion and mechanical motion are different responsibilities. Follow the connections before selecting components.</p></div><div class="note-panel"><h3>Keep the evidence boundary visible.</h3><p>A schematic explains an architecture. It does not establish component performance, safety or physical validation.</p></div></div></div><aside id="component-inspector" class="inspector" aria-label="Selected component engineering details"></aside></div>
 <details class="comparison-note"><summary>EV versus conventional combustion vehicle · what changes?</summary><table><thead><tr><th>Function</th><th>Battery electric vehicle</th><th>Combustion vehicle</th></tr></thead><tbody><tr><td>Onboard energy</td><td>Electrochemical battery</td><td>Fuel tank</td></tr><tr><td>Torque production</td><td>Electric motor and inverter</td><td>Combustion engine</td></tr><tr><td>Transmission</td><td>Often reduction gearing; architecture varies</td><td>Typically multiple ratios; architecture varies</td></tr><tr><td>Deceleration</td><td>Friction brakes plus conditional regenerative recovery</td><td>Friction and engine braking; hybrid exceptions</td></tr><tr><td>Thermal systems</td><td>Battery, electronics, motor and cabin requirements</td><td>Engine, exhaust and cabin requirements</td></tr></tbody></table>${sourceLinks(["doe-components"])}</details>`;
  $("placement-view").onclick = () => {
    anatomyMode = "placement";
    renderAnatomy();
  };
  $("flow-view").onclick = () => {
    anatomyMode = "flow";
    vehicleOptions.view = "complete";
    vehicleOptions.selected = null;
    renderAnatomy();
  };
  drawAnatomy();
  if (anatomyMode === "flow") inspectFlow();
  else inspectComponent();
}
function drawAnatomy() {
  const slot = $("schematic-slot");
  slot.innerHTML = `<div class="vehicle-options"><label>System view<select id="vehicle-view">${["complete", "electrical", "drivetrain", "battery", "thermal"].map((v) => `<option value="${v}" ${vehicleOptions.view === v ? "selected" : ""}>${v[0].toUpperCase() + v.slice(1)}</option>`).join("")}</select></label><label>Body<select id="vehicle-body">${["cutaway", "transparent", "opaque"].map((v) => `<option ${vehicleOptions.body === v ? "selected" : ""}>${v}</option>`).join("")}</select></label><label><input type="checkbox" id="vehicle-annotations" ${vehicleOptions.annotations ? "checked" : ""}> Annotations</label><button id="vehicle-clear">Show all systems</button></div>${
    anatomyMode === "flow"
      ? `<div class="flow-controls">${[
          ["propulsion", "Propulsion"],
          ["regeneration", "Regeneration"],
          ["ac_charging", "AC charging"],
          ["dc_charging", "DC charging"],
          ["auxiliary", "Auxiliary loads"],
        ]
          .map(
            ([id, label]) =>
              `<button data-flow="${id}" aria-pressed="${flowMode === id}">${label}</button>`,
          )
          .join("")}</div>`
      : ""
  }${anatomySVG(content.components, true, { ...vehicleOptions, flow: anatomyMode === "flow" ? flowMode : null })}<div class="connection-legend"><span class="hv">HV DC / three-phase AC</span><span class="lv">Low voltage</span><span class="control">Control</span><span class="coolant">Coolant</span><span class="mechanical">Mechanical</span></div>`;
  const svg = slot.querySelector(".anatomy-svg");
  slot.onclick = (e) => {
    const marker = e.target.closest("[data-component-link]");
    if (!marker) return;
    selectedComponent = marker.dataset.componentLink;
    vehicleOptions.selected = selectedComponent;
    updateSchematic(svg, {
      ...vehicleOptions,
      flow: anatomyMode === "flow" ? flowMode : null,
    });
    inspectComponent();
  };
  const update = () =>
    updateSchematic(svg, {
      ...vehicleOptions,
      flow: anatomyMode === "flow" ? flowMode : null,
    });
  $("vehicle-view").onchange = (e) => {
    vehicleOptions.view = e.target.value;
    update();
  };
  $("vehicle-body").onchange = (e) => {
    vehicleOptions.body = e.target.value;
    update();
  };
  $("vehicle-annotations").onchange = (e) => {
    vehicleOptions.annotations = e.target.checked;
    update();
  };
  $("vehicle-clear").onclick = () => {
    vehicleOptions.selected = null;
    vehicleOptions.view = "complete";
    $("vehicle-view").value = "complete";
    update();
  };
  for (const b of slot.querySelectorAll("[data-flow]"))
    b.onclick = () => {
      flowMode = b.dataset.flow;
      vehicleOptions.view = "complete";
      vehicleOptions.selected = null;
      $("vehicle-view").value = "complete";
      inspectFlow();
      for (const x of slot.querySelectorAll("[data-flow]"))
        x.setAttribute("aria-pressed", x === b);
      update();
      $("anatomy-tooltip").textContent =
        "Conceptual " +
        b.textContent.toLowerCase() +
        " path; no live power or energy is calculated.";
    };
  for (const g of slot.querySelectorAll("[data-component]")) {
    const preview = () => {
      $("anatomy-tooltip").textContent = content.components.find(
        (c) => c.id === g.dataset.component,
      ).function;
    };
    g.onmouseenter = preview;
    g.onfocus = preview;
    const choose = () => {
      selectedComponent = g.dataset.component;
      vehicleOptions.selected = selectedComponent;
      update();
      inspectComponent();
    };
    g.onclick = choose;
    g.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        choose();
      }
    };
  }
}
function inspectFlow() {
  const paths = {
    propulsion: [
      "Propulsion",
      "Battery DC → inverter → three-phase motor → reduction and driven axle.",
    ],
    regeneration: [
      "Regenerative braking",
      "Driven axle → motor → inverter → HV battery, subject to battery acceptance and conversion limits.",
    ],
    ac_charging: [
      "AC charging",
      "External AC → onboard charger → protected DC battery path. Traction inverter is bypassed.",
    ],
    dc_charging: [
      "DC charging",
      "Offboard DC conversion → charge port → conceptual switching and protection → battery. The onboard AC charger and traction inverter are bypassed.",
    ],
    auxiliary: [
      "Auxiliary operation",
      "HV battery → DC/DC converter → 12 V battery and low-voltage auxiliaries.",
    ],
  };
  const [name, description] = paths[flowMode];
  $("component-inspector").innerHTML =
    `<div class="component-number">CONCEPTUAL ENERGY PATH</div><h2>${name}</h2><p>${description}</p><h3>Direction, not magnitude</h3><p>Arrows show the conceptual conversion path. No simulation is running and no measured power or energy is inferred.</p><p class="limit">Switchgear, protection and control are conceptual. This is not a production wiring diagram or safety model.</p>${sourceLinks(["doe-components", "models"])}`;
}
function inspectComponent() {
  const c = content.components.find((c) => c.id === selectedComponent);
  $("component-inspector").innerHTML =
    `<div class="component-number">COMPONENT ${c.number} / 10</div><h2>${esc(c.name)}</h2><p>${esc(c.function)}</p><h3>Engineering parameters</h3><p>${esc(c.parameters)}</p><h3>Connected systems</h3><p>${esc(c.relationships)}</p><p class="limit">${esc(c.limitation)}</p><label class="quiet">Choose a component<select id="component-select" aria-label="Choose an EV component">${content.components.map((x) => `<option value="${x.id}" ${x.id === c.id ? "selected" : ""}>${x.number} · ${esc(x.name)}</option>`).join("")}</select></label>${sourceLinks(c.sources)}`;
  $("component-select").onchange = (e) => {
    selectedComponent = e.target.value;
    vehicleOptions.selected = selectedComponent;
    updateSchematic(document.querySelector("#schematic-slot .anatomy-svg"), {
      ...vehicleOptions,
      flow: anatomyMode === "flow" ? flowMode : null,
    });
    inspectComponent();
  };
}
function renderChallenges() {
  $("workspace-panel").innerHTML =
    header(
      "02 / QUESTIONS BEFORE SOLUTIONS",
      "The trade-offs define the vehicle.",
      "Start with an engineering question. Separate the underlying physics from a technology claim.",
      "8 ENGINEERING CHALLENGES",
    ) +
    `<div class="challenge-layout"><aside class="challenge-list" aria-label="Engineering challenges">${content.challenges.map((c, i) => `<button data-challenge="${c.id}" aria-pressed="${challenge === c.id}"><span>0${i + 1}</span>${esc(c.title)}</button>`).join("")}</aside><article class="challenge-content" id="challenge-content"></article></div>`;
  const c = content.challenges.find((c) => c.id === challenge);
  $("challenge-content").innerHTML =
    `<div class="eyebrow">${esc(c.classification)}</div><h2>${esc(c.title)}</h2>${[
      ["01", "Problem", c.problem],
      ["02", "Underlying physics", c.physics],
      ["03", "Engineering technologies & trade-offs", c.technologies],
      ["04", "Investigate through VEUS", c.experiment],
    ]
      .map(
        ([n, t, body]) =>
          `<section class="challenge-stage"><span>${n} / ${t.split(" ")[0].toUpperCase()}</span><div><h3>${t}</h3><p>${esc(body)}</p>${n === "04" ? `<a href="/?workspace=${c.workspace}" id="challenge-experiment">Open ${workspaces.find((w) => w[0] === c.workspace)?.[1] || "Design Studio"} →</a>` : ""}</div></section>`,
      )
      .join(
        "",
      )}${sourceLinks(c.sources)}<p class="quiet">Foundation: proposed experiment, not an executed result. No manufacturer statistics or technology-derived efficiency gains.</p>`;
  for (const b of document.querySelectorAll("[data-challenge]"))
    b.onclick = () => {
      challenge = b.dataset.challenge;
      renderChallenges();
      document.querySelector(`[data-challenge="${challenge}"]`).focus();
    };
  $("challenge-experiment").onclick = (e) => {
    e.preventDefault();
    navigate(c.workspace);
  };
}
async function renderDesign() {
  $("workspace-panel").innerHTML =
    '<p class="quiet">Loading Design Studio…</p>';
  try {
    const module = await import("./design-studio.js");
    if (active !== "design") return;
    const cleanup = await module.mountStudio($("workspace-panel"), {
      content,
      header,
      notice,
      sourceLinks,
    });
    if (active !== "design") cleanup();
    else studioCleanup = cleanup;
  } catch (e) {
    if (active === "design")
      $("workspace-panel").textContent =
        "Design Studio could not load: " + e.message;
  }
}
async function renderSimulation() {
  const panel = $("workspace-panel");
  panel.innerHTML = '<p class="quiet">Loading Simulation Lab…</p>';
  try {
    const module = await import("./lab.js");
    if (active !== "simulation" || !panel.isConnected) return;
    const cleanup = await module.mountLab(panel, { header, notice, content });
    if (active !== "simulation" || !panel.isConnected) cleanup();
    else studioCleanup = cleanup;
  } catch (e) {
    if (active === "simulation" && panel.isConnected)
      panel.textContent = "Simulation Lab could not load: " + e.message;
  }
}

async function renderMeasurements() {
  if (!catalogue) {
    $("workspace-panel").innerHTML =
      '<p class="quiet">Loading genuine recording catalogue…</p>';
    try {
      catalogue = await get("/api/investigation/catalogue");
    } catch (e) {
      if (active === "measurements")
        $("workspace-panel").textContent = e.message;
      return;
    }
    if (active !== "measurements") return;
  }
  $("workspace-panel").innerHTML =
    header(
      "05 / RECORDED MEASUREMENTS",
      "Let the evidence set the limits.",
      "A focused entry to genuine vehicle data. Existing ingestion, readiness, event investigation and reporting remain available.",
      "2.X UNDER DEVELOPMENT",
    ) +
    `<div class="steps"><b>01 Select recording</b><span>→ 02 Choose a question</span><span>→ 03 Inspect signals</span><span>→ 04 Review evidence</span><span>→ 05 Export report</span></div><div class="measurement-layout"><aside class="selection-fields"><label>Genuine recording<select id="measurement-recording">${catalogue.map((c) => `<option value="${c.id}" ${c.id === "ved-10-1561-full" ? "selected" : ""}>${esc(c.label)}</option>`).join("")}</select></label><label>Engineering question<select id="measurement-question"><option value="speed">What supports an acceleration event?</option><option value="power">What do voltage and signed current show?</option><option value="quality">Where are the evidence gaps?</option></select></label><div class="prototype-note">The catalogue is connected to real importer metadata. The new 2.x measurement experience is under development. Use the existing measurement tools for actual investigation and exports.</div><a class="primary" href="/engineering?workspace=analyse">Open existing measurement tools →</a><p class="quiet">Select the matching recording in that view. CSV import, Data Readiness, investigation, comparison and report exports are preserved.</p></aside><article id="measurement-summary" class="recording-summary"></article></div>`;
  const show = () => {
    const c = catalogue.find((c) => c.id === $("measurement-recording").value);
    const question = $("measurement-question").value;
    const hint = {
      speed:
        "Inspect recorded speed and speed-derived acceleration at the same sample indices. Detection does not explain the cause.",
      power:
        "Inspect voltage, raw current and signed V × I. Unverified polarity prevents charging/discharging or regeneration claims.",
      quality:
        "Inspect timestamp gaps, missing channels and coverage. Unknown travel is not filled by interpolation.",
    }[question];
    $("measurement-summary").innerHTML =
      `<div class="eyebrow">${esc(c.kind)} / UNIVERSITY OF MICHIGAN VED</div><h2>${esc(c.label)}</h2><div class="recording-numbers"><div><span>ACTUAL SAMPLES</span><strong>${c.sample_count}</strong></div><div><span>RECORDING SPAN · s</span><strong>${c.duration_s.toFixed(1)}</strong></div><div><span>TIMESTAMP GAPS</span><strong>${c.timestamp_gaps.length}</strong></div></div><p>${esc(hint)}</p><h3>Available source channels</h3>${Object.entries(
        c.signals,
      )
        .map(
          ([s, u]) => `<span class="signal-chip">${esc(s)} · ${esc(u)}</span>`,
        )
        .join(
          "",
        )}<p class="prototype-note">Current polarity remains unverified. Measurement gaps remain unknown. Replay is not physical model validation: the assessment remains INCONCLUSIVE.</p><details><summary>Source identity, licence & checksum</summary><p>${esc(c.licence)}</p><p>Vehicle: ${esc(c.vehicle_id)} · trip: ${esc(c.trip_id)}</p><pre>${esc(c.source_sha256)}</pre><a href="${esc(c.source.source_url)}" target="_blank" rel="noopener">Pinned dataset source ↗</a></details>`;
  };
  $("measurement-recording").onchange = show;
  $("measurement-question").onchange = show;
  show();
}
loadLibrary();
function activeLabel() {
  const label = document.querySelector(".edition-note");
  if (label)
    label.textContent = state.design
      ? "Active · " +
        state.design.name +
        (state.evaluation ? "" : " · unchecked")
      : "Understand · Design · Simulate · Optimize";
}
window.addEventListener("veus:design", activeLabel);
activeLabel();
try {
  content = await get("/api/workbench/content");
  if (state.design) {
    const snapshot = JSON.stringify(state.design);
    fetch("/api/workbench/v2/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: snapshot,
    })
      .then(async (r) => {
        if (!r.ok) throw Error("Saved active design requires review");
        return r.json();
      })
      .then((result) => {
        if (JSON.stringify(state.design) === snapshot && !state.dirty) {
          state.evaluation = result;
          state.design = structuredClone(result.design);
          activeLabel();
        }
      })
      .catch((e) => notice(e.message + "; open Design Studio to correct it."));
  }
  $("loading").hidden = true;
  navigate(new URLSearchParams(location.search).get("workspace"), false);
} catch (e) {
  $("loading").textContent =
    "Workspace could not load: " + e.message + ". Reload to retry.";
}

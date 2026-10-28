"use strict";
// Move existing panels without replacing their IDs, handlers or state.
(() => {
  const byId = (id) => document.getElementById(id),
    main = document.querySelector("main");
  const layout = document.querySelector(".layout");
  const header = document.querySelector("header");
  header.innerHTML =
    '<a class="brand" href="#drive" aria-label="VEUS Drive">V<span>∕</span>EUS<small>EV WORKBENCH</small></a><nav aria-label="Workspaces"><button data-workspace="drive" aria-current="page">Drive</button><button data-workspace="analyse">Analyse</button><button data-workspace="validate">Validate</button><button data-workspace="settings">Settings</button></nav><div class="connection-state"><i id="connectionDot"></i><span id="connection">Connecting…</span><span class="badge" id="status">READY</span></div>';
  const make = (name, title, subtitle) => {
    const section = document.createElement("section");
    section.id = name + "Workspace";
    section.className = "workspace";
    section.hidden = name !== "drive";
    section.innerHTML = `<div class="workspace-heading"><div><div class="eyebrow">${subtitle}</div><h1>${title}</h1></div></div>`;
    main.append(section);
    return section;
  };
  const drive = make(
    "drive",
    "A little further.",
    "THE OPEN ROAD / VEUS DRIVE",
  );
  drive.innerHTML += `<div class="drive-toolbar"><div><strong id="selectedVehicle">Choose your electric</strong><span id="vehicleSpec" class="muted"></span></div><button id="chooseVehicle">Change vehicle →</button></div>
  <div class="driving-surface"><div class="scene-head"><span><i class="live-dot"></i> NORTH RIDGE <small> / LONGITUDINAL DRIVE</small></span><span id="sceneMode">MANUAL</span></div><canvas id="driveScene" aria-label="Side-view driving scene; landscape follows simulated displacement" role="img"></canvas><div class="scene-caption"><span id="sceneHint">Choose a vehicle. Press Run. Hold W to accelerate.</span><span id="leadReadout">5 px/m · illustrative side view</span></div></div>
  <div class="drive-readouts"><div class="speed-readout"><span>SPEED</span><strong id="driveSpeed">—</strong><small>km/h</small></div><div><span>BATTERY</span><strong id="driveSoc">—</strong><small>% SOC</small><div class="soc-track"><i id="socFill"></i></div></div><div><span>BATTERY POWER</span><strong id="drivePower">—</strong><small>kW <b id="energyDirection">Standby</b></small></div><div><span>DISTANCE</span><strong id="driveDistance">—</strong><small>km</small></div></div>
  <div id="driveControls" class="drive-controls"><div class="drive-actions"><button id="driveRun" class="primary">▶ Run</button><button id="driveReset" aria-label="Reset simulation">↺ Reset</button></div><label class="mode-control">DRIVING MODE<select id="driveMode"><option value="manual">Manual</option><option value="cruise">Cruise control</option><option value="acc">Adaptive cruise</option><option value="aeb">Emergency braking</option><option value="acceleration" disabled>Acceleration (Validate)</option><option value="braking" disabled>Braking (Validate)</option><option value="coast" disabled>Coast-down (Validate)</option></select></label><div class="pedal-slot" id="pedalSlot"></div><div class="touch-pedals"><button id="touchBrake">S ↓ Brake</button><button id="touchThrottle">W ↑ Accelerate</button></div></div>
  <div id="driveNotice" role="status" aria-live="polite">Connecting to the simulation…</div>
  <div class="drive-bottom"><span><kbd>W</kbd> / <kbd>↑</kbd> accelerate <kbd>S</kbd> / <kbd>↓</kbd> brake <kbd>Space</kbd> pause <kbd>R</kbd> reset</span><span id="driveDuration">120 s illustrative runs · 1× playback</span></div>
  <div class="drive-plots charts"><section class="panel"><h2>Speed <small>km/h</small></h2><canvas id="driveSpeedChart" role="img" aria-label="Vehicle speed over time"></canvas></section><section class="panel"><h2>Battery power <small>kW · negative = charging</small></h2><canvas id="drivePowerChart" role="img" aria-label="Battery power over time"></canvas></section></div>`;
  const analyse = make(
    "analyse",
    "From data to understanding.",
    "MEASUREMENTS / MODEL CALIBRATION",
  );
  analyse.append(byId("modelValidation").closest("section"));
  byId("modelValidation").open = true;
  const validate = make(
    "validate",
    "Inspect every response.",
    "ENGINEERING / SCENARIOS & SENSORS",
  );
  validate.append(layout);
  const aside = layout.querySelector("aside"),
    commands = byId("throttle").closest("section");
  const pedals = document.createElement("div");
  pedals.className = "pedals";
  for (const id of ["throttle", "brake"]) {
    pedals.append(byId(id).previousElementSibling);
    pedals.append(byId(id));
  }
  byId("pedalSlot").append(pedals);
  commands.querySelector("h2").textContent = "Run controls & telemetry export";
  const moveControls = document.createElement("button");
  moveControls.textContent = "Open driving controls";
  moveControls.onclick = () => window.setWorkspace("drive");
  commands.prepend(moveControls);
  // Keep old diagnostic side-view for compatibility, but the Drive scene is primary.
  document
    .querySelector(".road")
    .closest("section")
    .classList.add("engineering-scene");
  const tools = document.createElement("section");
  tools.className = "panel";
  tools.innerHTML =
    '<h2>Reproducible scenario reports</h2><p class="muted">Interactive modes use the same existing controllers. Batch scenarios and engineering reports run locally with the CLI; the browser does not imply that a batch was executed.</p><pre>python -m veus.testing run scenarios --output reports/adas-001\npython -m veus.testing run scenarios/sensors --output reports/sensors-001\npython -m veus.testing physics --output reports/physics-001</pre><p><a href="https://github.com/AsherFerdinand/VEUS-ev-testbench/blob/feature/veus-drive-experience/docs/validation.md" target="_blank" rel="noopener">Scenario configuration & report guide ↗</a></p>';
  aside.append(tools);
  const settings = make("settings", "Make it yours.", "APPEARANCE / ABOUT");
  settings.innerHTML +=
    '<section class="panel settings-panel"><h2>Vehicle paint</h2><label>Body colour<input id="vehicleColor" type="color" value="#a3dfbd"></label><p class="muted">Original unbranded SVG silhouettes. Presets are illustrative, not manufacturer specifications.</p><h2>What you are driving</h2><p>Simplified forward longitudinal EV dynamics, a constant-OCV battery, regenerative brake blending and educational ADAS. No steering, lateral motion or suspension simulation. Real-world vehicle validation remains pending.</p><p>Position comes from the Python physics engine. Smooth visuals interpolate telemetry; they never change the simulated state. Scenery uses layered parallax, with the road at 5 logical px/m. Vehicle silhouettes are enlarged for legibility; lead separation uses bumper anchors at that road scale.</p><p>No maximum vehicle speed or driven axle topology is asserted by these presets.</p></section>';
  const dialog = document.createElement("dialog");
  dialog.id = "vehicleDialog";
  dialog.setAttribute("aria-labelledby", "garageTitle");
  dialog.innerHTML =
    '<div class="garage-heading"><div><div class="eyebrow">YOUR NEXT DRIVE</div><h1 id="garageTitle">Choose your electric.</h1><p class="muted">Four body styles. One open road. Illustrative configurations.</p></div><button id="closeGarage" aria-label="Close vehicle selection">✕</button></div><div id="vehicleCards"></div><p class="muted">No manufacturer affiliation. Existing simplified drivetrain; maximum speed is not specified.</p>';
  document.body.append(dialog);
  byId("chooseVehicle").onclick = () => dialog.showModal();
  byId("closeGarage").onclick = () => dialog.close();
  window.activeWorkspace = "drive";
  window.setWorkspace = (name) => {
    if (!["drive", "analyse", "validate", "settings"].includes(name)) return;
    document.dispatchEvent(new CustomEvent("veus:workspace", { detail: name }));
    window.activeWorkspace = name;
    for (const s of document.querySelectorAll(".workspace"))
      s.hidden = s.id !== name + "Workspace";
    for (const b of document.querySelectorAll("[data-workspace]")) {
      if (b.dataset.workspace === name) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    }
    requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
  };
  for (const b of document.querySelectorAll("[data-workspace]"))
    b.onclick = () => window.setWorkspace(b.dataset.workspace);
  document.querySelector(".brand").onclick = (e) => {
    e.preventDefault();
    window.setWorkspace("drive");
  };
})();

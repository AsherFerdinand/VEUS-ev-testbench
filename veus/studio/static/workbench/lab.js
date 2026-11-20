// Simulation is executed once by Python. This module only configures and replays results.
import { state, loadLibrary, persist } from "./design-state.js";
import { anatomySVG, updateSchematic } from "./schematic.js";
const ACKS = [
  "illustrative_parameters",
  "constant_efficiency",
  "constant_ocv",
  "longitudinal_only",
  "unmodelled_thermal_charging",
];
const ACK_TEXT = [
  "Illustrative parameters are not calibrated vehicle specifications.",
  "Conversion efficiencies are constant assumptions.",
  "Battery OCV/resistance use the retained simplified model.",
  "Longitudinal motion only; no cornering or lap-time prediction.",
  "Thermal, ageing and charging-curve dynamics are not modelled.",
];
const TYPES = {
  constant_speed: {
    label: "Constant-speed consumption",
    mode: "prescribed",
    speed: 80,
    target: 80,
    duration: 30,
    grade: 0,
  },
  acceleration: {
    label: "Acceleration",
    mode: "predictive",
    speed: 0,
    target: 100,
    duration: 20,
    grade: 0,
  },
  braking: {
    label: "Braking & regeneration",
    mode: "predictive",
    speed: 80,
    target: 0,
    duration: 15,
    grade: 0,
  },
  gradient: {
    label: "Road-gradient demand",
    mode: "prescribed",
    speed: 80,
    target: 80,
    duration: 30,
    grade: 5,
  },
  coast: {
    label: "Coast-down",
    mode: "predictive",
    speed: 80,
    target: 0,
    duration: 30,
    grade: 0,
  },
};
const SIGNALS = {
  speed_ms: ["Achieved speed", "km/h", 3.6],
  target_speed_ms: ["Requested speed", "km/h", 3.6],
  battery_power_w: ["Battery DC power", "kW", 0.001],
  motor_power_w: ["Motor mechanical power", "kW", 0.001],
  requested_dc_power_w: ["Requested DC demand", "kW", 0.001],
  unmet_dc_power_w: ["Unmet requested DC demand", "kW", 0.001],
  tracking_error_ms: ["Achieved minus target speed", "m/s", 1],
  soc: ["Battery SOC", "%", 100],
  acceleration_ms2: ["Acceleration", "m/s²", 1],
  motor_torque_nm: ["Motor torque", "N·m", 1],
  regen_power_w: ["Regenerative power", "kW", 0.001],
  grade_percent: ["Road gradient", "%", 1],
};
const esc = (v) =>
  String(v).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const number = (v, d = 2) =>
  Number.isFinite(v)
    ? v.toLocaleString(undefined, { maximumFractionDigits: d })
    : "Unavailable";
let retainedInputs = { profile: null, route: null },
  cataloguePromise = null;
let retainedTime = 0,
  retainedResult = null,
  clockPromise = null;
function clockLibrary() {
  if (window.VEUSReplayController) return Promise.resolve();
  if (clockPromise) return clockPromise;
  clockPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/static/replay-controller.js";
    script.onload = resolve;
    script.onerror = () => {
      clockPromise = null;
      reject(Error("Playback clock failed to load"));
    };
    document.head.append(script);
  });
  return clockPromise;
}
function style() {
  if (document.getElementById("lab-styles")) return;
  const link = document.createElement("link");
  link.id = "lab-styles";
  link.rel = "stylesheet";
  link.href = "/static/workbench/lab.css";
  document.head.append(link);
}
function save(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type })),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const traceRows = (r) => (Array.isArray(r?.trace) ? r.trace : []);
function recording(rows) {
  const length = rows.length;
  return {
    time_s: rows.map((r) => r.time_s),
    measured: { vehicle_speed_ms: rows.map((r) => r.speed_ms) },
    derived: { known_segment_distance_m: rows.map((r) => r.position_m) },
    valid_speed_intervals: Array(Math.max(0, length - 1)).fill(true),
    configuration: { preprocessing: { max_gap_s: 1e9 } },
    metadata: { time_origin_s: 0 },
  };
}
export async function mountLab(root, { header, notice, content }) {
  style();
  loadLibrary();
  await clockLibrary();
  const life = new AbortController();
  let request = null,
    exportRequest = null,
    raf = 0,
    clock = null,
    result = retainedResult,
    plotCache = null,
    routeCache = null,
    profile = retainedInputs.profile,
    route = retainedInputs.route,
    inputControllers = {},
    disposed = false,
    sequence = 0,
    lastDraw = 0,
    lastFlow = undefined;
  const $ = (id) => root.querySelector("#" + id);
  const on = (node, event, fn) =>
    node.addEventListener(event, fn, { signal: life.signal });
  root.innerHTML =
    header(
      "04 / COUPLED ENGINEERING EXPERIMENTS",
      "Run once. Inspect every response.",
      "Use the active vehicle design, control the conditions and replay a frozen numerical result.",
      "DETERMINISTIC LAB",
    ) +
    `
 <section class="lab-workspace"><aside class="lab-controls"><form id="lab-form"><label>Active vehicle<select id="lab-vehicle"></select></label><p class="quiet" id="lab-active-note"></p><label>Experiment<select id="lab-kind">${Object.entries(
   TYPES,
 )
   .map(([id, v]) => `<option value="${id}">${v.label}</option>`)
   .join(
     "",
   )}<option value="profile">Driving profile · sourced or illustrative</option></select></label><div id="lab-profile-controls" hidden><label>Driving profile<select id="lab-profile"><option value="">Choose a profile</option></select></label><label>Analysis mode<select id="lab-analysis-mode"><option value="predictive">Predictive achieved movement</option><option value="prescribed">Prescribed demand & feasibility</option></select></label><label>Optional distance-indexed route<select id="lab-route"><option value="">No route · time/speed profile only</option></select></label><label>Missing profile / route gradient policy<select id="lab-grade-policy"><option value="require">Require sourced gradient/elevation</option><option value="experiment_constant_assumption">Explicitly use experiment constant gradient</option></select></label><p id="lab-input-note" class="quiet">Loading lightweight profile catalogue…</p><details><summary>Import a custom CSV</summary><label>Input contract<select id="lab-import-kind"><option value="profile">Time-indexed speed profile</option><option value="route">Distance-indexed route</option></select></label><label>CSV<input id="lab-import-file" type="file" accept=".csv"></label><label>Source name<input id="lab-import-name" type="text" value="Custom engineering profile" maxlength="120"></label><div class="lab-field-grid"><label>Time column<input data-column="time" value="time_s"></label><label>Speed column<input data-column="speed" value="speed_ms"></label><label>Distance column<input data-column="distance" value="distance_m"></label><label>Latitude column<input data-column="latitude" value="latitude"></label><label>Longitude column<input data-column="longitude" value="longitude"></label><label>Elevation column<input data-column="elevation" value="elevation_m"></label><label>Gradient column<input data-column="grade" value=""></label><label>Speed unit<select id="lab-speed-unit"><option value="m/s">m/s</option><option value="km/h">km/h</option></select></label><label>Time unit<select id="lab-time-unit"><option value="s">s</option><option value="ms">ms</option></select></label><label>Distance unit<select id="lab-distance-unit"><option value="m">m</option><option value="km">km</option></select></label><label>Gradient unit<select id="lab-grade-unit"><option value="percent">percent</option><option value="fraction">fraction</option></select></label><label>Maximum time gap · s<input id="lab-max-gap-s" type="number" min=".01" max="60" step="any" value="2"></label><label>Maximum route gap · m<input id="lab-max-gap-m" type="number" min="1" max="10000" step="any" value="1000"></label></div><label class="lab-check"><input id="lab-import-confirm" type="checkbox"> I reviewed source origin, column names and units. Importing does not authenticate measurements.</label><button id="lab-import" type="button">Validate and import CSV</button><p class="quiet">Leave absent optional column names blank. Source hashes and original sampling are retained; bounded server validation rejects gaps/inconsistent units rather than truncating.</p></details><details><summary>Selected input source and coverage</summary><pre id="lab-input-source">No profile selected.</pre></details></div><p id="lab-mode-description" class="quiet"></p><div class="lab-field-grid"><label>Initial speed · km/h<input id="lab-initial" type="number" min="0" max="300" step="any" value="80" required></label><label id="lab-target-label">Target speed · km/h<input id="lab-target" type="number" min="0" max="300" step="any" value="80" required></label><label>Duration · s<input id="lab-duration" type="number" min=".01" max="1800" step="any" value="30" required></label><label>Gradient · %<input id="lab-grade" type="number" min="-30" max="30" step="any" value="0" required></label></div><details><summary>Numerical and braking settings</summary><div class="lab-field-grid"><label>Timestep · s<input id="lab-dt" type="number" min=".01" max=".25" step=".01" value=".01" required></label><label>Braking demand · m/s²<input id="lab-brake" type="number" min=".1" max="12" step=".1" value="4" required></label></div><label class="lab-check"><input id="lab-regen" type="checkbox" checked> Enable regenerative braking within modelled limits</label></details><details id="lab-assumptions"><summary>Required model acknowledgements</summary>${ACKS.map((id, i) => `<label class="lab-check"><input type="checkbox" class="lab-ack" value="${id}">${ACK_TEXT[i]}</label>`).join("")}</details><div class="lab-submit"><button type="submit" id="lab-run" class="primary">Run experiment</button><p id="lab-status" class="configuration-status" role="status">Select conditions and acknowledge model limitations. No experiment executed.</p></div></form><p class="quiet">Predicted movement and requested demand are different quantities. Unachievable targets remain visible.</p><a href="/engineering?workspace=validate" class="quiet">Existing engineering tools ↗</a></aside>
 <div class="lab-results"><section class="lab-instrument"><div class="lab-identity"><span id="lab-result-name">NO RESULT LOADED</span><span id="lab-result-mode">NOT EXECUTED</span></div><p id="lab-frozen-note" class="lab-frozen-note"></p><div class="lab-instrument-row"><svg id="lab-speedometer" class="lab-speedometer" viewBox="0 0 230 145" role="img" aria-label="Achieved speed unavailable"><path class="lab-speed-track" d="M30 125A93 93 0 1 1 200 125"/><path id="lab-speed-needle" d="M115 98L57 109"/><circle cx="115" cy="98" r="4"/><text id="lab-speed" x="115" y="105" text-anchor="middle">—</text><text class="lab-gauge-unit" x="115" y="133" text-anchor="middle">km/h · ACHIEVED</text></svg><div class="lab-current"><span>BATTERY SOC</span><strong id="lab-soc">—</strong><small>%</small></div><div class="lab-current"><span>BATTERY DC POWER</span><strong id="lab-power">—</strong><small>kW · + discharge / − charge</small></div></div><div class="lab-visual-controls"><label>Engineering view<select id="lab-visual-mode"><option value="vehicle">Vehicle power paths</option><option value="inputs">Route / speed profile</option></select></label><label id="lab-overlay-label" hidden>Route overlay<select id="lab-route-overlay"><option value="none">Source geometry only</option><option value="speed_ms">Achieved speed</option><option value="battery_power_w">Battery DC power</option><option value="regen_power_w">Recovered DC power</option><option value="elevation_m">Source elevation</option><option value="grade_percent">Source gradient</option></select></label></div><div id="lab-visual" class="lab-visual"><div id="lab-car"></div><canvas id="lab-route-plot" role="img" aria-label="Source route or time-indexed speed profile" hidden></canvas><p id="lab-visual-caption">Conceptual systems illustration; no detailed component-internal model is implied.</p></div><div class="lab-plot-heading"><label>Telemetry<select id="lab-signal"><option value="speed_ms">Achieved & requested speed</option></select></label><span id="lab-plot-unit">km/h</span><span id="lab-sample">No trace samples</span></div><canvas id="lab-plot" role="img" aria-label="Synchronized experiment telemetry plot"></canvas><div class="lab-transport"><button id="lab-play" type="button" disabled>▶ Play</button><button id="lab-restart" type="button" disabled>Restart</button><input id="lab-seek" type="range" min="0" max="1" value="0" step=".001" aria-label="Experiment replay time" disabled><span id="lab-time">— / — s</span><label>Rate<select id="lab-rate" aria-label="Playback rate" disabled><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></label></div></section><section class="lab-evidence"><div class="lab-evidence-head"><h2>Engineering findings</h2><div class="lab-export"><button id="lab-json" disabled>JSON</button><button id="lab-csv" disabled>CSV</button><button id="lab-html" disabled>HTML report</button></div></div><div id="lab-findings"><p class="quiet">Computed findings appear after a successful run. No synthetic outcomes are inserted into this view.</p></div><details><summary>Summary, assumptions and reproduction</summary><div id="lab-summary"></div><pre id="lab-reproduction">No result.</pre></details></section></div></section>`;
  function inputSources() {
    return result
      ? {
          profile: result.request?.profile || null,
          route: result.request?.route || null,
        }
      : { profile, route };
  }
  function applyProfileSettings(value) {
    const duration = value.time_s.at(-1),
      minimum = 0.01;
    $("lab-duration").max = 1800;
    $("lab-duration").value = duration;
    const candidates = [0.05, 0.1, 0.2, 0.25];
    let dt = candidates.find(
      (v) =>
        duration / v <= 12000 + 1e-8 &&
        Math.abs(duration / v - Math.round(duration / v)) < 1e-7,
    );
    if (!dt) {
      const count = Math.min(12000, Math.ceil(duration / 0.05));
      dt = duration / count;
    }
    if (dt >= minimum && dt <= 0.25) $("lab-dt").value = dt;
    $("lab-dt").step = "any";
    $("lab-initial").value = value.speed_ms[0] * 3.6;
    $("lab-input-note").textContent =
      `Full source span ${number(duration, 3)} s / ${value.time_s.length} original samples. Suggested solver step ${number(dt, 5)} s; source samples are not resampled or truncated.`;
    $("lab-input-source").textContent = JSON.stringify(
      { profile: value.source, route: route?.source ?? null },
      null,
      2,
    );
  }
  function selectedInputsChanged() {
    retainedInputs = { profile, route };
    routeCache = null;
    $("lab-input-source").textContent = JSON.stringify(
      { profile: profile?.source ?? null, route: route?.source ?? null },
      null,
      2,
    );
    if (result)
      $("lab-input-note").textContent +=
        " New inputs apply on the next run; the previous replay remains frozen.";
    updateOverlayChoices();
    if (!result) drawVisual();
  }
  async function loadInput(kind, id) {
    if (!id) {
      if (kind === "route") route = null;
      else profile = null;
      selectedInputsChanged();
      return;
    }
    if (id === "imported") return;
    inputControllers[kind]?.abort();
    const controller = new AbortController();
    inputControllers[kind] = controller;
    try {
      const response = await fetch(
        `/api/lab/${kind === "route" ? "routes" : "profiles"}/${encodeURIComponent(id)}`,
        { signal: controller.signal },
      );
      const data = await response.json();
      if (!response.ok)
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      if (disposed) return;
      if (kind === "profile") {
        profile = data;
        applyProfileSettings(data);
      } else route = data;
      selectedInputsChanged();
    } catch (e) {
      if (e.name !== "AbortError" && !disposed)
        $("lab-input-note").textContent = "Input unavailable: " + e.message;
    }
  }
  async function initCatalogue() {
    try {
      cataloguePromise ||= fetch("/api/lab/catalogue")
        .then(async (r) => {
          if (!r.ok) throw Error("Catalogue unavailable");
          return r.json();
        })
        .catch((e) => {
          cataloguePromise = null;
          throw e;
        });
      const data = await cataloguePromise;
      if (disposed) return;
      for (const [kind, items] of [
        ["profile", data.profiles || []],
        ["route", data.routes || []],
      ]) {
        for (const item of items) {
          const option = document.createElement("option");
          option.value = item.id;
          option.textContent = item.name;
          $("lab-" + kind).append(option);
        }
      }
      $("lab-input-note").textContent =
        "Source objects load only when selected. No route or standardized cycle is invented.";
      if (profile) {
        const option = new Option("Current · " + profile.name, "imported");
        $("lab-profile").append(option);
        $("lab-profile").value = "imported";
      }
      if (route) {
        const option = new Option("Current · " + route.name, "imported");
        $("lab-route").append(option);
        $("lab-route").value = "imported";
      }
    } catch (e) {
      if (!disposed)
        $("lab-input-note").textContent =
          "Profile catalogue unavailable: " + e.message;
    }
  }
  on($("lab-profile"), "change", () =>
    loadInput("profile", $("lab-profile").value),
  );
  on($("lab-route"), "change", () => loadInput("route", $("lab-route").value));
  on($("lab-analysis-mode"), "change", () => {
    $("lab-mode-description").textContent =
      $("lab-analysis-mode").value === "prescribed"
        ? "Requested profile demand is evaluated separately from constrained achieved movement; feasibility remains explicit."
        : "Deterministic tracking predicts achieved speed within the selected design limits. The target is not forced.";
  });
  on($("lab-import"), "click", async () => {
    const file = $("lab-import-file").files[0],
      kind = $("lab-import-kind").value;
    if (!file) {
      $("lab-input-note").textContent = "Choose a CSV first.";
      return;
    }
    if (!$("lab-import-confirm").checked) {
      $("lab-input-note").textContent =
        "Confirm source origin, columns and units before import.";
      return;
    }
    if (file.size > 2000000) {
      $("lab-input-note").textContent =
        "CSV exceeds the 2 MB client bound; no truncation performed.";
      return;
    }
    try {
      const csv_base64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1]);
        reader.onerror = () => reject(Error("Cannot read CSV"));
        reader.readAsDataURL(file);
      });
      const columns = {};
      for (const input of root.querySelectorAll("[data-column]"))
        if (input.value.trim())
          columns[input.dataset.column] = input.value.trim();
      if (kind === "profile") {
        delete columns.distance;
        delete columns.latitude;
        delete columns.longitude;
        delete columns.elevation;
      } else {
        delete columns.time;
        delete columns.speed;
      }
      const configuration = {
        name: $("lab-import-name").value,
        kind: "custom",
        time_unit: $("lab-time-unit").value,
        speed_unit: $("lab-speed-unit").value,
        distance_unit: $("lab-distance-unit").value,
        elevation_unit: "m",
        grade_unit: $("lab-grade-unit").value,
        columns,
        max_gap_s: $("lab-max-gap-s").valueAsNumber,
        max_gap_m: $("lab-max-gap-m").valueAsNumber,
      };
      inputControllers.import?.abort();
      const controller = new AbortController();
      inputControllers.import = controller;
      const response = await fetch("/api/lab/import/" + kind, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_base64, configuration }),
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok)
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      if (disposed) return;
      const selector = $("lab-" + kind);
      selector.querySelector('[value="imported"]')?.remove();
      selector.append(new Option("Imported · " + data.name, "imported"));
      selector.value = "imported";
      if (kind === "profile") {
        profile = data;
        applyProfileSettings(data);
      } else route = data;
      selectedInputsChanged();
      $("lab-input-note").textContent +=
        " Imported source was validated; measurements are not independently authenticated.";
    } catch (e) {
      if (e.name !== "AbortError" && !disposed)
        $("lab-input-note").textContent = "Import rejected: " + e.message;
    }
  });
  for (const input of root.querySelectorAll(
    "#lab-import-file,#lab-import-name,[data-column],#lab-time-unit,#lab-speed-unit,#lab-distance-unit,#lab-grade-unit,#lab-max-gap-s,#lab-max-gap-m",
  ))
    on(input, "change", () => {
      $("lab-import-confirm").checked = false;
    });
  function updateOverlayChoices() {
    const src = inputSources(),
      rows = traceRows(result),
      hasGeometry =
        src.route &&
        src.route.latitude?.some(Number.isFinite) &&
        src.route.longitude?.some(Number.isFinite);
    $("lab-overlay-label").hidden = !hasGeometry;
    for (const option of $("lab-route-overlay").options) {
      if (option.value === "none") continue;
      const key = option.value;
      option.disabled =
        key === "elevation_m" || key === "grade_percent"
          ? !src.route?.[key]?.some(Number.isFinite)
          : !rows.some((row) => Number.isFinite(row[key]));
    }
    if ($("lab-route-overlay").selectedOptions[0]?.disabled)
      $("lab-route-overlay").value = "none";
  }
  on($("lab-visual-mode"), "change", () => {
    routeCache = null;
    updateOverlayChoices();
    drawVisual(
      clock ? traceRows(result)[clock.state().index] : null,
      clock?.time ?? 0,
    );
  });
  on($("lab-route-overlay"), "change", () => {
    routeCache = null;
    drawVisual(
      clock ? traceRows(result)[clock.state().index] : null,
      clock?.time ?? 0,
    );
  });
  function drawVisual(sample = null, time = 0) {
    if (!$("lab-route-plot")) return;
    const inputs = $("lab-visual-mode").value === "inputs";
    $("lab-car").hidden = inputs;
    $("lab-route-plot").hidden = !inputs;
    if (!inputs) {
      $("lab-overlay-label").hidden = true;
      $("lab-visual-caption").textContent =
        "Conceptual systems illustration; highlights follow modelled battery/motor power, not a component-internal simulation.";
      return;
    }
    updateOverlayChoices();
    const sources = inputSources(),
      r = sources.route,
      p = sources.profile,
      canvas = $("lab-route-plot"),
      rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const dpr = Math.min(2, devicePixelRatio || 1),
      w = rect.width,
      h = rect.height,
      overlay = $("lab-route-overlay").value;
    const geometry =
      r &&
      r.s_m?.length > 1 &&
      r.latitude?.some(Number.isFinite) &&
      r.longitude?.some(Number.isFinite);
    const signature = [
      r?.id,
      p?.id,
      result?.run_sha256,
      overlay,
      w,
      h,
      dpr,
    ].join(":");
    const distanceRows = traceRows(result);
    const rowAtDistance = (distance) => {
      let lo = 0,
        hi = distanceRows.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (distanceRows[mid].position_m < distance) lo = mid + 1;
        else hi = mid;
      }
      return distanceRows[lo] ?? null;
    };
    if (!routeCache || routeCache.signature !== signature) {
      const image = document.createElement("canvas");
      image.width = w * dpr;
      image.height = h * dpr;
      const c = image.getContext("2d");
      c.scale(dpr, dpr);
      c.fillStyle = "#102131";
      c.fillRect(0, 0, w, h);
      c.fillStyle = "#b2ccd2";
      c.font = "10px Segoe UI";
      let project = null;
      if (geometry) {
        const points = r.s_m
          .map((distance, i) => ({
            distance,
            lat: r.latitude[i],
            lon: r.longitude[i],
            index: i,
          }))
          .filter((v) => Number.isFinite(v.lat) && Number.isFinite(v.lon));
        const meanLat = points.reduce((s, v) => s + v.lat, 0) / points.length,
          cos = Math.cos((meanLat * Math.PI) / 180);
        const xs = points.map((v) => v.lon * cos),
          ys = points.map((v) => v.lat),
          minX = Math.min(...xs),
          maxX = Math.max(...xs),
          minY = Math.min(...ys),
          maxY = Math.max(...ys);
        const scale = Math.min(
          (w - 52) / Math.max(1e-9, maxX - minX),
          (h - 38) / Math.max(1e-9, maxY - minY),
        );
        project = (lat, lon) => [
          w / 2 + (lon * cos - (minX + maxX) / 2) * scale,
          h / 2 - (lat - (minY + maxY) / 2) * scale,
        ];
        const valueAt = (v) =>
          overlay === "none"
            ? null
            : overlay === "elevation_m" || overlay === "grade_percent"
              ? r[overlay]?.[v.index]
              : rowAtDistance(v.distance)?.[overlay];
        const values = points.map(valueAt).filter(Number.isFinite),
          lo = Math.min(...values),
          hi = Math.max(...values);
        c.lineWidth = 3;
        for (let i = 1; i < points.length; i++) {
          const a = points[i - 1],
            b = points[i];
          if (
            b.index !== a.index + 1 ||
            b.distance - a.distance > (r.max_gap_m ?? 1000)
          )
            continue;
          const value = valueAt(b);
          c.strokeStyle = Number.isFinite(value)
            ? `hsl(${210 - (180 * (value - lo)) / Math.max(1e-9, hi - lo)} 47% 65%)`
            : "#769c9c";
          const pa = project(a.lat, a.lon),
            pb = project(b.lat, b.lon);
          c.beginPath();
          c.moveTo(...pa);
          c.lineTo(...pb);
          c.stroke();
        }
        c.fillText(
          overlay === "none"
            ? "SOURCE GEOMETRY ONLY"
            : (()=>{const meta=SIGNALS[overlay]||(overlay==='elevation_m'?['Source elevation','m',1]:['Source gradient','%',1]);return `${meta[0]} · ${number(lo*meta[2],2)} to ${number(hi*meta[2],2)} ${meta[1]}`})(),
          10,
          14,
        );
      } else if (p?.time_s?.length > 1) {
        const max = Math.max(1, ...p.speed_ms) * 3.6,
          duration = p.time_s.at(-1);
        c.strokeStyle = "#e1b784";
        c.lineWidth = 2;
        c.beginPath();
        for (let i = 0; i < p.time_s.length; i++) {
          const x = 25 + (p.time_s[i] / duration) * (w - 50),
            y = h - 22 - ((p.speed_ms[i] * 3.6) / max) * (h - 46);
          if (i === 0) c.moveTo(x, y);
          else c.lineTo(x, y);
        }
        c.stroke();
        c.fillText(
          "TIME-INDEXED REQUESTED SPEED PROFILE · NO MAP COORDINATES",
          10,
          13,
        );
        c.fillText(`0 → ${number(duration, 1)} s`, w - 100, h - 6);
      } else {
        c.fillText(
          r
            ? "Distance-indexed source has no usable geographic coordinates. No map invented."
            : "Select a sourced route or time-indexed profile to inspect its input.",
          15,
          h / 2,
        );
      }
      routeCache = { signature, image, project, geometry };
    }
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    const c = canvas.getContext("2d");
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.drawImage(routeCache.image, 0, 0);
    c.scale(dpr, dpr);
    if (routeCache.geometry && sample && Number.isFinite(sample.position_m)) {
      const distance = sample.position_m,
        s = r.s_m;
      if (distance >= s[0] && distance <= s.at(-1)) {
        let low = 0,
          high = s.length - 1;
        while (low + 1 < high) {
          const mid = (low + high) >> 1;
          if (s[mid] <= distance) low = mid;
          else high = mid;
        }
        const i = Math.min(s.length - 2, low);
        if (
          Number.isFinite(r.latitude[i]) &&
          Number.isFinite(r.latitude[i + 1]) &&
          Number.isFinite(r.longitude[i]) &&
          Number.isFinite(r.longitude[i + 1]) &&
          s[i + 1] - s[i] <= (r.max_gap_m ?? 1000)
        ) {
          const f = (distance - s[i]) / (s[i + 1] - s[i]),
            xy = routeCache.project(
              r.latitude[i] + f * (r.latitude[i + 1] - r.latitude[i]),
              r.longitude[i] + f * (r.longitude[i + 1] - r.longitude[i]),
            );
          c.fillStyle = "#fff2ce";
          c.beginPath();
          c.arc(...xy, 4, 0, Math.PI * 2);
          c.fill();
        }
      }
    } else if (!routeCache.geometry && p?.time_s?.length > 1) {
      const x = 25 + (time / p.time_s.at(-1)) * (w - 50);
      c.strokeStyle = "#dce9ec";
      c.setLineDash([3, 3]);
      c.beginPath();
      c.moveTo(x, 25);
      c.lineTo(x, h - 18);
      c.stroke();
      c.setLineDash([]);
    }
    canvas.dataset.cursorTime = time.toFixed(6);
    canvas.dataset.geometry = String(!!routeCache.geometry);
    const kind = r?.source?.kind || p?.source?.kind || "source";
    $("lab-visual-caption").textContent = routeCache.geometry
      ? `${r.name} · ${kind} geometry · approximate local display projection, not a lateral model or lap-time prediction.`
      : p
        ? `${p.name} · requested source profile; the map is unavailable without coordinates.`
        : "Source geometry unavailable.";
  }
  initCatalogue();
  function vehicleMenu() {
    const selected = state.activeId || "active";
    $("lab-vehicle").innerHTML =
      (state.design
        ? `<option value="active">Active · ${esc(state.design.name)}</option>`
        : '<option value="">No active design — create one in Design Studio</option>') +
      state.library
        .map(
          (r) =>
            `<option value="${esc(r.id)}">Saved · ${esc(r.design.name)}</option>`,
        )
        .join("");
    $("lab-vehicle").value = state.library.some((r) => r.id === selected)
      ? selected
      : state.design
        ? "active"
        : "";
    $("lab-active-note").textContent = state.design
      ? state.dirty
        ? "Current unsaved changes will be frozen into the run."
        : "Active design is validated by the backend when run."
      : "A vehicle snapshot is required. No default vehicle will be silently substituted.";
    $("lab-run").disabled = !state.design;
    if (!result) {
      showCar(state.design);
      drawVisual();
    }
    frozenNote();
  }
  function stable(value) {
    return JSON.stringify(value, (_, v) =>
      v && typeof v === "object" && !Array.isArray(v)
        ? Object.fromEntries(
            Object.keys(v)
              .sort()
              .map((k) => [k, v[k]]),
          )
        : v,
    );
  }
  function frozenNote() {
    if (!result) return;
    const changed = stable(state.design) !== stable(result.vehicle);
    $("lab-frozen-note").textContent = changed
      ? "Active design or settings differ from this frozen result. Replay still describes the recorded run vehicle."
      : "Frozen result: changing the active design does not change these numerical samples.";
  }
  function showCar(design) {
    $("lab-car").innerHTML =
      design && content?.components
        ? anatomySVG(content.components, false, {
            annotations: false,
            body: "cutaway",
            selected: null,
          })
        : '<p class="lab-empty">Select an active vehicle design to prepare a simulation.</p>';
    const svg = $("lab-car").querySelector("svg");
    if (svg) svg.classList.add("lab-cutaway");
    lastFlow = undefined;
  }
  function defaults() {
    const kind = $("lab-kind").value,
      d = TYPES[kind] || {
        mode: "predictive",
        speed: 0,
        target: 100,
        duration: 30,
        grade: 0,
      };
    $("lab-profile-controls").hidden = kind !== "profile";
    $("lab-initial").value = d.speed;
    $("lab-target").value = d.target;
    $("lab-duration").value = d.duration;
    $("lab-grade").value = d.grade;
    $("lab-regen").checked = kind !== "coast";
    $("lab-target-label").hidden = ["braking", "coast"].includes(kind);
    $("lab-mode-description").textContent =
      d.mode === "prescribed"
        ? "Prescribed demand analysis: requested speed is an input; feasibility must be checked."
        : "Predictive dynamics: achieved movement follows the modelled component and traction limits.";
  }
  on($("lab-kind"), "change", () => {
    defaults();
    if ($("lab-kind").value === "profile" && profile)
      applyProfileSettings(profile);
  });
  defaults();
  vehicleMenu();
  on($("lab-vehicle"), "change", () => {
    const record = state.library.find((r) => r.id === $("lab-vehicle").value);
    if (!record) return;
    const previous = {
      design: state.design,
      activeId: state.activeId,
      dirty: state.dirty,
      evaluation: state.evaluation,
    };
    try {
      state.design = structuredClone(record.design);
      state.dirty = false;
      state.evaluation = null;
      persist(state.library, record.id);
    } catch (e) {
      Object.assign(state, previous);
      notice(e.message);
      vehicleMenu();
    }
  });
  on(window, "veus:design", vehicleMenu);
  function stop() {
    if (clock) clock.pause(performance.now());
    cancelAnimationFrame(raf);
    raf = 0;
    if ($("lab-play")) $("lab-play").textContent = "▶ Play";
  }
  on(document, "visibilitychange", () => {
    if (document.hidden) stop();
  });
  function paint(now = performance.now(), force = false) {
    if (disposed || !result || !clock) return;
    const playback = clock.tick(now);
    if (force || now - lastDraw > 70) {
      lastDraw = now;
      const rows = traceRows(result),
        sample = rows[playback.index];
      $("lab-speed").textContent = number(sample.speed_ms * 3.6, 1);
      $("lab-speedometer").setAttribute(
        "aria-label",
        `Achieved speed ${number(sample.speed_ms * 3.6, 1)} km/h`,
      );
      const angle =
        ((-160 +
          Math.min(1, Math.max(0, (sample.speed_ms * 3.6) / 240)) * 140) *
          Math.PI) /
        180;
      $("lab-speed-needle").setAttribute(
        "d",
        `M115 98L${115 + 72 * Math.cos(angle)} ${98 + 72 * Math.sin(angle)}`,
      );
      $("lab-soc").textContent = number(sample.soc * 100, 2);
      $("lab-power").textContent = number(sample.battery_power_w / 1000, 2);
      $("lab-seek").value = playback.time_s;
      $("lab-time").textContent =
        `${number(playback.time_s, 2)} / ${number(clock.duration, 2)} s`;
      $("lab-sample").textContent =
        `Actual sample ${playback.index} · ${number(sample.time_s, 3)} s`;
      $("lab-play").textContent = playback.playing ? "Ⅱ Pause" : "▶ Play";
      drawPlot(playback.time_s);
      drawVisual(sample, playback.time_s);
      const flow =
        sample.regen_power_w > 0 && sample.battery_power_w < 0
          ? "regeneration"
          : sample.motor_power_w > 0 && sample.battery_power_w > 0
            ? "propulsion"
            : null;
      if (flow !== lastFlow) {
        updateSchematic($("lab-car").querySelector("svg"), { flow });
        lastFlow = flow;
      }
    }
  }
  function frame(now) {
    if (disposed) return;
    paint(now);
    if (clock?.playing) raf = requestAnimationFrame(frame);
    else raf = 0;
  }
  function drawPlot(time) {
    const canvas = $("lab-plot"),
      rect = canvas.getBoundingClientRect(),
      dpr = Math.min(2, devicePixelRatio || 1),
      key = $("lab-signal").value,
      meta = SIGNALS[key] || [key, "", 1],
      rows = traceRows(result);
    if (!rect.width || !rect.height) return;
    const signature = [
      result.run_sha256,
      key,
      rect.width,
      rect.height,
      dpr,
      document.documentElement.dataset.theme,
    ].join(":");
    const w = rect.width,
      h = rect.height,
      left = 54,
      right = w - 15,
      top = 12,
      bottom = h - 25;
    if (!plotCache || plotCache.signature !== signature) {
      const image = document.createElement("canvas");
      image.width = w * dpr;
      image.height = h * dpr;
      const c = image.getContext("2d");
      c.scale(dpr, dpr);
      c.fillStyle = "#102131";
      c.fillRect(0, 0, w, h);
      let values = rows
        .map((r) => r[key])
        .filter(Number.isFinite)
        .map((v) => v * meta[2]);
      if (key === "speed_ms")
        values = values.concat(
          rows
            .map((r) => r.target_speed_ms)
            .filter(Number.isFinite)
            .map((v) => v * 3.6),
        );
      const lo = Math.min(0, ...values),
        hi = Math.max(1, ...values);
      c.font = "10px Segoe UI";
      c.strokeStyle = "#35505e";
      c.fillStyle = "#b5cbd2";
      for (let i = 0; i < 3; i++) {
        const y = top + ((bottom - top) * i) / 2;
        c.beginPath();
        c.moveTo(left, y);
        c.lineTo(right, y);
        c.stroke();
        c.fillText(number(hi - ((hi - lo) * i) / 2, 1), 2, y + 3);
      }
      c.fillText("0 s", left, h - 5);
      c.fillText(number(clock.duration, 1) + " s", right - 42, h - 5);
      const curve = (field, scale, color, dashed) => {
        c.strokeStyle = color;
        c.setLineDash(dashed ? [4, 4] : []);
        c.lineWidth = 1.5;
        c.beginPath();
        let open = false;
        for (const row of rows) {
          const v = row[field];
          if (!Number.isFinite(v)) {
            open = false;
            continue;
          }
          const x = left + (row.time_s / clock.duration) * (right - left),
            y = bottom - ((v * scale - lo) / (hi - lo)) * (bottom - top);
          if (open) c.lineTo(x, y);
          else {
            c.moveTo(x, y);
            open = true;
          }
        }
        c.stroke();
        c.setLineDash([]);
      };
      curve(key, meta[2], "#a8d0bd", false);
      if (key === "speed_ms") curve("target_speed_ms", 3.6, "#e3b880", true);
      plotCache = { signature, image };
    }
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    const c = canvas.getContext("2d");
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.drawImage(plotCache.image, 0, 0);
    c.scale(dpr, dpr);
    c.strokeStyle = "#d9e7e4";
    c.setLineDash([3, 3]);
    const x = left + (time / clock.duration) * (right - left);
    c.beginPath();
    c.moveTo(x, top);
    c.lineTo(x, bottom);
    c.stroke();
    c.setLineDash([]);
    canvas.dataset.cursorTime = time.toFixed(6);
    canvas.dataset.plotLeft = left;
    canvas.dataset.plotRight = right;
  }
  function install(value, restore = false) {
    const rows = traceRows(value);
    if (rows.length < 2 || rows.some((r) => !Number.isFinite(r.speed_ms)))
      throw Error("Server returned no replayable numerical trace");
    stop();
    result = value;
    retainedResult = value;
    clock = new window.VEUSReplayController(recording(rows));
    if (restore) clock.seek(retainedTime, performance.now());
    else retainedTime = 0;
    plotCache = null;
    $("lab-result-name").textContent =
      `${value.vehicle.name} · ${TYPES[value.experiment.kind]?.label || value.experiment.kind}`;
    $("lab-result-mode").textContent =
      value.experiment.mode.toUpperCase() + " / FROZEN";
    $("lab-signal").innerHTML = Object.entries(SIGNALS)
      .filter(([key]) => rows.some((r) => Number.isFinite(r[key])))
      .map(
        ([key, v]) =>
          `<option value="${key}">${key === "speed_ms" ? "Achieved & requested speed" : v[0]}</option>`,
      )
      .join("");
    for (const id of [
      "lab-play",
      "lab-restart",
      "lab-seek",
      "lab-rate",
      "lab-json",
      "lab-csv",
      "lab-html",
    ])
      $(id).disabled = false;
    $("lab-seek").max = clock.duration;
    showCar(value.vehicle);
    routeCache = null;
    updateOverlayChoices();
    frozenNote();
    renderEvidence();
    paint(performance.now(), true);
  }
  function renderEvidence() {
    const findings = result.findings || [];
    $("lab-findings").replaceChildren();
    for (const finding of findings) {
      const section = document.createElement("section"),
        title = document.createElement("strong"),
        p = document.createElement("p");
      title.textContent =
        finding.title ||
        (finding.id || finding.type || "Computed finding").replaceAll("_", " ");
      if (Number.isFinite(finding.value)) {
        const value = document.createElement("span");
        value.className = "lab-finding-value";
        value.textContent =
          number(finding.value, 4) + " " + (finding.unit || "");
        title.append(" · ", value);
      }
      p.textContent =
        finding.statement ||
        finding.message ||
        finding.explanation ||
        finding.text ||
        JSON.stringify(finding);
      section.append(title, p);
      $("lab-findings").append(section);
    }
    if (!findings.length)
      $("lab-findings").textContent =
        "No additional finding was justified by the result.";
    const table = document.createElement("table");
    table.innerHTML =
      "<thead><tr><th>Metric</th><th>Value</th><th>Unit / qualification</th></tr></thead>";
    for (const [key, v] of Object.entries(result.summary || {})) {
      const row = table.insertRow();
      row.insertCell().textContent = key.replaceAll("_", " ");
      row.insertCell().textContent =
        typeof v === "number"
          ? number(v, 5)
          : typeof v === "object" && v !== null
            ? number(v.value, 5)
            : String(v ?? "Unavailable");
      row.insertCell().textContent =
        typeof v === "object" && v !== null
          ? v.unit || v.unavailable_reason || ""
          : result.summary_units?.[key] || "";
    }
    $("lab-summary").replaceChildren(table);
    $("lab-reproduction").textContent = JSON.stringify(
      {
        run_sha256: result.run_sha256,
        model_version: result.model_version,
        experiment: result.experiment,
        assumptions: result.assumptions,
        provenance: {
          classification: result.provenance?.classification,
          energy_basis: result.provenance?.energy_basis,
          route_basis: result.provenance?.route_basis,
          profile: result.request?.profile?.source,
          route: result.request?.route?.source,
        },
        limitations: result.limitations,
      },
      null,
      2,
    );
  }
  on($("lab-form"), "submit", async (event) => {
    event.preventDefault();
    if (!state.design) {
      notice("Create or select an active design first.");
      return;
    }
    const ack = [...root.querySelectorAll(".lab-ack:checked")].map(
      (x) => x.value,
    );
    if (ack.length !== ACKS.length) {
      $("lab-assumptions").open = true;
      $("lab-status").textContent =
        "Acknowledge all listed model assumptions before running.";
      return;
    }
    const kind = $("lab-kind").value;
    if (kind === "profile" && !profile) {
      $("lab-status").textContent =
        "Select or import a validated driving profile first.";
      return;
    }
    const experiment = {
      kind,
      mode:
        kind === "profile" ? $("lab-analysis-mode").value : TYPES[kind].mode,
      duration_s: $("lab-duration").valueAsNumber,
      dt_s: $("lab-dt").valueAsNumber,
      initial_speed_ms: $("lab-initial").valueAsNumber / 3.6,
      target_speed_ms: $("lab-target").valueAsNumber / 3.6,
      grade_percent: $("lab-grade").valueAsNumber,
      regen_enabled: $("lab-regen").checked,
      brake_deceleration_ms2: $("lab-brake").valueAsNumber,
      route_grade_policy: $("lab-grade-policy").value,
    };
    request?.abort();
    request = new AbortController();
    const token = ++sequence;
    stop();
    $("lab-run").disabled = true;
    $("lab-status").textContent = "Running deterministic backend experiment…";
    try {
      const response = await fetch("/api/lab/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_version: 1,
          vehicle: structuredClone(state.design),
          experiment,
          acknowledgements: ack,
          profile: kind === "profile" ? profile : null,
          route: kind === "profile" ? route : null,
        }),
        signal: request.signal,
      });
      const value = await response.json();
      if (!response.ok)
        throw Error(
          typeof value.detail === "string"
            ? value.detail
            : JSON.stringify(value.detail),
        );
      if (disposed || token !== sequence) return;
      install(value);
      $("lab-status").textContent =
        "Completed. Replay reads stored samples; it does not rerun the experiment.";
    } catch (e) {
      if (e.name !== "AbortError")
        $("lab-status").textContent = "Run unavailable: " + e.message;
    } finally {
      if (!disposed) $("lab-run").disabled = !state.design;
    }
  });
  on($("lab-play"), "click", () => {
    if (!clock) return;
    if (clock.playing) stop();
    else {
      clock.play(performance.now());
      if (!raf) raf = requestAnimationFrame(frame);
    }
    paint(performance.now(), true);
  });
  on($("lab-restart"), "click", () => {
    stop();
    clock.restart(performance.now());
    paint(performance.now(), true);
  });
  on($("lab-seek"), "input", () => {
    clock.seek(Number($("lab-seek").value), performance.now());
    paint(performance.now(), true);
  });
  on($("lab-rate"), "change", () =>
    clock?.setRate(Number($("lab-rate").value), performance.now()),
  );
  on($("lab-signal"), "change", () => {
    plotCache = null;
    $("lab-plot-unit").textContent = SIGNALS[$("lab-signal").value]?.[1] || "";
    if (clock) drawPlot(clock.time);
  });
  on($("lab-plot"), "click", (event) => {
    if (!clock) return;
    const box = $("lab-plot").getBoundingClientRect(),
      left = Number($("lab-plot").dataset.plotLeft),
      right = Number($("lab-plot").dataset.plotRight);
    clock.seek(
      Math.max(
        0,
        Math.min(1, (event.clientX - box.left - left) / (right - left)),
      ) * clock.duration,
      performance.now(),
    );
    paint(performance.now(), true);
  });
  on(window, "resize", () => {
    plotCache = null;
    routeCache = null;
    if (clock) paint(performance.now(), true);
    else drawVisual();
  });
  async function exportResult(format) {
    if (!result) return;
    exportRequest?.abort();
    exportRequest = new AbortController();
    $("lab-status").textContent =
      "Preparing reproducible " +
      format.toUpperCase() +
      " export from the frozen result…";
    try {
      const response = await fetch("/api/lab/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ result, format }),
        signal: exportRequest.signal,
      });
      const body = await response.json();
      if (!response.ok)
        throw Error(
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail),
        );
      if (disposed) return;
      save(body.filename, body.content, body.media_type);
      $("lab-status").textContent =
        "Exported " + format.toUpperCase() + ". No simulation was rerun.";
    } catch (e) {
      if (e.name !== "AbortError" && !disposed)
        $("lab-status").textContent = "Export unavailable: " + e.message;
    }
  }
  on($("lab-json"), "click", () => exportResult("json"));
  on($("lab-csv"), "click", () => exportResult("csv"));
  on($("lab-html"), "click", () => exportResult("html"));
  if (result) install(result, true);
  // Bounded debug state supports browser verification without a second playback implementation.
  window.VEUSLab = {
    get result() {
      return result;
    },
    get playing() {
      return !!clock?.playing;
    },
    get time() {
      return clock?.time ?? 0;
    },
    get framePending() {
      return !!raf;
    },
  };
  return () => {
    retainedTime = clock?.time ?? 0;
    disposed = true;
    sequence++;
    stop();
    request?.abort();
    for (const controller of Object.values(inputControllers))
      controller.abort();
    exportRequest?.abort();
    life.abort();
    plotCache = null;
    if (window.VEUSLab) delete window.VEUSLab;
  };
}

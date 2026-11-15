"use strict";
(() => {
  const el = (id) => document.getElementById(id),
    host = el("analyseWorkspace");
  const original = el("modelValidation").closest("section");
  original.id = "modelExperimentsPanel";
  const tabs = document.createElement("div");
  tabs.className = "analyse-tabs";
  tabs.innerHTML =
    '<button data-analyse="replay" aria-current="page">Recorded EV replay</button><button data-analyse="experiments">Model experiments & calibration</button>';
  host.querySelector(".workspace-heading").after(tabs);
  const panel = document.createElement("section");
  panel.id = "replayPanel";
  panel.innerHTML = `
 <div class="replay-title"><div><div class="eyebrow">OBSERVATIONS / NOT SIMULATION</div><h2>Inside a recorded drive.</h2></div><span class="badge" id="replayOrigin">NO RECORDING</span></div>
 <div class="replay-load"><label>RECORDING<select id="replayDataset" aria-label="Recorded dataset"></select></label><button id="loadReplay" class="primary">Load recording</button><button id="openReplayMetadata">Dataset information</button></div>
 <p id="replayStatus" role="status" aria-live="polite">Select a genuine VED recording to begin. Model validation remains pending.</p>
 <details id="replayMetadata" class="panel"><summary>Dataset, signals & provenance</summary><div id="replayMetadataContent"></div></details>
 <div class="driving-surface"><div class="scene-head"><span>RECORDED MEASUREMENTS <small> / FICTIONAL LANDSCAPE</small></span><span id="replayState">PAUSED</span></div><canvas id="replayScene" role="img" aria-label="Recorded EV illustration; displacement derived from measured speed, not a GPS trajectory"></canvas><div class="scene-caption"><span>Generic EV silhouette · illustrative appearance</span><span id="replaySceneNote">Derived displacement · 5 px/m · not GPS</span></div></div>
 <div class="replay-transport"><div class="replay-transport-top"><button id="replayPlay" class="primary" disabled>Play</button><button id="replayRestart" disabled>Restart</button><strong id="replayTime">0.00 / — s</strong><label>RATE<select id="replayRate" aria-label="Playback speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></label><label>JUMP TO · elapsed s<input id="replayJump" type="number" min="0" step="0.1" value="0"></label><button id="replayJumpButton" disabled>Go</button></div><input id="replayTimeline" type="range" min="0" max="1" step="0.01" value="0" disabled aria-label="Recorded journey timeline"></div>
 <div class="replay-readouts"><div><span id="replaySpeedKind">MEASURED SPEED</span><strong id="replaySpeed">—</strong><small>km/h</small></div><div><span id="replaySocKind">MEASURED SOC</span><strong id="replaySoc">—</strong><small>%</small></div><div><span id="replayPowerKind">DERIVED SIGNED V×I</span><strong id="replayPower">—</strong><small>kW · polarity may be unknown</small></div><div><span>DERIVED DISTANCE</span><strong id="replayDistance">—</strong><small id="replayDistanceKind">km · not GPS</small></div></div>
 <p id="replaySampleNote" class="muted">Readouts show actual recorded samples; smooth movement is a visual interpolation.</p>
 <div class="replay-content-tabs"><button data-replay-view="charts" aria-current="page">Signals</button><button data-replay-view="events">Driving events <span id="replayEventCount"></span></button><button data-replay-view="summary">Trip insights</button><button data-replay-view="export">Export</button></div>
 <div id="replayChartsView" class="replay-view"><div class="replay-graphs"><section class="panel"><div class="replay-chart-head"><label>PRIMARY SIGNAL<select id="replaySignalA" aria-label="Primary replay graph signal"></select></label><output id="replayHoverA">Hover for an actual sample; click to seek.</output></div><canvas id="replayGraphA" role="img" aria-label="Recorded signal with synchronized playback cursor"></canvas></section><section class="panel"><div class="replay-chart-head"><label>SECONDARY SIGNAL<select id="replaySignalB" aria-label="Secondary replay graph signal"></select></label><output id="replayHoverB">Hover for an actual sample; click to seek.</output></div><canvas id="replayGraphB" role="img" aria-label="Second recorded signal with synchronized playback cursor"></canvas></section></div></div>
 <div id="replayEventsView" class="replay-view panel" hidden><p class="muted">Transparent threshold episodes. Inferred events are not diagnoses. Select an event to inspect its start.</p><div id="replayEvents"></div></div>
 <div id="replaySummaryView" class="replay-view panel" hidden><h2>What the measurements support</h2><div id="replaySummary"></div><details><summary>Additional recorded values & derivation rules</summary><div id="replaySecondary"></div><pre id="replayMethods"></pre></details><p id="replayComparison"></p><button id="replayOpenExperiments">Open Phase 8 model experiments</button></div>
 <div id="replayExportView" class="replay-view panel" hidden><h2>A reproducible analysis</h2><p class="muted">Exports retain source/configuration hashes, elapsed and original timestamps, units, thresholds and measured/derived classifications. HTML is descriptive analysis, not a model validation report.</p><div class="buttons"><button id="replayExportSummary" disabled>Summary JSON</button><button id="replayExportEvents" disabled>Events CSV</button><button id="replayExportMetadata" disabled>Metadata & settings</button><button id="replayExportFull" disabled>Full-resolution JSON</button><button id="replayExportHtml" disabled>Engineering HTML</button></div></div>
 <details id="replayAdvanced" class="panel"><summary>Advanced analysis · thresholds & CSV import</summary><p class="muted">Reanalyse after editing. Unknown current polarity disables energy/regen claims. Source assertions are not authenticated.</p><div class="fields"><label>Acceleration threshold · m/s²<input id="replayAccelThreshold" type="number" min="0.01" step="0.1" value="2"></label><label>Deceleration magnitude · m/s²<input id="replayDecelThreshold" type="number" min="0.01" step="0.1" value="2.5"></label><label>High abs(V×I) · kW<input id="replayPowerThreshold" type="number" min="0.001" value="50"></label><label>Standstill · m/s<input id="replayStopThreshold" type="number" min="0" step="0.1" value="0.1"></label><label>Minimum episode · s<input id="replayDurationThreshold" type="number" min="0" step="0.1" value="0.5"></label></div><button id="replayApplyThresholds" disabled>Reanalyse thresholds</button><details><summary>Custom CSV and configuration</summary><p class="muted">Up to 2 MB / 5000 rows / one day. Load matching config JSON with explicit units, source, provenance and SHA-256. Source bytes are never changed. Only mapped columns are replayed.</p><div class="fields"><label>Measurement CSV<input id="replayCsv" type="file" accept=".csv"></label><label>Replay config JSON<input id="replayConfigFile" type="file" accept=".json"></label></div><textarea id="replayConfig" aria-label="Replay configuration JSON"></textarea><button id="replayImport">Analyse imported CSV / JSON</button></details></details>`;
  tabs.after(panel);
  original.hidden = true;
  let result = null,
    request = null,
    clock = null,
    raf = null,
    lastUI = -1,
    lastPlot = -1,
    tab = "replay",
    subview = "charts",
    loadToken = 0;
  let replayImages = {},
    plotCache = {},
    readinessContext = null,
    selectedInterval = null;
  const scene = new window.VEUSScene(
    el("replayScene"),
    () => replayImages,
    "REPLAY",
  );
  const names = {
    vehicle_speed_ms: "Speed",
    battery_voltage_v: "Battery voltage",
    battery_current_a: "Signed battery current",
    battery_soc: "Battery SOC",
    ambient_temperature_c: "Outside air temperature",
    longitudinal_acceleration_ms2: "Recorded acceleration",
    electrical_power_w: "Signed V×I",
    battery_power_w: "Recorded signed power",
    acceleration_ms2: "Derived acceleration",
    known_segment_distance_m: "Known-segment displacement",
    electrical_energy_used_wh: "Electrical energy used",
    electrical_energy_received_wh: "Electrical energy received",
  };
  function setTab(name) {
    tab = name;
    document.dispatchEvent(
      new CustomEvent("veus:analyse-tab", { detail: name }),
    );
    panel.hidden = name !== "replay";
    original.hidden = name !== "experiments";
    for (const b of tabs.querySelectorAll("button")) {
      if (b.dataset.analyse === name) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    }
    if (!["replay", "investigate"].includes(name)) pause();
    else start();
    window.dispatchEvent(new Event("resize"));
  }
  for (const b of tabs.querySelectorAll("button"))
    b.onclick = () => setTab(b.dataset.analyse);
  el("replayOpenExperiments").onclick = () => setTab("experiments");
  for (const b of panel.querySelectorAll("[data-replay-view]"))
    b.onclick = () => {
      subview = b.dataset.replayView;
      for (const name of ["charts", "events", "summary", "export"])
        el("replay" + name[0].toUpperCase() + name.slice(1) + "View").hidden =
          name !== subview;
      for (const button of panel.querySelectorAll("[data-replay-view]")) {
        if (button === b) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
      }
      plotCache = {};
      update(performance.now(), true);
    };
  function text(node, value) {
    if (node.textContent !== value) node.textContent = value;
  }
  const num = (value, digits = 2) =>
    Number.isFinite(value) ? value.toFixed(digits) : "Unavailable";
  const download = (name, value, type = "application/json") => {
    const content =
        typeof value === "string"
          ? value
          : JSON.stringify(value, null, 2) + "\n",
      url = URL.createObjectURL(new Blob([content], { type })),
      a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  function pause() {
    if (clock) clock.pause(performance.now());
    cancelAnimationFrame(raf);
    raf = null;
    update(performance.now(), true);
  }
  function start() {
    if (
      raf === null &&
      window.activeWorkspace === "analyse" &&
      ["replay", "investigate"].includes(tab) &&
      !document.hidden
    )
      raf = requestAnimationFrame(frame);
  }
  function frame(now) {
    raf = null;
    update(now);
    if (
      clock?.playing &&
      window.activeWorkspace === "analyse" &&
      ["replay", "investigate"].includes(tab) &&
      !document.hidden
    )
      start();
  }
  function seek(time) {
    if (!clock) return;
    clock.seek(time, performance.now());
    update(performance.now(), true);
    start();
  }
  el("replayPlay").onclick = () => {
    if (!clock) return;
    if (clock.playing) pause();
    else {
      clock.play(performance.now());
      start();
    }
  };
  el("replayRestart").onclick = () => {
    if (clock) {
      clock.restart(performance.now());
      update(performance.now(), true);
    }
  };
  el("replayTimeline").oninput = () => seek(Number(el("replayTimeline").value));
  el("replayRate").onchange = () => {
    if (clock) {
      clock.setRate(Number(el("replayRate").value), performance.now());
      update(performance.now(), true);
      start();
    }
  };
  el("replayJumpButton").onclick = () => seek(Number(el("replayJump").value));
  el("openReplayMetadata").onclick = () => {
    el("replayMetadata").open = !el("replayMetadata").open;
  };
  function getSignal(key) {
    return result.measured[key] || result.derived[key];
  }
  function display(key, value) {
    if (value === null || value === undefined) return "Unavailable";
    if (key === "vehicle_speed_ms") return num(value * 3.6, 2) + " km/h";
    if (key === "battery_soc") return num(value * 100, 3) + " %";
    if (["electrical_power_w", "battery_power_w"].includes(key))
      return num(value / 1000, 3) + " kW";
    return num(value, 4) + " " + (result.units[key] || "");
  }
  function install(data, payload, evidence = null) {
    readinessContext = evidence;
    selectedInterval = null;
    pause();
    result = data;
    request = payload;
    clock = new window.VEUSReplayController(data);
    clock.setRate(Number(el("replayRate").value), performance.now());
    plotCache = {};
    el("replayConfig").value = JSON.stringify(data.configuration, null, 2);
    const cfg = data.configuration,
      t = cfg.thresholds;
    for (const [id, key, scale] of [
      ["replayAccelThreshold", "acceleration_ms2", 1],
      ["replayDecelThreshold", "deceleration_ms2", 1],
      ["replayPowerThreshold", "power_magnitude_w", 0.001],
      ["replayStopThreshold", "standstill_ms", 1],
      ["replayDurationThreshold", "minimum_duration_s", 1],
    ])
      el(id).value = t[key] * scale;
    const src = cfg.source;
    el("replaySpeedKind").textContent =
      cfg.source.kind === "measured" ? "MEASURED SPEED" : "SYNTHETIC SPEED";
    el("replaySocKind").textContent =
      cfg.source.kind === "measured" ? "MEASURED SOC" : "SYNTHETIC SOC";
    el("replayOrigin").textContent =
      src.kind === "measured"
        ? "GENUINE MEASURED DATA"
        : "SYNTHETIC SOFTWARE FIXTURE";
    el("replayStatus").textContent =
      `${src.dataset} · ${src.run_id} · ${data.time_s.length} rows · ${data.time_s.at(-1).toFixed(1)} s window · current polarity ${cfg.current_sign}. No physical validation claim.`;
    el("replayTimeline").max = String(clock.duration);
    el("replayJump").max = String(clock.duration);
    for (const id of [
      "replayPlay",
      "replayRestart",
      "replayJumpButton",
      "replayTimeline",
      "replayApplyThresholds",
      "replayExportSummary",
      "replayExportEvents",
      "replayExportMetadata",
      "replayExportFull",
      "replayExportHtml",
    ])
      el(id).disabled = false;
    const metadata = el("replayMetadataContent");
    metadata.replaceChildren();
    const p = document.createElement("p");
    p.textContent = `${src.dataset} / ${src.run_id} · ${src.kind} · ${src.licence} · timestamp intervals ${data.metadata.sampling_min_s.toFixed(3)}–${data.metadata.sampling_max_s.toFixed(3)} s (median ${data.metadata.sampling_median_s.toFixed(3)} s). Original time origin ${data.metadata.time_origin_s} s.`;
    metadata.append(p);
    const source = document.createElement("a");
    try {
      const url = new URL(src.source_url);
      if (["https:", "http:"].includes(url.protocol)) {
        source.href = url.href;
        source.textContent = "Dataset source ↗";
        source.target = "_blank";
        source.rel = "noopener";
        metadata.append(source);
      }
    } catch {}
    const details = document.createElement("pre");
    details.textContent = JSON.stringify(
      {
        source: src,
        signals: Object.fromEntries(
          Object.keys(data.classifications).map((k) => [
            k,
            { unit: data.units[k], class: data.classifications[k] },
          ]),
        ),
        limits: cfg.limitations,
        missing: data.metadata.missing_counts,
        gaps: data.metadata.gaps,
        provenance: cfg.provenance,
        source_sha256: data.metadata.raw_sha256,
        analysis_sha256: data.analysis_sha256,
      },
      null,
      2,
    );
    metadata.append(details);
    for (const id of ["replaySignalA", "replaySignalB"]) {
      el(id).replaceChildren();
      for (const key of Object.keys(data.classifications)) {
        const option = document.createElement("option");
        option.value = key;
        option.textContent =
          (names[key] || key) +
          " · " +
          (key === "vehicle_speed_ms"
            ? "km/h"
            : key === "battery_soc"
              ? "%"
              : ["electrical_power_w", "battery_power_w"].includes(key)
                ? "kW"
                : data.units[key]) +
          " · " +
          data.classifications[key].split(" ")[0];
        el(id).append(option);
      }
    }
    el("replayPowerKind").textContent = data.derived.electrical_power_w
      ? "DERIVED SIGNED V×I"
      : data.measured.battery_power_w
        ? "MEASURED SIGNED POWER"
        : "POWER UNAVAILABLE";
    el("replaySignalA").value = "vehicle_speed_ms";
    el("replaySignalB").value = data.derived.electrical_power_w
      ? "electrical_power_w"
      : data.measured.battery_power_w
        ? "battery_power_w"
        : data.measured.battery_soc
          ? "battery_soc"
          : "vehicle_speed_ms";
    renderEvents();
    renderSummary();
    document.dispatchEvent(
      new CustomEvent("veus:recording", {
        detail: { source_sha256: data.metadata.raw_sha256 },
      }),
    );
    update(performance.now(), true);
    start();
  }
  function selectEvent(index) {
    const event = result?.events[index];
    if (!event) return;
    selectedInterval = [event.start_s, event.end_s];
    seek(event.start_s);
    document.dispatchEvent(
      new CustomEvent("veus:replay-event", { detail: { event_index: index } }),
    );
  }
  function renderEvents() {
    const host = el("replayEvents");
    host.replaceChildren();
    el("replayEventCount").textContent = "(" + result.events.length + ")";
    if (!result.events.length) {
      host.textContent = "No supported events meet the current thresholds.";
      return;
    }
    for (const e of result.events.slice(0, 200)) {
      const b = document.createElement("button");
      b.className = "replay-event";
      b.textContent = `${e.start_s.toFixed(2)}–${e.end_s.toFixed(2)} s · ${e.type.replaceAll("_", " ")} · ${e.classification}`;
      b.title = e.rule + " / " + e.qualification;
      b.dataset.eventStart = e.start_s;
      b.onclick = () => {
        selectEvent(result.events.indexOf(e));
        el("replayStatus").textContent = e.rule + " · " + e.qualification;
      };
      host.append(b);
    }
    if (result.events.length > 200) {
      const note = document.createElement("p");
      note.textContent =
        "First 200 events shown; exports retain all " +
        result.events.length +
        ".";
      host.append(note);
    }
  }
  function renderSummary() {
    const host = el("replaySummary");
    host.replaceChildren();
    for (const [key, m] of Object.entries(result.summary)) {
      const row = document.createElement("div");
      row.className = "replay-summary-row";
      const label = document.createElement("span"),
        value = document.createElement("strong"),
        note = document.createElement("small");
      label.textContent = key.replaceAll("_", " ");
      value.textContent =
        m.value === null ? "Unavailable" : num(m.value, 3) + " " + m.unit;
      note.textContent =
        m.definition + (m.unavailable_reason ? " " + m.unavailable_reason : "");
      row.append(label, value, note);
      host.append(row);
    }
    el("replayMethods").textContent = JSON.stringify(result.methods, null, 2);
    el("replayComparison").textContent =
      result.comparison.reason + " " + result.quality.physical_validation;
  }
  async function postRecording(data) {
    const response = await fetch("/api/replay/analyse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        configuration: data.configuration,
        csv_base64: data.csv_base64,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.detail || "Recording rejected");
    return result;
  }
  async function loadDataset() {
    const token = ++loadToken;
    pause();
    el("replayStatus").textContent =
      "Loading and validating source measurements…";
    try {
      const response = await fetch(
        (el("replayDataset").value.endsWith("-full")
          ? "/api/investigation/recordings/"
          : "/api/replay/datasets/") + el("replayDataset").value,
      );
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Cannot load recording");
      if (token !== loadToken) return;
      const resolved = data.analysis || (await postRecording(data));
      if (token !== loadToken) return;
      install(resolved, {
        configuration: data.configuration,
        csv_base64: data.csv_base64,
      });
    } catch (e) {
      if (token === loadToken)
        el("replayStatus").textContent = "Recording rejected: " + e.message;
    }
  }
  el("loadReplay").onclick = loadDataset;
  async function analyseImport(thresholds = false) {
    const token = ++loadToken;
    try {
      if (!request) throw Error("Load a supplied recording or CSV first.");
      const configuration = JSON.parse(el("replayConfig").value);
      if (thresholds) {
        configuration.thresholds = {
          ...configuration.thresholds,
          acceleration_ms2: Number(el("replayAccelThreshold").value),
          deceleration_ms2: Number(el("replayDecelThreshold").value),
          power_magnitude_w: Number(el("replayPowerThreshold").value) * 1000,
          standstill_ms: Number(el("replayStopThreshold").value),
          minimum_duration_s: Number(el("replayDurationThreshold").value),
        };
      }
      const payload = { ...request, configuration };
      pause();
      el("replayStatus").textContent =
        "Analysing full-resolution measurements…";
      const response = await fetch("/api/replay/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Import failed");
      if (token !== loadToken) return;
      install(data, payload);
    } catch (e) {
      if (token === loadToken)
        el("replayStatus").textContent = "Analysis rejected: " + e.message;
    }
  }
  el("replayApplyThresholds").onclick = () => analyseImport(true);
  el("replayImport").onclick = () => analyseImport();
  el("replayConfigFile").onchange = async (e) => {
    try {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 500000) throw Error("Configuration limit is 500 KB.");
      el("replayConfig").value = JSON.stringify(
        JSON.parse(await file.text()),
        null,
        2,
      );
    } catch (e) {
      el("replayStatus").textContent = e.message;
    }
  };
  el("replayCsv").onchange = async (e) => {
    try {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 2_000_000) throw Error("CSV limit is 2 MB.");
      const bytes = await file.arrayBuffer(),
        sha = await crypto.subtle.digest("SHA-256", bytes),
        base64 = await new Promise((resolve, reject) => {
          const r = new FileReader();
          r.onload = () => resolve(r.result.split(",")[1]);
          r.onerror = reject;
          r.readAsDataURL(file);
        });
      request = { ...(request || {}), csv_base64: base64 };
      el("replayStatus").textContent =
        "CSV loaded. Set its explicit source SHA-256 in the config: " +
        [...new Uint8Array(sha)]
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");
    } catch (e) {
      el("replayStatus").textContent = e.message;
    }
  };
  el("replayExportSummary").onclick = () => {
    if (result) {
      const { time_s, measured, derived, valid_speed_intervals, ...summary } =
        result;
      download("veus-recorded-trip-summary.json", summary);
    }
  };
  el("replayExportFull").onclick = () => {
    if (result) download("veus-replay-analysis.json", result);
  };
  el("replayExportMetadata").onclick = () => {
    if (result)
      download("veus-replay-metadata.json", {
        configuration: result.configuration,
        configuration_sha256: result.configuration_sha256,
        metadata: result.metadata,
        analysis_sha256: result.analysis_sha256,
        methods: result.methods,
        classifications: result.classifications,
        units: result.units,
      });
  };
  el("replayExportEvents").onclick = () => {
    if (!result) return;
    const keys = [
        "type",
        "start_s",
        "end_s",
        "source_start_s",
        "source_end_s",
        "classification",
        "signals",
        "rule",
        "qualification",
      ],
      quote = (v) =>
        '"' +
        String(Array.isArray(v) ? v.join(";") : v).replaceAll('"', '""') +
        '"';
    download(
      "veus-replay-events.csv",
      keys.join(",") +
        "\n" +
        result.events
          .map((e) => keys.map((k) => quote(e[k])).join(","))
          .join("\n") +
        "\n",
      "text/csv",
    );
  };
  el("replayExportHtml").onclick = async () => {
    if (!result || !request) return;
    el("replayExportHtml").disabled = true;
    try {
      const response = await fetch("/api/replay/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...request,
          configuration: result.configuration,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Report failed");
      if (data.analysis_sha256 !== result.analysis_sha256)
        throw Error("Analysis changed; reanalyse before export");
      download("veus-recorded-ev-analysis.html", data.report_html, "text/html");
    } catch (e) {
      el("replayStatus").textContent = "Report export failed: " + e.message;
    } finally {
      el("replayExportHtml").disabled = false;
    }
  };
  const sharedPlot = new window.VEUSRecordingPlot();
  function drawGraph(id, key, state) {
    sharedPlot.draw(el(id), result, state, key, selectedInterval);
  }
  for (const [canvasId, selector, hoverId] of [
    ["replayGraphA", "replaySignalA", "replayHoverA"],
    ["replayGraphB", "replaySignalB", "replayHoverB"],
  ]) {
    el(selector).onchange = () => {
      plotCache = {};
      update(performance.now(), true);
    };
    const timeAt = (e) => {
      const canvas = el(canvasId),
        box = canvas.getBoundingClientRect(),
        left = Number(canvas.dataset.plotLeft) || 62,
        right = Number(canvas.dataset.plotRight) || box.width - 12;
      return Math.max(
        0,
        Math.min(
          clock.duration,
          ((e.clientX - box.left - left) / (right - left)) * clock.duration,
        ),
      );
    };
    el(canvasId).onclick = (e) => {
      if (clock) seek(timeAt(e));
    };
    el(canvasId).onmousemove = (e) => {
      if (!result || !clock) return;
      const time = timeAt(e),
        ts = result.time_s;
      let lo = 0,
        hi = ts.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (ts[mid] < time) lo = mid + 1;
        else hi = mid;
      }
      let i = Math.min(lo, ts.length - 1);
      if (i > 0 && Math.abs(ts[i - 1] - time) < Math.abs(ts[i] - time)) i--;
      const key = el(selector).value;
      el(hoverId).textContent =
        `Actual sample ${ts[i].toFixed(3)} s (source ${(ts[i] + result.metadata.time_origin_s).toFixed(3)} s): ${display(key, getSignal(key)[i])} · ${result.classifications[key]}`;
    };
  }
  function update(now, force = false) {
    if (!clock || !result) return;
    const state = clock.tick(now),
      active =
        window.activeWorkspace === "analyse" &&
        ["replay", "investigate"].includes(tab) &&
        !document.hidden;
    if (active) {
      scene.render(state.position_m, null, "sedan");
      el("replayScene").dataset.positionM = state.position_m.toFixed(6);
      el("replayScene").dataset.recordedTime = state.time_s.toFixed(6);
    }
    if (!force && now - lastUI < 80) return;
    lastUI = now;
    document.dispatchEvent(
      new CustomEvent("veus:replay-clock", { detail: state }),
    );
    text(
      el("replayState"),
      state.gap
        ? "DATA GAP"
        : state.ended
          ? "END OF RECORDING"
          : state.playing
            ? "REPLAYING"
            : "PAUSED",
    );
    text(
      el("replayPlay"),
      state.playing ? "Pause" : state.ended ? "Replay" : "Play",
    );
    text(
      el("replayTime"),
      `${state.time_s.toFixed(2)} / ${clock.duration.toFixed(2)} s`,
    );
    el("replayTimeline").value = String(state.time_s);
    text(
      el("replaySpeed"),
      num(
        state.values.vehicle_speed_ms === null
          ? null
          : state.values.vehicle_speed_ms * 3.6,
        1,
      ),
    );
    text(
      el("replaySoc"),
      num(
        state.values.battery_soc == null
          ? null
          : state.values.battery_soc * 100,
        2,
      ),
    );
    text(
      el("replayPower"),
      num(
        (state.values.electrical_power_w ?? state.values.battery_power_w) ==
          null
          ? null
          : (state.values.electrical_power_w ?? state.values.battery_power_w) /
              1000,
        2,
      ),
    );
    text(el("replayDistance"), num(state.position_m / 1000, 3));
    text(
      el("replayDistanceKind"),
      result.quality.full_speed_coverage
        ? "km · speed-integrated, not GPS"
        : "km · known segments only; total unknown",
    );
    text(
      el("replaySampleNote"),
      state.gap
        ? "Timestamp gap: no readout interpolation or inferred travel. Scene holds known-segment displacement."
        : `Timeline ${state.time_s.toFixed(2)} s · actual sample ${state.recorded_time_s.toFixed(3)} s (source ${state.source_time_s.toFixed(3)} s). Speed/SOC/power readouts retain sample values; scene/distance integrate recorded speed to the timeline.${state.missing_speed ? " Missing speed: unknown travel excluded." : ""}`,
    );
    text(
      el("replaySceneNote"),
      state.gap || state.missing_speed
        ? "Missing interval · unknown travel excluded"
        : "Derived displacement · 5 px/m · not GPS",
    );
    const secondary = [
      "battery_voltage_v",
      "battery_current_a",
      "ambient_temperature_c",
      "longitudinal_acceleration_ms2",
      "acceleration_ms2",
    ]
      .map(
        (k) =>
          `${names[k] || k}: ${display(k, state.values[k])} (${result.classifications[k] || "unavailable"})`,
      )
      .join(" · ");
    text(el("replaySecondary"), secondary);
    if (active && subview === "charts" && (force || now - lastPlot >= 80)) {
      lastPlot = now;
      drawGraph("replayGraphA", el("replaySignalA").value, state);
      drawGraph("replayGraphB", el("replaySignalB").value, state);
    }
  }
  document.addEventListener("veus:workspace", (e) => {
    if (e.detail !== "analyse") pause();
    else {
      if (!result && el("replayDataset").options.length) loadDataset();
      requestAnimationFrame(() => {
        update(performance.now(), true);
        start();
      });
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pause();
    else {
      update(performance.now(), true);
      start();
    }
  });
  window.addEventListener("resize", () => {
    plotCache = {};
    update(performance.now(), true);
  });
  // Exposed for integration checks; never references or changes SimulationSession.
  window.VEUSReplay = {
    get state() {
      return clock?.state() || null;
    },
    get analysis() {
      return result;
    },
    seek,
    selectTab: setTab,
    get input() {
      return request
        ? {
            ...request,
            readiness_configuration: readinessContext,
            mappings_confirmed: true,
          }
        : null;
    },
    selectEvent,
    async loadRecording(payload, evidence = null) {
      const token = ++loadToken;
      pause();
      // A pending import must not expose a previous recording as the new result.
      result = null;
      const response = await fetch("/api/replay/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok)
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      if (token !== loadToken) return;
      install(data, payload, evidence);
      setTab("replay");
    },
    pause,
  };
  fetch("/api/investigation/catalogue")
    .then((r) => r.json())
    .then((items) => {
      for (const item of items) {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.label;
        el("replayDataset").append(option);
      }
      if (window.activeWorkspace === "analyse" && !result) loadDataset();
    })
    .catch((e) => {
      el("replayStatus").textContent = "Dataset list unavailable: " + e.message;
    });
  const generic = new Image();
  generic.src = "/static/vehicles/sedan.svg";
  generic.onload = () => {
    replayImages = { sedan: generic };
    update(performance.now(), true);
  };
})();

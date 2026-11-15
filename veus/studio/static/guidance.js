"use strict";
(() => {
  const el = (id) => document.getElementById(id),
    key = "veus.welcome.seen.v1";
  let storage = true;
  function remembered() {
    try {
      return localStorage.getItem(key) === "yes";
    } catch {
      storage = false;
      return false;
    }
  }
  function remember(value) {
    try {
      if (value) localStorage.setItem(key, "yes");
      else localStorage.removeItem(key);
    } catch {
      storage = false;
    }
    el("preferenceStatus").textContent = storage
      ? "Preference saved on this browser only."
      : "Browser storage is unavailable. Navigation works for this visit; Welcome may return after reload.";
  }
  const welcome = document.createElement("section");
  welcome.id = "welcomeWorkspace";
  welcome.className = "workspace";
  welcome.hidden = true;
  welcome.innerHTML = `<div class="welcome-heading"><div class="eyebrow">YOUR ELECTRIC VEHICLE WORKBENCH</div><h1>VEUS — Explore. Analyse. Validate.</h1><p>An interactive engineering platform for electric vehicle simulation, real-world telemetry analysis and model-based testing.</p></div>
 <div class="welcome-cards"><article class="welcome-card"><span class="workflow-number">01 / DRIVE</span><svg viewBox="0 0 260 110" aria-hidden="true"><use href=""/></svg><img src="/static/vehicles/hatch.svg" alt="Illustrative electric hatchback"><h2>Drive a Virtual EV</h2><p>Experience vehicle acceleration, braking, battery behaviour and driver-assistance systems through an interactive physics-based simulation.</p><strong>No data required.</strong><small>VEUS provides illustrative vehicle presets.</small><button id="welcomeDrive" class="primary">Start Driving</button><button id="welcomeParameters" class="text-button">Explore Vehicle Parameters →</button></article>
 <article class="welcome-card"><span class="workflow-number">02 / ANALYSE</span><div class="workflow-illustration" aria-hidden="true"><svg viewBox="0 0 260 110"><path d="M15 85H245M15 20V85" fill="none" stroke="#617669"/><path d="M15 79 40 72 66 43 90 51 119 27 148 35 176 62 200 50 245 16" fill="none" stroke="#b4e5bb" stroke-width="3"/><path d="M157 15V88" stroke="#d7b88f" stroke-dasharray="3 4"/></svg></div><h2>Explore Real Vehicle Data</h2><p>Replay recorded vehicle journeys, investigate driving events and explore synchronized vehicle and battery measurements.</p><strong>Minimum: timestamp and vehicle speed.</strong><small>Optional battery voltage, current, SOC, motor torque/speed and other supported signals unlock specific analyses.</small><button id="welcomeImport" class="primary">Import Vehicle Data</button><button id="welcomeExample" class="text-button">Try Example Recording →</button></article>
 <article class="welcome-card"><span class="workflow-number">03 / VALIDATE</span><div class="workflow-illustration" aria-hidden="true"><svg viewBox="0 0 260 110"><rect x="38" y="15" width="184" height="80" rx="8" fill="none" stroke="#617669"/><path d="m58 39 6 6 12-15m-18 34 6 6 12-15m22-16h98m-98 25h75" fill="none" stroke="#c5b8e0" stroke-width="3"/></svg></div><h2>Test Engineering Models</h2><p>Run reproducible physics and ADAS experiments, investigate sensor faults and compare model predictions against measured data when sufficient evidence is available.</p><strong>No external data required for built-in test scenarios.</strong><small>Custom tests need parameters, initial conditions and scenario settings. Physical validation also needs suitable measurements and operating evidence.</small><button id="welcomeValidate" class="primary">Open Test Laboratory</button><button id="welcomeRequirements" class="text-button">View Input Requirements →</button></article></div>
 <div class="welcome-footer"><label><input id="rememberWelcome" type="checkbox" checked> Remember that I have seen Welcome on this browser</label><button id="skipWelcome">Go directly to Drive</button><span id="welcomeStorageNote"></span></div><p class="welcome-scope">Simulation, recorded-data replay and physical validation serve different purposes. Readiness does not prove measurement validity; Phase 8 physical validation remains INCONCLUSIVE.</p>`;
  welcome.querySelector(".welcome-card>svg").remove();
  document.querySelector("main").append(welcome);
  const home = document.createElement("button");
  home.dataset.workspace = "welcome";
  home.innerHTML =
    '<span class="welcome-full">Welcome</span><span class="welcome-short">Home</span>';
  home.setAttribute("aria-label", "Welcome — choose your workflow");
  document.querySelector("nav").prepend(home);
  home.onclick = () => window.setWorkspace("welcome");
  const prefs = document.createElement("section");
  prefs.className = "panel settings-panel";
  prefs.innerHTML =
    '<h2>Welcome preference</h2><label><input id="showWelcome" type="checkbox"> Show Welcome on next startup</label><p id="preferenceStatus" role="status">Stored locally in this browser; no account or cloud storage.</p><button id="returnWelcome">Open Welcome</button>';
  el("settingsWorkspace").append(prefs);
  const seen = remembered();
  el("showWelcome").checked = !seen;
  el("showWelcome").onchange = () => remember(!el("showWelcome").checked);
  el("returnWelcome").onclick = () => window.setWorkspace("welcome");
  function go(workspace) {
    if (el("rememberWelcome").checked) {
      remember(true);
      el("showWelcome").checked = false;
    }
    window.setWorkspace(workspace);
    window.scrollTo(0, 0);
  }
  el("welcomeDrive").onclick = () => {
    go("drive");
    el("chooseVehicle").click();
  };
  el("skipWelcome").onclick = () => go("drive");
  el("welcomeParameters").onclick = () => {
    go("validate");
    el("configuration").scrollIntoView({ block: "start" });
  };
  el("welcomeValidate").onclick = () => go("validate");
  for (const [name, title, description, more] of [
    [
      "drive",
      "About Drive",
      "The vehicle is simulated. Python physics calculates forward acceleration and braking. Presets are illustrative; no upload is needed.",
      "<h3>What vehicle parameters can I customise?</h3><p>Mass, motor power/torque limits, friction, grade, initial speed and duration; battery capacity, initial SOC, voltage, resistance, current limits and drive/regen efficiencies; existing controller speeds, gaps and delays. Change them in Validate → Vehicle & road, then Apply & reset.</p>",
    ],
    [
      "analyse",
      "What data should I upload?",
      "The replay vehicle follows recorded measurements, not a predictive physics simulation. Replay needs time and speed; additional signals support additional analyses.",
      "<p>Upload a UTF-8 CSV. Confirm columns and units in Data Readiness before analysis. Voltage/current support signed electrical inspection; energy needs polarity and quality evidence. JSON is for configuration, not arbitrary telemetry. Try the genuine VED example or labelled synthetic templates below.</p>",
    ],
    [
      "validate",
      "Verification or physical validation?",
      "Verification checks equations and defined software requirements. Physical validation compares predictions with suitable real-world measurements.",
      "<p>Built-in interactive modes and CLI scenarios need no external data and do not establish real-world validation. Custom scenarios need parameters, initial conditions and a supported scenario JSON. Physical comparison needs independent measured inputs/outputs, compatible units/times and documented conditions. Phase 8 remains INCONCLUSIVE. Model comparison/calibration is in Analyse → Model experiments & calibration.</p>",
    ],
  ]) {
    const details = document.createElement("details");
    details.id = name + "Guide";
    details.className = "workspace-guide";
    details.innerHTML =
      "<summary>" +
      title +
      "</summary><div><p>" +
      description +
      "</p>" +
      more +
      "</div>";
    el(name + "Workspace")
      .querySelector(".workspace-heading")
      .append(details);
  }
  el("welcomeRequirements").onclick = () => {
    go("validate");
    el("validateGuide").open = true;
  };
  const readTab = document.createElement("button");
  readTab.dataset.analyse = "readiness";
  readTab.textContent = "Data Readiness";
  document.querySelector(".analyse-tabs").prepend(readTab);
  const panel = document.createElement("section");
  panel.id = "readinessPanel";
  panel.hidden = true;
  panel.innerHTML = `<div class="readiness-heading"><div><div class="eyebrow">A CLEAR START / CONFIRMED INPUTS</div><h2>VEUS Data Readiness Check</h2><p>See what your recording supports, what is missing and what evidence still matters.</p></div><span class="badge">READINESS ≠ VALIDATION</span></div>
 <div class="readiness-load"><label>Bundled recording<select id="readinessDataset"><option value="ved-10-1561">Genuine VED · Vehicle 10 · Trip 1561</option><option value="ved-10-1558">Genuine VED · Vehicle 10 · Trip 1558</option><option value="basic-replay">Synthetic A · basic replay</option><option value="electrical-analysis">Synthetic B · EV electrical analysis</option></select></label><button id="readinessLoad">Inspect recording</button><label class="upload-control">Or choose your CSV<input id="readinessCsv" type="file" accept=".csv"></label></div>
 <p id="readinessStatus" role="status" aria-live="polite">Select a bundled recording or CSV. Suggestions are not confirmed mappings.</p>
 <details id="readinessMapping" hidden open><summary>1 · Confirm your input mappings and evidence</summary><div class="readiness-source"><label>Dataset name<input id="readinessName" type="text"></label><label>Data origin<select id="readinessOrigin"><option value="">Choose origin explicitly…</option><option value="measured">Measured recording</option><option value="synthetic">Synthetic fixture</option></select></label><label>Current polarity<select id="readinessPolarity"><option value="unknown">Unknown · inspect signed current only</option><option value="discharge_positive">Discharge-positive · evidence required</option><option value="charge_positive">Charge-positive · evidence required</option></select></label></div>
 <p class="muted" id="readinessFileInfo"></p><p id="readinessUnsupported" class="readiness-warning"></p><h3>Review columns and units</h3><p class="muted">Aliases propose columns only. Choose units; retain source signs unless you explicitly know a conversion. Polarity, calibration and accuracy are not inferred.</p><div id="readinessMainMappings" class="mapping-grid"></div><details><summary>Other supported signals · manual mapping</summary><div id="readinessOtherMappings" class="mapping-grid"></div></details>
 <details class="readiness-evidence"><summary>Advanced evidence & model-validation inputs</summary><label>Maximum interpolated sample interval · s<input id="readinessGap" type="number" min="0.001" max="60" step="0.1" value="2"></label><label>Current sign evidence<textarea id="readinessSignEvidence" rows="2" placeholder="Publisher specification or documented sign convention; leave polarity unknown if unresolved."></textarea></label><div class="assertions"><label><input id="readinessSync" type="checkbox"> Synchronization evidence is documented</label><label><input id="readinessQuality" type="checkbox"> Measurement accuracy/calibration/quality evidence is documented</label><label><input id="readinessConditions" type="checkbox"> Vehicle and operating conditions are documented</label><label><input id="readinessTorque" type="checkbox"> Drive torque sign/convention is established</label></div><label>Evidence notes<textarea id="readinessEvidenceNotes" rows="2"></textarea></label><label>Optional matching Phase 8 Experiment JSON<textarea id="readinessExperiment" rows="4" placeholder="An explicit supported Experiment, not a universal validation schema."></textarea></label><label>Advanced source metadata JSON<textarea id="readinessSource" rows="5"></textarea></label><p class="muted">These are uploader assertions, not automatic authentication. AVAILABLE never means the model passed validation.</p></details>
 <label class="mapping-confirm"><input id="readinessConfirm" type="checkbox"> I reviewed the selected columns, units, source origin and retained/inverted source signs.</label><div class="buttons"><button id="readinessAssess" class="primary">Check data readiness</button><button id="readinessProceed" disabled>Proceed to recorded replay</button><button id="readinessExport" disabled>Export readiness JSON</button></div></details>
 <div id="readinessResults" hidden><div class="readiness-result-head"><h3>What can I do with this recording?</h3><span id="readinessOriginLabel"></span></div><p class="muted">AVAILABLE is readiness for the named software calculation, not proof of physical validity. Checked evidence is supplied by the uploader.</p><div id="readinessCapabilities" class="capability-cards"></div><details id="readinessQualityDetails" class="panel"><summary>Dataset quality, units & provenance</summary><pre id="readinessQualitySummary"></pre></details><details><summary>What additional data would help?</summary><ul id="readinessAdditional"></ul></details></div>
 <details id="readinessTemplates" class="panel"><summary>Example CSVs and supported configuration formats</summary><div class="template-grid"><article><h3>A · Basic replay</h3><p>Time + speed. Small synthetic arithmetic fixture, not measurements.</p><a href="/api/readiness/templates/basic-replay/csv">Download CSV</a> · <a href="/api/readiness/templates/basic-replay/config">Replay config JSON</a></article><article><h3>B · EV electrical analysis</h3><p>Synthetic time, speed, voltage, signed current and SOC. Polarity starts unknown.</p><a href="/api/readiness/templates/electrical-analysis/csv">Download CSV</a> · <a href="/api/readiness/templates/electrical-analysis/config">Replay config JSON</a></article><article><h3>C · Existing model experiment</h3><p>Phase 8 synthetic battery-current reference, explicitly not real-world validation. Open Model experiments & calibration and select synthetic-battery-train.</p><a href="/api/readiness/templates/engineering-example/csv">Reference CSV</a> · <a href="/api/readiness/templates/engineering-example/config">Experiment JSON</a> · <a href="/api/readiness/templates/engineering-example/settings">Fit settings</a><p><a href="/api/readiness/templates/engineering-example/holdout-csv">Independent synthetic holdout CSV</a> · <a href="/api/readiness/templates/engineering-example/holdout-config">Holdout config</a></p></article></div></details>`;
  document.querySelector(".analyse-tabs").after(panel);
  const resultActions = document.createElement("div");
  resultActions.className = "buttons";
  resultActions.append(el("readinessProceed"), el("readinessExport"));
  el("readinessResults").prepend(resultActions);
  function selectReadiness() {
    window.VEUSReplay.selectTab("readiness");
  }
  readTab.onclick = selectReadiness;
  document.addEventListener("veus:analyse-tab", (e) => {
    panel.hidden = e.detail !== "readiness";
  });
  el("welcomeImport").onclick = () => {
    go("analyse");
    selectReadiness();
    el("readinessCsv").focus();
  };
  el("welcomeExample").onclick = () => {
    go("analyse");
    selectReadiness();
    el("readinessDataset").value = "ved-10-1561";
    loadBundled();
  };
  let rawBase64 = null,
    inspection = null,
    assessment = null,
    token = 0,
    baseOptions = null;
  const status = (text) => {
    el("readinessStatus").textContent = text;
  };
  function invalidate() {
    assessment = null;
    el("readinessResults").hidden = true;
    el("readinessProceed").disabled = true;
    el("readinessExport").disabled = true;
  }
  async function post(url, payload) {
    const response = await fetch(url, {
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
    return data;
  }
  function buildMappings(info, config) {
    for (const id of ["readinessMainMappings", "readinessOtherMappings"])
      el(id).replaceChildren();
    for (const suggestion of info.suggestions) {
      const row = document.createElement("div");
      row.className = "mapping-row";
      row.dataset.signal = suggestion.signal;
      const label = document.createElement("label");
      label.textContent =
        suggestion.label || suggestion.signal.replaceAll("_", " ");
      const col = document.createElement("select");
      col.dataset.mapping = "column";
      col.setAttribute("aria-label", suggestion.signal + " column");
      const none = document.createElement("option");
      none.value = "";
      none.textContent = "Not mapped";
      col.append(none);
      for (const header of info.columns) {
        const option = document.createElement("option");
        option.value = header;
        option.textContent = header;
        col.append(option);
      }
      const unit = document.createElement("select");
      unit.dataset.mapping = "unit";
      unit.setAttribute("aria-label", suggestion.signal + " unit");
      const choose = document.createElement("option");
      choose.value = "";
      choose.textContent = "Choose unit…";
      unit.append(choose);
      for (const value of suggestion.units) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        unit.append(option);
      }
      const sign = document.createElement("select");
      sign.dataset.mapping = "sign";
      sign.setAttribute("aria-label", suggestion.signal + " source sign");
      for (const [value, text] of [
        [1, "Retain source sign"],
        [-1, "Invert source sign"],
      ]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        sign.append(option);
      }
      const documented = config?.preprocessing.columns[suggestion.signal];
      col.value =
        documented?.column ||
        (suggestion.candidates.length === 1 ? suggestion.candidates[0] : "");
      unit.value = documented?.unit || "";
      sign.value = String(documented?.sign || 1);
      label.append(col);
      const unitLabel = document.createElement("label");
      unitLabel.textContent = "Unit";
      unitLabel.append(unit);
      const signLabel = document.createElement("label");
      signLabel.textContent = "Mapping sign (not polarity)";
      signLabel.append(sign);
      row.append(label, unitLabel, signLabel);
      const primary =
        !!documented ||
        suggestion.candidates.length ||
        ["time_s", "vehicle_speed_ms"].includes(suggestion.signal);
      el(primary ? "readinessMainMappings" : "readinessOtherMappings").append(
        row,
      );
      for (const node of [col, unit, sign])
        node.onchange = () => {
          el("readinessConfirm").checked = false;
          token++;
          invalidate();
        };
    }
  }
  async function inspectFile(csv, config = null, filename = "Uploaded CSV") {
    const my = ++token;
    invalidate();
    rawBase64 = null;
    inspection = null;
    el("readinessMapping").hidden = true;
    status(
      "Inspecting CSV structure; no units or quality assumptions are inferred…",
    );
    try {
      const info = await post("/api/readiness/inspect", { csv_base64: csv });
      if (my !== token) return;
      rawBase64 = csv;
      inspection = info;
      baseOptions = config;
      buildMappings(info, config);
      const source = config?.source || {
        dataset: filename,
        source_url:
          "User-provided CSV; provenance not independently established",
        licence: "Unspecified by uploader",
        kind: "",
        role: "exploration",
        run_id: filename,
        provenance_evidence: "User-provided metadata; not authenticated",
        inputs_verified: false,
      };
      el("readinessName").value = source.dataset;
      el("readinessOrigin").value = source.kind;
      el("readinessPolarity").value = config?.current_sign || "unknown";
      el("readinessSource").value = JSON.stringify(source, null, 2);
      el("readinessSignEvidence").value = config?.sign_evidence || "";
      el("readinessExperiment").value = "";
      el("readinessEvidenceNotes").value = "";
      for (const id of [
        "readinessSync",
        "readinessQuality",
        "readinessConditions",
        "readinessTorque",
        "readinessConfirm",
      ])
        el(id).checked = false;
      el("readinessFileInfo").textContent =
        `${info.record_count} records · ${info.columns.length} source columns · SHA-256 ${info.raw_sha256}`;
      el("readinessUnsupported").textContent = info.unsupported
        .map((v) => v.column + ": " + v.explanation)
        .join(" ");
      el("readinessGap").value = config?.preprocessing.max_gap_s || 2;
      el("readinessMapping").hidden = false;
      el("readinessMapping").open = true;
      status(
        config
          ? "Documented bundled mappings are proposed below. Review and confirm before checking readiness."
          : "Columns are proposed by alias. Choose units and data origin, then confirm. No measurements have been repaired or classified as physically valid.",
      );
    } catch (e) {
      if (my === token) status("CSV inspection rejected: " + e.message);
    }
  }
  async function loadBundled() {
    const my = ++token;
    invalidate();
    try {
      const name = el("readinessDataset").value;
      const response = await fetch(
        name.startsWith("ved-")
          ? (name.endsWith("-full")
              ? "/api/investigation/recordings/"
              : "/api/replay/datasets/") + name
          : "/api/readiness/templates/" + name + "/config",
      );
      if (!response.ok) throw Error("Cannot load example");
      const data = await response.json();
      if (my !== token) return;
      if (name.startsWith("ved-"))
        await inspectFile(data.csv_base64, data.configuration);
      else {
        const file = await fetch("/api/readiness/templates/" + name + "/csv");
        if (!file.ok) throw Error("Cannot load example CSV");
        const bytes = new Uint8Array(await file.arrayBuffer());
        let text = "";
        for (const b of bytes) text += String.fromCharCode(b);
        if (my !== token) return;
        await inspectFile(btoa(text), data);
      }
    } catch (e) {
      status("Example rejected: " + e.message);
    }
  }
  el("readinessLoad").onclick = loadBundled;
  el("readinessCsv").onchange = async (e) => {
    const my = ++token;
    invalidate();
    rawBase64 = null;
    inspection = null;
    baseOptions = null;
    el("readinessMapping").hidden = true;
    try {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 2_000_000)
        throw Error("Choose a CSV no larger than 2 MB.");
      const csv = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(r.result.split(",")[1]);
        r.onerror = () => reject(Error("Cannot read the selected CSV."));
        r.readAsDataURL(file);
      });
      if (my !== token) return;
      await inspectFile(csv, null, file.name);
    } catch (error) {
      if (my === token) status(error.message);
    }
  };
  function configFromForm() {
    if (!inspection || !rawBase64) throw Error("Inspect a recording first.");
    if (!el("readinessConfirm").checked)
      throw Error("Review the mappings and check the confirmation box.");
    if (!el("readinessOrigin").value)
      throw Error("Choose measured or synthetic data origin explicitly.");
    const columns = {};
    for (const row of panel.querySelectorAll("[data-signal]")) {
      const col = row.querySelector("[data-mapping=column]").value;
      if (!col) continue;
      const unit = row.querySelector("[data-mapping=unit]").value;
      if (!unit) throw Error("Choose a unit for " + row.dataset.signal + ".");
      columns[row.dataset.signal] = {
        column: col,
        unit,
        sign: Number(row.querySelector("[data-mapping=sign]").value),
      };
    }
    const source = {
      ...JSON.parse(el("readinessSource").value),
      dataset: el("readinessName").value,
      kind: el("readinessOrigin").value,
      expected_sha256: inspection.raw_sha256,
    };
    const experiment = el("readinessExperiment").value.trim();
    return {
      source,
      preprocessing: {
        columns,
        zero_time: true,
        max_gap_s: Number(el("readinessGap").value),
      },
      current_sign: el("readinessPolarity").value,
      sign_evidence: el("readinessSignEvidence").value || null,
      assertions: {
        synchronization_confirmed: el("readinessSync").checked,
        measurement_quality_documented: el("readinessQuality").checked,
        operating_conditions_documented: el("readinessConditions").checked,
        torque_sign_confirmed: el("readinessTorque").checked,
        evidence_notes: el("readinessEvidenceNotes").value,
      },
      experiment: experiment ? JSON.parse(experiment) : null,
      provenance: baseOptions?.provenance || {},
      limitations: baseOptions?.limitations || [
        "Readiness is not physical model validation. Source metadata and checked evidence are supplied by the uploader.",
      ],
    };
  }
  el("readinessAssess").onclick = async () => {
    const my = ++token;
    el("readinessAssess").disabled = true;
    try {
      const configuration = configFromForm();
      status("Validating confirmed units, timestamps and measurement quality…");
      const result = await post("/api/readiness/assess", {
        csv_base64: rawBase64,
        configuration,
        mappings_confirmed: true,
      });
      if (my !== token) return;
      assessment = result;
      renderResult(result);
      status(
        "Readiness assessed from confirmed mappings and available samples. This is not a physical-validation verdict.",
      );
    } catch (e) {
      invalidate();
      status("Readiness check rejected: " + e.message);
    } finally {
      el("readinessAssess").disabled = false;
    }
  };
  function renderResult(result) {
    const host = el("readinessCapabilities");
    host.replaceChildren();
    el("readinessOriginLabel").textContent =
      result.configuration.source.kind.toUpperCase() +
      " · " +
      result.configuration.source.dataset;
    const additions = new Set();
    for (const cap of result.capabilities) {
      const article = document.createElement("article");
      article.className = "capability-card";
      article.dataset.capability = cap.id;
      article.dataset.status = cap.status;
      const header = document.createElement("div");
      header.className = "capability-head";
      const title = document.createElement("h3");
      title.textContent = cap.name;
      const badge = document.createElement("span");
      badge.className = "readiness-badge " + cap.status;
      badge.textContent = cap.status;
      header.append(title, badge);
      const text = document.createElement("p");
      text.textContent =
        cap.explanation.split(". ")[0] +
        (cap.explanation.includes(". ") ? "." : "");
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Requirements & scope";
      const desc = document.createElement("p");
      desc.textContent = cap.description + " " + cap.explanation;
      const requirements = document.createElement("pre");
      requirements.textContent = JSON.stringify(
        {
          required: cap.requirements.required_signals,
          optional: cap.requirements.optional_signals,
          quality: cap.requirements.quality_conditions,
          assumptions: cap.requirements.assumptions,
        },
        null,
        2,
      );
      details.append(summary, desc, requirements);
      article.append(header, text, details);
      host.append(article);
      if (cap.requirements.implemented)
        for (const item of cap.additional_data) additions.add(item);
    }
    el("readinessAdditional").replaceChildren();
    for (const item of additions) {
      const li = document.createElement("li");
      li.textContent = item;
      el("readinessAdditional").append(li);
    }
    if (!additions.size) {
      const li = document.createElement("li");
      li.textContent =
        "No additional input is requested for the supported calculations. This does not authenticate accuracy or establish physical validity.";
      el("readinessAdditional").append(li);
    }
    el("readinessQualitySummary").textContent = JSON.stringify(
      {
        records: result.metadata.row_count,
        duration_s: result.recording_duration_s,
        metadata: result.metadata,
        signal_quality: result.signal_quality,
        duplicates: result.duplicate_timestamps,
        timestamp_status: result.timestamp_status,
        evidence: result.assumptions,
        current_sign: result.current_sign,
        limitations: result.configuration.limitations,
        scope: result.scope,
      },
      null,
      2,
    );
    el("readinessMapping").open = false;
    el("readinessResults").hidden = false;
    el("readinessProceed").disabled = !result.replay_configuration;
    el("readinessExport").disabled = false;
  }
  el("readinessProceed").onclick = async () => {
    if (!assessment?.replay_configuration) return;
    el("readinessProceed").disabled = true;
    try {
      await window.VEUSReplay.loadRecording(
        {
          csv_base64: rawBase64,
          configuration: assessment.replay_configuration,
        },
        assessment.configuration,
      );
      window.scrollTo(0, 0);
    } catch (e) {
      status("Replay unavailable: " + e.message);
    } finally {
      el("readinessProceed").disabled = !assessment?.replay_configuration;
    }
  };
  el("readinessExport").onclick = () => {
    if (!assessment) return;
    const url = URL.createObjectURL(
        new Blob([JSON.stringify(assessment, null, 2) + "\n"], {
          type: "application/json",
        }),
      ),
      a = document.createElement("a");
    a.href = url;
    a.download = "veus-data-readiness.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  for (const node of panel.querySelectorAll(
    "input:not([type=file]),textarea,select",
  )) {
    if (node.id === "readinessDataset" || node.closest("[data-signal]"))
      continue;
    node.addEventListener("input", () => {
      token++;
      invalidate();
      if (node.id !== "readinessConfirm")
        el("readinessConfirm").checked = false;
    });
  }
  document.addEventListener("veus:workspace", (e) => {
    if (
      window.activeWorkspace === "welcome" &&
      e.detail !== "welcome" &&
      el("rememberWelcome").checked
    ) {
      remember(true);
      el("showWelcome").checked = false;
    }
    if (e.detail === "welcome" && el("vehicleDialog").open)
      el("vehicleDialog").close();
  });
  const direct = new URLSearchParams(location.search).get("workspace");
  if (["drive", "analyse", "validate", "settings"].includes(direct))
    window.setWorkspace(direct);
  else if (!seen) {
    window.setWorkspace("welcome");
    if (el("vehicleDialog").open) el("vehicleDialog").close();
  }
  if (!storage)
    el("welcomeStorageNote").textContent =
      "Storage unavailable; Welcome is dismissible for this visit.";
  fetch("/api/investigation/catalogue")
    .then((r) => r.json())
    .then((items) => {
      for (const item of items.filter((i) => !i.legacy)) {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.label;
        el("readinessDataset").append(option);
      }
    })
    .catch(() => {});
  window.VEUSGuidance = {
    open: () => window.setWorkspace("welcome"),
    readiness: () => {
      window.setWorkspace("analyse");
      selectReadiness();
    },
    get assessment() {
      return assessment;
    },
  };
})();

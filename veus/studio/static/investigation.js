"use strict";
(() => {
  const el = (id) => document.getElementById(id),
    tabs = document.querySelector(".analyse-tabs");
  const panel = document.createElement("section");
  panel.id = "investigatePanel";
  panel.hidden = true;
  panel.innerHTML = `<div class="investigation-heading"><div><div class="eyebrow">OBSERVED / DERIVED / INFERRED</div><h2>Investigate a recorded drive.</h2><p>Inspect supporting samples and engineering interpretations. No causal or efficiency ranking.</p></div><span class="badge">READINESS GATED</span></div>
 <div class="investigation-load"><label>Recording catalogue<select id="investigationDataset"></select></label><button id="investigationLoad">Load into Replay</button><button id="investigationCurrent">Review current Replay recording</button></div>
 <details class="panel"><summary>Recording library · source, coverage and limitations</summary><div id="investigationCatalogue"></div></details>
 <div id="investigationShared"><details id="investigationScenePreview"><summary>Replay illustration · same recorded-time cursor</summary><div id="investigationSceneSlot"></div></details></div>
 <div class="investigation-confirm"><label><input id="investigationConfirm" type="checkbox"> I reviewed the current Replay columns/units and source. Bundled comparison mappings are documented in the catalogue.</label><button id="investigationRun" class="primary">Check readiness & investigate</button></div>
 <p id="investigationStatus" role="status" aria-live="polite">Load a recording, or use your confirmed Replay import. Existing 2 MB / 5000-row limits apply to each recording.</p>
 <div id="investigationResults" hidden><div id="investigationOverview" class="investigation-overview"></div><p id="investigationEnergy" class="investigation-warning"></p>
 <div class="investigation-main"><section class="panel"><h3>Engineering events</h3><small id="investigationEventCount"></small><div id="investigationEvents"></div></section><section class="panel"><h3>Engineering insights</h3><div id="investigationInsight"></div></section></div>
 <div id="investigationGraphs" class="investigation-graphs"></div><details id="investigationMoreSignals" class="panel"><summary>Additional synchronized signals</summary><div id="investigationExtraGraphs" class="investigation-graphs"></div></details>
 <details class="panel"><summary>All metrics, readiness and quality</summary><div id="investigationMetrics"></div><pre id="investigationQuality"></pre></details></div>`;
  const compare = document.createElement("section");
  compare.id = "comparePanel";
  compare.hidden = true;
  compare.innerHTML = `<div class="investigation-heading"><div><div class="eyebrow">TWO RECORDINGS / DESCRIPTIVE CONTRAST</div><h2>Compare without assuming a cause.</h2><p>Different journeys do not share a real-world time origin or controlled conditions.</p></div></div><div class="investigation-load"><label>Second recording<select id="comparisonDataset"></select></label><label>Display time axis<select id="comparisonAxis"><option value="elapsed">Independent elapsed seconds</option><option value="normalized">Normalized elapsed time · display only</option></select></label><button id="comparisonRun" class="primary">Compare with current Replay</button></div><details class="panel"><summary>Import second recording</summary><p>Choose a CSV and matching ReplayConfig JSON. Existing 2 MB / 5000-row limits apply. Select Imported recording in the second-recording menu.</p><label>Second CSV<input id="comparisonCsv" type="file" accept=".csv"></label><label>Second ReplayConfig JSON<input id="comparisonConfig" type="file" accept=".json"></label><label><input id="comparisonConfirm" type="checkbox"> I reviewed the second recording source, columns, units and signs.</label></details><p class="investigation-warning">Vehicle, distance, traffic, grade, temperature and data quality may differ. This does not rank driving efficiency.</p><div id="comparisonResults" hidden><div class="comparison-navigation"><label>First recording cursor · elapsed s<input id="comparisonTimeA" type="range" min="0" step="0.01" value="0"></label><label>Second recording cursor · elapsed s<input id="comparisonTimeB" type="range" min="0" step="0.01" value="0"></label></div><p id="comparisonAxisNote"></p><div id="comparisonPlots" class="investigation-graphs"><section class="panel"><h3 id="comparisonNameA"></h3><canvas id="comparisonPlotA" role="img" aria-label="First recording speed with independently navigable cursor"></canvas></section><section class="panel"><h3 id="comparisonNameB"></h3><canvas id="comparisonPlotB" role="img" aria-label="Second recording speed with independently navigable cursor"></canvas></section></div><div id="comparisonMetrics" class="comparison-table"></div><p id="comparisonLimitations"></p></div>`;
  const reports = document.createElement("section");
  reports.id = "caseReportsPanel";
  reports.hidden = true;
  reports.innerHTML = `<div class="investigation-heading"><div><div class="eyebrow">EVIDENCE / REPRODUCIBILITY</div><h2>Generate Engineering Case Study</h2><p>Export the investigated recording or latest comparison, with selected events and source/configuration hashes.</p></div></div><label>Case-study title<input id="caseTitle" type="text" maxlength="160" value="Recorded EV engineering investigation"></label><p id="caseSummary">Investigate or compare recordings first. Reports distinguish observations, calculations and interpretations.</p><div class="buttons"><button id="caseHtml" disabled>Generate Engineering Case Study · HTML</button><button id="caseJson" disabled>JSON analysis data</button><button id="caseCsv" disabled>Measurements + derived CSV</button></div><p id="caseStatus" role="status" aria-live="polite"></p>`;
  for (const [name, label, node] of [
    ["investigate", "Investigate", panel],
    ["compare", "Compare", compare],
    ["reports", "Reports", reports],
  ]) {
    const button = document.createElement("button");
    button.dataset.analyse = name;
    button.textContent = label;
    button.onclick = () => window.VEUSReplay.selectTab(name);
    tabs.append(button);
    tabs.after(node);
  }
  const importedOption = document.createElement("option");
  importedOption.value = "imported";
  importedOption.textContent = "Imported recording · CSV + ReplayConfig JSON";
  el("comparisonDataset").append(importedOption);
  let active = "replay",
    catalogue = [],
    caseResult = null,
    casePayload = null,
    nonce = 0,
    moved = [],
    selected = null;
  const plot = new window.VEUSRecordingPlot();
  const names = {
    vehicle_speed_ms: "Vehicle speed · km/h",
    acceleration_ms2: "Derived acceleration · m/s²",
    battery_voltage_v: "Recorded voltage · V",
    battery_current_a: "Recorded signed current · A",
    electrical_power_w: "Derived signed V×I · kW",
    battery_soc: "Recorded SOC · %",
  };
  const status = (text) => {
    el("investigationStatus").textContent = text;
    el("caseStatus").textContent = text;
  };
  const fmt = (v) =>
    v === null || v === undefined
      ? "Unavailable"
      : typeof v === "number"
        ? Number(v.toFixed(4)).toLocaleString()
        : String(v);
  function table(headers, rows) {
    const t = document.createElement("table");
    const head = document.createElement("tr");
    for (const h of headers) {
      const th = document.createElement("th");
      th.textContent = h;
      head.append(th);
    }
    t.append(head);
    for (const values of rows) {
      const row = document.createElement("tr");
      for (const value of values) {
        const cell = document.createElement("td");
        cell.textContent = fmt(value);
        row.append(cell);
      }
      t.append(row);
    }
    return t;
  }
  function moveShared() {
    if (moved.length) return;
    for (const node of [
      el("replayScene").closest(".driving-surface"),
      document.querySelector(".replay-transport"),
      document.querySelector(".replay-readouts"),
      el("replaySampleNote"),
    ]) {
      const marker = document.createComment("Shared replay view");
      node.before(marker);
      moved.push({ node, marker });
      (node.classList.contains("driving-surface")
        ? el("investigationSceneSlot")
        : el("investigationShared")
      ).append(node);
    }
  }
  function restoreShared() {
    for (const { node, marker } of moved) marker.replaceWith(node);
    moved = [];
  }
  document.addEventListener("veus:analyse-tab", (e) => {
    active = e.detail;
    panel.hidden = active !== "investigate";
    compare.hidden = active !== "compare";
    reports.hidden = active !== "reports";
    if (active === "investigate") moveShared();
    else restoreShared();
    requestAnimationFrame(draw);
  });
  async function post(payload) {
    const response = await fetch("/api/investigation/case-study", {
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
  function input() {
    const item = window.VEUSReplay.input;
    if (!item) throw Error("Load or import a recording in Replay first.");
    if (!el("investigationConfirm").checked)
      throw Error(
        "Review the Replay column/unit configuration and confirm it before investigation.",
      );
    return { ...item, selected_events: null };
  }
  async function recording(name) {
    const r = await fetch("/api/investigation/recordings/" + name);
    const data = await r.json();
    if (!r.ok) throw Error(data.detail || "Cannot load recording");
    return {
      configuration: data.configuration,
      csv_base64: data.csv_base64,
      mappings_confirmed: true,
    };
  }
  el("investigationLoad").onclick = async () => {
    try {
      const p = await recording(el("investigationDataset").value);
      await window.VEUSReplay.loadRecording({
        configuration: p.configuration,
        csv_base64: p.csv_base64,
      });
      window.VEUSReplay.selectTab("investigate");
      status(
        "Documented catalogue recording loaded. Review its units/source, confirm and run readiness.",
      );
    } catch (e) {
      status(e.message);
    }
  };
  el("investigationCurrent").onclick = () => {
    window.VEUSReplay.selectTab("replay");
  };
  async function build(second = false, event = null) {
    const token = ++nonce;
    try {
      const first = input();
      if (event !== null) first.selected_events = [event];
      const payload = {
        first,
        title: el("caseTitle").value,
        axis: el("comparisonAxis").value,
      };
      if (second) {
        if (el("comparisonDataset").value === "imported") {
          if (!el("comparisonConfirm").checked)
            throw Error(
              "Confirm the second recording mappings and source first.",
            );
          const csv = el("comparisonCsv").files[0],
            config = el("comparisonConfig").files[0];
          if (!csv || !config)
            throw Error("Choose both second CSV and ReplayConfig JSON.");
          if (csv.size > 2000000 || config.size > 100000)
            throw Error(
              "Second CSV exceeds 2 MB or configuration exceeds 100 KB.",
            );
          const csv_base64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(",")[1]);
            reader.onerror = () => reject(Error("Cannot read second CSV"));
            reader.readAsDataURL(csv);
          });
          payload.second = {
            csv_base64,
            configuration: JSON.parse(await config.text()),
            mappings_confirmed: true,
          };
        } else payload.second = await recording(el("comparisonDataset").value);
      }
      status("Applying existing Data Readiness and event rules…");
      const data = await post(payload);
      if (token !== nonce) return;
      casePayload = payload;
      caseResult = data;
      render();
      status(
        "Investigation generated from recorded samples. Physical validation remains INCONCLUSIVE.",
      );
    } catch (e) {
      status("Investigation unavailable: " + e.message);
    }
  }
  el("investigationRun").onclick = () => build();
  el("comparisonRun").onclick = () => build(true);
  for (const id of ["comparisonCsv", "comparisonConfig"])
    el(id).onchange = () => {
      el("comparisonConfirm").checked = false;
    };

  function render() {
    const first = caseResult.recordings[0],
      a = first.analysis;
    el("investigationResults").hidden = false;
    const overview = el("investigationOverview");
    overview.replaceChildren();
    for (const key of [
      "recording_duration_s",
      "sample_count",
      "known_segment_distance_m",
      "speed_interval_coverage",
    ]) {
      const item = first.metrics[key],
        card = document.createElement("div");
      const label = document.createElement("span"),
        value = document.createElement("strong");
      label.textContent = key.replaceAll("_", " ");
      value.textContent = fmt(item.value) + " " + item.unit;
      card.append(label, value);
      overview.append(card);
    }
    el("investigationEnergy").textContent = first.analysis
      .investigation_energy_gate.available
      ? "Electrical energy is available under the supplied readiness assertions; it is not automatically regenerative energy."
      : "Energy calculation unavailable: current polarity or measurement-quality requirements are unresolved.";
    el("investigationMetrics").replaceChildren(
      table(
        ["Metric", "Value", "Unit", "Class", "Status"],
        Object.entries(first.metrics).map(([key, v]) => [
          key,
          v.value,
          v.unit,
          v.classification,
          v.status,
        ]),
      ),
    );
    el("investigationQuality").textContent = JSON.stringify(
      {
        source: a.configuration.source,
        quality: a.quality,
        readiness: first.readiness.capabilities.map((c) => ({
          name: c.name,
          status: c.status,
          explanation: c.explanation,
        })),
        limitations: first.limitations,
      },
      null,
      2,
    );
    const events = el("investigationEvents");
    events.replaceChildren();
    el("investigationEventCount").textContent =
      `${first.events.length} existing detector episodes · first 200 listed`;
    for (const event of first.events.slice(0, 200)) {
      const b = document.createElement("button");
      b.className = "investigation-event";
      b.dataset.eventIndex = event.event_index;
      b.textContent = `${event.start_s.toFixed(2)}–${event.end_s.toFixed(2)} s · ${event.type.replaceAll("_", " ")}`;
      b.onclick = () => {
        window.VEUSReplay.selectEvent(event.event_index);
      };
      events.append(b);
    }
    if (!first.events.length)
      events.textContent =
        "No events meet the configured thresholds; no event evidence is invented.";
    const insight = first.insights[0];
    selected = insight ? [insight.start_s, insight.end_s] : null;
    const host = el("investigationInsight");
    host.replaceChildren();
    if (insight) {
      const heading = document.createElement("h4");
      heading.textContent =
        insight.event_type.replaceAll("_", " ") +
        ` · ${insight.start_s.toFixed(2)}–${insight.end_s.toFixed(2)} s`;
      const rule = document.createElement("p");
      rule.textContent = "Rule: " + insight.rule;
      const interpretation = document.createElement("p");
      interpretation.textContent =
        insight.interpretation_classification + ": " + insight.interpretation;
      host.append(
        heading,
        rule,
        interpretation,
        table(
          [
            "Supporting signal",
            "Class",
            "Valid / missing",
            "Min",
            "Max",
            "Unit",
          ],
          insight.evidence.map((e) => [
            e.signal,
            e.classification,
            e.valid_samples + " / " + e.missing_samples,
            e.minimum,
            e.maximum,
            e.unit,
          ]),
        ),
      );
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Traceable sample indices and limitations";
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(insight, null, 2);
      details.append(summary, pre);
      host.append(details);
    } else
      host.textContent =
        "Choose a supported detector event to inspect; observations remain available in the overview.";
    for (const id of ["investigationGraphs", "investigationExtraGraphs"])
      el(id).replaceChildren();
    for (const key of Object.keys(names)) {
      if (!a.measured[key] && !a.derived[key]) continue;
      const section = document.createElement("section");
      section.className = "panel";
      const label = document.createElement("h3");
      label.textContent = names[key] + " · " + a.classifications[key];
      const canvas = document.createElement("canvas");
      canvas.id = "investigationPlot_" + key;
      canvas.dataset.signal = key;
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", label.textContent);
      section.append(label, canvas);
      el(
        ["vehicle_speed_ms", "electrical_power_w"].includes(key)
          ? "investigationGraphs"
          : "investigationExtraGraphs",
      ).append(section);
      attach(canvas, key, a);
    }
    el("investigationMoreSignals").hidden = !el("investigationExtraGraphs")
      .children.length;
    if (caseResult.comparison) {
      el("comparisonResults").hidden = false;
      const c = caseResult.comparison;
      el("comparisonAxisNote").textContent = c.axis_definition;
      el("comparisonLimitations").textContent = c.limitations.join(" ");
      for (const [letter, rec] of [
        ["A", caseResult.recordings[0]],
        ["B", caseResult.recordings[1]],
      ]) {
        el("comparisonTime" + letter).max = rec.analysis.time_s.at(-1);
        el("comparisonName" + letter).textContent =
          rec.configuration.source.run_id + " · speed km/h";
      }
      el("comparisonMetrics").replaceChildren(
        table(
          [
            "Metric",
            "First",
            "First class/status",
            "Second",
            "Second class/status",
            "Unit",
            "Second − first",
          ],
          c.metrics.map((r) => [
            r.metric,
            r.first.value,
            r.first.classification + "/" + r.first.status,
            r.second.value,
            r.second.classification + "/" + r.second.status,
            r.unit,
            r.difference_second_minus_first,
          ]),
        ),
      );
    }
    el("caseSummary").textContent =
      caseResult.title +
      " · " +
      caseResult.recordings
        .map(
          (r) =>
            r.configuration.source.run_id +
            " (" +
            r.configuration.source.kind +
            ")",
        )
        .join(" vs ") +
      " · " +
      caseResult.case_sha256;
    for (const id of ["caseHtml", "caseJson", "caseCsv"])
      el(id).disabled = false;
    requestAnimationFrame(draw);
  }
  function attach(canvas, key, a) {
    const coordinate = (e) => {
      const box = canvas.getBoundingClientRect(),
        left = Number(canvas.dataset.plotLeft) || 62,
        right = Number(canvas.dataset.plotRight) || box.width - 12;
      return Math.max(
        0,
        Math.min(
          a.time_s.at(-1),
          ((e.clientX - box.left - left) / (right - left)) * a.time_s.at(-1),
        ),
      );
    };
    canvas.onclick = (e) => window.VEUSReplay.seek(coordinate(e));
    canvas.onmousemove = (e) => {
      const time = coordinate(e),
        i = a.time_s.reduce(
          (best, t, j) =>
            Math.abs(t - time) < Math.abs(a.time_s[best] - time) ? j : best,
          0,
        ),
        value = (a.measured[key] || a.derived[key])[i];
      canvas.title = `Actual sample ${a.time_s[i].toFixed(3)} s · ${value === null ? "Unavailable" : value + " " + a.units[key]} · ${a.classifications[key]}`;
    };
  }
  function draw() {
    if (!caseResult || window.activeWorkspace !== "analyse") return;
    if (active === "investigate") {
      const state = window.VEUSReplay.state || { time_s: 0 };
      for (const canvas of panel.querySelectorAll("canvas[data-signal]"))
        plot.draw(
          canvas,
          caseResult.recordings[0].analysis,
          state,
          canvas.dataset.signal,
          selected,
        );
    }
    if (active === "compare" && caseResult.recordings.length === 2) {
      for (const [i, letter] of [
        [0, "A"],
        [1, "B"],
      ]) {
        const a = caseResult.recordings[i].analysis;
        plot.draw(
          el("comparisonPlot" + letter),
          a,
          { time_s: Number(el("comparisonTime" + letter).value) },
          "vehicle_speed_ms",
          null,
          el("comparisonAxis").value === "normalized",
        );
      }
    }
  }
  for (const letter of ["A", "B"]) el("comparisonTime" + letter).oninput = draw;
  el("comparisonAxis").onchange = () => {
    el("comparisonAxisNote").textContent =
      el("comparisonAxis").value === "normalized"
        ? "Each elapsed time divided by its own duration; display transformation only, not resampling or simultaneous real-world moments."
        : "Independent elapsed seconds from separate source origins; not simultaneous real-world moments.";
    draw();
  };
  el("investigationMoreSignals").ontoggle = draw;
  el("investigationScenePreview").ontoggle = () =>
    window.dispatchEvent(new Event("resize"));
  document.addEventListener("veus:replay-clock", draw);
  window.addEventListener("resize", draw);
  document.addEventListener("veus:replay-event", (e) => {
    if (caseResult) build(!!caseResult.comparison, e.detail.event_index);
  });
  document.addEventListener("veus:recording", () => {
    nonce++;
    caseResult = null;
    casePayload = null;
    el("investigationConfirm").checked = false;
    el("investigationResults").hidden = true;
    el("comparisonResults").hidden = true;
    for (const id of ["caseHtml", "caseJson", "caseCsv"])
      el(id).disabled = true;
    status(
      "Recording changed. Review mappings/source and confirm before investigation.",
    );
  });
  function download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type })),
      a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function exportCase(format) {
    if (!casePayload) return;
    try {
      const payload = {
        ...casePayload,
        title: el("caseTitle").value,
        axis: el("comparisonAxis").value,
      };
      const result = await post(payload);
      casePayload = payload;
      caseResult = result;
      if (format === "json") {
        download(
          "veus-engineering-case-study.json",
          JSON.stringify(result, null, 2) + "\n",
          "application/json",
        );
      } else {
        const artifact = await post({ ...payload, format });
        if (artifact.case_sha256 !== result.case_sha256)
          throw Error("Case changed; rerun investigation before exporting");
        download(
          "veus-engineering-case-study." + (format === "html" ? "html" : "csv"),
          artifact.content,
          format === "html" ? "text/html" : "text/csv",
        );
      }
      el("caseStatus").textContent =
        "Exported " + format.toUpperCase() + " · " + result.case_sha256;
    } catch (e) {
      el("caseStatus").textContent = "Export failed: " + e.message;
    }
  }
  el("caseHtml").onclick = () => exportCase("html");
  el("caseJson").onclick = () => exportCase("json");
  el("caseCsv").onclick = () => exportCase("csv");
  fetch("/api/investigation/catalogue")
    .then((r) => r.json())
    .then((items) => {
      catalogue = items;
      for (const id of ["investigationDataset", "comparisonDataset"])
        for (const item of items) {
          const option = document.createElement("option");
          option.value = item.id;
          option.textContent = item.label;
          el(id).append(option);
        }
      el("investigationDataset").value = "ved-10-1561-full";
      el("comparisonDataset").value = "ved-10-1567-full";
      for (const item of items) {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent =
          item.label +
          ` · ${item.sample_count} rows · ${item.duration_s.toFixed(1)} s · ${item.kind}`;
        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(item, null, 2);
        details.append(summary, pre);
        el("investigationCatalogue").append(details);
      }
    })
    .catch((e) => status("Catalogue unavailable: " + e.message));
  window.VEUSInvestigation = {
    get caseStudy() {
      return caseResult;
    },
  };
})();

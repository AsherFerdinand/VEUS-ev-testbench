// Original recorded samples and legacy quality gates; one shared cursor, no simulation.
import { state } from "./design-state.js";
import { esc, fmt, download } from "./engineering-insights.js";
let clockPromise;
async function clockLibrary() {
  if (window.VEUSReplayController) return;
  await (clockPromise ||= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "/static/replay-controller.js";
    s.onload = resolve;
    s.onerror = reject;
    document.head.append(s);
  }));
}
export async function mountMeasurements(root, { header }) {
  const life = new AbortController();
  let request = null,
    first = null,
    second = null,
    result = null,
    frozenCase = null,
    findingToken = null,
    uploaded = false,
    clock = null,
    raf = 0,
    cache = {},
    selected = null;
  const $ = (id) => root.querySelector("#" + id),
    on = (node, event, fn) =>
      node.addEventListener(event, fn, { signal: life.signal });
  if (!document.getElementById("measurements-css")) {
    const l = document.createElement("link");
    l.id = "measurements-css";
    l.rel = "stylesheet";
    l.href = "/static/workbench/measurements.css";
    document.head.append(l);
  }
  await clockLibrary();
  const catalogue = await (
    await fetch("/api/investigation/catalogue", { signal: life.signal })
  ).json();
  if (!root.isConnected) return () => life.abort();
  const opts =
    '<option value="">None</option>' +
    catalogue
      .map((r) => `<option value="${r.id}">${esc(r.label)}</option>`)
      .join("");
  root.innerHTML =
    header(
      "05 / RECORDED EVIDENCE",
      "Investigate what was measured.",
      "Import → readiness → signals → events → comparison → reproducible report",
      "PHYSICAL VALIDATION / INCONCLUSIVE",
    ) +
    `<section class="measure-workspace"><div class="measure-controls"><label>Recording<select id="measurement-recording">${opts}<option value="imported">Imported CSV / JSON</option></select></label><label>Descriptive comparison<select id="measure-second">${opts}</select></label><label class="measure-confirm" id="measure-second-review" hidden><input id="measure-second-confirm" type="checkbox">I reviewed comparison source mappings and units.</label><label>Investigation question<select id="measurement-question"><option value="speed">Acceleration / braking and speed</option><option value="power">High current and measured voltage</option><option value="quality">Missing signals and quality</option></select></label><button id="measure-investigate">Check readiness & investigate</button></div><pre id="measure-second-note"></pre><div id="measurement-summary" class="measure-note">Select a recording. Import success is not measurement validation.</div><details id="measure-import"><summary>Import CSV / JSON and review signal mapping</summary><div class="measure-controls"><label>CSV or combined replay JSON<input id="measure-file" type="file" accept=".csv,.json"></label><label>Existing configuration JSON (optional with CSV)<input id="measure-config" type="file" accept=".json"></label><label>Dataset / source name<input id="measure-name" value="User supplied recording"></label><label>Source URL<input id="measure-url" value="user://uploaded-recording"></label><label>Licence / permission<input id="measure-licence" value="User supplied; rights not independently verified"></label><label>Origin<select id="measure-origin"><option value="measured">User-asserted measured data</option><option value="synthetic">Synthetic demonstration</option></select></label></div><button id="measure-inspect">Inspect headers / coverage proposal</button><pre id="measure-inspection"></pre><div class="measure-controls">${[
      ["time_s", "Timestamp(ms)", "ms"],
      ["vehicle_speed_ms", "Vehicle Speed[km/h]", "km/h"],
      ["battery_voltage_v", "HV Battery Voltage[V]", "V"],
      ["battery_current_a", "HV Battery Current[A]", "A"],
      ["battery_soc", "HV Battery SOC[%]", "%"],
    ]
      .map(
        ([key, col, unit]) =>
          `<label>${key}<input data-map="${key}" value="${col}"><input data-unit="${key}" value="${unit}" aria-label="${key} unit"></label>`,
      )
      .join(
        "",
      )}<label>Maximum valid gap · s<input id="measure-gap" type="number" min=".01" max="60" value="2" step="any"></label><label>Current sign<select id="measure-sign"><option value="unknown">Unknown polarity</option><option value="discharge_positive">Discharge positive (evidence required)</option><option value="charge_positive">Charge positive (evidence required)</option></select></label><label>Sign / provenance evidence<input id="measure-evidence" placeholder="Do not infer polarity from a plot"></label></div><p class="quiet">Review names and units explicitly; blank optional mappings stay unavailable. Original bytes, source time and gaps are preserved. Header recognition never confirms polarity or measurement validity.</p></details><label class="measure-confirm"><input id="measure-confirm" type="checkbox">I reviewed source, column mappings, units and the declared polarity evidence.</label><p id="measure-status" role="status">No investigation executed.</p><div id="measure-readiness" aria-live="polite"></div><section class="measure-dashboard"><p id="measure-frozen-name">No frozen recording loaded.</p><div class="measure-plots"><article><h3>Measured speed · km/h</h3><canvas id="measure-speed" role="img" aria-label="Original measured speed samples"></canvas></article><article><label>Electrical signal<select id="measure-signal"><option value="battery_voltage_v">Measured voltage · V</option><option value="battery_current_a">Measured current · A (source sign)</option><option value="electrical_power_w">Signed battery power · W (gated)</option></select></label><canvas id="measure-electrical" role="img" aria-label="Original measured electrical signal"></canvas></article></div><div class="measure-transport"><button id="measure-play" disabled>▶ Play</button><button id="measure-stop" disabled>Stop</button><input id="measure-seek" type="range" min="0" max="1" step=".001" value="0" aria-label="Measured time cursor" disabled><span id="measure-time">No cursor</span></div><p id="measure-sample"></p><div class="measure-controls"><label>Detected event<select id="measure-event"><option value="">Full recording</option></select></label><button id="measure-interval">Use selected event as interval</button></div><div id="measure-findings"></div></section><details id="measure-model"><summary>Measured versus simulated comparison readiness</summary><p>Presets are illustrative EVs, not the recorded Nissan Leaf. Independent boundary/vehicle inputs are required before model residuals are defensible.</p><div class="measure-controls"><label>Model design<select id="measure-model-design"><option value="active">Active design</option>${state.library.map((r) => `<option value="${esc(r.id)}">${esc(r.design.name)}</option>`).join("")}</select></label><label>Interval start · elapsed s<input id="measure-start" type="number" value="0" min="0" step="any"></label><label>Interval end · elapsed s<input id="measure-end" type="number" min="0" step="any"></label><button id="measure-gate">Assess comparison inputs</button></div><div id="measure-model-result">No quantitative comparison executed.</div></details><details id="measure-validation"><summary>Validation & calibration readiness · evidence-specific assessment</summary><p>No fitting or residual is manufactured for insufficient data. Optional training/evaluation intervals must share no samples.</p><div class="measure-controls"><label>Assessed motor loss model<select id="validation-model"><option value="">Legacy constant</option><option value="illustrative_map">Illustrative efficiency map</option></select></label><label>Calibration interval · s, comma separated<input id="validation-calibration" placeholder="0,150"></label><label>Held-out evaluation interval · s<input id="validation-evaluation" placeholder="200,350"></label><button id="validation-assess">Audit validation / calibration evidence</button></div><p class="quiet">Uses the model design selected below. Reports freeze its exact configuration; recordings do not establish a match to an illustrative preset.</p><label>Validation model design<select id="validation-design"><option value="active">Active design</option>${state.library.map((r) => `<option value="${esc(r.id)}">${esc(r.design.name)}</option>`).join("")}</select></label><div id="validation-result" role="status" aria-live="polite"></div><button id="validation-export" disabled>Export validation assessment JSON</button><button id="validation-html" disabled>HTML validation report</button><a href="/engineering?workspace=validate">Retained bounded calibration tools for appropriately documented data</a></details><details><summary>Readiness, provenance, interval evidence and descriptive recording comparison</summary><pre id="measure-details"></pre></details><div class="measure-export"><button data-measure-format="json" disabled>JSON evidence</button><button data-measure-format="csv" disabled>CSV original samples</button><button data-measure-format="html" disabled>HTML report</button></div><a href="/engineering?workspace=analyse">Retained engineering measurement tools ↗</a></section>`;
  async function api(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: request?.signal || life.signal,
    });
    const data = await r.json();
    if (life.signal.aborted)
      throw new DOMException("Workspace closed", "AbortError");
    if (!r.ok)
      throw Error(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail),
      );
    return data;
  }
  function pause() {
    clock?.pause(performance.now());
    cancelAnimationFrame(raf);
    raf = 0;
    if ($("measure-play")) $("measure-play").textContent = "▶ Play";
  }
  function mappingUI(config) {
    for (const node of root.querySelectorAll("[data-map]")) {
      const v = config.preprocessing.columns[node.dataset.map];
      node.value = v?.column || "";
      root.querySelector(`[data-unit="${node.dataset.map}"]`).value =
        v?.unit || "";
    }
    $("measure-sign").value = config.current_sign;
    $("measure-evidence").value = config.sign_evidence || "";
    $("measure-gap").value = config.preprocessing.max_gap_s;
  }
  function summary() {
    const entry = first?.catalogue,
      cfg = first?.configuration;
    $("measurement-summary").textContent = cfg
      ? `${cfg.source.dataset} · ${cfg.source.kind} · ${entry?.sample_count ?? "Imported"} samples · source SHA256 ${cfg.source.expected_sha256}. ${cfg.current_sign === "unknown" ? "Unverified polarity: signed power/energy conclusions stay gated." : "Polarity assertion requires readiness checks; no authentication is implied."}`
      : "Select a source.";
  }
  async function choose() {
    pause();
    request?.abort();
    request = new AbortController();
    $("measure-confirm").checked = false;
    const id = $("measurement-recording").value;
    if (id === "imported") {
      $("measure-import").open = true;
      return;
    }
    if (!id) return;
    try {
      uploaded = false;
      first = await (
        await fetch("/api/investigation/recordings/" + id, {
          signal: request.signal,
        })
      ).json();
      mappingUI(first.configuration);
      summary();
      $("measure-status").textContent =
        "Source loaded. Review mapping and confirm before investigation.";
    } catch (e) {
      if (e.name !== "AbortError") $("measure-status").textContent = e.message;
    }
  }
  on($("measurement-recording"), "change", choose);
  on($("measurement-question"), "change", () => {
    summary();
    if (result) {
      if ($("measurement-question").value === "power")
        $("measure-signal").value = "battery_current_a";
      cache = {};
      paint();
    }
  });
  on($("measure-second"), "change", async () => {
    const id = $("measure-second").value;
    $("measure-second-review").hidden = !id;
    $("measure-second-confirm").checked = false;
    try {
      if (id) {
        const p = await (
          await fetch("/api/investigation/recordings/" + id, {
            signal: life.signal,
          })
        ).json();
        $("measure-second-note").textContent = JSON.stringify(
          {
            source: p.configuration.source,
            columns: p.configuration.preprocessing.columns,
          },
          null,
          2,
        );
      } else $("measure-second-note").textContent = "";
    } catch (e) {
      $("measure-status").textContent = e.message;
    }
  });
  on($("measure-file"), "change", async () => {
    try {
      const file = $("measure-file").files[0];
      if (!file) return;
      if (file.size > 2_000_000)
        throw Error("Import limit 2 MB; use a documented window");
      $("measurement-recording").value = "imported";
      $("measure-confirm").checked = false;
      if (file.name.endsWith(".json")) {
        uploaded = false;
        const data = JSON.parse(await file.text());
        if (data.first) {
          first = data.first;
          second = data.second || null;
        } else if (data.csv_base64) first = data;
        else if (data.preprocessing && data.source) {
          first = { ...(first || {}), configuration: data };
        } else
          throw Error(
            "JSON must contain a replay configuration or source payload",
          );
        if (first.configuration) mappingUI(first.configuration);
        summary();
      } else {
        const bytes = new Uint8Array(await file.arrayBuffer()),
          hash = Array.from(
            new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
            (b) => b.toString(16).padStart(2, "0"),
          ).join("");
        let binary = "";
        for (const b of bytes) binary += String.fromCharCode(b);
        uploaded = true;
        first = {
          csv_base64: btoa(binary),
          configuration: {
            schema_version: 1,
            source: {
              dataset: $("measure-name").value,
              source_url: $("measure-url").value,
              licence: $("measure-licence").value,
              kind: $("measure-origin").value,
              run_id: file.name,
              role: "exploration",
              expected_sha256: hash,
              provenance_evidence:
                "User supplied raw file; identity and instrument calibration are not authenticated",
              inputs_verified: false,
            },
            preprocessing: { columns: {}, max_gap_s: 2 },
            current_sign: "unknown",
            limitations: [
              "User-supplied recording; measurement provenance, channel calibration and conditions require independent evidence.",
            ],
          },
        };
        summary();
      }
      $("measure-status").textContent =
        "Original input loaded; inspect and explicitly map columns before confirming.";
    } catch (e) {
      $("measure-status").textContent = "Import unavailable: " + e.message;
    }
  });
  on($("measure-config"), "change", async () => {
    try {
      const file = $("measure-config").files[0];
      if (!file || file.size > 200000)
        throw Error("Configuration JSON limit 200 KB");
      const config = JSON.parse(await file.text());
      if (!first) throw Error("Load CSV first");
      first.configuration = config;
      mappingUI(config);
      $("measure-confirm").checked = false;
      summary();
    } catch (e) {
      $("measure-status").textContent = e.message;
    }
  });
  on($("measure-inspect"), "click", async () => {
    try {
      if (!first?.csv_base64) throw Error("Load CSV or combined payload first");
      const r = await api("/api/readiness/inspect", {
        csv_base64: first.csv_base64,
      });
      $("measure-inspection").textContent = JSON.stringify(r, null, 2);
    } catch (e) {
      $("measure-status").textContent = e.message;
    }
  });
  function prepared() {
    if (!first || !$("measure-confirm").checked)
      throw Error("Review and confirm source mappings first");
    const config = structuredClone(first.configuration),
      columns = {};
    for (const input of root.querySelectorAll("[data-map]"))
      if (input.value.trim())
        columns[input.dataset.map] = {
          column: input.value.trim(),
          unit: root
            .querySelector(`[data-unit="${input.dataset.map}"]`)
            .value.trim(),
          sign: config.preprocessing.columns[input.dataset.map]?.sign || 1,
        };
    // Preserve all pre-existing mapped channels, including temperature/gradient, unless an editable channel was explicitly cleared.
    for (const [key, value] of Object.entries(config.preprocessing.columns))
      if (!root.querySelector(`[data-map="${key}"]`)) columns[key] = value;
    if (uploaded)
      Object.assign(config.source, {
        dataset: $("measure-name").value,
        source_url: $("measure-url").value,
        licence: $("measure-licence").value,
        kind: $("measure-origin").value,
      });
    config.preprocessing.columns = columns;
    config.preprocessing.max_gap_s = Number($("measure-gap").value);
    config.current_sign = $("measure-sign").value;
    config.sign_evidence = $("measure-evidence").value || null;
    return {
      configuration: config,
      csv_base64: first.csv_base64,
      mappings_confirmed: true,
    };
  }
  function caseRequest(format = "json") {
    return {
      first: prepared(),
      second: second
        ? {
            configuration: second.configuration,
            csv_base64: second.csv_base64,
            mappings_confirmed: true,
          }
        : null,
      title: "Recorded EV engineering investigation",
      axis: "elapsed",
      format,
    };
  }
  function renderFindings() {
    const r = result.recordings[0],
      idx = clock?.state().index ?? 0;
    const a = r.analysis;
    $("measure-sample").textContent =
      `Original sample ${idx}, elapsed ${fmt(a.time_s[idx])} s; source time ${fmt(a.time_s[idx] + a.metadata.time_origin_s)} s. No gaps filled.`;
    const token =
      result.case_sha256 +
      ":" +
      selected +
      ":" +
      $("measurement-question").value;
    if (token === findingToken) return;
    findingToken = token;
    const selectedEvent =
      selected == null
        ? null
        : r.events.find((e) => e.event_index === selected);
    $("measure-findings").innerHTML =
      (selectedEvent
        ? `<p>Event ${selectedEvent.event_index}: ${esc(selectedEvent.type)} · ${fmt(selectedEvent.start_s)}–${fmt(selectedEvent.end_s)} s</p>`
        : "") +
      r.insights
        .filter((v) => selected == null || v.event_index === selected)
        .slice(0, 6)
        .map(
          (v) =>
            `<article><strong>${esc(v.event_type || "Recorded finding")} · ${fmt(v.start_s)}–${fmt(v.end_s)} s</strong><p>${esc(v.interpretation)}</p>${(
              v.observations || []
            )
              .filter(
                (o) =>
                  a.configuration.current_sign !== "unknown" || o.unit !== "W",
              )
              .slice(0, 3)
              .map(
                (o) =>
                  `<p>${esc(o.statement)} <small>(${esc(o.classification)})</small></p>`,
              )
              .join(
                "",
              )}<details><summary>Original sample indices and evidence</summary><pre>${esc(JSON.stringify(v, null, 2))}</pre></details></article>`,
        )
        .join("");
  }
  function draw(time) {
    if (!result) return;
    const a = result.recordings[0].analysis;
    for (const [id, key, scale] of [
      ["measure-speed", "vehicle_speed_ms", 3.6],
      ["measure-electrical", $("measure-signal").value, 1],
    ]) {
      const canvas = $(id),
        rect = canvas.getBoundingClientRect();
      if (!rect.width) return;
      const w = rect.width,
        h = rect.height,
        dpr = Math.min(2, devicePixelRatio || 1),
        values =
          key === "electrical_power_w" &&
          a.configuration.current_sign === "unknown"
            ? null
            : a.measured[key] || a.derived[key],
        signature = [result.case_sha256, key, w, h].join(":");
      canvas.dataset.available = String(!!values?.some(Number.isFinite));
      if (!cache[id] || cache[id].signature !== signature) {
        const image = document.createElement("canvas");
        image.width = w * dpr;
        image.height = h * dpr;
        const c = image.getContext("2d");
        c.scale(dpr, dpr);
        c.fillStyle = "#102131";
        c.fillRect(0, 0, w, h);
        c.font = "10px Segoe UI";
        c.fillStyle = "#bad7e2";
        if (!values?.some(Number.isFinite))
          c.fillText(
            "Unavailable under current signal/polarity/readiness gates",
            15,
            h / 2,
          );
        else {
          const finite = values.filter(Number.isFinite).map((v) => v * scale),
            lo = Math.min(0, ...finite),
            hi = Math.max(1, ...finite);
          c.strokeStyle = "#365263";
          for (let i = 0; i < 3; i++) {
            const y = 15 + ((h - 45) * i) / 2;
            c.beginPath();
            c.moveTo(48, y);
            c.lineTo(w - 10, y);
            c.stroke();
            c.fillText(fmt(hi - ((hi - lo) * i) / 2), 2, y + 3);
          }
          c.fillText("0 s", 48, h - 5);
          c.fillText(fmt(a.time_s.at(-1)) + " s", w - 55, h - 5);
          c.strokeStyle = "#73d0cd";
          c.lineWidth = 1.5;
          c.beginPath();
          let open = false;
          for (let i = 0; i < a.time_s.length; i++) {
            const v = values[i],
              gap =
                i &&
                a.time_s[i] - a.time_s[i - 1] >
                  a.configuration.preprocessing.max_gap_s;
            if (!Number.isFinite(v)) {
              open = false;
              continue;
            }
            const x = 48 + (a.time_s[i] / clock.duration) * (w - 58),
              y = h - 30 - ((v * scale - lo) / (hi - lo)) * (h - 45);
            if (open && !gap) c.lineTo(x, y);
            else c.moveTo(x, y);
            open = true;
          }
          c.stroke();
        }
        cache[id] = { signature, image };
      }
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      const c = canvas.getContext("2d");
      c.drawImage(cache[id].image, 0, 0);
      c.scale(dpr, dpr);
      c.strokeStyle = "#e3f1f1";
      c.setLineDash([3, 3]);
      const x = 48 + (time / clock.duration) * (w - 58);
      c.beginPath();
      c.moveTo(x, 10);
      c.lineTo(x, h - 25);
      c.stroke();
      canvas.dataset.cursorTime = time.toFixed(6);
    }
  }
  function paint(now = performance.now()) {
    if (!clock) return;
    const p = clock.tick(now);
    $("measure-seek").value = p.time_s;
    $("measure-time").textContent =
      fmt(p.time_s) + " / " + fmt(clock.duration) + " s";
    $("measure-play").textContent = p.playing ? "Ⅱ Pause" : "▶ Play";
    draw(p.time_s);
    renderFindings();
  }
  function frame(now) {
    paint(now);
    raf = clock?.playing ? requestAnimationFrame(frame) : 0;
  }
  on($("measure-investigate"), "click", async () => {
    try {
      pause();
      request?.abort();
      request = new AbortController();
      $("measure-status").textContent =
        "Applying legacy readiness and investigation gates…";
      const id = $("measure-second").value;
      if (id && !$("measure-second-confirm").checked)
        throw Error("Review and confirm the comparison source mapping first");
      if (id)
        second = await (
          await fetch("/api/investigation/recordings/" + id, {
            signal: request.signal,
          })
        ).json();
      else second = null;
      frozenCase = caseRequest();
      result = await api(
        "/api/workbench/v2/measurements/case-study",
        frozenCase,
      );
      window.VEUSMeasurements = result;
      window.VEUSMeasurementReplay = {
        get framePending() {
          return !!raf;
        },
        get playing() {
          return !!clock?.playing;
        },
        get time() {
          return clock?.time || 0;
        },
      };
      $("measure-frozen-name").textContent =
        "Frozen recording: " +
        result.recordings[0].configuration.source.run_id +
        " · " +
        result.recordings[0].configuration.source.kind +
        " · SHA256 " +
        result.recordings[0].source_sha256;
      const r = result.recordings[0],
        a = r.analysis;
      clock = new window.VEUSReplayController(a);
      cache = {};
      selected = null;
      $("measure-end").value = clock.duration;
      $("measure-seek").max = clock.duration;
      for (const id of ["measure-play", "measure-stop", "measure-seek"])
        $(id).disabled = false;
      for (const b of root.querySelectorAll("[data-measure-format]"))
        b.disabled = false;
      $("measure-event").innerHTML =
        '<option value="">Full recording</option>' +
        r.events
          .map(
            (e) =>
              `<option value="${e.event_index}">${e.event_index} · ${esc(e.type)} · ${fmt(e.start_s)}–${fmt(e.end_s)} s</option>`,
          )
          .join("");
      $("measure-readiness").innerHTML = r.readiness.capabilities
        .filter((c) =>
          [
            "recorded_replay",
            "energy_consumption",
            "regenerative_energy",
            "longitudinal_validation",
          ].includes(c.id),
        )
        .map(
          (c) =>
            `<div><strong>${esc(c.id)} · ${esc(c.status)}</strong><p>${esc(c.explanation)}</p></div>`,
        )
        .join("");
      $("measure-details").textContent = JSON.stringify(
        {
          readiness: r.readiness,
          provenance: a.configuration,
          metrics: r.metrics,
          comparison: result.comparison,
          limitations: r.limitations,
        },
        null,
        2,
      );
      $("measure-status").textContent =
        "Investigation complete. Source samples and quality gates retained; physical validation INCONCLUSIVE.";
      paint();
    } catch (e) {
      if (e.name !== "AbortError")
        $("measure-status").textContent = "Unavailable: " + e.message;
    }
  });
  on($("measure-event"), "change", async () => {
    selected =
      $("measure-event").value === "" ? null : Number($("measure-event").value);
    if (!result || !frozenCase) return;
    try {
      pause();
      const req = structuredClone(frozenCase);
      if (selected == null) delete req.first.selected_events;
      else req.first.selected_events = [selected];
      result = await api("/api/workbench/v2/measurements/case-study", req);
      frozenCase = req;
      window.VEUSMeasurements = result;
      $("measure-details").textContent = JSON.stringify(
        {
          recording: result.recordings[0].configuration,
          selected_event_indices: result.recordings[0].selected_event_indices,
          metrics: result.recordings[0].metrics,
          comparison: result.comparison,
          limitations: result.recordings[0].limitations,
        },
        null,
        2,
      );
      if (selected != null) {
        const event = result.recordings[0].events.find(
          (v) => v.event_index === selected,
        );
        clock.seek(event.start_s, performance.now());
      }
      cache = {};
      paint();
    } catch (error) {
      $("measure-status").textContent = error.message;
    }
  });
  on($("measure-interval"), "click", () => {
    if (selected == null || !result) return;
    const e = result.recordings[0].events.find(
      (e) => e.event_index === selected,
    );
    $("measure-start").value = e.start_s;
    $("measure-end").value = e.end_s;
  });
  on($("measure-play"), "click", () => {
    if (!clock) return;
    if (clock.playing) pause();
    else {
      clock.play(performance.now());
      if (!raf) raf = requestAnimationFrame(frame);
    }
    paint();
  });
  on($("measure-stop"), "click", () => {
    pause();
    clock?.seek(0, performance.now());
    paint();
  });
  on($("measure-seek"), "input", () => {
    clock?.seek(Number($("measure-seek").value), performance.now());
    paint();
  });
  on($("measure-signal"), "change", () => {
    cache = {};
    paint();
  });
  on(window, "resize", () => {
    cache = {};
    paint();
  });
  on(document, "visibilitychange", () => {
    if (document.hidden) pause();
  });
  on($("measure-gate"), "click", async () => {
    try {
      const model =
        $("measure-model-design").value === "active"
          ? state.design
          : state.library.find((r) => r.id === $("measure-model-design").value)
              ?.design;
      const r = await api(
        "/api/workbench/v2/measurements/comparison-readiness",
        {
          recording: frozenCase?.first || prepared(),
          vehicle: model,
          interval_start_s: Number($("measure-start").value),
          interval_end_s: Number($("measure-end").value),
        },
      );
      $("measure-model-result").innerHTML =
        `<strong>${esc(r.status)} · model residuals unavailable</strong><ul>${r.missing_inputs.map((item) => `<li>${esc(item)}</li>`).join("")}</ul><p>${esc(r.explanation)}</p><details><summary>Coverage, alignment and exact model snapshot</summary><pre>${esc(JSON.stringify(r, null, 2))}</pre></details>`;
    } catch (e) {
      $("measure-model-result").textContent = e.message;
    }
  });
  for (const b of root.querySelectorAll("[data-measure-format]"))
    on(b, "click", async () => {
      try {
        const format = b.dataset.measureFormat;
        if (format === "json") {
          download("veus-measurements.json", JSON.stringify(result, null, 2));
          return;
        }
        const r = await api("/api/workbench/v2/measurements/case-study", {
          ...frozenCase,
          format,
        });
        download(
          "veus-measurements." + format,
          r.content,
          format === "html" ? "text/html" : "text/csv",
        );
      } catch (e) {
        $("measure-status").textContent = "Export unavailable: " + e.message;
      }
    });
  on(root, "input", (e) => {
    if (
      e.target.matches(
        "[data-map],[data-unit],#measure-sign,#measure-evidence,#measure-gap,#measure-name,#measure-url,#measure-licence,#measure-origin",
      )
    )
      $("measure-confirm").checked = false;
  });
  let assessment = null;
  on($("validation-assess"), "click", async () => {
    assessment = null;
    delete window.VEUSValidationAssessment;
    $("validation-export").disabled = true;
    $("validation-html").disabled = true;
    $("validation-assess").disabled = true;
    $("validation-result").textContent =
      "Auditing the selected recording and frozen model inputs…";
    try {
      const calibration = $("validation-calibration").value.trim(),
        evaluation = $("validation-evaluation").value.trim();
      const model =
        $("validation-design").value === "active"
          ? state.design
          : state.library.find((r) => r.id === $("validation-design").value)
              ?.design;
      if (!model)
        throw Error(
          "Select a saved model design here, or create an active design in Design Studio first.",
        );
      const r = await api(
        "/api/workbench/v2/measurements/validation-readiness",
        {
          recording: frozenCase?.first || prepared(),
          vehicle: model,
          efficiency_model: $("validation-model").value || null,
          calibration_interval_s: calibration
            ? calibration.split(",").map(Number)
            : null,
          evaluation_interval_s: evaluation
            ? evaluation.split(",").map(Number)
            : null,
        },
      );
      assessment = r;
      window.VEUSValidationAssessment = r;
      $("validation-result").innerHTML =
        `<strong>${esc(r.status)} · no calibration performed</strong><p>Frozen model: ${esc(r.request.vehicle.name)} · ${esc(r.powertrain_model_version)}</p><p>${esc(r.conclusion)}</p><table><tr><th>Signal / boundary</th><th>Evidence status</th><th>Missing evidence</th></tr>${r.checks.map((c) => `<tr><td>${esc(c.item)}</td><td>${esc(c.status)}</td><td>${esc(c.missing_evidence)}</td></tr>`).join("")}</table><details><summary>Parameter identifiability, split, provenance and exact model snapshot</summary><pre>${esc(JSON.stringify(r, null, 2))}</pre></details>`;
      $("validation-export").disabled = false;
      $("validation-html").disabled = false;
    } catch (e) {
      if (!life.signal.aborted && e.name !== "AbortError")
        $("validation-result").textContent =
          "Assessment unavailable: " + e.message;
    } finally {
      if (!life.signal.aborted) $("validation-assess").disabled = false;
    }
  });
  on($("validation-export"), "click", () =>
    download(
      "veus-validation-readiness.json",
      JSON.stringify(assessment, null, 2),
    ),
  );
  on($("validation-html"), "click", async () => {
    try {
      const r = await api(
        "/api/workbench/v2/measurements/validation-readiness/export",
        { result: assessment, format: "html" },
      );
      download(r.filename, r.content, r.media_type);
    } catch (e) {
      $("validation-result").textContent = e.message;
    }
  });
  $("measurement-recording").value = "ved-10-1561-full";
  await choose();
  return () => {
    pause();
    life.abort();
    request?.abort();
    cache = {};
    delete window.VEUSMeasurements;
    delete window.VEUSMeasurementReplay;
    delete window.VEUSValidationAssessment;
  };
}

// Sequential milestone acceptance. Phase-specific switches permit focused checkpoint runs.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright"),
  fs = require("node:fs"),
  assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
      viewport: { width: 1440, height: 1100 },
    }),
    page = await context.newPage(),
    errors = [];
  const base = process.env.VEUS_URL || "http://127.0.0.1:8770",
    out = process.env.VEUS_SCREENSHOTS || "/tmp/veus25-workflow";
  fs.mkdirSync(out, { recursive: true });
  const presets = (
    await (await context.request.get(base + "/api/workbench/v2/presets")).json()
  ).presets;
  await page.addInitScript(
    (p) =>
      localStorage.setItem(
        "veus.design-library.v2",
        JSON.stringify({
          schema_version: 1,
          active_id: "s1",
          records: p.map((v) => ({ id: v.id, design: v.design })),
        }),
      ),
    presets,
  );
  require("./advanced-disclosure.cjs")(page);
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base + "/?workspace=design");
  await page.locator("#insights-panel summary").click();
  await page.check("#insights-ack");
  await page.fill("#insights-distance", "50");
  await page.fill("#insights-tariff", ".4");
  await page.fill("#insights-efficiency", ".9");
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/workbench/v2/insights") &&
        r.request().method() === "POST",
    ),
    page.click("#insights-run"),
  ]);
  assert.equal(response.status(), 200, await response.text());
  const result = await response.json();
  await page.waitForFunction(() => window.VEUSInsights?.metrics);
  assert.equal(result.request.vehicle.appearance, "sedan");
  const m = result.metrics;
  assert(
    Math.abs(
      m.daily_battery_energy_kwh.value -
        (50 * m.modelled_consumption_kwh_100km.value) / 100,
    ) < 1e-10,
  );
  assert(
    Math.abs(
      m.daily_electricity_cost_eur.value -
        (m.daily_battery_energy_kwh.value / 0.9) * 0.4,
    ) < 1e-10,
  );
  const hash = result.insights_sha256;
  await page.fill("#design-name", "Changed after frozen analysis");
  assert(
    (await page.locator("#insights-status").innerText()).includes("frozen"),
  );
  assert.equal(await page.evaluate(() => VEUSInsights.insights_sha256), hash);
  const [file] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#insights-export"),
  ]);
  await file.saveAs(out + "/insights.json");
  assert.equal(
    JSON.parse(fs.readFileSync(out + "/insights.json", "utf8")).insights_sha256,
    hash,
  );
  await page.click("#insights-presets");
  await page.waitForFunction(() => window.VEUSInsights?.results?.length === 3);
  assert.equal(
    await page.locator("#insights-charts .analysis-chart").count(),
    3,
  );
  for (const width of [1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      "Insights overflow " + width,
    );
  }
  await page.setViewportSize({ width: 1440, height: 1100 });
  if (process.env.VEUS_CAPTURE === "1") {
    await page.locator("#engineering-insights").scrollIntoViewIfNeeded();
    await page.screenshot({ path: out + "/engineering-insights.png" });
  }
  if (process.env.VEUS_PHASE !== "A") {
    await page.locator("#analysis-panel summary").click();
    await page.check("#analysis-ack");
    await page.selectOption("#analysis-baseline", "s1");
    await page.selectOption("#analysis-modified", "r1");
    const [compare] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/design-analysis") &&
          r.request().method() === "POST",
      ),
      page.click("#analysis-run"),
    ]);
    assert.equal(compare.status(), 200, await compare.text());
    await page.waitForFunction(
      () => window.VEUSDesignAnalysis?.rows?.length === 2,
    );
    assert.equal(
      await page.evaluate(() => VEUSDesignAnalysis.matched_conditions),
      true,
    );
    if (process.env.VEUS_CAPTURE === "1") {
      await page.locator("#controlled-analysis").scrollIntoViewIfNeeded();
      await page.screenshot({ path: out + "/design-comparison.png" });
    }
    await page.selectOption("#analysis-kind", "sensitivity");
    await page.fill("#analysis-values", ".22,.3");
    const [sweep] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/design-analysis") &&
          r.request().method() === "POST",
      ),
      page.click("#analysis-run"),
    ]);
    assert.equal(sweep.status(), 200, await sweep.text());
    await page.waitForFunction(() => VEUSDesignAnalysis.rows.length === 3);
    const study = await page.evaluate(() => VEUSDesignAnalysis);
    assert(
      study.rows[1].analysis.metrics.modelled_consumption_kwh_100km.value <
        study.rows[2].analysis.metrics.modelled_consumption_kwh_100km.value,
    );
    for (const format of ["json", "csv", "html"]) {
      const [d] = await Promise.all([
        page.waitForEvent("download"),
        page.click('[data-analysis-format="' + format + '"]'),
      ]);
      await d.saveAs(out + "/study." + format);
    }
    const saved = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("veus.design-library.v2")),
    );
    assert.equal(saved.records.length, 3);
    assert.equal(saved.records[0].design.body.drag_coefficient, 0.25);
    fs.writeFileSync(
      out + "/checkpoint-B-browser.json",
      JSON.stringify(
        {
          status: "PASS",
          matched_comparison: true,
          sensitivity: true,
          exports: ["json", "csv", "html"],
          saved_designs_intact: true,
          study_sha256: study.study_sha256,
        },
        null,
        2,
      ),
    );
  }
  if (!["A", "B"].includes(process.env.VEUS_PHASE)) {
    await page.click("#tab-measurements");
    await page.locator("#measure-investigate").waitFor();
    await page.waitForFunction(() =>
      document
        .getElementById("measurement-summary")
        .textContent.includes("534"),
    );
    await page.check("#measure-confirm");
    await page.selectOption("#measure-second", "ved-10-1567-full");
    await page.check("#measure-second-confirm");
    const [measured] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/measurements/case-study") &&
          r.request().method() === "POST",
      ),
      page.click("#measure-investigate"),
    ]);
    assert.equal(measured.status(), 200, await measured.text());
    await page.waitForFunction(
      () => window.VEUSMeasurements?.recordings?.length === 2,
    );
    const recording = await page.evaluate(() => VEUSMeasurements);
    assert.equal(recording.recordings[0].analysis.time_s.length, 534);
    assert.equal(recording.recordings[1].analysis.time_s.length, 367);
    assert.equal(
      recording.recordings[0].metrics.electrical_energy_used_wh.value,
      null,
    );
    await page.locator("#measure-seek").evaluate((e) => {
      e.value = 12.3;
      e.dispatchEvent(new Event("input"));
    });
    for (const id of ["measure-speed", "measure-electrical"])
      assert.equal(
        await page.locator("#" + id).getAttribute("data-cursor-time"),
        "12.300000",
      );
    await page.selectOption("#measure-signal", "electrical_power_w");
    assert.equal(
      await page.locator("#measure-electrical").getAttribute("data-available"),
      "false",
    );
    await page.selectOption("#measure-signal", "battery_current_a");
    assert.equal(
      await page.locator("#measure-electrical").getAttribute("data-available"),
      "true",
    );
    await page.click("#measure-play");
    await page.waitForTimeout(120);
    await page.click("#measure-play");
    assert.equal(
      await page.evaluate(() => VEUSMeasurementReplay.framePending),
      false,
    );
    const event = await page
      .locator("#measure-event option")
      .nth(1)
      .getAttribute("value");
    const [selectedEvent] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/measurements/case-study") &&
          r.request().method() === "POST",
      ),
      page.selectOption("#measure-event", event),
    ]);
    assert.equal(selectedEvent.status(), 200, await selectedEvent.text());
    await page.waitForFunction(
      (index) =>
        VEUSMeasurements.recordings[0].selected_event_indices.length === 1 &&
        VEUSMeasurements.recordings[0].selected_event_indices[0] ===
          Number(index),
      event,
    );
    await page.locator("#measure-model summary").click();
    await page.click("#measure-gate");
    await page.waitForFunction(() =>
      document
        .getElementById("measure-model-result")
        .textContent.includes("INCONCLUSIVE"),
    );
    assert(
      (await page.locator("#measure-model-result").innerText()).includes(
        "polarity",
      ),
    );
    for (const format of ["json", "csv", "html"]) {
      const [d] = await Promise.all([
        page.waitForEvent("download"),
        page.click('[data-measure-format="' + format + '"]'),
      ]);
      await d.saveAs(out + "/measurements." + format);
    }
    const frozen = JSON.parse(
      fs.readFileSync(out + "/measurements.json", "utf8"),
    );
    assert.equal(frozen.recordings[0].selected_event_indices[0], Number(event));
    assert(
      fs
        .readFileSync(out + "/measurements.csv", "utf8")
        .includes(recording.recordings[0].source_sha256),
    );
    if (process.env.VEUS_CAPTURE === "1") {
      await page.locator(".measure-dashboard").scrollIntoViewIfNeeded();
      await page.screenshot({ path: out + "/measurements-investigation.png" });
    }
    // Real raw VED CSV + original JSON configuration import, same source hash and sample count.
    await page.locator("#measure-import summary").click();
    await page
      .locator("#measure-file")
      .setInputFiles("datasets/ved/ved-10-1561-full.csv");
    await page.waitForFunction(
      () =>
        document.getElementById("measurement-recording").value === "imported",
    );
    await page
      .locator("#measure-config")
      .setInputFiles("examples/replay/ved-10-1561-full.json");
    await page.waitForFunction(
      () =>
        document.querySelector('[data-map="time_s"]').value === "Timestamp(ms)",
    );
    await page.check("#measure-confirm");
    await page.selectOption("#measure-second", "");
    const [imported] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/measurements/case-study") &&
          r.request().method() === "POST",
      ),
      page.click("#measure-investigate"),
    ]);
    assert.equal(imported.status(), 200, await imported.text());
    const data = await imported.json();
    assert.equal(
      data.recordings[0].source_sha256,
      recording.recordings[0].source_sha256,
    );
    assert.equal(data.recordings[0].analysis.time_s.length, 534);
    for (const width of [1024, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
        "Measurements overflow " + width,
      );
    }
    await page.click("#tab-anatomy");
    await page.waitForTimeout(150);
    assert.equal(await page.evaluate(() => !!window.VEUSMeasurements), false);
    fs.writeFileSync(
      out + "/checkpoint-C-browser.json",
      JSON.stringify(
        {
          status: "PASS",
          real_ved_import: true,
          provenance_preserved: true,
          unknown_polarity_gate: true,
          source_samples: [534, 367],
          event_indices: true,
          shared_cursor: true,
          formats: ["json", "csv", "html"],
          gated_model_comparison: true,
          inactive_cleanup: true,
        },
        null,
        2,
      ),
    );
  }
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    out + "/checkpoint-A-browser.json",
    JSON.stringify(
      {
        status: "PASS",
        vehicle: "s1",
        snapshot_hash: hash,
        cost_reference: true,
        three_default_charts: true,
        saved_design_stale: true,
        export: true,
        widths: [1440, 1024, 390],
        page_errors: errors,
      },
      null,
      2,
    ),
  );
  await browser.close();
  console.log("Engineering workflow checkpoint A PASS");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

// VEUS2.6 focused gates, then final combined regression. Exactly two optional captures.
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
    out = process.env.VEUS_SCREENSHOTS || "/tmp/veus26";
  fs.mkdirSync(out, { recursive: true });
  const presets = (
    await (await context.request.get(base + "/api/workbench/v2/presets")).json()
  ).presets;
  const vehicle = presets[0].design;
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
  await page.goto(base + "/?workspace=simulation");
  await page.locator("#lab-config").evaluate((e) => (e.open = true));
  await page.locator("#lab-assumptions").evaluate((e) => (e.open = true));
  for (const c of await page.locator(".lab-ack").all()) await c.check();
  await page
    .getByText("Numerical and braking settings", { exact: true })
    .click();
  await page.fill("#lab-duration", "2");
  await page.fill("#lab-dt", ".05");
  async function run() {
    const [r] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
      ),
      page.click("#lab-run"),
    ]);
    assert.equal(r.status(), 200, await r.text());
    return await r.json();
  }
  const legacy = await run();
  await page.selectOption("#lab-efficiency-model", "illustrative_map");
  const mapped = await run();
  assert.equal(mapped.request.efficiency_model, "illustrative_map");
  assert.notEqual(legacy.run_sha256, mapped.run_sha256);
  assert(mapped.summary.maximum_energy_balance_error_j < 0.01);
  await page.selectOption("#lab-efficiency-model", "");
  assert.equal((await run()).run_sha256, legacy.run_sha256);
  await page.locator("#lab-model-comparison summary").first().click();
  const [c] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/powertrain-comparison")),
    page.click("#motor-map-compare"),
  ]);
  assert.equal(c.status(), 200, await c.text());
  const comparison = await c.json();
  await page.waitForFunction(
    () => window.VEUSMotorComparison?.comparison_sha256,
  );
  assert.deepEqual(
    comparison.legacy.request.vehicle,
    comparison.mapped.request.vehicle,
  );
  assert.equal(
    comparison.legacy.request.profile_id,
    comparison.mapped.request.profile_id,
  );
  fs.writeFileSync(
    out + "/model-comparison.json",
    JSON.stringify(comparison, null, 2),
  );
  if (process.env.VEUS_STAGE !== "A") {
    await page.click("#tab-measurements");
    await page.locator("#measure-investigate").waitFor();
    await page.waitForFunction(() =>
      document
        .getElementById("measurement-summary")
        .textContent.includes("534"),
    );
    await page.check("#measure-confirm");
    await page.click("#measure-investigate");
    await page.waitForFunction(() => window.VEUSMeasurements?.recordings);
    await page.locator("#measure-validation summary").first().click();
    await page.fill("#validation-calibration", "0,150");
    await page.fill("#validation-evaluation", "200,350");
    await page.click("#validation-assess");
    await page.waitForFunction(
      () => window.VEUSValidationAssessment?.assessment_sha256,
    );
    const assessment = await page.evaluate(() => VEUSValidationAssessment);
    assert.equal(assessment.status, "INCONCLUSIVE");
    assert.equal(assessment.metrics, null);
    assert(
      assessment.checks.some(
        (c) => c.item === "current_polarity" && c.status === "UNAVAILABLE",
      ),
    );
    for (const id of ["validation-export", "validation-html"]) {
      const [d] = await Promise.all([
        page.waitForEvent("download"),
        page.click("#" + id),
      ]);
      await d.saveAs(
        out +
          "/" +
          (id === "validation-export" ? "validation.json" : "validation.html"),
      );
    }
    assert(
      fs
        .readFileSync(out + "/validation.html", "utf8")
        .includes("INCONCLUSIVE"),
    );
    fs.writeFileSync(
      out + "/checkpoint-B-browser.json",
      JSON.stringify(
        {
          status: "PASS",
          real_ved_readiness: true,
          calibration_blockers: true,
          no_fake_residuals: true,
          heldout_intervals: true,
          reports: ["json", "html"],
        },
        null,
        2,
      ),
    );
  }
  if (!["A", "B"].includes(process.env.VEUS_STAGE)) {
    await page.click("#tab-simulation");
    await page.locator("#lab-scenarios-mode").waitFor();
    await page.click('[data-kind="acceleration"]');
    await page.locator("#lab-config").evaluate((e) => (e.open = true));
    await page.locator("#lab-assumptions").evaluate((e) => (e.open = true));
    for (const c of await page.locator(".lab-ack").all()) await c.check();
    await page
      .getByText("Numerical and braking settings", { exact: true })
      .click();
    await page.fill("#lab-duration", "30");
    await page.fill("#lab-dt", ".05");
    const result = await run();
    const outRows = result.trace.filter((r) => {
      const gap = 70 + 8 * r.time_s - r.position_m;
      return gap < 43 && gap > 20;
    });
    assert(outRows.length);
    const point = outRows[Math.floor(outRows.length / 2)];
    const seek = async (time) =>
      page.locator("#lab-seek").evaluate((e, t) => {
        e.value = t;
        e.dispatchEvent(new Event("input"));
      }, time);
    await seek(point.time_s);
    assert.equal(
      await page.locator("#lab-scene-svg").getAttribute("data-stage"),
      "lane_change_out",
    );
    const pose = await page.locator("#lab-hero-car").getAttribute("transform");
    const angle = Number(
      await page.locator("#lab-scene-svg").getAttribute("data-wheel-angle"),
    );
    assert(
      Math.abs(
        angle -
          ((point.position_m / vehicle.body.wheel_radius_m) * 180) / Math.PI,
      ) < 1e-5,
    );
    await seek(15);
    await seek(point.time_s);
    assert.equal(
      await page.locator("#lab-hero-car").getAttribute("transform"),
      pose,
    );
    await page.locator("#lab-config").evaluate((e) => (e.open = false));
    if (process.env.VEUS_CAPTURE === "1") {
      await page.locator(".lab-instrument").scrollIntoViewIfNeeded();
      await page.screenshot({ path: out + "/overtaking-lane-change.png" });
    }
    await seek(4);
    assert.equal(
      Number(
        await page
          .locator("#lab-scene-svg")
          .getAttribute("data-traffic-position-m"),
      ),
      102,
    );
    if (process.env.VEUS_CAPTURE === "1") {
      await page.locator(".lab-instrument").scrollIntoViewIfNeeded();
      await page.screenshot({ path: out + "/road-with-traffic.png" });
    }
    await page.getByText("Playback options", { exact: true }).click();
    await page.selectOption("#lab-playback-rate", "2");
    const before = await page.evaluate(() => VEUSLab.time);
    await page.click("#lab-play");
    await page.waitForTimeout(180);
    await page.click("#lab-play");
    assert((await page.evaluate(() => VEUSLab.time)) > before + 0.2);
    const paused = await page
      .locator("#lab-hero-car")
      .getAttribute("transform");
    await page.waitForTimeout(100);
    assert.equal(
      await page.locator("#lab-hero-car").getAttribute("transform"),
      paused,
    );
    await page.click("#lab-stop");
    assert.equal(await page.evaluate(() => VEUSLab.time), 0);
    assert.equal(
      await page.locator("#lab-scene-svg").getAttribute("data-wheel-angle"),
      "0",
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
    await seek(point.time_s);
    assert.equal(
      await page.locator("#lab-scene-svg").getAttribute("data-reduced-motion"),
      "true",
    );
    assert.equal(
      await page.locator("#lab-scene-svg").getAttribute("data-wheel-angle"),
      "0",
    );
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await seek(30);
    assert.equal(
      await page.locator("#lab-scene-svg").getAttribute("data-stage"),
      "continue",
    );
    assert.equal(await page.evaluate(() => VEUSLab.framePending), false);
    for (const width of [1024, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
    }
    await page.click("#tab-anatomy");
    await page.waitForTimeout(100);
    assert.equal(await page.evaluate(() => !!window.VEUSLab), false);
    fs.writeFileSync(
      out + "/checkpoint-C-browser.json",
      JSON.stringify(
        {
          status: "PASS",
          deterministic_seek: true,
          wheel_distance: true,
          traffic_own_speed: true,
          lane_change: true,
          playback_rate: true,
          stop_reset: true,
          reduced_motion: true,
          mobile: true,
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
        legacy_hash_unchanged: true,
        optional_map: true,
        same_design_cycle: true,
        comparison_sha256: comparison.comparison_sha256,
        page_errors: errors,
      },
      null,
      2,
    ),
  );
  await browser.close();
  console.log("Advanced workflow PASS");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

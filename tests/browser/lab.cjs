// Optional real browser verification of executed Lab results and shared playback.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs"),
  assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
      viewport: { width: 1366, height: 768 },
    }),
    page = await context.newPage(),
    errors = [],
    runs = [],
    sockets = [],
    requests = [];
  const base = process.env.VEUS_URL || "http://127.0.0.1:8770",
    out = process.env.VEUS_SCREENSHOTS || "/tmp/veus-lab-screens";
  fs.mkdirSync(out, { recursive: true });
  const response = await context.request.get(base + "/api/workbench/v2/design");
  assert.equal(response.status(), 200);
  const design = await response.json();
  design.name = "Lab non-default vehicle";
  design.body.mass_excluding_components_kg = 1234;
  design.body.drag_coefficient = 0.31;
  design.body.wheel_radius_m = 0.34;
  design.gearbox.reduction_ratio = 8.4;
  const second = structuredClone(design);
  second.name = "Different active design";
  second.body.mass_excluding_components_kg = 1400;
  second.battery.discharge_limit_a = 5;
  await page.addInitScript(
    ({ design, second }) =>
      localStorage.setItem(
        "veus.design-library.v2",
        JSON.stringify({
          schema_version: 1,
          active_id: "lab-source",
          records: [
            { id: "lab-source", design },
            { id: "lab-second", design: second },
          ],
        }),
      ),
    { design, second },
  );
  require("./advanced-disclosure.cjs")(page);
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("websocket", (s) => sockets.push(s.url()));
  page.on("request", (r) => {
    requests.push(r.url());
    if (r.url().endsWith("/api/lab/run")) runs.push(r.postDataJSON());
  });
  await page.goto(base + "/?workspace=simulation");
  await page.locator("#lab-scenarios-mode").waitFor();
  await page.locator("#lab-config summary").first().click();
  await page.locator("#lab-assumptions summary").click();
  for (const c of await page.locator(".lab-ack").all()) await c.check();
  async function run(kind) {
    await page.click(`[data-kind="${kind}"]`);
    await page.locator("#lab-config").evaluate((e) => (e.open = true));
    await page.fill("#lab-duration", "3");
    await page.fill("#lab-dt", ".05");
    await page.fill("#lab-initial", kind === "acceleration" ? "0" : "36");
    if (!["braking", "coast"].includes(kind))
      await page.fill("#lab-target", "72");
    const old = await page.evaluate(
      () => window.VEUSLab?.result?.run_sha256 ?? null,
    );
    const [response] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
      ),
      page.click("#lab-run"),
    ]);
    const body = await response.json();
    assert.equal(response.status(), 200, JSON.stringify(body));
    await page.waitForFunction(
      (old) =>
        window.VEUSLab?.result?.run_sha256 &&
        window.VEUSLab.result.run_sha256 !== old,
      old,
    );
    const result = await page.evaluate(() => VEUSLab.result);
    assert.equal(result.vehicle.name, design.name);
    assert.equal(result.vehicle.body.drag_coefficient, 0.31);
    assert.equal(result.vehicle.body.wheel_radius_m, 0.34);
    assert.equal(result.vehicle.gearbox.reduction_ratio, 8.4);
    assert(result.trace.length > 2);
    return result;
  }
  await page
    .getByText("Numerical and braking settings", { exact: true })
    .click();
  const results = {};
  for (const kind of [
    "constant_speed",
    "acceleration",
    "braking",
    "gradient",
    "coast",
  ]) {
    const result = await run(kind);
    results[kind] = result.run_sha256;
    assert.equal(result.experiment.kind, kind);
    await page.locator("#lab-seek").evaluate((e) => {
      e.value = 1;
      e.dispatchEvent(new Event("input"));
    });
    const row = result.trace.find((r) => Math.abs(r.time_s - 1) < 1e-8);
    const fill = Number(
      await page.locator("#lab-battery-fill").getAttribute("width"),
    );
    assert(
      Math.abs(fill - 116 * row.soc) < 1e-8,
      "Battery fill represents actual SOC",
    );
    assert(
      Math.abs(
        Number(
          await page.locator("#lab-battery").getAttribute("data-power-w"),
        ) - row.battery_power_w,
      ) < 1e-6,
    );
    if (kind === "braking") {
      assert(row.battery_power_w < 0);
      assert.equal(
        await page.locator("#lab-battery").getAttribute("data-state"),
        "regen",
      );
      assert.equal(
        await page.locator("#lab-energy-flow").getAttribute("data-direction"),
        "in",
      );
    }
    if (kind === "coast")
      assert.equal(
        await page.locator("#lab-battery").getAttribute("data-state"),
        "idle",
      );
    for (const id of ["lab-plot", "lab-power-plot", "lab-soc-plot"])
      assert.equal(
        await page.locator("#" + id).getAttribute("data-cursor-time"),
        "1.000000",
      );
    const arc = await page
      .locator("#lab-speed-arc")
      .evaluate((e) => getComputedStyle(e).strokeDasharray);
    if (row.speed_ms > 0)
      assert(
        parseFloat(arc) > 0,
        "Computed gauge arc follows nonzero achieved speed",
      );
    const gauge = await page.locator("#lab-speedometer").boundingBox(),
      panel = await page.locator(".lab-speed-panel").boundingBox();
    assert(
      gauge.x >= panel.x - 1 &&
        gauge.x + gauge.width <= panel.x + panel.width + 1,
    );
    if (
      ["constant_speed", "braking", "gradient"].includes(kind) &&
      process.env.VEUS_CAPTURE !== "0"
    ) {
      // Representative captures use unchanged scenario defaults, not the short golden-test window.
      await page.click(`[data-kind="${kind}"]`);
      const previous = await page.evaluate(() => VEUSLab.result.run_sha256);
      const [captureRun] = await Promise.all([
        page.waitForResponse(
          (r) =>
            r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
        ),
        page.click("#lab-run"),
      ]);
      assert.equal(captureRun.status(), 200, await captureRun.text());
      await page.waitForFunction(
        (hash) => VEUSLab.result.run_sha256 !== hash,
        previous,
      );
      await page.locator("#lab-seek").evaluate((e) => {
        e.value = 2;
        e.dispatchEvent(new Event("input"));
      });
      if (kind === "braking") await page.click("#theme-toggle");
      await page.locator("#lab-config").evaluate((e) => (e.open = false));
      await page.evaluate(() => {
        document.activeElement?.blur();
        scrollTo(0, 0);
      });
      await page.setViewportSize({ width: 1366, height: 1200 });
      await page.screenshot({
        path:
          out +
          "/" +
          {
            constant_speed: "highway-cruising",
            braking: "traffic-light-braking",
            gradient: "mountain-climb",
          }[kind] +
          ".png",
        fullPage: false,
      });
    }
  }
  assert.deepEqual(
    results,
    JSON.parse(
      fs.readFileSync(
        __dirname + "/../../docs/veus2/evidence-2.3/lab-browser.json",
        "utf8",
      ),
    ).experiments,
    "Frozen five-experiment outputs equal VEUS 2.3 baseline",
  );
  await page.setViewportSize({ width: 1366, height: 768 });
  const calls = runs.length;
  await page.locator("#lab-seek").evaluate((e) => {
    e.value = 1.25;
    e.dispatchEvent(new Event("input"));
  });
  assert.equal(
    await page.locator("#lab-plot").getAttribute("data-cursor-time"),
    "1.250000",
  );
  for (const id of ["lab-power-plot", "lab-soc-plot"])
    assert.equal(
      await page.locator("#" + id).getAttribute("data-cursor-time"),
      "1.250000",
    );
  assert.equal(await page.evaluate(() => VEUSLab.time), 1.25);

  await page.click("#lab-play");
  await page.waitForTimeout(220);
  await page.click("#lab-play");
  assert((await page.evaluate(() => VEUSLab.time)) > 1.4);
  assert.equal(runs.length, calls, "Replay never recalculates a simulation");
  await page.click("#lab-stop");
  assert.equal(await page.evaluate(() => VEUSLab.time), 0);
  assert.equal(await page.evaluate(() => VEUSLab.playing), false);
  assert.equal(
    await page.locator("#lab-scene-svg").getAttribute("data-position-m"),
    "0",
  );
  await page.locator("#lab-seek").evaluate((e) => {
    e.value = 3;
    e.dispatchEvent(new Event("input"));
  });
  const endScene = await page
    .locator("#lab-scene-svg")
    .getAttribute("data-position-m");
  await page.waitForTimeout(100);
  assert.equal(
    await page.locator("#lab-scene-svg").getAttribute("data-position-m"),
    endScene,
  );
  await page.locator("#lab-seek").evaluate((e) => {
    e.value = 2.95;
    e.dispatchEvent(new Event("input"));
  });
  await page.click("#lab-play");
  await page.waitForFunction(
    () => VEUSLab.time === 3 && !VEUSLab.playing && !VEUSLab.framePending,
  );
  const completedScene = await page
    .locator("#lab-scene-svg")
    .getAttribute("data-position-m");
  await page.waitForTimeout(120);
  assert.equal(
    await page.locator("#lab-scene-svg").getAttribute("data-position-m"),
    completedScene,
  );
  const seekTiming = [];
  for (let i = 0; i < 6; i++) {
    const elapsed = await page.evaluate(
      (i) =>
        new Promise((resolve) => {
          const start = performance.now(),
            e = document.getElementById("lab-seek");
          e.value = String(0.1 + i * 0.3);
          e.dispatchEvent(new Event("input"));
          requestAnimationFrame(() => resolve(performance.now() - start));
        }),
      i,
    );
    if (i) seekTiming.push(elapsed);
  }
  const idleRequests = requests.length;
  await page.waitForTimeout(350);
  assert.equal(requests.length, idleRequests, "Paused Lab does not poll");
  assert.equal(await page.evaluate(() => VEUSLab.framePending), false);
  const jsHeap = await page.evaluate(
    () => performance.memory?.usedJSHeapSize ?? null,
  );
  const sha = await page.evaluate(() => VEUSLab.result.run_sha256),
    paused = await page.evaluate(() => VEUSLab.time);
  await page.selectOption("#lab-vehicle", "lab-second");
  assert.equal(
    await page.evaluate(() => VEUSLab.result.vehicle.name),
    design.name,
  );
  assert(
    (await page.locator("#lab-frozen-note").innerText()).includes("differ"),
  );
  await page.click('[data-key="anatomy"]');
  await page.waitForTimeout(200);
  assert.equal(await page.evaluate(() => !!window.VEUSLab), false);
  assert.equal(runs.length, calls);
  await page.click('[data-key="simulation"]');
  await page.locator("#lab-play").waitFor();
  assert.equal(await page.evaluate(() => VEUSLab.result.run_sha256), sha);
  assert.equal(await page.evaluate(() => VEUSLab.playing), false);
  assert.equal(await page.evaluate(() => VEUSLab.framePending), false);
  assert(Math.abs((await page.evaluate(() => VEUSLab.time)) - paused) < 0.02);
  // Restore the saved non-default vehicle without relabelling frozen prior results.
  await page.locator("#lab-config").evaluate((e) => (e.open = true));
  await page.locator("#lab-assumptions").evaluate((e) => (e.open = true));
  for (const c of await page.locator(".lab-ack").all()) await c.check();
  await page.selectOption("#lab-vehicle", "lab-source");
  for (const [id, file] of [
    ["lab-json", "result.json"],
    ["lab-csv", "trace.csv"],
    ["lab-html", "report.html"],
  ]) {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.click("#" + id),
    ]);
    await download.saveAs(out + "/" + file);
  }
  assert.equal(
    JSON.parse(fs.readFileSync(out + "/result.json", "utf8")).run_sha256,
    sha,
  );
  assert(fs.readFileSync(out + "/trace.csv", "utf8").includes("time_s"));
  assert(fs.readFileSync(out + "/report.html", "utf8").includes("Lab"));
  await page.locator("#lab-seek").evaluate((e) => {
    e.value = 1.5;
    e.dispatchEvent(new Event("input"));
  });
  await page.evaluate(() => {
    document.activeElement?.blur();
    scrollTo(0, 0);
  });
  // Profiles are loaded only in Lab. Official source duration is not silently shortened.
  await page.click("#lab-profile-mode");
  await page.waitForFunction(() =>
    document.querySelector('#lab-profile option[value="udds"]'),
  );
  await page.selectOption("#lab-profile", "udds");
  await page.waitForFunction(
    () => Number(document.getElementById("lab-duration").value) === 1369,
  );
  assert(Number(await page.locator("#lab-dt").inputValue()) >= 0.1);
  // This source profile is time-only: the central input view must not invent a map.
  await page.selectOption("#lab-profile", "constant-reference");
  await page.waitForFunction(
    () => Number(document.getElementById("lab-duration").value) === 120,
  );
  const [profileResponse] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
    ),
    page.click("#lab-run"),
  ]);
  assert.equal(profileResponse.status(), 200, await profileResponse.text());
  await page.waitForFunction(
    () => VEUSLab.result?.experiment.kind === "profile",
  );
  await page.selectOption("#lab-visual-mode", "inputs");
  assert.equal(
    await page.locator("#lab-route-plot").getAttribute("data-geometry"),
    "false",
  );
  await page.selectOption("#lab-route", "synthetic-local-loop");
  await page.waitForFunction(() =>
    document
      .getElementById("lab-input-source")
      .textContent.includes("local-loop"),
  );
  // The new route selection cannot replace the frozen old result geometry before a new run.
  assert.equal(
    await page.locator("#lab-route-plot").getAttribute("data-geometry"),
    "false",
  );
  const beforeRoute = await page.evaluate(() => VEUSLab.result.run_sha256);
  const [routeRun] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
    ),
    page.click("#lab-run"),
  ]);
  assert.equal(routeRun.status(), 200, await routeRun.text());
  await page.waitForFunction(
    (hash) => VEUSLab.result?.run_sha256 !== hash,
    beforeRoute,
  );
  assert.equal(
    await page.locator("#lab-route-plot").getAttribute("data-geometry"),
    "true",
  );
  await page.selectOption("#lab-route-overlay", "elevation_m");
  await page.locator("#lab-seek").evaluate((e) => {
    e.value = 60;
    e.dispatchEvent(new Event("input"));
  });
  await page.evaluate(() => {
    document.activeElement?.blur();
    scrollTo(0, 0);
  });
  // Explicit CSV import mapping: time-only profile and distance-indexed geometry are separate contracts.
  const profileCSV = out + "/custom-profile.csv";
  fs.writeFileSync(profileCSV, "time_s,speed_ms\n0,0\n1,5\n2,0\n");
  await page
    .locator("#lab-profile-controls details")
    .filter({ hasText: "Import Driving Data" })
    .locator("summary")
    .first()
    .click();
  await page.selectOption("#lab-route", "");
  await page.locator("#lab-import-file").setInputFiles(profileCSV);
  await page.fill("#lab-import-name", "Browser custom speed source");
  await page.check("#lab-import-confirm");
  const [importedProfile] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/lab/import/profile")),
    page.click("#lab-import"),
  ]);
  assert.equal(importedProfile.status(), 200, await importedProfile.text());
  await page.waitForFunction(
    () => Number(document.getElementById("lab-duration").value) === 2,
  );
  const [customRun] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
    ),
    page.click("#lab-run"),
  ]);
  assert.equal(
    customRun.status(),
    422,
    "Missing profile gradient must require an explicit assumption",
  );
  assert((await customRun.text()).includes("experiment_constant_assumption"));
  await page.selectOption(
    "#lab-grade-policy",
    "experiment_constant_assumption",
  );
  const [flatAssumptionRun] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
    ),
    page.click("#lab-run"),
  ]);
  assert.equal(flatAssumptionRun.status(), 200, await flatAssumptionRun.text());
  await page.waitForFunction(
    () => VEUSLab.result?.request?.profile?.source?.kind === "custom",
  );
  assert.equal(
    await page.locator("#lab-route-plot").getAttribute("data-geometry"),
    "false",
  );
  const routeCSV = out + "/custom-route.csv";
  fs.writeFileSync(
    routeCSV,
    "distance_m,latitude,longitude,elevation_m\n0,0,0,0\n100,0,.0008993,1\n200,.0008993,.0008993,2\n",
  );
  await page.selectOption("#lab-import-kind", "route");
  await page.locator("#lab-import-file").setInputFiles(routeCSV);
  await page.fill("#lab-import-name", "Browser synthetic coordinate fixture");
  await page.check("#lab-import-confirm");
  const [importedRoute] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/lab/import/route")),
    page.click("#lab-import"),
  ]);
  assert.equal(importedRoute.status(), 200, await importedRoute.text());
  const customBefore = await page.evaluate(() => VEUSLab.result.run_sha256);
  const [customRouteRun] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
    ),
    page.click("#lab-run"),
  ]);
  assert.equal(customRouteRun.status(), 200, await customRouteRun.text());
  await page.waitForFunction(
    (h) => VEUSLab.result?.run_sha256 !== h,
    customBefore,
  );
  assert.equal(
    await page.locator("#lab-route-plot").getAttribute("data-geometry"),
    "true",
  );

  // A real run with a tight battery-current limit must show the recorded electrical constraint.
  await page.click('[data-key="simulation"]');
  await page.locator("#lab-scenarios-mode").waitFor();
  await page.click('[data-kind="acceleration"]');
  await page.locator("#lab-config").evaluate((e) => (e.open = true));
  await page.selectOption("#lab-vehicle", "lab-second");
  await page.locator("#lab-assumptions").evaluate((e) => (e.open = true));
  for (const c of await page.locator(".lab-ack").all()) await c.check();
  await page
    .getByText("Numerical and braking settings", { exact: true })
    .click();
  await page.fill("#lab-duration", "3");
  await page.fill("#lab-dt", ".05");
  const [limitedResponse] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
    ),
    page.click("#lab-run"),
  ]);
  assert.equal(limitedResponse.status(), 200, await limitedResponse.text());
  await page.waitForFunction(
    () => VEUSLab.result?.vehicle?.battery?.discharge_limit_a === 5,
  );
  await page.locator("#lab-seek").evaluate((e) => {
    e.value = 1;
    e.dispatchEvent(new Event("input"));
  });
  assert.equal(
    await page.locator("#lab-battery").getAttribute("data-state"),
    "limited",
  );
  assert.equal(
    await page.locator("#lab-energy-flow").getAttribute("data-direction"),
    "out",
  );
  await page.click("#theme-toggle");
  await page.locator("#lab-seek").evaluate((e) => {
    e.value = 1;
    e.dispatchEvent(new Event("input"));
  });
  await page.evaluate(() => {
    document.activeElement?.blur();
    scrollTo(0, 0);
  });
  await page.click("#lab-scenarios-mode");
  await page.locator("#lab-config").evaluate((e) => (e.open = false));
  for (const width of [1024, 820, 390]) {
    await page.setViewportSize({ width, height: 844 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      "Lab horizontal overflow " + width,
    );
    const g = await page.locator("#lab-speedometer").boundingBox(),
      p = await page.locator(".lab-speed-panel").boundingBox();
    assert(g.x >= p.x - 1 && g.x + g.width <= p.x + p.width + 1);
  }
  await page.evaluate(() => {
    document.activeElement?.blur();
    scrollTo(0, 0);
  });
  assert.equal(sockets.length, 0);
  assert.deepEqual(errors, []);
  const summary = {
    status: "PASS",
    experiments: results,
    scenario_cards: true,
    exactly_three_synchronized_plots: true,
    battery_soc_and_regen: true,
    stop_resets_scene: true,
    gauge_boundaries: true,
    shared_cursor: true,
    replay_without_recalculation: true,
    frozen_vehicle_identity: true,
    lifecycle_cleanup: true,
    formats: ["json", "csv", "html"],
    profile_source_duration: true,
    no_time_profile_map: true,
    validated_csv_imports: ["profile", "route"],
    paused_background_requests: 0,
    paused_owned_animation_frames: 0,
    lab_resources: await page.evaluate(() =>
      performance
        .getEntriesByType("resource")
        .filter((r) =>
          /\/(lab(?:-scene)?\.js|lab\.css|replay-controller\.js)$/.test(
            new URL(r.name).pathname,
          ),
        )
        .map((r) => ({
          name: new URL(r.name).pathname,
          body_bytes: r.decodedBodySize,
        })),
    ),
    js_heap_bytes_chromium: jsHeap,
    seek_frame_callback_ms: seekTiming,
    timing_scope:
      "Five warm seek-input handlers to the next requestAnimationFrame callback; cloud Chromium, not display latency or a real-time guarantee.",
    widths: [1366, 1024, 820, 390],
    page_errors: errors,
  };
  fs.writeFileSync(
    out + "/browser.json",
    JSON.stringify(summary, null, 2) + "\n",
  );
  console.log(JSON.stringify(summary, null, 2));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

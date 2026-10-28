const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict"),
  fs = require("node:fs"),
  crypto = require("node:crypto");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({
      viewport: { width: 1366, height: 768 },
    }),
    errors = [],
    sent = [];
  let latest;
  page.on("pageerror", (e) => errors.push(e.stack));
  page.on("websocket", (ws) => {
    ws.on("framesent", (f) => sent.push(JSON.parse(f.payload)));
    ws.on("framereceived", (f) => {
      const d = JSON.parse(f.payload);
      if (d.type !== "error") latest = d;
    });
  });
  await page.goto(process.env.VEUS_URL || "http://127.0.0.1:8770");
  await page.locator('[data-vehicle="hatch"]').waitFor();
  await page.click('[data-vehicle="hatch"]');
  await page.waitForTimeout(150);
  await page.click("#driveRun");
  await page.keyboard.down("w");
  await page.waitForTimeout(350);
  await page.keyboard.up("w");
  await page.click('[data-workspace="analyse"]');
  await page.waitForFunction(() => window.VEUSReplay?.analysis);
  await page.waitForTimeout(150);
  assert.equal(latest.status, "paused");
  const simTime = latest.time_s,
    simPosition = latest.position_m,
    commands = sent.length;
  assert.equal(await page.locator("#replaySpeed").innerText(), "29.6");
  assert.equal(await page.locator("#replayPower").innerText(), "-8.55");
  assert((await page.locator("#replayOrigin").innerText()).includes("GENUINE"));
  await page.click("#replayPlay");
  await page.waitForTimeout(330);
  await page.click("#replayPlay");
  let paused = await page.evaluate(() => VEUSReplay.state.time_s);
  await page.waitForTimeout(150);
  assert.equal(await page.evaluate(() => VEUSReplay.state.time_s), paused);
  await page.fill("#replayJump", "20.3");
  await page.click("#replayJumpButton");
  assert.equal(await page.evaluate(() => VEUSReplay.state.time_s), 20.3);
  const before = await page.evaluate(() => VEUSReplay.state.position_m);
  await page.selectOption("#replayRate", "4");
  await page.click("#replayPlay");
  await page.waitForTimeout(300);
  await page.click("#replayPlay");
  const after = await page.evaluate(() => VEUSReplay.state);
  assert(after.time_s > 21.2 && after.time_s < 22.3);
  assert(after.position_m > before);
  assert.equal(latest.time_s, simTime);
  assert.equal(latest.position_m, simPosition);
  assert.equal(
    sent.length,
    commands,
    "Replay commands do not reach simulation WebSocket",
  );
  await page.locator("#replayGraphA").scrollIntoViewIfNeeded();
  const graph = await page.locator("#replayGraphA").boundingBox(),
    geometry = await page.locator("#replayGraphA").evaluate((c) => ({
      left: Number(c.dataset.plotLeft),
      right: Number(c.dataset.plotRight),
    }));
  await page.mouse.move(
    graph.x + geometry.left + (geometry.right - geometry.left) * 0.5,
    graph.y + graph.height / 2,
  );
  assert(
    (await page.locator("#replayHoverA").innerText()).includes("Actual sample"),
  );
  await page.mouse.click(
    graph.x + geometry.left + (geometry.right - geometry.left) * 0.5,
    graph.y + graph.height / 2,
  );
  assert(
    Math.abs((await page.evaluate(() => VEUSReplay.state.time_s)) - 36.05) <
      0.1,
  );
  await page.click('[data-replay-view="events"]');
  await page.locator("[data-event-start]").first().click();
  assert((await page.evaluate(() => VEUSReplay.state.time_s)) >= 71.5);
  await page.click("#replayPlay");
  await page.waitForTimeout(350);
  assert.equal(await page.evaluate(() => VEUSReplay.state.ended), true);
  await page.click("#replayRestart");
  assert.equal(await page.evaluate(() => VEUSReplay.state.time_s), 0);
  await page.click('[data-replay-view="summary"]');
  assert(
    (await page.locator("#replaySummary").innerText()).includes(
      "Current polarity is unverified",
    ),
  );
  assert(
    (await page.locator("#replayComparison").innerText()).includes(
      "INCONCLUSIVE",
    ),
  );
  await page.click('[data-replay-view="export"]');
  const downloads = {};
  const out = process.env.VEUS_SCREENSHOTS || "/tmp/veus-replay-screens";
  fs.mkdirSync(out, { recursive: true });
  for (const [id, name] of [
    ["replayExportSummary", "summary.json"],
    ["replayExportEvents", "events.csv"],
    ["replayExportMetadata", "metadata.json"],
    ["replayExportFull", "analysis.json"],
    ["replayExportHtml", "report.html"],
  ]) {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.click("#" + id),
    ]);
    await download.saveAs(out + "/" + name);
    downloads[name] = true;
  }
  const summary = JSON.parse(fs.readFileSync(out + "/summary.json"));
  assert(Math.abs(summary.summary.distance_m.value - 493.1573509971) < 1e-6);
  assert.equal(summary.summary.electrical_energy_used_wh.value, null);
  assert(
    fs
      .readFileSync(out + "/report.html", "utf8")
      .includes("Genuine measured recording"),
  );
  await page.locator("#replayAdvanced").evaluate((d) => (d.open = true));
  await page.fill("#replayAccelThreshold", "0.2");
  await page.click("#replayApplyThresholds");
  await page.waitForFunction(
    () => VEUSReplay.analysis.configuration.thresholds.acceleration_ms2 === 0.2,
  );
  assert.equal(
    await page.evaluate(() => VEUSReplay.analysis.metadata.raw_sha256),
    summary.metadata.raw_sha256,
  );
  await page.locator("#replayAdvanced").evaluate((d) => (d.open = false));
  await page.click('[data-replay-view="charts"]');
  await page.fill("#replayJump", "35");
  await page.click("#replayJumpButton");
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path: out + "/replay-laptop.png", fullPage: true });
  for (const [width, height] of [
    [1920, 1080],
    [1366, 768],
    [820, 1180],
    [390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(100);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      `No overflow ${width}`,
    );
    const controls = await page.locator(".replay-transport").boundingBox();
    assert(
      controls.y >= 0 && controls.y + controls.height <= height,
      `Playback visible ${width}`,
    );
    if (width === 390)
      await page.screenshot({
        path: out + "/replay-mobile.png",
        fullPage: true,
      });
  }
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.locator("#replayAdvanced").evaluate((d) => (d.open = true));
  await page
    .locator("#replayAdvanced details")
    .evaluate((d) => (d.open = true));
  const csv = "t,v\n0,0\n1,1\n10,2\n11,\n";
  const cfg = {
    schema_version: 1,
    source: {
      dataset: "Browser synthetic missing-data fixture",
      source_url: "synthetic://test-only",
      licence: "Test fixture",
      kind: "synthetic",
      run_id: "browser-gap-fixture",
      role: "exploration",
      expected_sha256: crypto.createHash("sha256").update(csv).digest("hex"),
      provenance_evidence: "Synthetic browser fixture, never experimental data",
    },
    preprocessing: {
      columns: {
        time_s: { column: "t", unit: "s" },
        vehicle_speed_ms: { column: "v", unit: "m/s" },
      },
      max_gap_s: 2,
    },
    limitations: ["Synthetic fixture only, not measured vehicle data."],
  };
  await page.setInputFiles("#replayCsv", {
    name: "gap.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.fill("#replayConfig", JSON.stringify(cfg));
  await page.click("#replayImport");
  await page.waitForFunction(
    () =>
      VEUSReplay.analysis.configuration.source.run_id === "browser-gap-fixture",
  );
  await page.fill("#replayJump", "5");
  await page.click("#replayJumpButton");
  assert.equal(await page.locator("#replaySpeed").innerText(), "Unavailable");
  assert.equal(await page.locator("#replayPower").innerText(), "Unavailable");
  assert.equal(await page.evaluate(() => VEUSReplay.state.position_m), 0.5);
  assert(
    (await page.locator("#replayOrigin").innerText()).includes("SYNTHETIC"),
  );
  assert(
    (await page.locator("#replaySampleNote").innerText()).includes(
      "Timestamp gap",
    ),
  );
  await page.selectOption("#replayDataset", "ved-10-1561");
  await page.click("#loadReplay");
  await page.waitForFunction(
    () => VEUSReplay.analysis.configuration.source.kind === "measured",
  );
  await page.click("#replayPlay");
  await page.waitForTimeout(200);
  await page.click('[data-workspace="drive"]');
  await page.waitForTimeout(100);
  assert.equal(await page.evaluate(() => VEUSReplay.state.playing), false);
  assert.equal(latest.time_s, simTime);
  await page.click("#driveRun");
  await page.keyboard.down("w");
  await page.waitForTimeout(250);
  await page.keyboard.up("w");
  assert(latest.time_s > simTime, "Drive resumes its own simulation");
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify(
      {
        status: "PASS",
        dataset: "VED vehicle 10 trip 1561",
        rows: 111,
        simulationStateSeparated: true,
        exports: downloads,
        resolutions: [
          [1920, 1080],
          [1366, 768],
          [820, 1180],
          [390, 844],
        ],
        screenshots: out,
        errors,
      },
      null,
      2,
    ),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

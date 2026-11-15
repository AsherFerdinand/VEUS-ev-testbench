const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict"),
  fs = require("node:fs");
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
    errors = [];
  page.on("pageerror", (e) => errors.push(e.stack));
  const base = new URL(process.env.VEUS_URL || "http://127.0.0.1:8770");
  base.searchParams.set("workspace", "analyse");
  await page.goto(base.href);
  await page.click('[data-analyse="investigate"]');
  await page.waitForFunction(
    () => document.getElementById("investigationDataset").options.length === 4,
  );
  await page.click("#investigationLoad");
  await page.waitForFunction(() => VEUSReplay.analysis?.time_s.length === 534);
  assert.equal(
    await page.locator("#replayScene").getAttribute("aria-label"),
    "Recorded EV illustration; displacement derived from measured speed, not a GPS trajectory",
  );
  await page.check("#investigationConfirm");
  await page.click("#investigationRun");
  await page.waitForFunction(() => VEUSInvestigation.caseStudy);
  const first = await page.evaluate(() => VEUSInvestigation.caseStudy);
  assert.equal(first.recordings[0].metrics.distance_m.value, null);
  assert.equal(first.recordings[0].analysis.metadata.row_count, 534);
  assert(
    (await page.locator("#investigationEnergy").innerText()).includes(
      "unavailable",
    ),
  );
  const chosen = first.recordings[0].events.find(
    (e) => e.type === "strong_acceleration",
  );
  await page.click(`[data-event-index="${chosen.event_index}"]`);
  await page.waitForFunction(
    (i) =>
      VEUSInvestigation.caseStudy.recordings[0].selected_event_indices
        .length === 1 &&
      VEUSInvestigation.caseStudy.recordings[0].selected_event_indices[0] === i,
    chosen.event_index,
  );
  assert(
    Math.abs(
      (await page.evaluate(() => VEUSReplay.state.time_s)) - chosen.start_s,
    ) < 1e-8,
  );
  assert(
    (await page.locator("#investigationInsight").innerText()).includes(
      chosen.rule,
    ),
  );
  await page
    .locator("#investigationMoreSignals")
    .evaluate((d) => (d.open = true));
  await page.waitForTimeout(150);
  const cursors = await page
    .locator("#investigatePanel canvas[data-signal]")
    .evaluateAll((cs) => cs.map((c) => Number(c.dataset.cursorTime)));
  assert(
    cursors.length === 6 &&
      cursors.every((t) => Math.abs(t - chosen.start_s) < 1e-5),
  );
  await page.click("#replayPlay");
  await page.waitForTimeout(250);
  await page.click("#replayPlay");
  assert((await page.evaluate(() => VEUSReplay.state.time_s)) > chosen.start_s);
  await page
    .locator("#investigationMoreSignals")
    .evaluate((d) => (d.open = false));
  const out = process.env.VEUS_SCREENSHOTS || "/tmp/veus-investigation-screens";
  fs.mkdirSync(out, { recursive: true });
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: out + "/investigation-laptop.png",
    fullPage: true,
  });
  await page.click('[data-analyse="compare"]');
  await page.click("#comparisonRun");
  await page.waitForFunction(
    () => VEUSInvestigation.caseStudy.recordings.length === 2,
  );
  assert(
    (await page.locator("#comparisonLimitations").innerText()).includes(
      "not a controlled experiment",
    ),
  );
  await page.selectOption("#comparisonAxis", "normalized");
  await page.locator("#comparisonTimeA").evaluate((e) => {
    e.value = "230.2";
    e.dispatchEvent(new Event("input"));
  });
  await page.locator("#comparisonTimeB").evaluate((e) => {
    e.value = "185.15";
    e.dispatchEvent(new Event("input"));
  });
  assert(
    (await page.locator("#comparisonAxisNote").innerText()).includes(
      "display transformation",
    ),
  );
  assert.equal(
    await page.locator("#comparisonPlotA").getAttribute("data-cursor-time"),
    "230.200000",
  );
  await page.screenshot({
    path: out + "/comparison-laptop.png",
    fullPage: true,
  });
  await page.click('[data-analyse="reports"]');
  for (const [id, name] of [
    ["caseHtml", "report.html"],
    ["caseJson", "case-study.json"],
    ["caseCsv", "measurements.csv"],
  ]) {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.click("#" + id),
    ]);
    await download.saveAs(out + "/" + name);
  }
  const report = JSON.parse(fs.readFileSync(out + "/case-study.json", "utf8"));
  assert.equal(report.recordings.length, 2);
  assert.equal(report.comparison.axis, "normalized");
  assert(
    report.recordings.every(
      (r) => r.metrics.electrical_energy_used_wh.value === null,
    ),
  );
  assert.equal(
    fs
      .readFileSync(out + "/measurements.csv", "utf8")
      .trim()
      .split("\n").length,
    1 + 534 + 367,
  );
  assert(
    fs
      .readFileSync(out + "/report.html", "utf8")
      .includes("No physical vehicle validation"),
  );
  await page.screenshot({ path: out + "/reports-laptop.png", fullPage: true });
  await page.click('[data-analyse="compare"]');
  await page.selectOption("#comparisonDataset", "imported");
  await page
    .locator("#comparisonCsv")
    .setInputFiles("datasets/ved/ved-10-1567-full.csv");
  await page
    .locator("#comparisonConfig")
    .setInputFiles("examples/replay/ved-10-1567-full.json");
  await page.locator("#comparisonConfirm").evaluate((e) => {
    e.checked = true;
  });
  const [importResponse] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/investigation/case-study") &&
        r.request().method() === "POST",
    ),
    page.click("#comparisonRun"),
  ]);
  assert.equal(importResponse.status(), 200);
  assert.equal(
    (await importResponse.json()).recordings[1].analysis.time_s.length,
    367,
  );
  await page.waitForFunction(
    () =>
      VEUSInvestigation.caseStudy?.recordings[1]?.analysis.time_s.length ===
      367,
  );
  assert.equal(
    await page.evaluate(
      () => VEUSInvestigation.caseStudy.recordings[1].metrics.distance_m.value,
    ),
    null,
  );

  for (const [width, height] of [
    [1920, 1080],
    [1366, 768],
    [820, 1180],
    [390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    await page.click('[data-analyse="investigate"]');
    await page.waitForTimeout(100);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      "No overflow " + width,
    );
    if (width === 390)
      await page.screenshot({
        path: out + "/investigation-mobile.png",
        fullPage: true,
      });
  }
  await page.click('[data-analyse="replay"]');
  assert(await page.locator("#replayPanel .replay-transport").isVisible());
  await page.click("#replayPlay");
  await page.waitForTimeout(150);
  await page.click("#replayPlay");
  await page.click('[data-workspace="drive"]');
  await page.click("#chooseVehicle");
  await page.click('[data-vehicle="hatch"]');
  await page.click("#driveRun");
  await page.keyboard.down("w");
  await page.waitForTimeout(250);
  await page.keyboard.up("w");
  assert(Number(await page.locator("#driveSpeed").innerText()) > 0);
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify(
      {
        status: "PASS",
        fullRecordingSamples: 534,
        secondRecordingSamples: 367,
        sharedCursor: true,
        eventEvidence: true,
        exports: ["html", "json", "csv"],
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

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
  const context = await browser.newContext({
      viewport: { width: 1366, height: 768 },
    }),
    page = await context.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.stack));
  const base = process.env.VEUS_URL || "http://127.0.0.1:8770";
  await page.goto(base);
  await page.locator("#welcomeWorkspace").waitFor({ state: "visible" });
  await page.locator('[data-vehicle="hatch"]').waitFor({ state: "attached" });
  assert.equal(
    await page.locator("#vehicleDialog").evaluate((d) => d.open),
    false,
    "Welcome is not blocked by a garage modal",
  );
  const out = process.env.VEUS_SCREENSHOTS || "/tmp/veus-guidance-screens";
  fs.mkdirSync(out, { recursive: true });
  await page.screenshot({ path: out + "/welcome-laptop.png", fullPage: true });
  await page.click("#welcomeDrive");
  await page.locator("#vehicleDialog").waitFor({ state: "visible" });
  await page.click('[data-vehicle="hatch"]');
  await page.waitForTimeout(150);
  assert.equal(await page.evaluate(() => activeWorkspace), "drive");
  await page.click("#driveRun");
  await page.keyboard.down("w");
  await page.waitForTimeout(300);
  await page.keyboard.up("w");
  assert(Number(await page.locator("#driveSpeed").innerText()) > 0);
  await page.reload();
  await page.locator('[data-vehicle="hatch"]').waitFor({ state: "attached" });
  assert.equal(
    await page.evaluate(() => activeWorkspace),
    "drive",
    "Returning visitor bypasses Welcome",
  );
  await page.keyboard.press("Escape");
  await page.click('[data-workspace="welcome"]');
  await page.click("#welcomeRequirements");
  assert.equal(await page.evaluate(() => activeWorkspace), "validate");
  assert.equal(
    await page.locator("#validateGuide").evaluate((d) => d.open),
    true,
  );
  assert(
    (await page.locator("#validateGuide").innerText()).includes("INCONCLUSIVE"),
  );
  await page.click('[data-workspace="welcome"]');
  await page.click("#welcomeExample");
  await page.waitForFunction(
    () => !document.getElementById("readinessMapping").hidden,
  );
  assert.equal(await page.locator("#readinessConfirm").isChecked(), false);
  await page.click("#readinessAssess");
  assert(
    (await page.locator("#readinessStatus").innerText()).includes(
      "confirmation",
    ),
  );
  await page.check("#readinessConfirm");
  await page.click("#readinessAssess");
  await page.waitForFunction(() => VEUSGuidance.assessment);
  const status = async (id) =>
    page.locator(`[data-capability="${id}"]`).getAttribute("data-status");
  assert.equal(await status("recorded_replay"), "AVAILABLE");
  assert.equal(await status("signed_power"), "AVAILABLE");
  assert.equal(await status("energy_consumption"), "CONDITIONAL");
  assert.equal(await status("motor_efficiency"), "UNAVAILABLE");
  assert.equal(await status("longitudinal_validation"), "UNAVAILABLE");
  const ved = await page.evaluate(() => VEUSGuidance.assessment);
  assert.equal(ved.metadata.source.kind, "measured");
  assert.equal(ved.recording_duration_s > 72, true);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: out + "/readiness-laptop.png",
    fullPage: true,
  });
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#readinessExport"),
  ]);
  await download.saveAs(out + "/ved-readiness.json");
  assert.equal(
    JSON.parse(fs.readFileSync(out + "/ved-readiness.json")).assessment_sha256,
    ved.assessment_sha256,
  );
  await page.click("#readinessProceed");
  await page.waitForFunction(() => VEUSReplay.analysis);
  assert.equal(
    await page.evaluate(() => VEUSReplay.analysis.configuration.source.kind),
    "measured",
  );
  assert(await page.locator("#replayPanel").isVisible());
  await page.click('[data-analyse="readiness"]');
  await page.selectOption("#readinessDataset", "basic-replay");
  await page.click("#readinessLoad");
  await page.waitForFunction(() =>
    document.getElementById("readinessName").value.includes("synthetic"),
  );
  await page.check("#readinessConfirm");
  await page.click("#readinessAssess");
  await page.waitForFunction(
    () =>
      VEUSGuidance.assessment?.configuration.source.run_id === "basic-replay",
  );
  assert.equal(await status("recorded_replay"), "AVAILABLE");
  assert.equal(await status("signed_power"), "UNAVAILABLE");
  assert.equal(
    await page.evaluate(() => VEUSGuidance.assessment.metadata.source.kind),
    "synthetic",
  );
  // Custom aliases propose columns but leave units/origin unselected.
  const csv =
    "clock,velocity,throttle,brake\n1000,0,0,0\n2000,10,50,0\n3000,20,50,0\n";
  await page.setInputFiles("#readinessCsv", {
    name: "manual-mapping.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.waitForFunction(
    () =>
      document.getElementById("readinessName").value === "manual-mapping.csv",
  );
  assert.equal(await page.locator("#readinessOrigin").inputValue(), "");
  assert.equal(
    await page
      .locator('[data-signal="vehicle_speed_ms"] [data-mapping="unit"]')
      .inputValue(),
    "",
  );
  assert(
    (await page.locator("#readinessUnsupported").innerText()).includes(
      "not a brake force",
    ),
  );
  await page.selectOption(
    '[data-signal="time_s"] [data-mapping="column"]',
    "clock",
  );
  await page.selectOption('[data-signal="time_s"] [data-mapping="unit"]', "ms");
  await page.selectOption(
    '[data-signal="vehicle_speed_ms"] [data-mapping="column"]',
    "velocity",
  );
  await page.selectOption(
    '[data-signal="vehicle_speed_ms"] [data-mapping="unit"]',
    "mph",
  );
  await page.selectOption("#readinessOrigin", "synthetic");
  await page.check("#readinessConfirm");
  await page.click("#readinessAssess");
  await page.waitForFunction(
    () =>
      VEUSGuidance.assessment?.configuration.source.dataset ===
      "manual-mapping.csv",
  );
  assert.equal(await status("recorded_replay"), "AVAILABLE");
  assert.equal(
    await page.evaluate(() => VEUSGuidance.assessment.recording_duration_s),
    2,
  );
  // A duplicate time fails the existing importer; no repairs or stale readiness.
  await page.setInputFiles("#readinessCsv", {
    name: "duplicates.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("time_s,speed_kmh\n0,0\n0,2\n"),
  });
  await page.waitForFunction(
    () => document.getElementById("readinessName").value === "duplicates.csv",
  );
  await page.selectOption("#readinessOrigin", "synthetic");
  await page.selectOption('[data-signal="time_s"] [data-mapping="unit"]', "s");
  await page.selectOption(
    '[data-signal="vehicle_speed_ms"] [data-mapping="unit"]',
    "km/h",
  );
  await page.check("#readinessConfirm");
  await page.click("#readinessAssess");
  await page.waitForFunction(() =>
    document
      .getElementById("readinessStatus")
      .textContent.includes("duplicates"),
  );
  assert.equal(await page.evaluate(() => VEUSGuidance.assessment), null);
  assert(await page.locator("#readinessProceed").isDisabled());
  await page.selectOption("#readinessDataset", "ved-10-1561");
  await page.click("#readinessLoad");
  await page.waitForFunction(
    () =>
      document.getElementById("readinessName").value ===
      "University of Michigan VED",
  );
  await page.check("#readinessConfirm");
  await page.click("#readinessAssess");
  await page.waitForFunction(() => VEUSGuidance.assessment);
  for (const [width, height] of [
    [1366, 768],
    [390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(100);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    if (width === 390) {
      await page.screenshot({
        path: out + "/readiness-mobile.png",
        fullPage: true,
      });
      await page.click('[data-workspace="welcome"]');
      await page.screenshot({
        path: out + "/welcome-mobile.png",
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.click('[data-workspace="settings"]');
  await page.check("#showWelcome");
  await page.reload();
  await page.locator("#welcomeWorkspace").waitFor({ state: "visible" });
  const direct = new URL(base);
  direct.searchParams.set("workspace", "drive");
  await page.goto(direct.href);
  await page.locator("#driveWorkspace").waitFor({ state: "visible" });
  assert.equal(await page.evaluate(() => activeWorkspace), "drive");
  const restricted = await browser.newContext();
  await restricted.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("Storage blocked for test");
      },
    });
  });
  const fallback = await restricted.newPage();
  fallback.on("pageerror", (e) => errors.push(e.stack));
  await fallback.goto(base);
  await fallback.locator("#welcomeWorkspace").waitFor({ state: "visible" });
  await fallback.click("#skipWelcome");
  assert.equal(await fallback.evaluate(() => activeWorkspace), "drive");
  assert(
    (await fallback.locator("#preferenceStatus").innerText()).includes(
      "unavailable",
    ),
  );
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify(
      {
        status: "PASS",
        welcome: true,
        returningPreference: true,
        directDrive: true,
        storageFallback: true,
        manualMapping: true,
        invalidTimestampsRejected: true,
        ved: Object.fromEntries(ved.capabilities.map((c) => [c.id, c.status])),
        resolutions: [
          [1366, 768],
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

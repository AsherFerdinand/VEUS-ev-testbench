// Optional documentation capture. Uses external Playwright/Chromium; no app dependency.
// Run from repository root with VEUS_URL pointing to the running, unchanged app.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
(async () => {
  const out = process.env.MEDIA_OUTPUT || "docs/assets/readme";
  const frames = process.env.FRAME_OUTPUT || "/tmp/veus-readme-frames";
  fs.mkdirSync(out, { recursive: true });
  fs.mkdirSync(frames, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const base = process.env.VEUS_URL || "http://127.0.0.1:8770";
  await page.goto(base + "/?workspace=drive");
  await page.locator('[data-vehicle="sedan"]').waitFor();
  await page.click('[data-vehicle="sedan"]');
  await page.waitForFunction(() =>
    document.getElementById("connection").textContent.includes("Connected"),
  );
  await page.click("#driveRun");
  const samples = [];
  const start = Date.now();
  for (let i = 0; i < 100; i++) {
    if (i === 8) await page.keyboard.down("w");
    if (i === 52) {
      await page.keyboard.up("w");
      await page.keyboard.down("s");
    }
    if (i === 82) await page.keyboard.up("s");
    if (i === 90) await page.keyboard.press("r");
    if (i === 94) await page.click("#driveRun");
    await page.screenshot({
      path: path.join(frames, String(i).padStart(3, "0") + ".png"),
    });
    if (i === 48)
      await page.screenshot({ path: path.join(out, "drive-overview.png") });
    if (i % 10 === 0)
      samples.push(
        await page.evaluate(() => ({
          speed: document.getElementById("driveSpeed").textContent,
          soc: document.getElementById("driveSoc").textContent,
          power: document.getElementById("drivePower").textContent,
        })),
      );
    await page.waitForTimeout(Math.max(0, start + (i + 1) * 100 - Date.now()));
  }
  const driveCaptureMs = Date.now() - start;
  await page.click("#driveRun");
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.click('[data-workspace="analyse"]');
  await page.click('[data-analyse="investigate"]');
  await page.waitForFunction(
    () => document.getElementById("investigationDataset").options.length === 4,
  );
  await page.click("#investigationLoad");
  await page.waitForFunction(() => VEUSReplay.analysis?.time_s.length === 534);
  await page.check("#investigationConfirm");
  await page.click("#investigationRun");
  await page.waitForFunction(() => VEUSInvestigation.caseStudy);
  const event = await page.evaluate(() =>
    VEUSInvestigation.caseStudy.recordings[0].events.find(
      (e) =>
        e.type === "strong_acceleration" && Math.abs(e.start_s - 143) < 0.01,
    ),
  );
  assert(event);
  await page.click(`[data-event-index="${event.event_index}"]`);
  await page.waitForFunction(
    (i) =>
      VEUSInvestigation.caseStudy.recordings[0].selected_event_indices
        .length === 1 &&
      VEUSInvestigation.caseStudy.recordings[0].selected_event_indices[0] === i,
    event.event_index,
  );
  await page
    .locator(".investigation-main")
    .evaluate((e) => scrollTo(0, e.getBoundingClientRect().top + scrollY - 8));
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(out, "investigate-overview.png") });
  await page.click('[data-analyse="compare"]');
  await page.selectOption("#comparisonDataset", "ved-10-1567-full");
  await page.click("#comparisonRun");
  await page.waitForFunction(
    () => VEUSInvestigation.caseStudy?.recordings.length === 2,
  );
  await page.evaluate(() => scrollTo(0, 0));
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(out, "compare-overview.png") });
  await page.click('[data-workspace="validate"]');
  await page.evaluate(() => scrollTo(0, 0));
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(out, "validate-overview.png") });
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    path.join(out, "capture.json"),
    JSON.stringify(
      {
        source_commit: require("node:child_process")
          .execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" })
          .trim(),
        viewport: [1280, 720],
        frames: 100,
        target_fps: 10,
        drive_capture_ms: driveCaptureMs,
        drive_readouts: samples,
        selected_event: event,
        page_errors: errors,
      },
      null,
      2,
    ) + "\n",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

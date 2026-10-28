// Optional real-browser regression. npm install playwright; set VEUS_URL if needed.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
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
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("websocket", (ws) => {
    ws.on("framesent", (f) => sent.push(JSON.parse(f.payload)));
    ws.on("framereceived", (f) => {
      const d = JSON.parse(f.payload);
      if (d.type !== "error") latest = d;
    });
  });
  await page.goto(process.env.VEUS_URL || "http://127.0.0.1:8770");
  await page.locator('[data-vehicle="hatch"]').waitFor();
  const choose = async (id) => {
    if (!(await page.locator("#vehicleDialog").evaluate((d) => d.open)))
      await page.click("#chooseVehicle");
    await page.click(`[data-vehicle="${id}"]`);
    await page.waitForFunction((id) => VEUS.debug().selected === id, id);
    await page.waitForTimeout(180);
  };
  for (const [id, mass, power, capacity] of [
    ["hatch", 1350, 100, 42],
    ["sedan", 1800, 150, 60],
    ["coupe", 1700, 250, 72],
    ["suv", 2250, 200, 85],
  ]) {
    await choose(id);
    assert.equal(latest.resolved_config.mass_kg, mass);
    assert.equal(latest.resolved_config.max_power_kw, power);
    assert.equal(latest.resolved_config.battery_capacity_kwh, capacity);
  }
  await choose("sedan");
  const box = await page.locator("#driveControls").boundingBox();
  assert(box.y >= 0 && box.y + box.height <= 768, "Laptop controls visible");
  await page.evaluate(() => scrollTo(0, document.body.scrollHeight));
  const pinned = await page.locator("#driveControls").boundingBox();
  assert(
    pinned.y >= 0 && pinned.y + pinned.height <= 768,
    "Controls remain visible while scrolling",
  );
  await page.evaluate(() => scrollTo(0, 0));
  const stationary = await page
    .locator("#driveScene")
    .getAttribute("data-position-m");
  await page.waitForTimeout(200);
  assert.equal(
    await page.locator("#driveScene").getAttribute("data-position-m"),
    stationary,
  );
  await page.click("#driveRun");
  const initialMessages = sent.length;
  await page.keyboard.down("w");
  await page.waitForTimeout(1000);
  assert(Number(await page.locator("#driveSpeed").innerText()) > 0);
  assert(sent.length - initialMessages < 8, "No keyboard-event request flood");
  await page.keyboard.down("s");
  await page.waitForTimeout(130);
  assert.equal(await page.locator("#throttle").inputValue(), "0");
  assert.equal(await page.locator("#brake").inputValue(), "100");
  await page.keyboard.up("s");
  await page.keyboard.up("w");
  await page.waitForTimeout(150);
  assert.equal(await page.locator("#throttle").inputValue(), "0");
  assert.equal(await page.locator("#brake").inputValue(), "0");
  await page.keyboard.down("w");
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await page.waitForTimeout(100);
  assert.equal(await page.locator("#throttle").inputValue(), "0");
  await page.keyboard.up("w");
  await page.keyboard.press("Space");
  await page.waitForTimeout(150);
  assert.equal(latest.status, "paused");
  const frozen = await page
    .locator("#driveScene")
    .getAttribute("data-position-m");
  await page.waitForTimeout(150);
  assert.equal(
    await page.locator("#driveScene").getAttribute("data-position-m"),
    frozen,
  );
  await page.keyboard.press("Space");
  await page.waitForTimeout(150);
  assert.equal(latest.status, "running");
  await page.keyboard.press("r");
  await page.waitForTimeout(150);
  assert.equal(latest.status, "ready");
  assert.equal(latest.position_m, 0);
  await page.click("#driveRun");
  await page.keyboard.down("w");
  await page.click('[data-workspace="analyse"]');
  await page.keyboard.up("w");
  await page.waitForTimeout(150);
  assert.equal(latest.status, "paused");
  assert.equal(await page.locator("#throttle").inputValue(), "0");
  await page.click('[data-analyse="experiments"]');
  assert(await page.locator("#modelValidation").isVisible());
  await page.click("#loadValidationExample");
  await page.waitForFunction(
    () => document.getElementById("validationConfig").value.length > 0,
  );
  await page.locator("#validationConfig").focus();
  await page.keyboard.type("w");
  assert.equal(await page.locator("#throttle").inputValue(), "0");
  await page.selectOption("#validationExample", "synthetic-battery-train");
  await page.click("#loadValidationExample");
  await page.waitForFunction(() =>
    document
      .getElementById("validationConfig")
      .value.includes("synthetic-battery-train"),
  );
  await page.selectOption("#validationAction", "calibrate");
  await page.click("#runValidation");
  await page.waitForFunction(
    () => !document.getElementById("runValidation").disabled,
  );
  assert(
    (await page.locator("#validationStatus").innerText()).includes("PASS"),
  );
  await page.selectOption("#validationExample", "synthetic-battery-holdout");
  await page.click("#loadValidationExample");
  await page.waitForFunction(() =>
    document
      .getElementById("validationConfig")
      .value.includes("synthetic-battery-holdout"),
  );
  await page.selectOption("#validationAction", "evaluate");
  await page.click("#runValidation");
  await page.waitForFunction(
    () => !document.getElementById("runValidation").disabled,
  );
  assert(
    (await page.locator("#validationStatus").innerText()).includes("PASS"),
  );
  await page.click('[data-workspace="validate"]');
  assert(await page.locator("#sensorSettings").isVisible());
  await page.locator("#sensorSettings").evaluate((d) => (d.open = true));
  assert(await page.locator("#sensorsEnabled").isVisible());
  assert(await page.locator("#export").isVisible());
  await page.click('[data-workspace="drive"]');
  await page.selectOption("#driveMode", "acc");
  await page.waitForTimeout(180);
  await page.click("#driveRun");
  await page.waitForTimeout(200);
  assert(latest.gap_m !== null);
  assert((await page.locator("#leadReadout").innerText()).includes("Gap"));
  assert(await page.locator("#throttle").isDisabled());
  await page.selectOption("#driveMode", "manual");
  await page.waitForTimeout(180);
  await choose("sedan"); // Reset initial speed to zero for the Drive screenshots.
  await page.click("#driveRun");
  await page.keyboard.down("w");
  await page.waitForTimeout(1200);
  await page.keyboard.up("w");
  await page.waitForTimeout(130);
  const position = Number(
    await page.locator("#driveScene").getAttribute("data-position-m"),
  );
  assert(
    position >= 0 && position <= latest.position_m + 0.0001,
    "Visual interpolation never extrapolates",
  );
  const out = process.env.VEUS_SCREENSHOTS || "/tmp/veus-drive-screens";
  fs.mkdirSync(out, { recursive: true });
  await page.screenshot({ path: out + "/drive-laptop.png", fullPage: true });
  const performance = await page.evaluate(() => VEUS.debug());
  for (const [width, height] of [
    [1920, 1080],
    [1366, 768],
    [820, 1180],
    [390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(150);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      `No overflow ${width}`,
    );
    const controls = await page.locator("#driveControls").boundingBox();
    assert(controls.y + controls.height <= height, `Visible controls ${width}`);
    if (width === 390) {
      const pedal = await page.locator("#touchBrake").boundingBox();
      await page.mouse.move(
        pedal.x + pedal.width / 2,
        pedal.y + pedal.height / 2,
      );
      await page.mouse.down();
      await page.waitForTimeout(100);
      assert.equal(await page.locator("#brake").inputValue(), "100");
      await page.mouse.up();
      assert.equal(await page.locator("#brake").inputValue(), "0");
      await page.screenshot({
        path: out + "/drive-mobile.png",
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.click("#chooseVehicle");
  await page.screenshot({
    path: out + "/vehicle-selection.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page.evaluate(() => send({ action: "reset", config: { mass_kg: 1 } }));
  await page.waitForFunction(() =>
    document.getElementById("driveNotice").textContent.includes("rejected"),
  );
  // Hiding the page releases demands, requests pause and stops rendering.
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(100);
  assert.equal(await page.locator("#throttle").inputValue(), "0");
  await page.evaluate(() => {
    delete document.hidden;
    document.dispatchEvent(new Event("visibilitychange"));
  });
  // Renderer-only synthetic samples: no Python state is changed by these events.
  await page.click("#driveReset");
  await page.waitForTimeout(150);
  await page.evaluate(() => {
    const sample = samples.at(-1);
    document.dispatchEvent(
      new CustomEvent("veus:telemetry", {
        detail: { ...sample, status: "paused", position_m: 100, time_s: 0 },
      }),
    );
    document.dispatchEvent(
      new CustomEvent("veus:telemetry", {
        detail: { ...sample, status: "running", position_m: 110, time_s: 0.1 },
      }),
    );
  });
  await page.waitForTimeout(40);
  const between = Number(
    await page.locator("#driveScene").getAttribute("data-position-m"),
  );
  assert(
    between >= 100 && between <= 110,
    "Interpolated position remains between authoritative samples",
  );
  await page.waitForTimeout(180);
  assert.equal(
    Number(await page.locator("#driveScene").getAttribute("data-position-m")),
    110,
  );
  await page.waitForTimeout(180);
  assert.equal(
    Number(await page.locator("#driveScene").getAttribute("data-position-m")),
    110,
    "No extrapolation when updates cease",
  );
  await page.evaluate(() => socket.close());
  await page.waitForTimeout(180);
  assert(await page.locator("#driveRun").isDisabled());
  assert.equal(await page.locator("#throttle").inputValue(), "0");
  assert.equal(await page.locator("#driveSpeed").innerText(), "—");
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify(
      { status: "PASS", performance, screenshots: out, errors },
      null,
      2,
    ),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

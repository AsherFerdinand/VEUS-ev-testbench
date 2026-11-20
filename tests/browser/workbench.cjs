// Foundation UI, keyboard, prototypes and genuine-data migration. No fabricated results.
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
      deviceScaleFactor: 1,
    }),
    errors = [],
    sockets = [],
    requests = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("websocket", (w) => sockets.push(w.url()));
  page.on("request", (r) => requests.push(r.url()));
  const base = process.env.VEUS_URL || "http://127.0.0.1:8770";
  const out = process.env.VEUS_SCREENSHOTS || "/tmp/veus2-screens";
  fs.mkdirSync(out, { recursive: true });
  await page.goto(base);
  await page.locator("#component-inspector h2").waitFor();
  assert.equal(
    await page
      .locator('[role="tab"][aria-selected="true"]')
      .getAttribute("data-key"),
    "anatomy",
  );
  assert.equal(
    await page.locator('.anatomy-component[role="button"]').count(),
    10,
  );
  const startup = await page.evaluate(() => ({
    resources: performance.getEntriesByType("resource").map((r) => ({
      name: r.name.split("/").at(-1),
      bytes: r.encodedBodySize,
    })),
    heap_bytes: performance.memory?.usedJSHeapSize ?? null,
  }));
  await page.locator('[data-component="motor"]').focus();
  assert(
    (await page.locator("#anatomy-tooltip").innerText()).includes(
      "mechanical torque",
    ),
  );
  await page.keyboard.press("Enter");
  assert.equal(
    await page.locator("#component-inspector h2").innerText(),
    "Traction motor",
  );
  await page.locator('[data-component="charger"]').focus();
  await page.keyboard.press("Space");
  assert(
    (await page.locator("#component-inspector").innerText()).includes(
      "offboard",
    ),
  );
  await page.selectOption("#component-select", "battery");
  await page.click("#flow-view");
  for (const flow of ["propulsion", "regeneration", "charging", "auxiliary"]) {
    await page.click(`[data-flow="${flow}"]`);
    assert.equal(await page.locator(".flow-active").count(), 1);
    assert(
      (await page.locator(".flow-svg").getAttribute("aria-label")).length > 20,
    );
  }
  await page.click("#placement-view");
  const drawing = await page.locator(".anatomy-svg").boundingBox(),
    dockTop = await page.locator(".workspace-dock").boundingBox();
  assert(
    drawing.y + drawing.height < dockTop.y,
    "Whole schematic visible above laptop navigation",
  );
  await page.locator("#tab-anatomy").focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(
    await page
      .locator('[role="tab"][aria-selected="true"]')
      .getAttribute("data-key"),
    "challenges",
  );
  assert.equal(await page.locator("[data-challenge]").count(), 8);
  await page.click('[data-challenge="charging"]');
  assert(
    (await page.locator("#challenge-content").innerText()).includes(
      "charging curve",
    ),
  );
  await page.click("#challenge-experiment");
  assert.equal(await page.locator("#design-form").count(), 1);
  await page
    .locator('[data-group="battery"][data-field="usable_capacity_kwh"]')
    .fill("70");
  await page.click('#design-form button[type="submit"]');
  await page.waitForFunction(() =>
    document
      .getElementById("configuration-status")
      .textContent.includes("Usable capacity"),
  );
  assert(await page.locator("#design-export").isDisabled());
  await page
    .locator('[data-group="battery"][data-field="usable_capacity_kwh"]')
    .fill("60");
  await page.locator("#design-name").fill("<script>engineering</script>");
  await page.click('#design-form button[type="submit"]');
  await page.waitForFunction(
    () => !document.getElementById("design-export").disabled,
  );
  const [file] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#design-export"),
  ]);
  await file.saveAs(out + "/illustrative-design.json");
  const design = JSON.parse(
    fs.readFileSync(out + "/illustrative-design.json", "utf8"),
  );
  assert.equal(design.schema_version, 1);
  assert.equal(design.classification, "illustrative");
  await page
    .locator("#design-import")
    .setInputFiles(out + "/illustrative-design.json");
  await page.waitForFunction(() =>
    document
      .getElementById("configuration-status")
      .textContent.includes("Imported valid"),
  );
  assert.equal(await page.locator("script:not([src])").count(), 0);
  await page.click("#tab-simulation");
  await page.click("#prescribed-mode");
  assert(
    (await page.locator("#mode-explanation").innerText()).includes(
      "not a prediction",
    ),
  );
  assert(
    await page.getByRole("button", { name: "Run in new Lab" }).isDisabled(),
  );
  await page.click("#tab-optimization");
  await page.click('[data-study="aero"]');
  assert((await page.locator(".equation").innerText()).includes("Cd"));
  await page.click("#tab-measurements");
  await page.selectOption("#measurement-recording", "ved-10-1567-full");
  assert(
    (await page.locator("#measurement-summary").innerText()).includes("367"),
  );
  await page.selectOption("#measurement-question", "power");
  assert(
    (await page.locator("#measurement-summary").innerText()).includes(
      "Unverified polarity",
    ),
  );
  await page.goBack();
  assert.equal(
    await page.locator("body").getAttribute("data-workspace"),
    "optimization",
  );
  await page.goForward();
  assert.equal(
    await page.locator("body").getAttribute("data-workspace"),
    "measurements",
  );
  assert.equal(sockets.length, 0);
  assert(
    !requests.some((u) =>
      /static\/(drive|scene|dashboard|workspaces)\.js/.test(u),
    ),
  );
  // Capture clean illustrative default after hostile-name escaping test.
  await page.goto(base);
  await page.locator("#component-inspector h2").waitFor();
  for (const theme of ["light", "dark"]) {
    if ((await page.locator("html").getAttribute("data-theme")) !== theme)
      await page.click("#theme-toggle");
    for (const key of [
      "anatomy",
      "challenges",
      "design",
      "simulation",
      "optimization",
      "measurements",
    ]) {
      await page.click("#tab-" + key);
      await page.waitForTimeout(100);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
        key + " laptop overflow",
      );
      const dock = await page.locator(".workspace-dock").boundingBox();
      assert(dock.y >= 0 && dock.y + dock.height <= 769);
      await page.screenshot({ path: `${out}/${key}-${theme}.png` });
      if (key === "anatomy") {
        await page.click("#flow-view");
        await page.click('[data-flow="charging"]');
        await page.screenshot({ path: `${out}/energy-paths-${theme}.png` });
        await page.click("#placement-view");
      }
    }
  }
  await page.reload();
  await page.locator("#measurement-summary").waitFor();
  assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
  for (const width of [1024, 820, 390]) {
    await page.setViewportSize({ width, height: 844 });
    for (const key of [
      "anatomy",
      "challenges",
      "design",
      "simulation",
      "optimization",
      "measurements",
    ]) {
      await page.click("#tab-" + key);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
        key + " overflow " + width,
      );
    }
  }
  await page.click("#tab-anatomy");
  await page.screenshot({ path: out + "/anatomy-mobile.png" });
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(base + "/engineering?workspace=analyse");
  await page.locator("#replayPanel").waitFor({ state: "attached" });
  assert(await page.locator('[data-analyse="investigate"]').isVisible());
  assert.deepEqual(errors, []);
  const result = {
    status: "PASS",
    screenshots: out,
    workspaces: 6,
    themes: ["light", "dark"],
    widths: [1366, 1024, 820, 390],
    keyboard_components: true,
    keyboard_tabs: true,
    design_validation_roundtrip: true,
    prototype_results_not_fabricated: true,
    legacy_migration: true,
    default_shell_websockets: 0,
    startup,
    page_errors: errors,
  };
  fs.writeFileSync(
    out + "/browser.json",
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

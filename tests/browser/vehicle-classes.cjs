// Three real preset workflows, legacy fallback and shared frozen visual identity.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs"),
  assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
      viewport: { width: 1440, height: 1400 },
    }),
    page = await context.newPage(),
    errors = [];
  const base = process.env.VEUS_URL || "http://127.0.0.1:8770",
    out = process.env.VEUS_SCREENSHOTS || "/tmp/veus232-classes";
  fs.mkdirSync(out, { recursive: true });
  const old = await (
    await context.request.get(base + "/api/workbench/v2/design")
  ).json();
  old.name = "Legacy preserved study";
  assert(!Object.hasOwn(old, "appearance"));
  const library = {
    schema_version: 1,
    active_id: "legacy",
    records: [{ id: "legacy", design: old }],
  };
  await page.addInitScript((data) => {
    if (!localStorage.getItem("veus.design-library.v2"))
      localStorage.setItem("veus.design-library.v2", JSON.stringify(data));
  }, library);
  require("./advanced-disclosure.cjs")(page);
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base + "/?workspace=design");
  await page.locator("[data-preset]").first().waitFor();
  assert.equal(
    await page.locator("#schematic-slot svg").getAttribute("data-appearance"),
    "performance",
  );
  const drawings = {},
    runs = {};
  for (const [id, appearance] of [
    ["s1", "sedan"],
    ["r1", "performance"],
    ["x1", "suv"],
  ]) {
    const beforePreview = await page.evaluate(() =>
      localStorage.getItem("veus.design-library.v2"),
    );
    const activeBefore = await page.locator("#design-name").inputValue();
    await page.click('[data-preset="' + id + '"]');
    assert.equal(
      await page.evaluate(() => localStorage.getItem("veus.design-library.v2")),
      beforePreview,
    );
    assert.match(
      await page.locator("#design-name").inputValue(),
      new RegExp("VEUS " + id.toUpperCase()),
    );
    await page.waitForFunction(
      (a) =>
        document.querySelector("#schematic-slot svg")?.dataset.appearance === a,
      appearance,
    );
    await page.waitForFunction(
      () => !document.getElementById("design-save").disabled,
    );
    const storage = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("veus.design-library.v2")),
    );
    assert.deepEqual(
      storage.records.find((r) => r.id === "legacy").design,
      old,
    );
    assert.equal(
      await page.locator("#schematic-slot .motor-cylinder").count(),
      1,
    );
    if (id === "s1") {
      const before = await page.evaluate(async () =>
        structuredClone(
          (await import("/static/workbench/design-state.js")).state.design,
        ),
      );
      await page.selectOption("#studio-appearance", "suv");
      await page.waitForFunction(
        () => !document.getElementById("design-save").disabled,
      );
      const after = await page.evaluate(async () =>
        structuredClone(
          (await import("/static/workbench/design-state.js")).state.design,
        ),
      );
      delete before.appearance;
      delete after.appearance;
      assert.deepEqual(
        after,
        before,
        "Visual-only changes preserve every numerical parameter",
      );
      await page.selectOption("#studio-appearance", "sedan");
      await page.selectOption("#design-group", "battery");
      const previousPack = await page.locator(".pack-envelope").innerHTML();
      await page.selectOption("#component-record", "battery-80");
      assert.notEqual(
        await page.locator(".pack-envelope").innerHTML(),
        previousPack,
      );
      assert.equal(
        await page.locator(".pack-envelope").getAttribute("data-record"),
        "battery-80",
      );
      await page.selectOption("#component-record", "battery-s1");
      await page.waitForFunction(
        () => !document.getElementById("design-save").disabled,
      );
    }
    await page.locator('#schematic-slot [data-component="motor"]').focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator("#design-group").inputValue(), "motor");
    await page.selectOption("#design-group", "body");
    const cd = Number(
      await page.locator('[data-field="drag_coefficient"]').inputValue(),
    );
    await page
      .locator('[data-field="drag_coefficient"]')
      .fill(String(cd + 0.005));
    await page.waitForFunction(() =>
      document
        .getElementById("configuration-status")
        .textContent.startsWith("Checked"),
    );
    await page.fill("#design-name", `Customized ${id.toUpperCase()}`);
    await page.click("#design-save");
    await page.waitForFunction(
      (name) =>
        document.querySelector("#library-select option:checked")
          ?.textContent === name,
      `Customized ${id.toUpperCase()}`,
    );
    assert.equal(
      await page.locator("#schematic-slot svg").getAttribute("data-appearance"),
      appearance,
    );
    const layout = await page
      .locator(".pack-envelope")
      .getAttribute("data-layout");
    assert(layout.startsWith(appearance));
    drawings[id] = await page
      .locator("#schematic-slot .class-body")
      .innerHTML();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page
        .click(".library-more summary")
        .then(() => page.click("#design-export")),
    ]);
    await download.saveAs(out + "/" + id + ".json");
    const snapshot = JSON.parse(
      fs.readFileSync(out + "/" + id + ".json", "utf8"),
    );
    assert.equal(snapshot.appearance, appearance);
    assert.equal(snapshot.body.drag_coefficient, cd + 0.005);
    await page.click(".library-more summary");
    if (id === "r1") await page.click("#theme-toggle");
    if (process.env.VEUS_CAPTURE !== "0") {
      await page.selectOption("#design-group", "body");
      await page.evaluate(() => {
        document.activeElement?.blur();
        scrollTo(0, 0);
      });
      await page.screenshot({ path: out + "/" + id + ".png" });
    }
    await page.click("#tab-simulation");
    await page.locator("#lab-config").evaluate((e) => (e.open = true));
    await page.locator("#lab-assumptions").evaluate((e) => (e.open = true));
    for (const ack of await page.locator(".lab-ack").all()) await ack.check();
    await page.fill("#lab-duration", "2");
    const [response] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
      ),
      page.click("#lab-run"),
    ]);
    assert.equal(response.status(), 200, await response.text());
    await page.waitForFunction(
      (a) => window.VEUSLab?.result?.vehicle?.appearance === a,
      appearance,
    );
    assert.equal(
      await page.locator("#lab-hero-car").getAttribute("data-appearance"),
      appearance,
    );
    runs[id] = await page.evaluate(() => VEUSLab.result.run_sha256);
    const frozen = await page.evaluate(() => VEUSLab.result.vehicle.appearance);
    await page.selectOption("#lab-vehicle", "legacy");
    assert.equal(
      await page.evaluate(() => VEUSLab.result.vehicle.appearance),
      frozen,
    );
    await page.click("#tab-anatomy");
    await page.locator("[data-preset]").first().waitFor();
  }
  assert.equal(new Set(Object.values(drawings)).size, 3);
  // Import keeps appearance; the original legacy record remains intact throughout.
  await page.click(".library-more summary");
  await page.locator("#design-import").setInputFiles(out + "/s1.json");
  await page.waitForFunction(
    () =>
      document.querySelector("#schematic-slot svg")?.dataset.appearance ===
      "sedan",
  );
  for (const width of [1024, 820, 390]) {
    await page.setViewportSize({ width, height: 900 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      "Design overflow " + width,
    );
  }
  await page.goto(base + "/?workspace=optimization");
  await page.locator("#compare-designs").waitFor({ state: "attached" });
  assert(new URL(page.url()).searchParams.get("workspace") === "anatomy");
  assert.equal(await page.locator("[role=tab]").count(), 4);
  await page.click("#tab-measurements");
  await page.waitForFunction(() =>
    document
      .getElementById("workspace-panel")
      .textContent.includes("Check readiness"),
  );
  assert.deepEqual(errors, []);
  const result = {
    status: "PASS",
    classes: ["sedan", "performance", "suv"],
    shared_identity: true,
    legacy_record_preserved: true,
    explicit_preset_drafts: true,
    customization_persistence_exports_imports: true,
    single_motor: true,
    distinct_body_geometry: true,
    runs,
    widths: [1440, 1024, 820, 390],
    themes: ["light", "dark"],
    optimization_redirect: true,
    measurements_functional: true,
    page_errors: errors,
  };
  fs.writeFileSync(
    out + "/browser.json",
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(JSON.stringify(result));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

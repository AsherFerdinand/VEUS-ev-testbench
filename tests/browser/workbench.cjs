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
  const out = process.env.VEUS_SCREENSHOTS || "/tmp/veus21-screens";
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
  for (const flow of [
    "propulsion",
    "regeneration",
    "ac_charging",
    "dc_charging",
    "auxiliary",
  ]) {
    await page.click(`[data-flow="${flow}"]`);
    assert((await page.locator(".vehicle-link.is-flow").count()) > 0);
    assert.equal(
      await page.locator(".anatomy-svg").getAttribute("data-flow"),
      flow,
    );
  }
  await page.click("#placement-view");
  const drawing = await page.locator(".anatomy-svg").boundingBox(),
    dockTop = await page.locator(".workspace-dock").boundingBox();
  assert(
    drawing.y + drawing.height < dockTop.y,
    "Whole schematic visible above laptop navigation",
  );
  for (const body of ["transparent", "opaque", "cutaway"]) {
    await page.selectOption("#vehicle-body", body);
    assert.equal(
      await page.locator(".anatomy-svg").getAttribute("data-body"),
      body,
    );
  }
  await page.uncheck("#vehicle-annotations");
  assert.equal(
    await page.locator(".anatomy-svg").getAttribute("data-annotations"),
    "false",
  );
  await page.check("#vehicle-annotations");
  for (const view of [
    "electrical",
    "drivetrain",
    "battery",
    "thermal",
    "complete",
  ]) {
    await page.selectOption("#vehicle-view", view);
    assert.equal(
      await page.locator(".anatomy-svg").getAttribute("data-view"),
      view,
    );
  }
  for (const id of [
    "battery",
    "motor",
    "inverter",
    "bms",
    "gearbox",
    "thermal",
    "dcdc",
    "charger",
    "port",
    "aux",
  ]) {
    await page.locator(`[data-component="${id}"]`).focus();
    await page.keyboard.press("Enter");
    assert.equal(
      await page.locator(".anatomy-svg").getAttribute("data-selected"),
      id,
    );
  }
  assert.equal(
    await page.locator('.vehicle-link[data-kind="phase"]').count(),
    3,
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
  await page.locator("#design-group").waitFor();
  await page.waitForFunction(() =>
    document
      .getElementById("configuration-status")
      .textContent.startsWith("Checked"),
  );
  await page.locator('[data-field="usable_capacity_kwh"]').fill("70");
  await page.click("#design-check");
  await page.waitForFunction(() =>
    document.querySelector('.compatibility-row[data-status="incompatible"]'),
  );
  assert(await page.locator("#prepare-adapter").isDisabled());
  await page.locator('[data-field="usable_capacity_kwh"]').fill("60");
  await page.locator("#design-name").fill("<script>engineering</script>");
  await page.click("#design-check");
  await page.waitForFunction(
    () =>
      !document.querySelector('.compatibility-row[data-status="incompatible"]'),
  );
  await page.locator(".library-more summary").click();
  const [file] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#design-export"),
  ]);
  await file.saveAs(out + "/illustrative-design.json");
  const design = JSON.parse(
    fs.readFileSync(out + "/illustrative-design.json", "utf8"),
  );
  assert.equal(design.schema_version, 2);
  assert.equal(design.classification, "illustrative");
  await page
    .locator("#design-import")
    .setInputFiles(out + "/illustrative-design.json");
  await page.waitForFunction(() =>
    document
      .getElementById("configuration-status")
      .textContent.startsWith("Checked"),
  );
  assert.equal(await page.locator("script:not([src])").count(), 0);
  await page.locator("#design-name").fill("Baseline analytical study");
  await page.click("#design-save");
  await page.waitForFunction(
    () => document.querySelectorAll("#library-select option").length === 2,
  );
  await page.reload();
  await page.locator("#design-group").waitFor();
  assert.equal(
    await page.locator("#design-name").inputValue(),
    "Baseline analytical study",
  );
  await page
    .getByText("Prepare for the retained physics model", { exact: true })
    .click();
  await page.click("#prepare-adapter");
  await page.waitForFunction(() =>
    document
      .getElementById("adapter-result")
      .textContent.includes("acknowledged"),
  );
  for (const box of await page.locator("[data-ack]").all()) await box.check();
  await page.click("#prepare-adapter");
  await page.waitForFunction(() =>
    document
      .getElementById("adapter-result")
      .textContent.includes("prepared_for_model_inspection"),
  );
  assert(
    (await page.locator("#adapter-result").innerText()).includes(
      "no experiment executed",
    ),
  );
  await page.click("#design-duplicate");
  await page.waitForFunction(
    () => document.querySelectorAll("#library-select option").length === 3,
  );
  await page.selectOption("#component-record", "battery-80");
  await page.waitForFunction(() =>
    document.getElementById("specifications").textContent.includes("1,848"),
  );
  await page.locator("#comparison-details summary").click();
  await page.selectOption("#comparison-baseline", {
    label: "Baseline analytical study",
  });
  await page.click("#compare-designs");
  await page.locator("#design-comparison table").first().waitFor();
  assert(
    (await page.locator("#design-comparison").innerText()).includes("100"),
  );
  assert(
    (await page.locator("#design-comparison").innerText()).includes(
      "Specifications only",
    ),
  );
  await page.selectOption("#component-record", "battery-64");
  await page.waitForFunction(() =>
    document.getElementById("specifications").textContent.includes("1,748"),
  );
  assert.equal(await page.locator("#design-comparison table").count(), 0);
  assert(
    (await page.locator("#design-comparison").innerText()).includes(
      "compare again",
    ),
  );
  await page.selectOption("#component-record", "battery-80");
  await page.waitForFunction(() =>
    document.getElementById("specifications").textContent.includes("1,848"),
  );
  await page.click("#design-save");
  await page.waitForFunction(
    () => document.querySelectorAll("#library-select option").length === 3,
  );
  await page.locator(".library-more summary").click();
  page.once("dialog", (d) => d.dismiss());
  await page.click("#design-delete");
  assert.equal(await page.locator("#library-select option").count(), 3);
  page.once("dialog", (d) => d.accept());
  await page.click("#design-delete");
  await page.waitForFunction(
    () => document.querySelectorAll("#library-select option").length === 2,
  );
  await page.locator("#design-group").selectOption("operating_point");
  await page.locator('[data-field="dc_power_kw"]').fill("90");
  await page.click("#tab-anatomy");
  await page.waitForTimeout(400);
  assert.equal(await page.locator("#component-inspector h2").count(), 1);
  await page.click("#tab-simulation");
  await page.locator("#lab-scenarios-mode").waitFor();
  await page.click("#lab-run");
  assert(
    (await page.locator("#lab-status").innerText())
      .toLowerCase()
      .includes("acknowledge"),
  );
  assert.equal(requests.filter((u) => u.endsWith("/api/lab/run")).length, 0);
  assert.equal(await page.locator("#tab-optimization").count(), 0);
  await page.goto(base + "/?workspace=optimization");
  await page.locator("#compare-designs").waitFor({ state: "attached" });
  assert.equal(new URL(page.url()).searchParams.get("workspace"), "design");
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
    "design",
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
      if (process.env.VEUS_CAPTURE !== "0")
        await page.screenshot({ path: `${out}/${key}-${theme}.png` });
      if (key === "anatomy") {
        await page.click("#flow-view");
        await page.click('[data-flow="ac_charging"]');
        if (process.env.VEUS_CAPTURE !== "0")
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
  if (process.env.VEUS_CAPTURE !== "0")
    await page.screenshot({ path: out + "/anatomy-mobile.png" });
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(base + "/engineering?workspace=analyse");
  await page.locator("#replayPanel").waitFor({ state: "attached" });
  assert(await page.locator('[data-analyse="investigate"]').isVisible());
  const corrupt = await browser.newPage();
  await corrupt.goto(base);
  await corrupt.locator("#component-inspector").waitFor();
  await corrupt.evaluate(() =>
    localStorage.setItem("veus.design-library.v2", "{broken"),
  );
  await corrupt.goto(base + "/?workspace=design");
  await corrupt.locator("#library-status").waitFor();
  assert(
    (await corrupt.locator("#library-status").innerText()).includes(
      "stored data was not changed",
    ),
  );
  assert.equal(
    await corrupt.evaluate(() =>
      localStorage.getItem("veus.design-library.v2"),
    ),
    "{broken",
  );
  await corrupt.close();
  const blocked = await browser.newPage();
  await blocked.addInitScript(() => {
    Storage.prototype.getItem = () => {
      throw Error("Storage blocked");
    };
    Storage.prototype.setItem = () => {
      throw Error("Storage blocked");
    };
  });
  await blocked.goto(base + "/?workspace=design");
  await blocked.locator("#design-save").waitFor();
  await blocked.waitForFunction(
    () => !document.getElementById("design-save").disabled,
  );
  await blocked.click("#design-save");
  await blocked.waitForFunction(() =>
    document
      .getElementById("notice")
      .textContent.includes("stored data was not changed"),
  );
  await blocked.close();
  assert.deepEqual(errors, []);
  const result = {
    status: "PASS",
    screenshots: out,
    workspaces: 5,
    themes: ["light", "dark"],
    widths: [1366, 1024, 820, 390],
    keyboard_components: true,
    keyboard_tabs: true,
    design_validation_roundtrip: true,
    persistence_and_comparison: true,
    corrupt_storage_preserved: true,
    blocked_storage_handled: true,
    component_effects: true,
    delete_confirmation: true,
    lab_requires_acknowledgements: true,
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

// First-time workflow: no automatic advanced-disclosure adapter.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright"),
  assert = require("node:assert/strict"),
  fs = require("node:fs");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ["--no-sandbox"],
  });
  try {
    const p = await browser.newPage({
        viewport: { width: 1440, height: 1100 },
      }),
      errors = [];
    p.on("pageerror", (e) => errors.push(e.message));
    const base = process.env.VEUS_URL || "http://127.0.0.1:8770",
      out = process.env.VEUS_SCREENSHOTS || "/tmp/refocus/normal";
    fs.mkdirSync(out, { recursive: true });
    const capture = process.env.VEUS_CAPTURE === "1",
      presets = (
        await (await p.request.get(base + "/api/workbench/v2/presets")).json()
      ).presets;
    const current = () =>
      p.evaluate(async () =>
        structuredClone(
          (await import("/static/workbench/design-state.js")).state.design,
        ),
      );
    await p.goto(base + "/?workspace=design");
    await p.locator("#basic-capacity").waitFor();
    assert.equal(new URL(p.url()).searchParams.get("workspace"), "anatomy");
    assert.equal(await p.locator("[role=tab]").count(), 4);
    assert.equal(await p.locator(".anatomy-svg").count(), 1);
    assert.equal(
      await p.locator("#advanced-configuration").getAttribute("open"),
      null,
    );
    assert.equal(
      await p.locator("#advanced-analysis").getAttribute("open"),
      null,
    );
    await p.click('[data-preset="s1"]');
    await p.waitForFunction(() =>
      document
        .querySelector("#configuration-status")
        .textContent.startsWith("Checked"),
    );
    assert.deepEqual(
      await current(),
      presets.find((v) => v.id === "s1").design,
    );
    await p.click("#design-save");
    await p.waitForFunction(() =>
      document
        .querySelector("#design-draft-status")
        .textContent.startsWith("Saved"),
    );
    const saved = await p.evaluate(() =>
      localStorage.getItem("veus.design-library.v2"),
    );
    await p.fill("#basic-drag", ".26");
    await p.locator("#basic-power").focus();
    await p.waitForFunction(() =>
      document
        .querySelector("#configuration-status")
        .textContent.startsWith("Checked"),
    );
    p.once("dialog", (d) => d.dismiss());
    await p.click('[data-preset="r1"]');
    assert.equal((await current()).body.drag_coefficient, 0.26);
    assert.equal(
      await p.evaluate(() => localStorage.getItem("veus.design-library.v2")),
      saved,
    );
    p.once("dialog", (d) => d.accept());
    await p.click('[data-preset="r1"]');
    await p.waitForFunction(
      () => document.querySelector("#basic-capacity").value === "90",
    );
    assert.deepEqual(
      await current(),
      presets.find((v) => v.id === "r1").design,
    );
    assert.equal(
      await p.locator("#schematic-slot svg").getAttribute("data-appearance"),
      "performance",
    );
    assert.equal(
      await p.evaluate(() => localStorage.getItem("veus.design-library.v2")),
      saved,
    );
    p.once("dialog", (d) => d.accept());
    await p.click('[data-preset="s1"]');
    await p.waitForFunction(
      () => document.querySelector("#basic-capacity").value === "60",
    );
    if (capture) {
      await p.setViewportSize({ width: 1440, height: 1500 });
      await p.screenshot({
        path: out + "/vehicle-architecture.png",
        fullPage: true,
      });
      await p.setViewportSize({ width: 1440, height: 1100 });
    }
    const source = await current();
    await p.click(".run-configuration");
    await p.locator("#model-ack").waitFor();
    assert.deepEqual(await current(), source);
    await p.click("#lab-run");
    assert.match(await p.locator("#lab-status").innerText(), /Confirm/);
    assert.equal(await p.evaluate(() => !!window.VEUSLab?.result), false);
    await p.check("#model-ack");
    async function run() {
      const [r] = await Promise.all([
        p.waitForResponse(
          (r) =>
            r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
        ),
        p.click("#lab-run"),
      ]);
      assert.equal(r.status(), 200, await r.text());
      const value = await r.json();
      await p.waitForFunction(
        (hash) => window.VEUSLab?.result?.run_sha256 === hash,
        value.run_sha256,
      );
      return value;
    }
    const cruise = await run();
    assert.deepEqual(cruise.request.vehicle, source);
    assert.equal(cruise.request.acknowledgements.length, 5);
    assert.equal(
      await p.locator("#lab-scene-svg").getAttribute("data-camera"),
      "side",
    );
    for (const kind of ["braking", "coast", "gradient"]) {
      await p.click('[data-kind="' + kind + '"]');
      const r = await run();
      assert.equal(
        await p.locator("#lab-scene-svg").getAttribute("data-camera"),
        "side",
      );
      if (kind === "gradient")
        assert(
          Math.abs(
            Number(
              await p
                .locator("#lab-scene-svg")
                .getAttribute("data-grade-angle"),
            ) -
              (Math.atan(r.experiment.grade_percent / 100) * 180) / Math.PI,
          ) < 1e-8,
        );
    }
    await p.click('[data-kind="acceleration"]');
    const passing = await run();
    assert.equal(
      await p.locator("#lab-scene-svg").getAttribute("data-camera"),
      "top-down",
    );
    const point = passing.trace.find(
      (r) =>
        70 + 8 * r.time_s - r.position_m < 35 &&
        70 + 8 * r.time_s - r.position_m > 20,
    );
    assert(point);
    const seek = (t) =>
      p.locator("#lab-seek").evaluate((e, t) => {
        e.value = t;
        e.dispatchEvent(new Event("input"));
      }, t);
    await seek(point.time_s);
    const pose = await p.locator("#lab-hero-car").getAttribute("transform");
    await seek(15);
    await seek(point.time_s);
    assert.equal(
      await p.locator("#lab-hero-car").getAttribute("transform"),
      pose,
    );
    if (capture) {
      await p.locator(".lab-instrument").scrollIntoViewIfNeeded();
      await p.screenshot({ path: out + "/simulation-overtaking.png" });
    }
    await p.selectOption("#lab-simple-cycle", "urban");
    await p.waitForFunction(
      () => document.querySelector("#lab-profile").value === "urban",
    );
    await p.waitForTimeout(200);
    const urban = await run();
    assert.equal(urban.experiment.kind, "profile");
    assert.equal(urban.request.profile.id, "urban");
    // A newly selected cycle may not reuse the previous one while its GET is pending.
    const nextProfile = await (
      await p.request.get(base + "/api/lab/profiles/motorway")
    ).json();
    let releaseCycle, cycleArrived;
    const cycleWait = new Promise((r) => (releaseCycle = r)),
      cycleStarted = new Promise((r) => (cycleArrived = r));
    await p.route("**/profiles/motorway", async (route) => {
      const response = await route.fetch();
      cycleArrived();
      await cycleWait;
      await route.fulfill({ response }).catch(() => {});
    });
    await p.selectOption("#lab-simple-cycle", "motorway");
    await cycleStarted;
    await p.click("#lab-run");
    assert.match(
      await p.locator("#lab-status").innerText(),
      /previous cycle will not be reused/,
    );
    assert.equal(
      await p.evaluate(() => VEUSLab.result.run_sha256),
      urban.run_sha256,
    );
    releaseCycle();
    const sourceLoaded = (src) => {
      try {
        return (
          JSON.stringify(
            JSON.parse(document.getElementById("lab-input-source").textContent)
              .profile,
          ) === src
        );
      } catch {
        return false;
      }
    };
    await p.waitForFunction(sourceLoaded, JSON.stringify(nextProfile.source));
    assert.equal((await run()).request.profile.id, "motorway");
    await p.unroute("**/profiles/motorway");
    await p.selectOption("#lab-simple-cycle", "urban");
    await p.waitForFunction(
      sourceLoaded,
      JSON.stringify(urban.request.profile.source),
    );
    assert.equal((await run()).run_sha256, urban.run_sha256);

    await p.locator("#lab-model-comparison summary").click();
    const [cmp] = await Promise.all([
      p.waitForResponse((r) => r.url().endsWith("/powertrain-comparison")),
      p.click("#motor-map-compare"),
    ]);
    assert.equal(cmp.status(), 200);
    const compared = await cmp.json();
    assert.deepEqual(
      compared.legacy.request.vehicle,
      compared.mapped.request.vehicle,
    );
    const [sim] = await Promise.all([
      p.waitForEvent("download"),
      p.click("#lab-json"),
    ]);
    await sim.saveAs(out + "/simulation.json");
    assert.equal(
      JSON.parse(fs.readFileSync(out + "/simulation.json", "utf8")).run_sha256,
      urban.run_sha256,
    );
    await p.click("#tab-measurements");
    await p.waitForFunction(
      () =>
        document.querySelector("#measure-speed")?.dataset.available === "true",
    );
    assert.equal(await p.locator("#measure-confirm").isChecked(), false);
    assert.match(await p.locator("#measurement-summary").innerText(), /534/);
    assert.equal(
      await p.locator('[data-measure-format="json"]').isDisabled(),
      true,
    );
    await p.selectOption("#measurement-recording", "ved-10-1567-full");
    await p.waitForFunction(
      () =>
        document
          .querySelector("#measurement-summary")
          .textContent.includes("367") &&
        document.querySelector("#measure-speed").dataset.available === "true",
    );
    assert.equal(await p.evaluate(() => !!window.VEUSMeasurements), false);
    await p.selectOption("#measure-signal", "battery_current_a");
    assert.equal(
      await p.locator("#measure-electrical").getAttribute("data-available"),
      "true",
    );
    await p.selectOption("#measure-signal", "electrical_power_w");
    assert.equal(
      await p.locator("#measure-electrical").getAttribute("data-available"),
      "false",
    );
    await p.selectOption("#measure-signal", "battery_voltage_v");
    await p.check("#measure-confirm");
    await p.click("#measure-investigate");
    await p.waitForFunction(
      () =>
        window.VEUSMeasurements?.recordings?.[0]?.analysis.time_s.length ===
        367,
    );
    const rec = await p.evaluate(() => VEUSMeasurements.recordings[0]);
    assert(rec.events.length);
    await p.selectOption("#measure-event", String(rec.events[0].event_index));
    await p.click("#measure-interval");
    await p.click("#measure-compare-entry");
    assert.match(
      await p.locator("#measure-model").innerText(),
      /illustrative|Independent/,
    );
    await p.click("#measure-validation summary");
    await p.click("#validation-assess");
    await p.waitForFunction(
      () => window.VEUSValidationAssessment?.status === "INCONCLUSIVE",
    );
    assert.equal(
      await p.evaluate(() => VEUSValidationAssessment.metrics),
      null,
    );
    const [report] = await Promise.all([
      p.waitForEvent("download"),
      p.click('[data-measure-format="html"]'),
    ]);
    await report.saveAs(out + "/investigation.html");
    assert(
      fs
        .readFileSync(out + "/investigation.html", "utf8")
        .includes("INCONCLUSIVE"),
    );
    for (const id of ["measure-validation", "measure-model"])
      await p.locator("#" + id).evaluate((e) => (e.open = false));
    if (capture) {
      await p.locator(".measure-dashboard").scrollIntoViewIfNeeded();
      await p.screenshot({ path: out + "/measurements.png" });
    }
    await p.route("**/recordings/ved-10-1561-full", (r) =>
      r.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Missing bundled recording (test fault)",
        }),
      }),
    );
    await p.selectOption("#measurement-recording", "ved-10-1561-full");
    await p.waitForFunction(() =>
      document
        .querySelector("#measure-status")
        .textContent.includes("Missing bundled"),
    );
    assert.equal(
      await p.locator("#measure-speed").getAttribute("data-available"),
      "false",
    );
    assert.equal(
      await p.locator('[data-measure-format="html"]').isDisabled(),
      true,
    );
    await p.unroute("**/recordings/ved-10-1561-full");
    await p.selectOption("#measurement-recording", "ved-10-1567-full");
    await p.waitForFunction(
      () =>
        document.querySelector("#measure-speed").dataset.available === "true",
    );
    for (const width of [1024, 390]) {
      await p.setViewportSize({ width, height: 1100 });
      assert.equal(
        await p.evaluate(
          () => document.documentElement.scrollWidth > innerWidth + 1,
        ),
        false,
      );
    }
    await p.click("#tab-challenges");
    await p.locator('[data-learn="drag"]').waitFor();
    for (const id of ["drag", "mass", "regen"]) {
      await p.click('[data-learn="' + id + '"]');
      await p.waitForFunction(
        (id) =>
          !document
            .querySelector("#learn-result-" + id)
            .textContent.startsWith("Computing"),
        id,
      );
      assert.doesNotMatch(
        await p.locator("#learn-result-" + id).innerText(),
        /Unavailable|Confirm|Configure/,
      );
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      out + "/refocus.json",
      JSON.stringify(
        {
          status: "PASS",
          unified_vehicle: true,
          saved_protection: true,
          configuration_transfer: true,
          single_explicit_ack: true,
          backend_flags: 5,
          side_views: 4,
          top_down_overtaking: true,
          deterministic_seek: true,
          urban_run_sha256: urban.run_sha256,
          preview_without_consent: true,
          mapping_confirmation_retained: true,
          event_report_export: true,
          failed_selection_clears_old_result: true,
          interactive_learning: 3,
          physical_validation: "INCONCLUSIVE",
          errors,
        },
        null,
        2,
      ),
    );
    console.log("Refocus normal workflow PASS");
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

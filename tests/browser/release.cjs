// Release-candidate UX/integration checks; calculations stay in existing Python services.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright"),
  assert = require("node:assert/strict"),
  fs = require("node:fs");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage({
        viewport: { width: 1440, height: 1100 },
      }),
      errors = [];
    require("./advanced-disclosure.cjs")(page);
    page.on("pageerror", (e) => errors.push(e.message));
    const operations = [];
    page.on("requestfinished", (req) => {
      if (req.method() === "POST" && req.url().includes("/api/"))
        operations.push({
          path: new URL(req.url()).pathname,
          elapsed_ms: req.timing().responseEnd,
        });
    });
    const base = process.env.VEUS_URL || "http://127.0.0.1:8770",
      out = process.env.VEUS_SCREENSHOTS || "/tmp/veus30";
    fs.mkdirSync(out, { recursive: true });
    const presets = (
      await (await page.request.get(base + "/api/workbench/v2/presets")).json()
    ).presets;
    await page.addInitScript(
      (p) =>
        localStorage.setItem(
          "veus.design-library.v2",
          JSON.stringify({
            schema_version: 1,
            active_id: "s1",
            records: p.map((v) => ({ id: v.id, design: v.design })),
          }),
        ),
      presets,
    );
    await page.goto(base + "/?workspace=design");
    await page.locator("#design-draft-status").waitFor();
    await page.waitForFunction(() =>
      document
        .querySelector("#configuration-status")
        .textContent.startsWith("Checked"),
    );
    assert.match(await page.locator(".edition").innerText(), /3.0 RC1/);
    assert.match(
      await page.locator("#design-draft-status").innerText(),
      /Saved custom/,
    );
    await page.fill("#design-name", "Release review draft");
    assert.match(
      await page.locator("#design-draft-status").innerText(),
      /Unsaved modifications/,
    );
    await page.click("#design-save");
    await page.waitForFunction(() =>
      document
        .querySelector("#design-draft-status")
        .textContent.startsWith("Saved custom"),
    );
    const stored = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("veus.design-library.v2")),
    );
    assert.equal(
      stored.records.find((v) => v.id === "s1").design.name,
      "Release review draft",
    );
    // Roving tabs retain keyboard access and browser Back/deep links.
    await page.focus("#tab-anatomy");
    await page.keyboard.press("ArrowRight");
    await page.locator("#lab-run").waitFor();
    assert.equal(
      await page.locator(":focus").getAttribute("id"),
      "tab-simulation",
    );
    assert.equal(
      await page.locator("#tab-simulation").getAttribute("aria-selected"),
      "true",
    );
    await page.keyboard.press("ArrowRight");
    await page.locator("#measurement-recording").waitFor();
    assert.equal(
      await page.locator(":focus").getAttribute("id"),
      "tab-measurements",
    );
    await page.click("#measure-validation summary");
    assert.equal(await page.locator("#validation-design").count(), 1);
    assert.equal(
      await page.locator("#validation-result").getAttribute("role"),
      "status",
    );
    await page.click("#workflow-next");
    await page.locator("#design-name").waitFor();
    assert.equal(await page.inputValue("#design-name"), "Release review draft");
    assert.equal(
      await page.locator(":focus").getAttribute("id"),
      "workspace-content",
    );
    await page.goBack();
    await page.locator("#measurement-recording").waitFor();
    if (process.env.VEUS_STAGE !== "A") {
      await page.click("#tab-anatomy");
      await page.waitForFunction(() =>
        document
          .querySelector("#configuration-status")
          ?.textContent.startsWith("Checked"),
      );
      let release, arrived;
      const gate = new Promise((r) => (release = r)),
        received = new Promise((r) => (arrived = r));
      await page.route("**/api/workbench/v2/evaluate", async (route) => {
        const response = await route.fetch();
        arrived();
        await gate;
        await route.fulfill({ response });
      });
      await page.click("#design-check");
      await received;
      await page.fill("#design-name", "Newer in-flight edit");
      release();
      await page.waitForFunction(
        () =>
          !document
            .querySelector("#configuration-status")
            .textContent.startsWith("Checking"),
      );
      assert.equal(
        await page.evaluate(
          async () =>
            (await import("/static/workbench/design-state.js")).state.design
              .name,
        ),
        "Newer in-flight edit",
      );
      assert.match(
        await page.locator("#configuration-status").innerText(),
        /Design changed/,
      );
      await page.unroute("**/api/workbench/v2/evaluate");
      await page.click("#design-check");
      await page.waitForFunction(() =>
        document
          .querySelector("#configuration-status")
          .textContent.startsWith("Checked"),
      );
      await page.click("#design-save");
      await page.waitForFunction(() =>
        document
          .querySelector("#design-draft-status")
          .textContent.startsWith("Saved custom"),
      );
      await page.click("#insights-panel summary");
      await page.check("#insights-ack");
      await page.click("#insights-run");
      await page.waitForFunction(() => window.VEUSInsights?.insights_sha256);
      const insights = await page.evaluate(() => VEUSInsights);
      assert.equal(insights.request.vehicle.name, "Newer in-flight edit");
      assert(insights.configuration_sha256);
      await page.click("#workflow-next");
      await page.locator("#lab-run").waitFor();
      const active = await page.evaluate(
        async () =>
          (await import("/static/workbench/design-state.js")).state.design,
      );
      assert.deepEqual(active, insights.request.vehicle);
      await page.locator("#lab-config").evaluate((e) => (e.open = true));
      await page.selectOption("#lab-vehicle", "r1");
      assert.match(await page.locator(".edition-note").innerText(), /R1/);
      await page.locator("#lab-assumptions").evaluate((e) => (e.open = true));
      for (const c of await page.locator(".lab-ack").all()) await c.check();
      const [run] = await Promise.all([
        page.waitForResponse(
          (r) =>
            r.url().endsWith("/api/lab/run") && r.request().method() === "POST",
        ),
        page.click("#lab-run"),
      ]);
      assert.equal(run.status(), 200);
      const result = await run.json();
      assert.deepEqual(
        result.request.vehicle,
        presets.find((p) => p.id === "r1").design,
      );
      assert(result.run_sha256);
      await page.click("#tab-measurements");
      await page.waitForFunction(() =>
        document
          .querySelector("#measurement-summary")
          ?.textContent.includes("534"),
      );
      await page.check("#measure-confirm");
      await page.click("#measure-investigate");
      await page.waitForFunction(() => window.VEUSMeasurements?.recordings);
      await page.click("#measure-validation summary");
      await page.selectOption("#validation-design", "x1");
      await page.click("#validation-assess");
      await page.waitForFunction(
        () => window.VEUSValidationAssessment?.assessment_sha256,
      );
      const assessment = await page.evaluate(() => VEUSValidationAssessment);
      assert.equal(assessment.status, "INCONCLUSIVE");
      assert.equal(assessment.metrics, null);
      assert.deepEqual(
        assessment.request.vehicle,
        presets.find((p) => p.id === "x1").design,
      );
      assert(assessment.source_sha256 && assessment.model_configuration_sha256);
      // A rejected retry cannot export the previously successful assessment.
      await page.fill("#validation-calibration", "0,150");
      await page.fill("#validation-evaluation", "100,200");
      await page.click("#validation-assess");
      await page.waitForFunction(() =>
        document
          .querySelector("#validation-result")
          .textContent.includes("Assessment unavailable"),
      );
      assert.equal(await page.locator("#validation-export").isDisabled(), true);
      assert.equal(await page.locator("#validation-html").isDisabled(), true);
      assert.equal(
        await page.evaluate(
          () => window.VEUSValidationAssessment === undefined,
        ),
        true,
      );
      // Leaving during an assessment aborts cleanly, without touching the next workspace.
      await page.fill("#validation-calibration", "");
      await page.fill("#validation-evaluation", "");
      let held, began;
      const wait = new Promise((r) => (held = r)),
        started = new Promise((r) => (began = r));
      await page.route("**/validation-readiness", async (route) => {
        const response = await route.fetch();
        began();
        await wait;
        await route.fulfill({ response }).catch(() => {});
      });
      await page.click("#validation-assess");
      await started;
      await page.click("#tab-anatomy");
      held();
      await page.locator("#vehicle-view").waitFor();
      await page.unroute("**/validation-readiness");
      fs.writeFileSync(
        out + "/release-B.json",
        JSON.stringify(
          {
            status: "PASS",
            stale_evaluation_preserves_edits: true,
            saved_snapshot_to_insights_and_lab: true,
            lab_selection_updates_active_label: true,
            validation_uses_explicit_saved_design: true,
            failed_retry_clears_old_export: true,
            in_flight_cleanup: true,
            source_hash: assessment.source_sha256,
          },
          null,
          2,
        ),
      );
      console.log("Release checkpoint B PASS");
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      out + "/release-A.json",
      JSON.stringify(
        {
          status: "PASS",
          keyboard_tabs: true,
          contextual_return: true,
          saved_draft_labels: true,
          theme_responsive_audit: "audit-A.json",
          errors,
        },
        null,
        2,
      ),
    );
    fs.writeFileSync(
      out + "/workflow-observations.json",
      JSON.stringify(
        {
          scope:
            "Single integration-run HTTP observations, not an isolated benchmark; no extra calculation repetitions",
          operations,
        },
        null,
        2,
      ),
    );
    console.log("Release checkpoint A PASS");
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

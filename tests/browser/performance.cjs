// Optional comparable Chromium snapshots; no runtime dependency or product feature.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright"),
  fs = require("node:fs");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
    args: ["--no-sandbox"],
  });
  const samples = [];
  for (let trial = 0; trial < 4; trial++) {
    const page = await browser.newPage({
        viewport: { width: 1366, height: 768 },
      }),
      urls = [],
      sockets = [];
    page.on("request", (r) => urls.push(r.url()));
    page.on("websocket", (w) => sockets.push(w.url()));
    await page.addInitScript(() => {
      const timeouts = new Set(),
        intervals = new Set(),
        frames = new Set(),
        set = window.setTimeout.bind(window),
        clear = window.clearTimeout.bind(window),
        interval = window.setInterval.bind(window),
        clearInterval = window.clearInterval.bind(window),
        frame = window.requestAnimationFrame.bind(window),
        cancel = window.cancelAnimationFrame.bind(window);
      window.setTimeout = (fn, d, ...a) => {
        let id = set(() => {
          timeouts.delete(id);
          typeof fn === "function" ? fn(...a) : eval(fn);
        }, d);
        timeouts.add(id);
        return id;
      };
      window.clearTimeout = (id) => {
        timeouts.delete(id);
        clear(id);
      };
      window.setInterval = (fn, d, ...a) => {
        let id = interval(fn, d, ...a);
        intervals.add(id);
        return id;
      };
      window.clearInterval = (id) => {
        intervals.delete(id);
        clearInterval(id);
      };
      window.requestAnimationFrame = (fn) => {
        let id = frame((t) => {
          frames.delete(id);
          fn(t);
        });
        frames.add(id);
        return id;
      };
      window.cancelAnimationFrame = (id) => {
        frames.delete(id);
        cancel(id);
      };
      window.veusTimers = () => ({
        timeouts: timeouts.size,
        intervals: intervals.size,
        frames: frames.size,
      });
    });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Performance.enable");
    let start = Date.now();
    await page.goto(process.env.VEUS_URL || "http://127.0.0.1:8790");
    await page.locator("#component-inspector h2").waitFor();
    await page.waitForLoadState("networkidle");
    let loaded = Date.now() - start;
    const resources = await page.evaluate(() =>
        performance.getEntriesByType("resource").map((x) => ({
          path: new URL(x.name).pathname,
          bytes: x.encodedBodySize,
        })),
      ),
      n = urls.length,
      before = (await cdp.send("Performance.getMetrics")).metrics;
    await page.waitForTimeout(1200);
    const after = (await cdp.send("Performance.getMetrics")).metrics,
      metric = (rows, n) => rows.find((x) => x.name === n)?.value ?? null;
    const idleRequests = urls.length - n,
      timers = await page.evaluate(() => window.veusTimers());
    const latencies = [];
    for (let i = 0; i < 15; i++)
      latencies.push(
        await page.evaluate((i) => {
          let t = performance.now();
          document
            .querySelector(`[data-component="${i % 2 ? "motor" : "battery"}"]`)
            .dispatchEvent(new MouseEvent("click", { bubbles: true }));
          return performance.now() - t;
        }, i),
      );
    const editStart = urls.length;
    await page.click("#tab-anatomy");
    await page.locator("#configuration-status").waitFor();
    await page.waitForFunction(
      () =>
        document
          .getElementById("configuration-status")
          .textContent.startsWith("Checked") ||
        document
          .getElementById("configuration-status")
          .textContent.includes("Illustrative defaults"),
    );
    samples.push({
      warmup: trial === 0,
      load_ms: loaded,
      first_load_resources: resources,
      first_resource_body_bytes: resources.reduce((a, r) => a + r.bytes, 0),
      editor_requests: urls.slice(editStart).map((u) => new URL(u).pathname),
      anatomy_heap_bytes: metric(after, "JSHeapUsedSize"),
      design_heap_bytes: metric(
        (await cdp.send("Performance.getMetrics")).metrics,
        "JSHeapUsedSize",
      ),
      browser_main_thread_idle_task_percent:
        ((metric(after, "TaskDuration") - metric(before, "TaskDuration")) /
          1.2) *
        100,
      idle_background_requests: idleRequests,
      static_websockets: sockets.length,
      static_pending_timers: timers,
      selection_ms_median: latencies.sort((a, b) => a - b)[7],
    });
    await page.close();
  }
  fs.writeFileSync(
    process.env.PERFORMANCE_OUTPUT || "/tmp/veus-browser-performance.json",
    JSON.stringify(
      {
        scope:
          "Warm-up excluded; three fresh Chromium pages. Load includes networkidle 500 ms. Main-thread task fraction is not total browser CPU; JS heap is not process RSS. Selection measures synchronous handler time, not full paint latency. Timer wrappers count pending application callbacks, not browser internals.",
        samples,
      },
      null,
      2,
    ) + "\n",
  );
  await browser.close();
  console.log("Browser snapshots complete");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

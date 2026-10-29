"use strict";
// Shared cached signal renderer; no source resampling, clock or analysis rules.
window.VEUSRecordingPlot = class {
  constructor() {
    this.cache = new WeakMap();
  }
  draw(canvas, result, state, key, interval = null, normalized = false) {
    if (!canvas?.getClientRects().length || !result) return;
    const clock = { duration: result.time_s.at(-1) };
    const w = canvas.clientWidth,
      h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1),
      signature = [
        key,
        w,
        h,
        dpr,
        result.analysis_sha256,
        JSON.stringify(interval),
        normalized,
      ].join(":");
    let cached = this.cache.get(canvas);
    if (!cached || cached.signature !== signature) {
      const image = document.createElement("canvas");
      image.width = w * dpr;
      image.height = h * dpr;
      const c = image.getContext("2d");
      c.scale(dpr, dpr);
      const left = 62,
        right = w - 12,
        top = 15,
        bottom = h - 28,
        scale =
          key === "vehicle_speed_ms"
            ? 3.6
            : key === "battery_soc"
              ? 100
              : ["electrical_power_w", "battery_power_w"].includes(key)
                ? 0.001
                : 1,
        values = result.measured[key] || result.derived[key] || [],
        finite = values.filter(Number.isFinite).map((v) => v * scale);
      let low =
          key === "battery_soc" && finite.length
            ? Math.min(...finite)
            : Math.min(0, ...finite),
        high = Math.max(low + 1, ...finite);
      const pad = (high - low) * 0.1;
      low -= key === "battery_soc" ? pad : 0;
      high += pad;
      c.fillStyle = "#19211e";
      c.fillRect(0, 0, w, h);
      c.font = "11px system-ui";
      for (const gap of result.metadata.gaps) {
        c.fillStyle = "#584b3c";
        c.fillRect(
          left + (gap.start_s / clock.duration) * (right - left),
          top,
          ((gap.end_s - gap.start_s) / clock.duration) * (right - left),
          bottom - top,
        );
      }
      if (interval) {
        c.fillStyle = "#3e6651";
        c.fillRect(
          left + (interval[0] / clock.duration) * (right - left),
          top,
          Math.max(
            2,
            ((interval[1] - interval[0]) / clock.duration) * (right - left),
          ),
          bottom - top,
        );
      }
      for (let i = 0; i <= 4; i++) {
        const y = top + ((bottom - top) * i) / 4;
        c.strokeStyle = "#334239";
        c.beginPath();
        c.moveTo(left, y);
        c.lineTo(right, y);
        c.stroke();
        c.fillStyle = "#adbcaf";
        c.fillText(
          (high - ((high - low) * i) / 4).toFixed(
            key === "battery_soc" ? 2 : 1,
          ),
          3,
          y + 4,
        );
      }
      c.fillText(normalized ? "0%" : "0 s", left, h - 6);
      c.fillText(
        normalized ? "100% elapsed" : clock.duration.toFixed(1) + " s",
        right - (normalized ? 78 : 43),
        h - 6,
      );
      c.strokeStyle = key === "electrical_power_w" ? "#d9b28c" : "#b4e5bb";
      c.lineWidth = 2;
      c.beginPath();
      let started = false;
      result.time_s.forEach((t, i) => {
        const v = values[i];
        if (v === null || v === undefined) {
          started = false;
          return;
        }
        if (
          i &&
          t - result.time_s[i - 1] >
            result.configuration.preprocessing.max_gap_s
        )
          started = false;
        const x = left + (t / clock.duration) * (right - left),
          y = bottom - ((v * scale - low) / (high - low)) * (bottom - top);
        if (started) c.lineTo(x, y);
        else c.moveTo(x, y);
        started = true;
      });
      c.stroke();
      if (!finite.length) {
        c.fillStyle = "#adbcaf";
        c.fillText("Unavailable: no valid samples", left, top + 30);
      }
      cached = { signature, image, left, right };
      this.cache.set(canvas, cached);
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.dataset.plotLeft = left;
      canvas.dataset.plotRight = right;
    }
    const c = canvas.getContext("2d");
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.drawImage(cached.image, 0, 0);
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    const x =
      cached.left +
      (state.time_s / clock.duration) * (cached.right - cached.left);
    c.strokeStyle = "#edf0d7";
    c.lineWidth = 1;
    c.setLineDash([4, 3]);
    c.beginPath();
    c.moveTo(x, 8);
    c.lineTo(x, h - 25);
    c.stroke();
    c.setLineDash([]);
    canvas.dataset.cursorTime = state.time_s.toFixed(6);
  }
};

"use strict";
(() => {
  const el = (id) => document.getElementById(id);
  let latest = null,
    previous = null,
    receipt = 0,
    interval = 100,
    selected = null,
    presets = [],
    images = {},
    paint = "#a3dfbd";
  let held = new Set(),
    touch = new Set(),
    inputTimer = null,
    lastInput = "",
    staleHandled = false;
  let requestedRun = false,
    queuedReset = null,
    viewPosition = 0,
    viewGap = null,
    raf = null,
    frameTimes = [],
    lastFrame = 0;
  const isTyping = (target) =>
    !!target?.closest('input,textarea,select,[contenteditable="true"]');
  const usable = () =>
    connected &&
    appliedConfig?.mode === "manual" &&
    window.activeWorkspace === "drive" &&
    !el("vehicleDialog").open &&
    latest &&
    !["completed", "collision"].includes(latest.status);
  function demands(throttle, brake) {
    if (brake > 0) throttle = 0;
    el("throttle").value = String(throttle);
    el("brake").value = String(brake);
    el("throttle_value").value = throttle + "%";
    el("brake_value").value = brake + "%";
    const value = JSON.stringify({
      throttle: throttle / 100,
      brake: brake / 100,
    });
    if (value !== lastInput) {
      send({ action: "controls", controls: JSON.parse(value) });
      lastInput = value;
    }
    el("touchThrottle").classList.toggle("active", throttle > 0);
    el("touchBrake").classList.toggle("active", brake > 0);
  }
  function release() {
    held.clear();
    touch.clear();
    clearInterval(inputTimer);
    inputTimer = null;
    demands(0, 0);
  }
  function keyDemand() {
    if (!usable()) {
      release();
      return;
    }
    const accelerate =
      held.has("KeyW") || held.has("ArrowUp") || touch.has("throttle");
    const brake =
      held.has("KeyS") || held.has("ArrowDown") || touch.has("brake");
    demands(accelerate ? 100 : 0, brake ? 100 : 0);
  }
  function scheduleDemand() {
    keyDemand();
    if (!inputTimer)
      inputTimer = setInterval(() => {
        if (held.size || touch.size) keyDemand();
        else {
          clearInterval(inputTimer);
          inputTimer = null;
        }
      }, 50);
  }
  // Send at state changes, not browser key-repeat frequency. Brake wins conflicts.
  window.VEUS = {
    release,
    slider: () => {
      held.clear();
      touch.clear();
      demands(Number(el("throttle").value), Number(el("brake").value));
    },
    debug: () => ({
      viewPosition,
      viewGap,
      frameCount: frameTimes.length,
      averageFrameMs: frameTimes.length
        ? frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length
        : null,
      selected: selected?.id,
    }),
  };
  function reset(start = false) {
    release();
    requestedRun = start;
    if (!connected) {
      el("driveNotice").textContent =
        "Disconnected. Reload to create a new session.";
      return;
    }
    el("configuration").requestSubmit();
  }
  function runPause() {
    release();
    if (!connected) return;
    if (latest?.status === "running") send({ action: "pause" });
    else if (["completed", "collision"].includes(latest?.status)) reset(true);
    else send({ action: "start" });
  }
  el("driveRun").onclick = runPause;
  el("driveReset").onclick = () => reset();
  document.addEventListener("keydown", (e) => {
    if (e.code === "Escape") {
      release();
      if (el("vehicleDialog").open) el("vehicleDialog").close();
      return;
    }
    if (
      window.activeWorkspace !== "drive" ||
      isTyping(e.target) ||
      el("vehicleDialog").open ||
      el("chartDialog").open ||
      e.ctrlKey ||
      e.metaKey ||
      e.altKey
    )
      return;
    if (
      ["KeyW", "ArrowUp", "KeyS", "ArrowDown", "Space", "KeyR"].includes(e.code)
    ) {
      e.preventDefault();
      if (e.repeat) return;
      if (e.code === "Space") {
        runPause();
        return;
      }
      if (e.code === "KeyR") {
        reset();
        return;
      }
      if (!usable()) return;
      held.add(e.code);
      scheduleDemand();
    }
  });
  document.addEventListener("keyup", (e) => {
    if (held.delete(e.code)) {
      e.preventDefault();
      keyDemand();
    }
  });
  document.addEventListener("focusin", (e) => {
    if (isTyping(e.target)) release();
  });
  window.addEventListener("blur", release);
  document.addEventListener("veus:workspace", () => {
    release();
    if (latest?.status === "running") send({ action: "pause" });
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      release();
      send({ action: "pause" });
      cancelAnimationFrame(raf);
      raf = null;
    } else startRender();
  });
  el("vehicleDialog").addEventListener("close", release);
  el("chooseVehicle").addEventListener("click", () => {
    release();
    send({ action: "pause" });
  });
  for (const [id, pedal] of [
    ["touchThrottle", "throttle"],
    ["touchBrake", "brake"],
  ]) {
    const button = el(id);
    button.addEventListener("pointerdown", (e) => {
      if (!usable()) return;
      e.preventDefault();
      button.setPointerCapture(e.pointerId);
      touch.add(pedal);
      scheduleDemand();
    });
    for (const name of ["pointerup", "pointercancel", "lostpointercapture"])
      button.addEventListener(name, () => {
        touch.delete(pedal);
        keyDemand();
      });
  }
  el("driveMode").onchange = () => {
    release();
    el("mode").value = el("driveMode").value;
    el("mode").dispatchEvent(new Event("change"));
    reset();
  };
  el("vehicleColor").oninput = () => {
    paint = el("vehicleColor").value;
    loadImages();
  };
  async function loadImages() {
    const color = paint;
    for (const id of ["hatch", "sedan", "coupe", "suv"]) {
      const svg = await fetch("/static/vehicles/" + id + ".svg").then((r) =>
        r.text(),
      );
      const img = new Image();
      img.src =
        "data:image/svg+xml;charset=utf-8," +
        encodeURIComponent(svg.replaceAll("#a3dfbd", color));
      await img.decode();
      if (paint === color) images[id] = img;
    }
  }
  function applyPreset(preset) {
    selected = preset;
    paint = preset.color;
    el("vehicleColor").value = paint;
    for (const [key, value] of Object.entries(preset.config)) {
      const node = el(key);
      if (!node) continue;
      if (node.type === "checkbox") node.checked = value;
      else if (typeof value !== "object") node.value = value;
    }
    el("resetSensors").click();
    el("driveMode").value = "manual";
    el("selectedVehicle").textContent = preset.name + " / " + preset.category;
    el("vehicleSpec").textContent =
      `${preset.config.mass_kg.toLocaleString()} kg · ${preset.config.max_power_kw} kW · ${preset.config.battery_capacity_kwh} kWh · illustrative`;
    for (const card of document.querySelectorAll(".vehicle-card"))
      card.classList.toggle("selected", card.dataset.vehicle === preset.id);
    loadImages();
    if (connected) reset();
    else queuedReset = preset;
    el("vehicleDialog").close();
    el("driveRun").focus();
  }
  fetch("/api/vehicles")
    .then((r) => {
      if (!r.ok) throw Error("Cannot load vehicle presets");
      return r.json();
    })
    .then((data) => {
      presets = data;
      for (const p of presets) {
        const card = document.createElement("button");
        card.className = "vehicle-card";
        card.dataset.vehicle = p.id;
        card.setAttribute("aria-label", `Select ${p.name}, ${p.category}`);
        card.innerHTML = `<img src="/static/vehicles/${p.id}.svg" alt="${p.category} silhouette"><span class="car-name">${p.name}</span><span class="category">${p.category}</span><span class="specs">${p.config.max_power_kw} kW motor<br>${p.config.battery_capacity_kwh} kWh battery<br>${p.config.mass_kg.toLocaleString()} kg</span><span class="choose-label">Select & drive →</span>`;
        card.onclick = () => applyPreset(p);
        el("vehicleCards").append(card);
        fetch("/static/vehicles/" + p.id + ".svg")
          .then((r) => r.text())
          .then((svg) => {
            card.querySelector("img").src =
              "data:image/svg+xml;charset=utf-8," +
              encodeURIComponent(svg.replaceAll("#a3dfbd", p.color));
          });
      }
      applyPreset(presets[0]);
      el("vehicleDialog").showModal();
    })
    .catch((e) => {
      el("driveNotice").textContent = e.message;
    });
  document.addEventListener("veus:telemetry", (event) => {
    const data = event.detail,
      now = performance.now();
    staleHandled = false;
    if (queuedReset && connected) {
      queuedReset = null;
      reset();
      return;
    }
    if (latest && data.time_s > latest.time_s && data.status === "running") {
      previous = latest;
      interval = Math.max(
        16,
        Math.min(250, (data.time_s - latest.time_s) * 1000),
      );
    } else previous = data;
    latest = data;
    receipt = now;
    el("driveSpeed").textContent = Number.isFinite(data.velocity_kmh)
      ? data.velocity_kmh.toFixed(1)
      : "—";
    el("driveSoc").textContent = Number.isFinite(data.soc)
      ? (data.soc * 100).toFixed(1)
      : "—";
    el("socFill").style.width = data.soc * 100 + "%";
    el("drivePower").textContent = data.battery_power_kw.toFixed(1);
    el("driveDistance").textContent = (data.position_m / 1000).toFixed(3);
    el("energyDirection").textContent =
      data.battery_power_kw < 0
        ? "Charging"
        : data.battery_power_kw > 0
          ? "Discharging"
          : "Standby";
    el("sceneMode").textContent = (
      appliedConfig?.mode || "manual"
    ).toUpperCase();
    el("driveMode").value = appliedConfig?.mode || "manual";
    if (selected && appliedConfig) {
      const c = appliedConfig;
      const custom = [
        "mass_kg",
        "max_power_kw",
        "max_torque_nm",
        "battery_capacity_kwh",
      ].some((k) => c[k] !== selected.config[k]);
      el("selectedVehicle").textContent =
        (custom ? "Custom / " : selected.name + " / ") + selected.category;
      el("vehicleSpec").textContent =
        `${c.mass_kg.toLocaleString()} kg · ${c.max_power_kw} kW · ${c.battery_capacity_kwh} kWh · illustrative`;
      el("driveDuration").textContent =
        c.duration_s + " s illustrative runs · 1× playback";
    }
    const automatic = appliedConfig?.mode !== "manual";
    el("touchThrottle").disabled = automatic;
    el("touchBrake").disabled = automatic;
    el("driveRun").disabled = !connected;
    el("driveReset").disabled = !connected;
    const running = data.status === "running";
    const label = running
      ? "Pause"
      : data.status === "paused"
        ? "Resume"
        : ["completed", "collision"].includes(data.status)
          ? "New run"
          : "Run";
    el("driveRun").innerHTML =
      '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="' +
      (running ? "M4 3h3v10H4zm5 0h3v10H9z" : "M4 2l10 6-10 6z") +
      '" fill="currentColor"/></svg> ' +
      label;
    el("driveNotice").textContent = data.collision
      ? "Collision detected. Run stopped. Adjust the engineering setup in Validate."
      : data.status === "completed"
        ? "Run complete. Start a new run or explore your telemetry in Validate."
        : automatic
          ? "Controller active. Pedals are disabled. Configure target speed, lead vehicle and sensors in Validate."
          : "Brake overrides throttle. Release keys to coast. Space pauses; R resets.";
    el("sceneHint").textContent =
      data.status === "running"
        ? automatic
          ? "Following the existing " +
            appliedConfig.mode.toUpperCase() +
            " controller."
          : innerWidth <= 760
            ? "Hold Accelerate to drive · Brake to slow down"
            : "Hold W / ↑ to accelerate · S / ↓ to brake"
        : data.status === "ready"
          ? innerWidth <= 760
            ? "Press Run. Hold Accelerate to begin your drive."
            : "Press Run. Hold W or ↑ to begin your drive."
          : "Simulation " + data.status + " · road position held";
    if (!["running", "ready", "paused"].includes(data.status)) release();
    if (data.status === "ready" && requestedRun) {
      requestedRun = false;
      send({ action: "start" });
    }
  });
  document.addEventListener("veus:error", (event) => {
    requestedRun = false;
    release();
    el("driveNotice").textContent =
      "Simulation rejected the request: " + event.detail;
  });
  document.addEventListener("veus:disconnect", () => {
    release();
    previous = latest;
    el("driveRun").disabled = true;
    el("driveReset").disabled = true;
    el("touchThrottle").disabled = true;
    el("touchBrake").disabled = true;
    for (const id of ["driveSpeed", "driveSoc", "drivePower", "driveDistance"])
      el(id).textContent = "—";
    el("driveNotice").textContent =
      "Disconnected — last scene held. Reload to create a new session; exports remain in Validate.";
    el("sceneHint").textContent = "Disconnected · no live telemetry";
  });
  const canvas = el("driveScene"),
    ctx = canvas.getContext("2d");
  const mod = (v, n) => ((v % n) + n) % n;
  function hill(w, h, offset, color, height, period) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(0, h);
    for (let x = 0; x <= w + 15; x += 15) {
      const world = x + offset;
      const y =
        height +
        Math.sin(world / period) * 18 +
        Math.sin(world / (period * 0.41)) * 9;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(w, h);
    ctx.fill();
  }
  function tree(x, y, s) {
    ctx.fillStyle = "#485d4b";
    ctx.fillRect(x - 2 * s, y - 25 * s, 4 * s, 27 * s);
    ctx.fillStyle = "#657e5b";
    for (const [dy, r] of [
      [-35, 16],
      [-49, 13],
      [-61, 9],
    ]) {
      ctx.beginPath();
      ctx.moveTo(x, y + (dy - r) * s);
      ctx.lineTo(x + r * s, y + (dy + 13) * s);
      ctx.lineTo(x - r * s, y + (dy + 13) * s);
      ctx.fill();
    }
  }
  function car(x, roadY, id, alpha = 1, displacement = 0) {
    const image = images[id];
    if (!image) return;
    const width = 145,
      height = (width * 110) / 260,
      y = roadY - (height * 100) / 110;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.drawImage(image, x, y, width, height);
    const angle = displacement / 0.355;
    for (const wheel of [65, 203]) {
      ctx.save();
      ctx.translate(x + (wheel * width) / 260, y + (81 * height) / 110);
      ctx.rotate(angle);
      ctx.strokeStyle = "#516b5b";
      ctx.lineWidth = 1.5;
      for (let i = 0; i < 5; i++) {
        ctx.rotate((Math.PI * 2) / 5);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(6, 0);
        ctx.stroke();
      }
      ctx.restore();
    }
    ctx.restore();
  }
  function renderScene(now) {
    raf = null;
    if (document.hidden) return;
    if (window.activeWorkspace === "drive") {
      const w = canvas.clientWidth,
        h = canvas.clientHeight,
        dpr = Math.min(2, window.devicePixelRatio || 1);
      if (
        canvas.width !== Math.round(w * dpr) ||
        canvas.height !== Math.round(h * dpr)
      ) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const alpha =
        latest?.status === "running" && connected
          ? Math.min(1, Math.max(0, (now - receipt) / interval))
          : 1;
      viewPosition = latest
        ? previous.position_m +
          (latest.position_m - previous.position_m) * alpha
        : 0;
      viewGap =
        latest?.gap_m == null
          ? null
          : (previous?.gap_m ?? latest.gap_m) +
            (latest.gap_m - (previous?.gap_m ?? latest.gap_m)) * alpha;
      canvas.dataset.positionM = viewPosition.toFixed(6);
      canvas.dataset.gapM = viewGap == null ? "" : viewGap.toFixed(6);
      const roadY = h * 0.79,
        offset = viewPosition * 5;
      const sky = ctx.createLinearGradient(0, 0, 0, h);
      sky.addColorStop(0, "#afc5bd");
      sky.addColorStop(1, "#dce1ba");
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#e9e5c0";
      ctx.beginPath();
      ctx.arc(w * 0.77, h * 0.25, 23, 0, Math.PI * 2);
      ctx.fill();
      hill(w, h, offset * 0.06, "#96ad9b", h * 0.4, 115);
      hill(w, h, offset * 0.14, "#7e9b7c", h * 0.55, 85);
      ctx.fillStyle = "#9ba879";
      ctx.fillRect(0, h * 0.64, w, h * 0.36);
      for (let i = -1; i <= Math.ceil(w / 260) + 1; i++) {
        const x = i * 260 - mod(offset * 0.4, 260);
        tree(x + 50, roadY - 18, 0.6);
        if (i % 2 === 0) {
          ctx.fillStyle = "#bcb59a";
          ctx.fillRect(x + 130, roadY - 61, 54, 38);
          ctx.fillStyle = "#6f7e6b";
          ctx.beginPath();
          ctx.moveTo(x + 122, roadY - 61);
          ctx.lineTo(x + 155, roadY - 83);
          ctx.lineTo(x + 192, roadY - 61);
          ctx.fill();
          ctx.fillStyle = "#6b837b";
          ctx.fillRect(x + 140, roadY - 49, 10, 12);
          ctx.fillRect(x + 164, roadY - 49, 10, 12);
        }
      }
      for (let i = -1; i <= Math.ceil(w / 370) + 1; i++) {
        const x = i * 370 - mod(offset * 0.7, 370);
        tree(x + 15, roadY - 5, 0.95);
      }
      ctx.fillStyle = "#727a68";
      ctx.fillRect(0, roadY - 3, w, 6);
      ctx.fillStyle = "#414b47";
      ctx.fillRect(0, roadY + 3, w, h - roadY);
      ctx.fillStyle = "#b8bea6";
      ctx.fillRect(0, roadY + 7, w, 2);
      ctx.fillStyle = "#d2d3b7";
      for (let x = -mod(offset, 95); x < w; x += 95)
        ctx.fillRect(x, roadY + 31, 46, 3);
      const signX = w + 90 - mod(offset + 180, w + 360);
      ctx.fillStyle = "#7f8f7d";
      ctx.fillRect(signX, roadY - 75, 3, 75);
      ctx.fillStyle = "#496950";
      ctx.fillRect(signX - 26, roadY - 79, 58, 24);
      ctx.fillStyle = "#e0e7d3";
      ctx.font = "8px system-ui";
      ctx.fillText("NORTH  08", signX - 19, roadY - 64);
      const egoX = Math.max(30, w * 0.19);
      car(egoX, roadY, selected?.id || "hatch", 1, viewPosition);
      if (viewGap !== null) {
        const leadX = egoX + ((245 - 15) * 145) / 260 + viewGap * 5;
        if (leadX < w - 20)
          car(leadX, roadY, "sedan", 0.85, viewPosition + viewGap);
        el("leadReadout").textContent =
          `Gap ${latest.gap_m.toFixed(1)} m${leadX > w - 145 ? " · lead ahead →" : ""} · 5 px/m`;
      } else el("leadReadout").textContent = "5 px/m · illustrative side view";
      ctx.fillStyle = "#667451";
      for (let i = -1; i <= Math.ceil(w / 150) + 1; i++) {
        const x = i * 150 - mod(offset * 1.2, 150);
        ctx.fillRect(x, h - 8, 43, 2);
      }
      if (lastFrame && now - lastFrame < 500) {
        frameTimes.push(now - lastFrame);
        if (frameTimes.length > 300) frameTimes.shift();
      }
      lastFrame = now;
    }
    if (
      latest?.status === "running" &&
      connected &&
      now - receipt > 1500 &&
      !staleHandled
    ) {
      staleHandled = true;
      release();
      send({ action: "pause" });
      el("driveNotice").textContent =
        "Telemetry delayed — inputs released and pause requested. Last received position held.";
    }
    raf = requestAnimationFrame(renderScene);
  }
  function startRender() {
    if (!raf && !document.hidden) raf = requestAnimationFrame(renderScene);
  }
  startRender();
})();

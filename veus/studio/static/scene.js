"use strict";
// Stateless shared renderer: callers supply positions; no clock or physics lives here.
window.VEUSScene = class {
  constructor(canvas, imageProvider, signLabel = "NORTH  08") {
    this.canvas = canvas;
    this.imageProvider = imageProvider;
    this.signLabel = signLabel;
  }
  render(positionM, gapM = null, vehicleId = "sedan") {
    const canvas = this.canvas,
      ctx = canvas.getContext("2d"),
      images = this.imageProvider(),
      signLabel = this.signLabel;
    const w = canvas.clientWidth,
      h = canvas.clientHeight,
      dpr = Math.min(2, window.devicePixelRatio || 1);
    if (!w || !h) return;
    if (
      canvas.width !== Math.round(w * dpr) ||
      canvas.height !== Math.round(h * dpr)
    ) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
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
    const roadY = h * 0.79,
      offset = positionM * 5;
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
    ctx.fillText(signLabel, signX - 19, roadY - 64);
    const egoX = Math.max(30, w * 0.19);
    car(egoX, roadY, vehicleId, 1, positionM);
    if (gapM !== null) {
      const leadX = egoX + ((245 - 15) * 145) / 260 + gapM * 5;
      if (leadX < w - 20) car(leadX, roadY, "sedan", 0.85, positionM + gapM);
    }
    ctx.fillStyle = "#667451";
    for (let i = -1; i <= Math.ceil(w / 150) + 1; i++) {
      const x = i * 150 - mod(offset * 1.2, 150);
      ctx.fillRect(x, h - 8, 43, 2);
    }
  }
};

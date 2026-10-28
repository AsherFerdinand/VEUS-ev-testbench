"use strict";
// Wall-clock playback of timestamped observations. No simulation state or commands.
class ReplayController {
  constructor(recording) {
    this.load(recording);
  }
  load(recording, now = 0) {
    if (
      !recording?.time_s ||
      recording.time_s.length < 2 ||
      recording.time_s[0] !== 0 ||
      recording.time_s.some(
        (t, i, a) => !Number.isFinite(t) || (i && t <= a[i - 1]),
      )
    )
      throw Error("Invalid replay timestamps");
    this.recording = recording;
    this.time = 0;
    this.rate = 1;
    this.playing = false;
    this.lastWall = now;
  }
  tick(now) {
    if (!Number.isFinite(now)) throw Error("Invalid playback clock");
    if (this.playing)
      this.time = Math.min(
        this.duration,
        this.time + (Math.max(0, now - this.lastWall) * this.rate) / 1000,
      );
    this.lastWall = now;
    if (this.time >= this.duration) this.playing = false;
    return this.state();
  }
  get duration() {
    return this.recording.time_s.at(-1);
  }
  play(now) {
    this.tick(now);
    if (this.time >= this.duration) this.time = 0;
    this.playing = true;
    this.lastWall = now;
  }
  pause(now) {
    this.tick(now);
    this.playing = false;
  }
  restart(now) {
    this.seek(0, now);
    this.playing = false;
  }
  seek(time, now) {
    if (!Number.isFinite(time) || !Number.isFinite(now))
      throw Error("Invalid seek");
    this.time = Math.max(0, Math.min(this.duration, time));
    this.lastWall = now;
    if (this.time >= this.duration) this.playing = false;
    return this.state();
  }
  setRate(rate, now) {
    if (![0.5, 1, 2, 4].includes(rate))
      throw Error("Unsupported playback speed");
    this.tick(now);
    this.rate = rate;
  }
  state() {
    const r = this.recording,
      t = this.time,
      ts = r.time_s;
    let lo = 0,
      hi = ts.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (ts[mid] <= t + 1e-10) lo = mid + 1;
      else hi = mid;
    }
    const i = Math.max(0, lo - 1),
      end = i === ts.length - 1,
      exact = Math.abs(t - ts[i]) < 1e-8;
    const gap =
      !end &&
      !exact &&
      ts[i + 1] - ts[i] > r.configuration.preprocessing.max_gap_s;
    const valid = !end && r.valid_speed_intervals[i];
    let position = r.derived.known_segment_distance_m[i];
    if (!end && !gap && valid) {
      const dt = Math.max(0, t - ts[i]),
        interval = ts[i + 1] - ts[i],
        v0 = r.measured.vehicle_speed_ms[i],
        v1 = r.measured.vehicle_speed_ms[i + 1];
      position += v0 * dt + ((0.5 * (v1 - v0)) / interval) * dt * dt;
    }
    const values = {};
    for (const [kind, channels] of [
      ["measured", r.measured],
      ["derived", r.derived],
    ])
      for (const [key, data] of Object.entries(channels))
        values[key] = gap ? null : data[i];
    return {
      time_s: t,
      index: i,
      recorded_time_s: gap ? null : ts[i],
      source_time_s: gap ? null : ts[i] + r.metadata.time_origin_s,
      gap,
      missing_speed: !end && !exact && !valid,
      position_m: position,
      values,
      playing: this.playing,
      rate: this.rate,
      ended: t >= this.duration,
    };
  }
}
if (typeof module !== "undefined" && module.exports)
  module.exports = ReplayController;
if (typeof window !== "undefined")
  window.VEUSReplayController = ReplayController;

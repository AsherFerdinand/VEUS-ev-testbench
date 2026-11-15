const test = require("node:test"),
  assert = require("node:assert/strict");
const Replay = require("../../veus/studio/static/replay-controller.js");
const recording = (gaps = false) => ({
  time_s: [0, 0.3, 1.1, 2],
  measured: {
    vehicle_speed_ms: [0, 0.6, 2.2, 4],
    battery_soc: [0.8, 0.79, null, 0.77],
  },
  derived: {
    known_segment_distance_m: gaps ? [0, 0.09, 0.09, 0.09] : [0, 0.09, 1.21, 4],
  },
  valid_speed_intervals: gaps ? [true, false, false] : [true, true, true],
  configuration: { preprocessing: { max_gap_s: gaps ? 0.5 : 2 } },
  metadata: { time_origin_s: 10 },
});

test("wall clock tracks recorded seconds and pauses without drift", () => {
  const c = new Replay(recording());
  c.play(100);
  c.tick(600);
  assert.equal(c.time, 0.5);
  c.pause(900);
  assert.equal(c.time, 0.8);
  c.tick(5000);
  assert.equal(c.time, 0.8);
  c.play(6000);
  c.tick(6200);
  assert.equal(c.time, 1);
});
test("speed changes account for elapsed time at the old rate", () => {
  const c = new Replay(recording());
  c.play(0);
  c.setRate(2, 500);
  assert.equal(c.time, 0.5);
  c.tick(750);
  assert.equal(c.time, 1);
  c.setRate(0.5, 750);
  c.tick(1250);
  assert.equal(c.time, 1.25);
  c.setRate(4, 1250);
  c.tick(1500);
  assert.equal(c.time, 2);
  assert.equal(c.playing, false);
  assert.equal(c.state().ended, true);
});
test("seeking clamps, preserves pause, and restart resets recording", () => {
  const c = new Replay(recording());
  c.seek(1.1, 0);
  assert.equal(c.time, 1.1);
  assert.equal(c.playing, false);
  c.seek(-20, 10);
  assert.equal(c.time, 0);
  c.seek(99, 20);
  assert.equal(c.time, 2);
  c.play(30);
  assert.equal(c.time, 0);
  c.seek(0.8, 40);
  assert.equal(c.playing, true);
  c.restart(50);
  assert.equal(c.time, 0);
  assert.equal(c.playing, false);
});
test("irregular lookup returns actual preceding sample and original source time", () => {
  const c = new Replay(recording());
  c.seek(0.8, 0);
  const s = c.state();
  assert.equal(s.index, 1);
  assert.equal(s.recorded_time_s, 0.3);
  assert.equal(s.source_time_s, 10.3);
  assert.equal(s.values.vehicle_speed_ms, 0.6);
  assert.equal(s.values.battery_soc, 0.79);
  assert.equal(s.position_m, 0.64);
});
test("partial speed integral follows the linear speed curve, not linear position", () => {
  const c = new Replay(recording());
  c.seek(0.15, 0);
  assert(Math.abs(c.state().position_m - 0.0225) < 1e-10);
  c.seek(1.1, 0);
  assert.equal(c.state().position_m, 1.21);
  c.seek(2, 0);
  assert.equal(c.state().position_m, 4);
});
test("gaps do not invent measurements or distance, endpoints remain available", () => {
  const c = new Replay(recording(true));
  c.seek(0.8, 0);
  const s = c.state();
  assert.equal(s.gap, true);
  assert.equal(s.position_m, 0.09);
  assert.equal(s.values.vehicle_speed_ms, null);
  assert.equal(s.recorded_time_s, null);
  c.seek(1.1, 1);
  assert.equal(c.state().values.vehicle_speed_ms, 2.2);
  assert.equal(c.state().values.battery_soc, null);
  assert.equal(c.state().position_m, 0.09);
});
test("stationary interval has no visual displacement", () => {
  const r = recording();
  r.measured.vehicle_speed_ms = [0, 0, 0, 0];
  r.derived.known_segment_distance_m = [0, 0, 0, 0];
  const c = new Replay(r);
  c.play(0);
  c.tick(800);
  assert.equal(c.state().position_m, 0);
  c.tick(1600);
  assert.equal(c.state().position_m, 0);
});
test("invalid clocks, rates, seeks and timestamps are rejected", () => {
  const c = new Replay(recording());
  assert.throws(() => c.setRate(3, 0));
  assert.throws(() => c.seek(NaN, 0));
  assert.throws(() => c.tick(Infinity));
  assert.throws(() => new Replay({ ...recording(), time_s: [0, 0, 1] }));
  assert.throws(() => new Replay({ ...recording(), time_s: [2, 3] }));
});
test("multiple replay instances are independent and load resets state", () => {
  const a = new Replay(recording()),
    b = new Replay(recording());
  a.play(0);
  a.tick(1000);
  assert.equal(b.time, 0);
  a.load(recording(), 5000);
  assert.equal(a.time, 0);
  assert.equal(a.playing, false);
  assert.equal(a.rate, 1);
});

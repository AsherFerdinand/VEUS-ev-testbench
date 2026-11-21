// Pure visual choreography. No vehicle physics, steering command or safety assertion.
export const SCENE = Object.freeze({
  lead_initial_gap_m: 70,
  lead_speed_ms: 8,
  lead_wheel_radius_m: 0.32,
  lane_width_m: 3.5,
  out_start_gap_m: 45,
  out_end_gap_m: 18,
  return_start_clearance_m: 12,
  return_end_clearance_m: 45,
  camera_lag_s: 0.15,
  camera_max_lag_m: 4,
});
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const smooth = (x) => {
  const u = clamp(x, 0, 1);
  return u * u * (3 - 2 * u);
};
const smoothDerivative = (x) => (x > 0 && x < 1 ? 6 * x * (1 - x) : 0);
export function project(longitudinal, lateral = 0) {
  const depth = 1 / (1 + clamp(longitudinal, -35, 260) / 60);
  return {
    x: 610 - 550 * (1 - depth) - lateral * 11 * depth,
    y: 290 - 115 * (1 - depth) - lateral * 19 * depth,
    scale: 0.63 * depth,
    visible: longitudinal > -34 && longitudinal < 240,
  };
}
export function drivingState(
  {
    time_s = 0,
    position_m = 0,
    speed_ms = 0,
    acceleration_ms2 = 0,
    wheel_radius_m = 0.32,
    kind = "constant_speed",
    grade_percent = 0,
    reduced_motion = false,
  } = {},
  parameters = SCENE,
) {
  if (
    ![
      time_s,
      position_m,
      speed_ms,
      acceleration_ms2,
      wheel_radius_m,
      grade_percent,
    ].every(Number.isFinite) ||
    time_s < 0 ||
    position_m < 0 ||
    speed_ms < 0 ||
    wheel_radius_m <= 0
  )
    throw Error("Finite recorded state and positive wheel radius required");
  const leadPosition =
      parameters.lead_initial_gap_m + parameters.lead_speed_ms * time_s,
    gap = leadPosition - position_m;
  const outward =
    (parameters.out_start_gap_m - gap) /
    (parameters.out_start_gap_m - parameters.out_end_gap_m);
  const returning =
    (-gap - parameters.return_start_clearance_m) /
    (parameters.return_end_clearance_m - parameters.return_start_clearance_m);
  const out = smooth(outward),
    back = smooth(returning),
    lane =
      kind === "acceleration" ? parameters.lane_width_m * out * (1 - back) : 0;
  const rate =
    kind === "acceleration"
      ? parameters.lane_width_m *
        (speed_ms - parameters.lead_speed_ms) *
        ((smoothDerivative(outward) /
          (parameters.out_start_gap_m - parameters.out_end_gap_m)) *
          (1 - back) -
          (out * smoothDerivative(returning)) /
            (parameters.return_end_clearance_m -
              parameters.return_start_clearance_m))
      : 0;
  const heading = reduced_motion
    ? 0
    : clamp(
        (-Math.atan2(rate, Math.max(0.1, speed_ms)) * 180) / Math.PI,
        -6,
        6,
      );
  const camera =
    position_m -
    Math.min(parameters.camera_max_lag_m, speed_ms * parameters.camera_lag_s);
  const stage =
    kind !== "acceleration"
      ? "cruising"
      : back >= 1
        ? "continue"
        : back > 0
          ? "returning"
          : out >= 1
            ? "passing"
            : out > 0
              ? "lane_change_out"
              : gap <= 60
                ? "following_gap"
                : "approaching";
  return {
    time_s,
    position_m,
    speed_ms,
    camera_position_m: camera,
    relative_gap_m: gap,
    lateral_m: lane,
    lateral_rate_ms: rate,
    heading_deg: heading,
    pitch_deg: reduced_motion ? 0 : clamp(-acceleration_ms2 * 0.22, -1, 1),
    body_heave_px: reduced_motion
      ? 0
      : Math.sin((position_m * 2 * Math.PI) / 24) *
        Math.min(speed_ms / 20, 1) *
        0.45,
    wheel_rotation_deg: reduced_motion
      ? 0
      : ((position_m / wheel_radius_m) * 180) / Math.PI,
    traffic_position_m: leadPosition,
    traffic_speed_ms: parameters.lead_speed_ms,
    traffic_wheel_rotation_deg: reduced_motion
      ? 0
      : (((parameters.lead_speed_ms * time_s) /
          parameters.lead_wheel_radius_m) *
          180) /
        Math.PI,
    hero: project(position_m - camera, lane),
    traffic: project(leadPosition - camera, 0),
    stage,
    reduced_motion,
    grade_angle_deg: (-Math.atan(grade_percent / 100) * 180) / Math.PI,
    far_parallax_m: reduced_motion ? 0 : position_m * 0.06,
    near_parallax_m: reduced_motion ? 0 : position_m * 0.4,
    motion_classification:
      "Illustrative traffic choreography and camera, driven by recorded longitudinal state; no lateral dynamics, sensors or safety guarantees",
  };
}

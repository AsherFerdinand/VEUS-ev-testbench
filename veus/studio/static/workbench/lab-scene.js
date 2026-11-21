import { drivingState } from "./driving-scene-state.mjs";
import {
  appearanceOf,
  sideVehicle,
  topVehicle,
  appearances,
} from "./vehicle-appearance.js";
// Original fictional VEUS Arrow body. Display transforms only; no simulation equations.
export const scenarios = {
  constant_speed: [
    "Highway Cruising",
    "Hold a steady pace. Inspect the energy needed to move.",
    "01",
    "M2 12h20M8 4v16m8-16v16",
  ],
  acceleration: [
    "Highway Overtaking",
    "Explore acceleration and available propulsion power.",
    "02",
    "M3 17l6-6 4 3 8-10m-7 0h7v7",
  ],
  braking: [
    "Traffic Light Braking",
    "Slow down. Follow recovered energy and friction braking.",
    "03",
    "M9 2h6v17H9zM12 5h.01M12 9h.01M12 13h.01M12 19v3",
  ],
  gradient: [
    "Mountain Climb",
    "Feel the load of the selected uphill gradient.",
    "04",
    "M2 20L10 5l4 7 3-5 5 13z",
  ],
  coast: [
    "Free Rolling",
    "Lift off. See aerodynamic and rolling resistance at work.",
    "05",
    "M2 8h13m-9 4h16M2 16h13",
  ],
};
export function sceneSVG() {
  return `<svg id="lab-scene-svg" viewBox="0 0 1000 400" role="img" aria-label="Recorded longitudinal driving"><defs><linearGradient id="pearl" x2="0" y2="1"><stop stop-color="#f1f8fb"/><stop offset="1" stop-color="#83a1b2"/></linearGradient></defs><rect width="1000" height="400" fill="#172e42"/><g id="lab-mountains" fill="#304d5e"><path d="M0 230L160 65l130 120L490 40l230 180L850 110l150 120V400H0Z"/></g><g id="lab-road-slope"><path id="lab-road-surface" fill="#283d49" stroke="#7f9ca8" stroke-width="2"/><g id="lab-road-markings" stroke="#d1e1e4" stroke-width="3"></g><g id="lab-other-car"></g><g id="lab-hero-car"></g><g id="lab-light"><path d="M0 0v80" stroke="#81a5ad" stroke-width="5"/><rect x="-13" y="-65" width="26" height="70" rx="7" fill="#091725"/><circle id="lab-light-red" cy="-48" r="7" fill="#ff7667"/><circle id="lab-light-green" cy="-12" r="6" fill="#234b41"/></g></g><text id="lab-scene-label" x="24" y="28" fill="#d4e7ee" font-size="12">VEUS / RECORDED LONGITUDINAL MOTION</text><text id="lab-scene-state" x="24" y="378" fill="#bad4df" font-size="11">Run a simulation to inspect achieved motion.</text></svg>`;
}
export function updateScene(root, sample, time, experiment, design) {
  const $ = (id) => root.querySelector("#" + id),
    svg = $("lab-scene-svg");
  if (!svg) return;
  const kind = experiment?.kind || "constant_speed",
    top = kind === "acceleration",
    appearance = appearanceOf(design),
    reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const v = drivingState({
    time_s: time,
    position_m: sample?.position_m ?? 0,
    speed_ms: sample?.speed_ms ?? 0,
    acceleration_ms2: sample?.acceleration_ms2 ?? 0,
    wheel_radius_m: design?.body?.wheel_radius_m ?? 0.32,
    kind,
    grade_percent: sample?.grade_percent ?? experiment?.grade_percent ?? 0,
    reduced_motion: reduced,
  });
  for (const [k, value] of Object.entries({
    positionM: v.position_m,
    time,
    stage: v.stage,
    lateralM: v.lateral_m,
    trafficPositionM: v.traffic_position_m,
    wheelAngle: v.wheel_rotation_deg,
    reducedMotion: reduced,
    cameraPositionM: v.camera_position_m,
    camera: top ? "top-down" : "side",
  }))
    svg.dataset[k] = String(value);
  svg.setAttribute(
    "aria-label",
    `${appearances[appearance].name}, ${top ? "top-down overtaking" : "side view"}, ${v.stage}; illustrative scene`,
  );
  const hero = $("lab-hero-car"),
    traffic = $("lab-other-car"),
    view = top ? "top" : "side";
  if (hero.dataset.appearance !== appearance || hero.dataset.view !== view) {
    hero.innerHTML = top
      ? topVehicle(appearance, "lab-arrow")
      : sideVehicle(appearance, "lab-arrow");
    hero.dataset.appearance = appearance;
    hero.dataset.view = view;
  }
  if (traffic.dataset.view !== view) {
    traffic.innerHTML = top
      ? topVehicle("sedan", "lab-reference-car", "#7598aa")
      : sideVehicle("sedan", "lab-reference-car", "#7598aa");
    traffic.dataset.view = view;
  }
  $("lab-road-surface").setAttribute(
    "d",
    top ? "M-300 178H1300V286H-300Z" : "M-600 280H1600V600H-600Z",
  );
  const phase = reduced ? 0 : (v.camera_position_m * (top ? 12.5 : 3.5)) % 100,
    mark = $("lab-road-markings");
  // Reuse paths while seeking/playing rather than allocating a new SVG tree per frame.
  while (mark.children.length < 18)
    mark.append(document.createElementNS("http://www.w3.org/2000/svg", "path"));
  for (let i = 0; i < 18; i++)
    mark.children[i].setAttribute(
      "d",
      `M${i * 100 - 300 + phase} ${top ? 232 : 320}h50`,
    );
  const grade = top ? 0 : -v.grade_angle_deg;
  $("lab-road-slope").setAttribute("transform", `rotate(${grade} 560 280)`);
  svg.dataset.gradeAngle = String(grade);
  const x =
    (top ? 850 : 600) -
    (v.position_m - v.camera_position_m) * (top ? 12.5 : 3.5);
  hero.setAttribute(
    "transform",
    top
      ? `translate(${x} ${254 - (v.lateral_m / 3.5) * 44}) rotate(${-v.heading_deg}) scale(.5)`
      : `translate(${x} ${280 + v.body_heave_px}) rotate(${v.pitch_deg}) scale(.62) translate(-290 -260)`,
  );
  traffic.setAttribute(
    "transform",
    top
      ? `translate(${x - v.relative_gap_m * 12.5} 254) scale(.5)`
      : `translate(${x - v.relative_gap_m * 3.5} 280) scale(.5) translate(-290 -260)`,
  );
  traffic.style.display = top ? "" : "none";
  for (const [node, angle] of [
    [hero, v.wheel_rotation_deg],
    [traffic, v.traffic_wheel_rotation_deg],
  ])
    for (const w of node.querySelectorAll("[data-scene-wheel]"))
      w.setAttribute(
        "transform",
        `rotate(${-angle % 360} ${w.dataset.wheelX} ${w.dataset.wheelY})`,
      );
  $("lab-mountains").style.display = kind === "gradient" ? "" : "none";
  $("lab-light").style.display = kind === "braking" ? "" : "none";
  $("lab-light").setAttribute(
    "transform",
    `translate(${600 - (70 - v.position_m) * 3.5} 200)`,
  );
  $("lab-scene-label").textContent =
    appearances[appearance].name +
    " / " +
    (top ? "TOP-DOWN OVERTAKING" : "SIDE VIEW");
  $("lab-scene-state").textContent = top
    ? `ILLUSTRATIVE ${v.stage.replaceAll("_", " ").toUpperCase()} · traffic 8 m/s · no steering/safety validation`
    : `Achieved longitudinal movement · ${kind === "gradient" ? "grade " + (sample?.grade_percent ?? experiment?.grade_percent ?? 0) + "%" : "horizontal road"}${reduced ? " · reduced decorative motion" : ""}`;
}

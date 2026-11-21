import { drivingState, project } from "./driving-scene-state.mjs";
import {
  appearanceOf,
  sideVehicle,
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
  return `<svg id="lab-scene-svg" viewBox="0 0 1000 400" role="img" aria-label="Original VEUS driving scene"><defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#0d1b30"/><stop offset="1" stop-color="#456276"/></linearGradient><linearGradient id="pearl" x2=".1" y2="1"><stop stop-color="#f8fcff"/><stop offset=".45" stop-color="#c6d6e2"/><stop offset="1" stop-color="#7d95a9"/></linearGradient><linearGradient id="roadshade" x2="0" y2="1"><stop stop-color="#304351"/><stop offset="1" stop-color="#111e2a"/></linearGradient><pattern id="far-land" width="360" height="220" patternUnits="userSpaceOnUse"><path d="M0 180L90 120L160 160L250 110L360 180V220H0Z" fill="#426473"/></pattern><clipPath id="scene-clip"><rect width="1000" height="400" rx="12"/></clipPath></defs>
<g clip-path="url(#scene-clip)"><rect width="1000" height="400" fill="url(#sky)"/><circle cx="805" cy="65" r="34" fill="#d4e9e8" opacity=".18"/>
<g id="lab-far-scenery" opacity=".6"><rect x="-360" width="1720" height="220" fill="url(#far-land)"/></g>
<g id="lab-mountains" fill="#5a7786"><path d="M-250 220L-60 100l120 78L210 40l180 155L570 75l220 126 130-85 300 100v100H-250z"/><path d="M165 87l45-47 65 57-52-24-15 15-15-17z" fill="#b2c6ce" opacity=".5"/></g>
<g id="lab-near-scenery" stroke="#537b85" stroke-width="2" opacity=".65"><path d="M-250 215H1300M-250 225H1300"/>${Array.from({ length: 14 }, (_, i) => `<path d="M${i * 110 - 200} 224v-37m-8 7l8-14 8 14"/>`).join("")}</g>
<g id="lab-road-slope"><path id="lab-road-surface" fill="url(#roadshade)" stroke="#6c8b97" stroke-width="2"/><g id="lab-road-markings" fill="#ccdedf" opacity=".8"></g><path id="lab-road-edge" fill="none" stroke="#9cb8bc" stroke-width="2"/>
<g id="lab-other-car">${sideVehicle("sedan", "lab-reference-car", "#6e8799")}</g>
<g id="lab-light"><path d="M0 0v100" stroke="#688b96" stroke-width="5"/><rect x="-13" y="-65" width="26" height="70" rx="8" fill="#132233" stroke="#6c8a9b"/><circle id="lab-light-red" cy="-48" r="7" fill="#ff7667"/><circle cy="-29" r="6" fill="#625b3c"/><circle id="lab-light-green" cy="-12" r="6" fill="#234b41"/></g>
<g id="lab-hero-car">${sideVehicle("performance", "lab-arrow")}</g></g>
<text id="lab-scene-label" x="24" y="28" fill="#cee2eb" font-size="11" font-family="sans-serif" letter-spacing="2">VEUS / ILLUSTRATIVE DRIVING</text><text id="lab-scene-state" x="24" y="378" fill="#b4d1db" font-family="sans-serif" font-size="10">Replay a recorded run to inspect motion.</text></g></svg>`;
}

export function updateScene(root, sample, time, experiment, design) {
  const $ = (id) => root.querySelector("#" + id);
  if (!$("lab-scene-svg")) return;
  const appearance = appearanceOf(design),
    hero = $("lab-hero-car");
  if (hero.dataset.appearance !== appearance) {
    hero.innerHTML = sideVehicle(appearance, "lab-arrow");
    hero.dataset.appearance = appearance;
  }
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const v = drivingState({
    time_s: time,
    position_m: sample?.position_m ?? 0,
    speed_ms: sample?.speed_ms ?? 0,
    acceleration_ms2: sample?.acceleration_ms2 ?? 0,
    wheel_radius_m: design?.body?.wheel_radius_m ?? 0.32,
    kind: experiment?.kind ?? "constant_speed",
    grade_percent: sample?.grade_percent ?? experiment?.grade_percent ?? 0,
    reduced_motion: reduced,
  });
  const svg = $("lab-scene-svg");
  svg.dataset.positionM = String(v.position_m);
  svg.dataset.time = String(time);
  svg.dataset.stage = v.stage;
  svg.dataset.lateralM = String(v.lateral_m);
  svg.dataset.trafficPositionM = String(v.traffic_position_m);
  svg.dataset.wheelAngle = String(v.wheel_rotation_deg);
  svg.dataset.reducedMotion = String(reduced);
  svg.dataset.cameraPositionM = String(v.camera_position_m);
  svg.setAttribute(
    "aria-label",
    `${appearances[appearance].name}: ${v.stage}, illustrative driving choreography`,
  );
  $("lab-scene-label").textContent =
    appearances[appearance].name + " / RECORDED LONGITUDINAL MOTION";
  $("lab-scene-state").textContent =
    experiment?.kind === "acceleration"
      ? `ILLUSTRATIVE ${v.stage.replaceAll("_", " ").toUpperCase()} · scene traffic 8 m/s; no steering, sensors or safe-overtake claim`
      : experiment?.kind === "braking"
        ? "RED AT t = 0 s · visual event; recorded braking supplies the deceleration"
        : experiment?.kind === "gradient"
          ? `SELECTED GRADE ${sample?.grade_percent ?? experiment.grade_percent}% · illustrative terrain`
          : "Scene traffic and surroundings are illustrative; vehicle motion follows the frozen result";
  if (reduced)
    $("lab-scene-state").textContent += " · reduced decorative motion";
  $("lab-far-scenery").setAttribute(
    "transform",
    `translate(${-v.far_parallax_m % 360} 0)`,
  );
  $("lab-near-scenery").setAttribute(
    "transform",
    `translate(${-v.near_parallax_m % 110} 0)`,
  );
  $("lab-mountains").style.display =
    experiment?.kind === "gradient" ? "" : "none";
  $("lab-road-slope").setAttribute(
    "transform",
    `rotate(${v.grade_angle_deg} 560 275)`,
  );
  const point = (s, l) => project(s, l),
    coords = (p) => `${p.x.toFixed(2)} ${p.y.toFixed(2)}`;
  const polygon = (points) => "M" + points.map(coords).join("L") + "Z";
  $("lab-road-surface").setAttribute(
    "d",
    polygon([point(240, -2), point(240, 5.5), point(-34, 5.5), point(-34, -2)]),
  );
  $("lab-road-edge").setAttribute(
    "d",
    `M${coords(point(240, -1.8))}L${coords(point(-34, -1.8))}M${coords(point(240, 5.3))}L${coords(point(-34, 5.3))}`,
  );
  // World-space 18 m repeat /9 m dash. Phase comes from camera distance, never frame deltas.
  const phase = reduced ? 0 : ((v.camera_position_m % 18) + 18) % 18;
  const markings = [];
  for (let i = -2; i < 15; i++) {
    const s = i * 18 - phase;
    if (s < -34 || s + 9 > 240) continue;
    markings.push(
      polygon([
        point(s, 1.68),
        point(s, 1.82),
        point(s + 9, 1.82),
        point(s + 9, 1.68),
      ]),
    );
  }
  const mark = $("lab-road-markings");
  while (mark.children.length < markings.length)
    mark.append(document.createElementNS("http://www.w3.org/2000/svg", "path"));
  while (mark.children.length > markings.length) mark.lastChild.remove();
  markings.forEach((d, i) => mark.children[i].setAttribute("d", d));
  function actor(node, p, heading, pitch, heave) {
    node.setAttribute(
      "transform",
      `translate(${p.x} ${p.y + heave}) rotate(${heading + pitch}) scale(${p.scale}) translate(-290 -260)`,
    );
    node.style.visibility = p.visible ? "visible" : "hidden";
  }
  actor(hero, v.hero, v.heading_deg, v.pitch_deg, v.body_heave_px);
  actor($("lab-other-car"), v.traffic, 0, 0, 0);
  // Paint far-lane hero behind near-lane traffic; z-order depends only on current state.
  const road = $("lab-road-slope");
  if (v.lateral_m > 1.75) {
    if (hero.nextSibling !== $("lab-other-car"))
      road.insertBefore(hero, $("lab-other-car"));
  } else if (road.lastChild !== hero) road.append(hero);
  const spin = (node, angle) => {
    for (const w of node.querySelectorAll("[data-scene-wheel]"))
      w.setAttribute(
        "transform",
        `rotate(${-angle % 360} ${w.dataset.wheelX} ${w.dataset.wheelY})`,
      );
  };
  spin(hero, v.wheel_rotation_deg);
  spin($("lab-other-car"), v.traffic_wheel_rotation_deg);
  $("lab-light").style.display = experiment?.kind === "braking" ? "" : "none";
  const light = point(70 - v.position_m, 5.6);
  $("lab-light").setAttribute(
    "transform",
    `translate(${light.x} ${light.y}) scale(${light.scale})`,
  );
  $("lab-light-red").setAttribute("fill", sample ? "#ff7667" : "#453440");
  $("lab-light-green").setAttribute("fill", sample ? "#234b41" : "#5bd0a2");
}

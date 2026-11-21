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
  return `<svg id="lab-scene-svg" viewBox="0 0 1000 380" role="img" aria-label="Original VEUS electric sports car in an illustrative driving scene">
 <defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#0c192c"/><stop offset="1" stop-color="#294358"/></linearGradient><linearGradient id="pearl" x2=".1" y2="1"><stop stop-color="#f8fcff"/><stop offset=".45" stop-color="#c6d6e2"/><stop offset="1" stop-color="#7d95a9"/></linearGradient><linearGradient id="roadshade" x2="0" y2="1"><stop stop-color="#293745"/><stop offset="1" stop-color="#101d2b"/></linearGradient><pattern id="road-dashes" width="140" height="8" patternUnits="userSpaceOnUse"><path d="M0 4h70" stroke="#b3c8ce" stroke-width="3"/></pattern></defs>
 <rect width="1000" height="380" rx="12" fill="url(#sky)"/>
 <circle cx="815" cy="64" r="33" fill="#d5eff0" opacity=".1"/>
 <g id="lab-mountains" fill="#365467" opacity=".65"><path d="M0 210L130 65l105 125L410 25l170 174L740 65l260 155v100H0z"/><path d="M358 82l52-57 65 65-45-20-20 14-20-20z" fill="#809fae"/></g>
 <g id="lab-horizon" stroke="#547687" stroke-width="2" opacity=".45"><path d="M0 195h1000M0 213h1000"/><path d="M25 195v-55m210 55v-35m320 35v-55m210 55v-35"/></g>
 <g id="lab-road-slope"><path d="M-120 231H1120V470H-120z" fill="url(#roadshade)"/><path d="M-120 234H1120" stroke="#608698" stroke-width="2"/>
 <rect id="lab-road-motion" x="-160" y="311" width="1400" height="8" fill="url(#road-dashes)"/>
 <g id="lab-other-car" transform="translate(530 141) scale(.45)" opacity=".48">${sideVehicle("sedan", "lab-reference-car", "#5e788a")}</g>
 <g id="lab-light" transform="translate(850 104)"><path d="M0 20v128" stroke="#577384" stroke-width="6"/><rect x="-16" y="0" width="32" height="78" rx="10" fill="#101b28" stroke="#567081"/><circle id="lab-light-red" cy="20" r="8" fill="#4a3440"/><circle cy="40" r="7" fill="#4c4937"/><circle id="lab-light-green" cy="60" r="8" fill="#4ae3aa"/></g>
 <g id="lab-hero-car" transform="translate(185 94) scale(.78)">${sideVehicle("performance", "lab-arrow")}</g></g>
 <text id="lab-scene-label" x="24" y="31" fill="#c1e3e8" font-family="sans-serif" font-size="11" letter-spacing="2">VEUS ARROW / ILLUSTRATIVE BODY</text>
 <text id="lab-scene-state" x="24" y="355" fill="#94bdcb" font-family="sans-serif" font-size="11">Run a scenario to load its recorded motion.</text>
 </svg>`;
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
  $("lab-scene-svg").setAttribute(
    "aria-label",
    `${appearances[appearance].name} ${appearances[appearance].label} in an illustrative longitudinal scene`,
  );
  $("lab-scene-label").textContent =
    appearances[appearance].name + " / ILLUSTRATIVE BODY";
  const kind = experiment?.kind || "constant_speed",
    position = sample?.position_m ?? 0,
    grade = sample?.grade_percent ?? experiment?.grade_percent ?? 0;
  $("lab-road-motion").setAttribute(
    "transform",
    `translate(${-((position * 2) % 140)} 0)`,
  );
  // Exact selected slope angle; scenery is illustrative, not a geographic reconstruction.
  const angle = (-Math.atan(grade / 100) * 180) / Math.PI;
  $("lab-road-slope").setAttribute("transform", `rotate(${angle} 500 245)`);
  $("lab-mountains").style.display = kind === "gradient" ? "" : "none";
  $("lab-other-car").style.display = kind === "acceleration" ? "" : "none";
  $("lab-other-car").setAttribute(
    "transform",
    `translate(${530 - Math.min(650, position * 1.1)} 141) scale(.45)`,
  );
  $("lab-light").style.display = kind === "braking" ? "" : "none";
  $("lab-light").setAttribute(
    "transform",
    `translate(${850 - Math.min(700, position * 2)} 104)`,
  );
  // Predefined visual event: red at t=0, when the existing braking experiment starts.
  $("lab-light-red").setAttribute("fill", sample ? "#ff685d" : "#4a3440");
  $("lab-light-green").setAttribute("fill", sample ? "#23483b" : "#4ae3aa");
  $("lab-scene-svg").dataset.positionM = String(position);
  $("lab-scene-svg").dataset.time = String(time);
  $("lab-scene-state").textContent =
    kind === "braking"
      ? "RED AT t = 0 s · visual trigger; braking comes from the recorded experiment"
      : kind === "acceleration"
        ? "Reference vehicle is illustrative · no lane change, collision model or safe-overtake claim"
        : kind === "gradient"
          ? `SELECTED GRADE ${grade.toFixed(1)}% · longitudinal model; illustrative terrain`
          : "Scenery follows achieved distance · fictional body, not a validated vehicle";
}

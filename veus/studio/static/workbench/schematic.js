import { appearances } from "./vehicle-appearance.js";
// Original schematic geometry; conceptual placement, not a production-vehicle CAD model.
const icons = {
  anatomy:
    '<path d="m3 15 9-6 9 6-9 6Z M3 10l9-6 9 6-9 6Z M3 10v5m18-5v5m-9 1v5"/>',
  challenges:
    '<path d="M5 19V9m7 10V5m7 14v-6M3 19h18"/><circle cx="5" cy="7" r="2"/><circle cx="12" cy="3" r="2"/><circle cx="19" cy="11" r="2"/>',
  design: '<path d="m4 16 12-12 4 4L8 20H4Zm9-9 4 4M4 4h5M4 4v5m16 6v5h-5"/>',
  simulation:
    '<path d="M4 19a10 10 0 1 1 16 0M12 12l6-6M4 12h2m12 0h2M12 2v2"/><circle cx="12" cy="12" r="2"/>',
  optimization: '<path d="M3 20V4m0 16h18M6 15l5-6 4 3 6-8M16 4h5v5"/>',
  measurements:
    '<path d="M3 20V4m0 16h18M4 14l4-2 4 3 4-8 5 3"/><circle cx="16" cy="7" r="2"/>',
};
export const icon = (key) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[key]}</svg>`;

// Coherent axonometric projection; x is vehicle length, y is width, z is height.
// Units are drawing coordinates, not manufacturer dimensions or a packaging model.
const p = (x, y, z = 0) => [
  450 + 0.86 * x + 0.58 * y,
  328 - 0.39 * x + 0.35 * y - z,
];
const xy = (v) => v.map((n) => n.toFixed(1)).join(" ");
const line = (points) =>
  points.map((v, i) => (i ? "L" : "M") + xy(p(...v))).join(" ");
const polygon = (points) => line(points) + "Z";
const escape = (text) =>
  String(text).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
function box(x, y, z, length, width, height, extra = "") {
  return `<g ${extra}><path class="component-side" d="${polygon([
    [x, y, z],
    [x + length, y, z],
    [x + length, y, z + height],
    [x, y, z + height],
  ])}"/><path class="component-side end-face" d="${polygon([
    [x, y, z],
    [x, y + width, z],
    [x, y + width, z + height],
    [x, y, z + height],
  ])}"/><path class="component-surface" d="${polygon([
    [x, y, z + height],
    [x + length, y, z + height],
    [x + length, y + width, z + height],
    [x, y + width, z + height],
  ])}"/></g>`;
}
const circle = (x, y, z, r, cls) => {
  const [a, b] = p(x, y, z);
  return `<circle class="${cls}" cx="0" cy="0" r="${r}" transform="matrix(.86 -.39 0 -1 ${a} ${b})"/>`;
};
function wheel(x, y, radius = 34) {
  const inner = y < 0 ? y + 16 : y - 16;
  return `<g class="vehicle-wheel"><path class="tyre-wall" d="${polygon([
    [x - radius, y, radius],
    [x - radius, inner, radius],
    [x + radius, inner, radius],
    [x + radius, y, radius],
  ])}"/>${circle(x, inner, radius, radius, "tyre-inner")}${circle(x, y, radius, radius, "tyre")}${circle(x, y, radius, 25, "rim")}${circle(x, y, radius, 20, "rim-inner")}${[
    0, 1, 2, 3, 4,
  ]
    .map((i) => {
      const a = (i * Math.PI * 2) / 5;
      return `<path class="rim-spoke" d="${line([
        [x, y, radius],
        [x + 21 * Math.cos(a), y, radius + 21 * Math.sin(a)],
      ])}"/>`;
    })
    .join("")}${circle(x, y, radius, 5, "hub")}</g>`;
}
function cylinder(x, y, z, r, width) {
  const a = -2.308,
    dx = r * Math.cos(a),
    dz = r * Math.sin(a);
  return `<g class="motor-cylinder">${circle(x, y, z, r, "motor-end far-end")}<path class="component-side" d="${polygon(
    [
      [x + dx, y, z + dz],
      [x + dx, y + width, z + dz],
      [x - dx, y + width, z - dz],
      [x - dx, y, z - dz],
    ],
  )}"/>${[0, 10, 20, 30, 40, 50]
    .filter((i) => i <= width)
    .map((d) => circle(x, y + d, z, r, "motor-rib"))
    .join(
      "",
    )}${circle(x, y + width, z, r, "motor-end")}${circle(x, y + width, z, r * 0.56, "motor-center")}<path class="motor-shaft" d="${line(
    [
      [x, y + width, z],
      [x, y + width + 22, z],
    ],
  )}"/></g>`;
}
const centers = {
  battery: [10, 0, 51],
  motor: [-170, 3, 53],
  inverter: [-115, -30, 79],
  bms: [111, 25, 75],
  gearbox: [-170, 48, 53],
  thermal: [-236, -5, 66],
  dcdc: [193, -42, 90],
  charger: [190, 42, 90],
  port: [240, 92, 80],
  aux: [-215, 54, 73],
};
const labels = {
  battery: [666, 400, "HV BATTERY"],
  motor: [90, 338, "TRACTION MOTOR"],
  inverter: [150, 112, "INVERTER"],
  bms: [569, 54, "BATTERY MANAGEMENT"],
  gearbox: [262, 462, "REDUCTION GEAR"],
  thermal: [74, 221, "RADIATOR / LOOP"],
  dcdc: [762, 120, "DC/DC CONVERTER"],
  charger: [792, 231, "ONBOARD CHARGER"],
  port: [786, 348, "CHARGE PORT"],
  aux: [110, 432, "12 V AUXILIARY"],
};
const shape = {
  battery: () =>
    `${box(-112, -66, 28, 249, 132, 18)}${Array.from({ length: 8 }, (_, i) => box(-107 + i * 30, -61, 47, 26, 58, 6)).join("")}${Array.from({ length: 8 }, (_, i) => box(-107 + i * 30, 3, 47, 26, 58, 6)).join("")}${box(133, -52, 49, 18, 26, 12, 'class="hv-protection"')}<text class="protection-label" x="${p(141, -38, 67)[0]}" y="${p(141, -38, 67)[1]}">+/−</text>`,
  motor: () => cylinder(-170, -32, 53, 21, 48),
  inverter: () =>
    `${box(-140, -65, 60, 50, 58, 16)}${Array.from(
      { length: 8 },
      (_, i) =>
        `<path class="cooling-fin" d="${line([
          [-136 + i * 6, -61, 78],
          [-136 + i * 6, -12, 78],
        ])}"/>`,
    ).join("")}<path class="terminal" d="${line([
      [-94, -50, 78],
      [-87, -50, 78],
    ])}"/>`,
  bms: () =>
    `${box(89, 8, 62, 40, 34, 11)}<path class="circuit-detail" d="${line([
      [95, 16, 74],
      [105, 16, 74],
      [105, 30, 74],
      [119, 30, 74],
    ])}"/>`,
  gearbox: () =>
    `${box(-193, 25, 40, 47, 36, 28)}${circle(-171, 62, 54, 15, "gear-cover")}${circle(-171, 62, 54, 5, "gear-hub")}`,
  thermal: () =>
    `${box(-247, -67, 36, 14, 134, 30)}${Array.from(
      { length: 16 },
      (_, i) =>
        `<path class="radiator-fin" d="${line([
          [-249, -61 + i * 8, 40],
          [-249, -61 + i * 8, 64],
        ])}"/>`,
    ).join(
      "",
    )}${box(-217, -69, 60, 28, 25, 14)}${circle(-204, -43, 72, 7, "coolant-cap")}`,
  dcdc: () =>
    `${box(170, -67, 70, 47, 44, 17)}${Array.from(
      { length: 5 },
      (_, i) =>
        `<path class="cooling-fin" d="${line([
          [175 + i * 8, -62, 88],
          [175 + i * 8, -27, 88],
        ])}"/>`,
    ).join("")}`,
  charger: () =>
    `${box(151, 12, 70, 79, 52, 18)}${Array.from(
      { length: 8 },
      (_, i) =>
        `<path class="cooling-fin" d="${line([
          [157 + i * 9, 17, 89],
          [157 + i * 9, 59, 89],
        ])}"/>`,
    ).join("")}`,
  port: () =>
    `<path class="port-surround" d="${polygon([
      [223, 93, 67],
      [254, 93, 67],
      [254, 93, 97],
      [223, 93, 97],
    ])}"/>${circle(239, 94, 82, 10, "port-insert")}${circle(235, 95, 84, 2, "port-pin")}${circle(243, 95, 84, 2, "port-pin")}${circle(239, 95, 77, 2, "port-pin")}`,
  aux: () =>
    `${box(-235, 34, 47, 36, 35, 24)}${box(-230, 39, 72, 5, 7, 4)}${box(-206, 39, 72, 5, 7, 4)}<path class="battery-sign" d="${line(
      [
        [-228, 57, 73],
        [-221, 57, 73],
      ],
    )} ${line([
      [-224.5, 53.5, 73],
      [-224.5, 60.5, 73],
    ])}"/>`,
};
// Connections describe one conceptual front-drive architecture. Protection/switching
// is a schematic boundary, not a safety implementation or an electrical simulation.
const connections = [
  [
    "battery-inverter",
    "hv",
    "battery inverter",
    [
      [-108, -42, 52],
      [-97, -57, 59],
      [-96, -57, 78],
      [-115, -55, 78],
    ],
    "Battery DC bus to traction inverter",
  ],
  [
    "battery-dcdc",
    "hv",
    "battery dcdc",
    [
      [137, -37, 58],
      [157, -72, 62],
      [188, -72, 88],
      [188, -50, 88],
    ],
    "HV bus to DC/DC input",
  ],
  [
    "charger-battery",
    "hv",
    "charger battery",
    [
      [157, 24, 88],
      [145, 24, 65],
      [143, -40, 65],
      [134, -40, 57],
    ],
    "Onboard charger DC output through conceptual protection to battery",
  ],
  [
    "port-ac",
    "ac",
    "port charger",
    [
      [239, 90, 82],
      [237, 72, 82],
      [215, 72, 88],
      [215, 57, 88],
    ],
    "External AC charge input to onboard charger",
  ],
  [
    "port-dc",
    "hv",
    "port battery",
    [
      [239, 91, 76],
      [253, 74, 57],
      [159, 74, 57],
      [147, -39, 60],
      [135, -39, 57],
    ],
    "External DC charging through conceptual switching/protection directly to pack; bypasses onboard AC conversion",
  ],
  [
    "dcdc-aux",
    "lv",
    "dcdc aux",
    [
      [173, -50, 80],
      [160, -82, 76],
      [-237, -82, 70],
      [-238, 52, 66],
      [-218, 52, 73],
    ],
    "DC/DC low-voltage output to 12 V battery and auxiliary system",
  ],
  [
    "bms-inverter",
    "control",
    "bms inverter",
    [
      [108, 22, 75],
      [87, -76, 66],
      [-125, -76, 70],
      [-123, -57, 78],
    ],
    "BMS limits and inverter control communication",
  ],
  [
    "bms-charger",
    "control",
    "bms charger",
    [
      [115, 31, 75],
      [134, 49, 83],
      [158, 49, 88],
    ],
    "Battery management charge-control communication",
  ],
  [
    "bms-thermal",
    "control",
    "bms thermal",
    [
      [101, 14, 75],
      [77, -80, 68],
      [-208, -80, 70],
      [-208, -61, 74],
    ],
    "Thermal control communication; no implemented control law",
  ],
  [
    "coolant-supply",
    "coolant",
    "thermal battery inverter motor",
    [
      [-240, -44, 63],
      [-206, -58, 72],
      [-137, -61, 74],
      [-133, -15, 73],
      [-157, 5, 67],
      [-126, 57, 55],
      [110, 57, 55],
    ],
    "Conceptual coolant supply through drive unit and battery cold plate",
  ],
  [
    "coolant-return",
    "coolant",
    "thermal battery inverter motor",
    [
      [114, 60, 54],
      [134, 66, 43],
      [-131, 68, 43],
      [-190, 15, 54],
      [-237, 55, 61],
    ],
    "Conceptual coolant return to radiator; temperature and flow are not calculated",
  ],
  [
    "drive-shaft",
    "mechanical",
    "motor gearbox",
    [
      [-170, 16, 53],
      [-170, 38, 57],
    ],
    "Motor output shaft to reduction gearbox",
  ],
  [
    "gear-output",
    "mechanical",
    "gearbox",
    [
      [-171, 48, 54],
      [-171, 48, 34],
    ],
    "Reduction output to driven axle",
  ],
  [
    "driven-axle",
    "mechanical",
    "gearbox motor",
    [
      [-171, -105, 34],
      [-171, 105, 34],
    ],
    "Conceptual driven front axle; not an inferred production drivetrain",
  ],
];
for (let i = 0; i < 3; i++)
  connections.push([
    `phase-${i + 1}`,
    "phase",
    "inverter motor",
    [
      [-126 - i * 5, -17, 78],
      [-112 - i * 5, -4, 73],
      [-143 - i * 5, 3, 69],
      [-159 - i * 4, 4, 66],
    ],
    `Motor phase ${i + 1} from inverter`,
  ]);
const flowLinks = {
  propulsion: [
    "battery-inverter",
    "phase-1",
    "phase-2",
    "phase-3",
    "drive-shaft",
    "gear-output",
    "driven-axle",
  ],
  regeneration: [
    "driven-axle",
    "gear-output",
    "drive-shaft",
    "phase-1",
    "phase-2",
    "phase-3",
    "battery-inverter",
  ],
  ac_charging: ["port-ac", "charger-battery"],
  dc_charging: ["port-dc"],
  auxiliary: ["battery-dcdc", "dcdc-aux"],
};
const viewComponents = {
  complete: null,
  electrical: [
    "battery",
    "inverter",
    "bms",
    "dcdc",
    "charger",
    "port",
    "aux",
    "motor",
  ],
  drivetrain: ["motor", "gearbox", "inverter"],
  battery: ["battery", "bms", "port", "charger"],
  thermal: ["thermal", "battery", "motor", "inverter"],
};
let drawingId = 0;
function shell() {
  const flank = [
    [-269, 91, 41],
    [-263, 91, 66],
    [-183, 91, 77],
    [-106, 91, 89],
    [151, 91, 93],
    [225, 91, 86],
    [267, 91, 66],
    [270, 91, 39],
  ];
  // The lower flank follows wheel-arch contours instead of a rectangular cover.
  let near =
    line(flank) +
    ` L${xy(p(212, 91, 29))} Q${xy(p(207, 91, 91))} ${xy(p(165, 91, 92))} Q${xy(p(124, 91, 91))} ${xy(p(120, 91, 29))} L${xy(p(-121, 91, 29))} Q${xy(p(-123, 91, 91))} ${xy(p(-165, 91, 92))} Q${xy(p(-207, 91, 91))} ${xy(p(-209, 91, 29))} L${xy(p(-263, 91, 29))}Z`;
  return `<g class="vehicle-body" aria-label="Generic sedan bodywork with bonnet, cabin, roof and rear deck">
 <path class="body-far" d="${polygon([
   [-267, -82, 44],
   [-261, -82, 65],
   [-180, -84, 77],
   [-105, -83, 89],
   [-40, -65, 146],
   [96, -64, 149],
   [161, -82, 101],
   [225, -82, 87],
   [267, -80, 65],
   [270, -80, 41],
 ])}"/>
 <path class="body-bonnet" d="${polygon([
   [-263, -76, 67],
   [-181, -82, 78],
   [-108, -78, 90],
   [-108, 78, 90],
   [-181, 82, 78],
   [-263, 76, 67],
 ])}"/>
 <path class="body-boot" d="${polygon([
   [160, -80, 99],
   [226, -79, 88],
   [266, -72, 67],
   [266, 72, 67],
   [226, 79, 88],
   [160, 80, 99],
 ])}"/>
 <path class="body-side" d="${near}"/>
 <path class="glass windscreen" d="${polygon([
   [-108, -78, 92],
   [-42, -61, 146],
   [-42, 61, 146],
   [-108, 78, 92],
 ])}"/>
 <path class="body-roof" d="${polygon([
   [-41, -62, 147],
   [95, -62, 150],
   [95, 62, 150],
   [-41, 62, 147],
 ])}"/>
 <path class="glass rear-screen" d="${polygon([
   [97, -62, 149],
   [161, -78, 101],
   [161, 78, 101],
   [97, 62, 149],
 ])}"/>
 <path class="glass side-window" d="${polygon([
   [-94, 81, 96],
   [-36, 66, 141],
   [92, 66, 144],
   [145, 81, 105],
 ])}"/>
 <path class="window-pillar" d="${line([
   [28, 69, 143],
   [34, 83, 101],
 ])}"/>
 <path class="body-seam" d="${line([
   [-105, 92, 87],
   [-100, 92, 38],
 ])} ${line([
   [32, 92, 96],
   [33, 92, 31],
 ])} ${line([
   [149, 92, 97],
   [139, 92, 46],
 ])}"/>
 <path class="door-handle" d="${line([
   [-30, 93, 91],
   [-10, 93, 92],
 ])} ${line([
   [83, 93, 94],
   [102, 93, 94],
 ])}"/>
 <path class="front-fascia" d="${polygon([
   [-267, -76, 64],
   [-269, 0, 69],
   [-267, 76, 64],
   [-271, 76, 39],
   [-275, 0, 35],
   [-271, -76, 39],
 ])}"/>
 <path class="headlamp" d="${line([
   [-271, -70, 61],
   [-275, -30, 64],
 ])} ${line([
   [-275, 30, 64],
   [-271, 70, 61],
 ])}"/>
 <path class="bumper-detail" d="${line([
   [-275, -47, 43],
   [-278, 0, 40],
   [-275, 47, 43],
 ])}"/>
 <path class="taillamp" d="${line([
   [270, -67, 66],
   [272, -36, 68],
 ])} ${line([
   [272, 36, 68],
   [270, 67, 66],
 ])}"/>
 <path class="roof-rail" d="${line([
   [-103, -82, 90],
   [-42, -65, 148],
   [95, -65, 151],
   [165, -83, 101],
 ])} ${line([
   [-103, 82, 90],
   [-42, 65, 148],
   [95, 65, 151],
   [165, 83, 101],
 ])}"/>
 </g>`;
}
function cabin() {
  const seat = (x, y) =>
    `<path d="${polygon([
      [x, y, 66],
      [x + 38, y, 66],
      [x + 38, y + 28, 66],
      [x, y + 28, 66],
    ])} ${polygon([
      [x + 36, y, 67],
      [x + 38, y, 119],
      [x + 38, y + 28, 119],
      [x + 36, y + 28, 67],
    ])}"/>`;
  return `<g class="vehicle-cabin" aria-label="Illustrative passenger cabin and seating envelope">${seat(-42, -48)}${seat(-42, 20)}<path d="${polygon(
    [
      [75, -60, 65],
      [120, -60, 65],
      [120, 60, 65],
      [75, 60, 65],
    ],
  )} ${polygon([
    [120, -60, 66],
    [130, -60, 110],
    [130, 60, 110],
    [120, 60, 66],
  ])}"/></g>`;
}
function classShell(key) {
  const a = appearances[key],
    w = a.width,
    h = a.deck,
    z = a.clearance;
  const roof = [
    [a.front, -w * 0.67, a.roof],
    [a.rear, -w * 0.67, a.roof],
    [a.rear, w * 0.67, a.roof],
    [a.front, w * 0.67, a.roof],
  ];
  const belt = [
    [-265, -w, h - 12],
    [-115, -w, h],
    [205, -w, h + 3],
    [270, -w, h - 10],
    [270, w, h - 10],
    [205, w, h + 3],
    [-115, w, h],
    [-265, w, h - 12],
  ];
  const side = [
    [-265, w, z],
    [-265, w, h - 12],
    [-115, w, h],
    [a.front, w * 0.67, a.roof],
    [a.rear, w * 0.67, a.roof],
    [205, w, h + 3],
    [270, w, h - 10],
    [270, w, z],
  ];
  // Explicit original body meshes; geometry is visual packaging, not aerodynamic input.
  return `<g class="vehicle-body class-body" data-class="${key}" aria-label="Original ${a.name} ${a.label}">
  <path class="body-far" d="${polygon(belt)}"/>
  <path class="body-near" d="${polygon(side)}"/>
  <path class="body-bonnet" d="${polygon([
    [-265, -w, h - 12],
    [-115, -w, h],
    [a.front, -w * 0.67, a.roof],
    [a.front, w * 0.67, a.roof],
    [-115, w, h],
    [-265, w, h - 12],
  ])}"/>
  <path class="body-roof" d="${polygon(roof)}"/>
  <path class="body-glass windscreen" d="${polygon([
    [-115, -w * 0.9, h + 3],
    [a.front, -w * 0.64, a.roof - 3],
    [a.front, w * 0.64, a.roof - 3],
    [-115, w * 0.9, h + 3],
  ])}"/>
  <path class="body-glass" d="${polygon([
    [a.front + 8, w * 0.68, a.roof - 8],
    [a.rear - 8, w * 0.68, a.roof - 8],
    [190, w, h + 8],
    [-100, w, h + 8],
  ])}"/>
  ${
    key === "performance"
      ? `<path class="body-intake" d="${polygon([
          [-90, w + 1, 42],
          [70, w + 1, 47],
          [115, w + 1, 65],
          [-65, w + 1, 65],
        ])}"/><path class="body-wing" d="${polygon([
          [214, -115, 104],
          [235, -115, 104],
          [235, 115, 104],
          [214, 115, 104],
        ])}"/>`
      : `<path class="body-seam" d="${line([
          [27, w, h + 3],
          [27, w, z + 10],
        ])} ${line([
          [155, w, h + 3],
          [155, w, z + 10],
        ])}"/>`
  }
  <path class="body-led" d="${line([
    [-267, -w + 12, h - 4],
    [-267, w - 12, h - 4],
  ])}"/>
  <text class="drawing-note" x="${p(20, w + 2, h - 12)[0]}" y="${p(20, w + 2, h - 12)[1]}">${a.name}</text></g>`;
}
function packShape(opts) {
  if (!opts.appearance) return shape.battery();
  const a = appearances[opts.appearance],
    base = a.pack;
  // Only discrete illustrative component envelopes; capacity does not determine dimensions.
  const alternate = opts.batteryId === "battery-80";
  const [x, y, l0, w0] = base,
    l = l0 + (alternate ? 12 : 0),
    w = w0 + (alternate ? 8 : 0),
    columns = alternate ? 10 : 8;
  const split = opts.appearance === "performance";
  const rows = split ? [y, y + w - 43] : [y + 5, y + w / 2 + 2];
  return `<g class="pack-envelope" data-layout="${opts.appearance}${alternate ? "-alternate" : ""}" data-record="${escape(opts.batteryId || "custom")}">${box(x, y, 28, l, w, 14)}${rows.map((yy) => Array.from({ length: columns }, (_, i) => box(x + 5 + (i * (l - 10)) / columns, yy, 43, (l - 15) / columns, split ? 38 : w / 2 - 7, 7)).join("")).join("")}</g>`;
}
function normalizedOptions(options = {}) {
  return {
    appearance: appearances[options.appearance] ? options.appearance : null,
    batteryId: options.batteryId || null,
    motorId: options.motorId || null,
    annotations: options.annotations !== false,
    body: ["cutaway", "transparent", "opaque"].includes(options.body)
      ? options.body
      : "cutaway",
    view: options.view in viewComponents ? options.view : "complete",
    selected: options.selected ?? null,
    flow: options.flow === "charging" ? "ac_charging" : options.flow || null,
  };
}
function states(options) {
  const view = viewComponents[options.view],
    selected = options.selected;
  const active = new Set(flowLinks[options.flow] || []);
  return {
    component(id) {
      return [
        selected === id ? "is-selected" : "",
        view && !view.includes(id) ? "is-hidden-system" : "",
        selected && selected !== id ? "is-dim" : "",
      ].join(" ");
    },
    link(id, kind, connects) {
      const related = selected && connects.split(" ").includes(selected),
        kinds = {
          electrical: ["hv", "phase", "ac", "lv", "control"],
          drivetrain: ["mechanical", "phase"],
          battery: ["hv", "ac", "control", "coolant"],
          thermal: ["coolant", "control"],
        }[options.view],
        viewAllowed =
          !view ||
          (connects.split(" ").some((c) => view.includes(c)) &&
            kinds.includes(kind));
      return [
        related ? "is-related" : "",
        selected && !related ? "is-dim" : "",
        !viewAllowed ? "is-hidden-system" : "",
        active.has(id) ? "is-flow-active is-flow" : "",
      ].join(" ");
    },
  };
}
export function anatomySVG(components, interactive = true, options = {}) {
  const opts = normalizedOptions(options),
    id = `ev-${++drawingId}`,
    state = states(opts);
  const known = components.filter((c) => shape[c.id]);
  return `<svg class="anatomy-svg vehicle-cutaway" data-appearance="${opts.appearance || "generic"}" data-body="${opts.body}" data-view="${opts.view}" data-annotations="${opts.annotations}" data-flow="${opts.flow || ""}" data-prefix="${id}" data-selected="${opts.selected || ""}" viewBox="${opts.annotations ? "0 0 900 520" : "145 102 610 400"}" role="group" aria-label="Original generic electric sedan cutaway. Conceptual front-drive architecture, not to scale or manufacturer-specific.">
 <defs><pattern id="${id}-grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" fill="none" stroke="currentColor" stroke-width=".5"/></pattern><marker id="${id}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="context-stroke"/></marker></defs>
 <rect class="vehicle-grid" x="26" y="20" width="848" height="475" fill="url(#${id}-grid)"/>
 <path class="vehicle-shadow" d="${polygon([
   [-290, -106, -7],
   [278, -106, -7],
   [288, 114, -7],
   [-285, 114, -7],
 ])}"/>
 ${wheel(165, -105, opts.appearance ? appearances[opts.appearance].wheel : 34)}${wheel(-171, -105, opts.appearance ? appearances[opts.appearance].wheel : 34)}
 <g class="vehicle-chassis"><path class="undertray" d="${polygon([
   [-270, -82, 28],
   [269, -82, 28],
   [269, 82, 28],
   [-270, 82, 28],
 ])}"/><path class="chassis-rail" d="${line([
   [-265, -76, 33],
   [265, -76, 33],
 ])} ${line([
   [-265, 76, 33],
   [265, 76, 33],
 ])}"/><path class="rear-axle-context" d="${line([
   [165, -105, 34],
   [165, 105, 34],
 ])}"/></g>
 <g class="vehicle-systems">${known.map((c) => `<g class="anatomy-component c-${c.id} ${state.component(c.id)}" data-component="${c.id}" ${interactive ? `tabindex="0" role="button" aria-pressed="${opts.selected === c.id}" aria-describedby="anatomy-tooltip"` : ""} aria-label="${escape(c.number + " " + c.name)}"><title>${escape(c.name + ": " + c.function)}</title>${c.id === "battery" ? packShape(opts) : c.id === "motor" && opts.appearance ? cylinder(-170, -32, 53, { "motor-150": 21, "motor-220": 26, "motor-s1": 23, "motor-r1": 31, "motor-x1": 26 }[opts.motorId] || 24, 48) : shape[c.id]()}</g>`).join("")}</g>
 <g class="vehicle-connections" aria-label="Conceptual high voltage, three-phase, low voltage, control, coolant and mechanical connections">${connections.map(([key, kind, connects, points, label]) => `<path class="vehicle-link link-${kind} ${state.link(key, kind, connects)}" data-link="${key}" data-kind="${kind}" data-connects="${connects}" d="${line(points)}" ${opts.flow && flowLinks[opts.flow]?.includes(key) ? `marker-${opts.flow === "regeneration" ? "start" : "end"}="url(#${id}-arrow)"` : ""}><title>${escape(label)}</title></path>`).join("")}</g>
 ${wheel(165, 107, opts.appearance ? appearances[opts.appearance].wheel : 34)}${wheel(-171, 107, opts.appearance ? appearances[opts.appearance].wheel : 34)}${cabin()}${opts.appearance ? classShell(opts.appearance) : shell()}
 <g class="vehicle-annotations">${known
   .map((c) => {
     const [mx, my, label] = labels[c.id],
       [cx, cy] = p(...centers[c.id]);
     return `<g class="vehicle-label c-${c.id}" data-label="${c.id}" data-component-link="${c.id}"><path class="leader" d="M${cx.toFixed(1)} ${cy.toFixed(1)}L${mx} ${my}"/><circle class="anchor-dot" cx="${cx}" cy="${cy}" r="3"/><circle class="annotation" cx="${mx}" cy="${my}" r="13"/><text class="annotation-number" x="${mx}" y="${my + 4}" text-anchor="middle">${escape(c.number)}</text><text class="annotation-label" x="${mx}" y="${my + 27}" text-anchor="middle">${label}</text></g>`;
   })
   .join("")}</g>
 <g class="vehicle-drawing-notes"><text x="30" y="505" class="drawing-note">EV CUTAWAY / CONCEPT FRONT-DRIVE ARCHITECTURE</text><text x="870" y="505" class="drawing-note" text-anchor="end">ILLUSTRATIVE PLACEMENT · NOT TO SCALE</text></g></svg>`;
}
export function updateSchematic(svg, options = {}) {
  if (!svg) return;
  const opts = normalizedOptions({
      annotations: svg.dataset.annotations !== "false",
      body: svg.dataset.body,
      view: svg.dataset.view,
      flow: svg.dataset.flow || null,
      selected: svg.dataset.selected || null,
      ...options,
    }),
    state = states(opts);
  svg.setAttribute(
    "viewBox",
    opts.annotations ? "0 0 900 520" : "145 102 610 400",
  );
  svg.dataset.body = opts.body;
  svg.dataset.view = opts.view;
  svg.dataset.annotations = String(opts.annotations);
  svg.dataset.flow = opts.flow || "";
  svg.dataset.selected = opts.selected || "";
  for (const g of svg.querySelectorAll("[data-component]")) {
    g.classList.toggle("is-selected", g.dataset.component === opts.selected);
    g.classList.toggle(
      "is-dim",
      !!opts.selected && g.dataset.component !== opts.selected,
    );
    g.classList.toggle(
      "is-hidden-system",
      !!viewComponents[opts.view] &&
        !viewComponents[opts.view].includes(g.dataset.component),
    );
    if (g.getAttribute("role") === "button") {
      const visible =
        !viewComponents[opts.view] ||
        viewComponents[opts.view].includes(g.dataset.component);
      g.setAttribute("tabindex", visible ? "0" : "-1");
      g.setAttribute("aria-hidden", String(!visible));
      g.setAttribute(
        "aria-pressed",
        String(g.dataset.component === opts.selected),
      );
    }
  }
  for (const link of svg.querySelectorAll("[data-link]")) {
    link.setAttribute(
      "class",
      `vehicle-link link-${link.dataset.kind} ${state.link(link.dataset.link, link.dataset.kind, link.dataset.connects)}`,
    );
    link.removeAttribute("marker-start");
    link.removeAttribute("marker-end");
    if (flowLinks[opts.flow]?.includes(link.dataset.link))
      link.setAttribute(
        opts.flow === "regeneration" ? "marker-start" : "marker-end",
        `url(#${svg.dataset.prefix}-arrow)`,
      );
  }
  for (const label of svg.querySelectorAll("[data-label]")) {
    label.classList.toggle(
      "is-hidden-system",
      !!viewComponents[opts.view] &&
        !viewComponents[opts.view].includes(label.dataset.label),
    );
    label.classList.toggle(
      "is-label-selected",
      label.dataset.label === opts.selected,
    );
  }
}

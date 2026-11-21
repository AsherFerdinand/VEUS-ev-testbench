// Shared original visual profiles. Drawing units are illustrative, never inferred CAD dimensions.
export const appearances = {
  sedan: {
    name: "VEUS S1",
    label: "Electric Sedan",
    roof: 148,
    front: -55,
    rear: 118,
    width: 90,
    deck: 82,
    clearance: 30,
    wheel: 34,
    pack: [-112, -66, 249, 132],
    description: "Balanced efficiency · everyday driving",
  },
  performance: {
    name: "VEUS R1",
    label: "Performance EV",
    roof: 108,
    front: -18,
    rear: 83,
    width: 106,
    deck: 66,
    clearance: 22,
    wheel: 37,
    pack: [-108, -76, 230, 152],
    description: "Single-drive-unit performance · low, wide packaging",
  },
  suv: {
    name: "VEUS X1",
    label: "Family SUV",
    roof: 195,
    front: -66,
    rear: 188,
    width: 102,
    deck: 103,
    clearance: 43,
    wheel: 43,
    pack: [-126, -79, 282, 158],
    description: "Capacity and utility · spacious passenger cabin",
  },
};
export const appearanceOf = (design) =>
  Object.hasOwn(appearances, design?.appearance)
    ? design.appearance
    : "performance";
export function sideVehicle(
  kind = "performance",
  id = "vehicle",
  color = "url(#pearl)",
) {
  const k = appearances[kind] ? kind : "performance",
    r = appearances[k].wheel;
  const body = {
    sedan:
      "M54 217l14-38 77-16 68-53h121l65 52 87 18 33 29-7 18h-39q-2-51-40-51t-44 51H198q-3-51-44-51t-44 51H65z",
    performance:
      "M48 224l16-29 75-22 99-36 76-2 70 35 98 12 40 25-13 19h-34q-3-53-42-53t-46 53H198q-3-53-44-53t-44 53H60z",
    suv: "M51 209l11-45 85-15 56-85 175 0 37 30 56 18 46 54 9 49-51 3q-1-59-42-59t-44 59H198q-2-59-44-59t-46 59H58z",
  }[k];
  const windows = {
    sedan: "M168 159l57-43h101l54 43z",
    performance: "M193 170l56-29h60l56 29z",
    suv: "M169 147l43-75h156l29 28 16 47z",
  }[k];
  return `<g id="${id}" data-appearance="${k}" aria-label="Original ${appearances[k].name} illustrative body"><ellipse cx="290" cy="259" rx="239" ry="13" fill="#020711" opacity=".45"/>
 ${[154, 433].map((x) => `<g data-scene-wheel data-wheel-x="${x}" data-wheel-y="220" fill="#101d2b" stroke="#3b5164" stroke-width="3"><circle cx="${x}" cy="220" r="${r + 5}"/><circle cx="${x}" cy="220" r="${r - 10}" fill="#3c5267"/><path d="M${x} ${220 - r + 11}v${2 * r - 22}m${-r + 11} ${-r + 11}h${2 * r - 22}" stroke="#a9c2d3"/></g>`).join("")}
 <path d="${body}" fill="${color}" stroke="#bdd1de" stroke-width="2"/>
 <path d="${windows}" fill="#152d42" stroke="#7392a5" stroke-width="2"/>
 ${k === "performance" ? '<path d="M72 214h42l13-15m83 5l48-20h115l26 23M466 169h40v8h-40" fill="none" stroke="#344f64" stroke-width="7"/>' : '<path d="M277 115v97m-65-44v40m150-40v40" fill="none" stroke="#7c97a9" stroke-width="2"/>'}
 <path d="M72 185l43-8m361 9l29 10M207 219h175" stroke="#6fdfeb" stroke-width="4" fill="none"/>
 <text x="290" y="200" fill="#314e63" font-family="sans-serif" font-size="10" letter-spacing="4">${appearances[k].name}</text></g>`;
}
export const vehicleThumbnail = (kind) =>
  `<svg viewBox="20 25 530 260" role="img" aria-label="${appearances[kind].name} ${appearances[kind].label}">${sideVehicle(kind, "thumb-" + kind, "#cbdbe3")}</svg>`;

// Original plan view shares the fictional class identity; not CAD or lateral dynamics.
export function topVehicle(kind = "sedan", id = "plan-car", color = "#c7dce5") {
  const k = appearances[kind] ? kind : "sedan",
    w = k === "suv" ? 55 : 48,
    l = k === "performance" ? 135 : 128;
  return `<g id="${id}" data-appearance="${k}" aria-label="${appearances[k].name} illustrative plan view"><ellipse rx="${l / 2 + 6}" ry="${w / 2 + 6}" fill="#020711" opacity=".35"/>${[-1, 1].flatMap((x) => [-1, 1].map((y) => `<rect x="${x * l * 0.3 - 10}" y="${y * (w / 2 + 2) - 5}" width="20" height="10" rx="3" fill="#0b1720"/>`)).join("")}<rect x="${-l / 2}" y="${-w / 2}" width="${l}" height="${w}" rx="${w * 0.3}" fill="${color}" stroke="#83a6b8" stroke-width="2"/><path d="M-25 -19Q-43 0 -25 19H24Q35 0 24 -19Z" fill="#18334a"/><rect x="-15" y="-16" width="30" height="32" rx="4" fill="#b1c9d5"/><path d="M${-l / 2 + 5} -15v30" stroke="#78dbe5" stroke-width="4"/><text y="4" text-anchor="middle" fill="#233f51" font-size="9">${appearances[k].name}</text></g>`;
}

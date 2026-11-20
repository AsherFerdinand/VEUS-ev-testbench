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
const shapes = {
  battery:
    '<path class="component-surface" d="m260 241 142-80 154 86-146 83Z"/><path class="component-side" d="m260 241 150 89v17l-150-88Zm150 89 146-83v17l-146 83Z"/><path class="cell-lines" d="m282 230 149 88m-126-101 149 88m-126-101 149 88m-126-101 149 88m-126-101 149 88"/>',
  motor:
    '<path class="component-surface" d="m157 250 50-29 53 30-51 30Z"/><path class="component-side" d="m157 250 52 31v30l-52-31Zm52 31 51-30v29l-51 31Z"/><ellipse cx="184" cy="279" rx="15" ry="21" transform="rotate(-30 184 279)"/>',
  inverter:
    '<path class="component-surface" d="m190 209 46-26 49 28-47 26Z"/><path class="component-side" d="m190 209 48 28v17l-48-28Zm48 28 47-26v17l-47 26Z"/><path d="m205 212 30 17m-20-23 30 17m-20-23 30 17"/>',
  bms: '<path class="component-surface" d="m413 188 29-16 38 22-30 17Z"/><path class="component-side" d="m413 188 37 23v12l-37-23Zm37 23 30-17v12l-30 17Z"/>',
  gearbox:
    '<path class="component-surface" d="m124 286 34-20 40 23-34 20Z"/><path class="component-side" d="m124 286 40 23v21l-40-23Zm40 23 34-20v21l-34 20Z"/>',
  thermal:
    '<path class="component-surface" d="m347 119 47-26 44 25-47 27Z"/><path class="component-side" d="m347 119 44 26v22l-44-26Zm44 26 47-27v22l-47 27Z"/><path d="m355 121 33 20m-20-28 34 20m-20-27 33 20"/>',
  dcdc: '<path class="component-surface" d="m484 182 29-17 37 21-29 17Z"/><path class="component-side" d="m484 182 37 21v14l-37-21Zm37 21 29-17v14l-29 17Z"/>',
  charger:
    '<path class="component-surface" d="m509 139 37-21 54 31-37 22Z"/><path class="component-side" d="m509 139 54 32v18l-54-32Zm54 32 37-22v18l-37 22Z"/>',
  port: '<path class="component-surface" d="m613 197 20-12 17 10v31l-20 12-17-10Z"/><circle cx="630" cy="213" r="7"/>',
  aux: '<path class="component-surface" d="m112 225 26-15 28 16-26 15Z"/><path class="component-side" d="m112 225 28 16v25l-28-16Zm28 16 26-15v25l-26 15Z"/><path d="m124 223 8 4m-2-6-4 8"/>',
};
const annotations = {
  battery: [410, 281, 650, 400, "HV BATTERY"],
  motor: [200, 277, 48, 194, "TRACTION MOTOR"],
  inverter: [236, 220, 110, 107, "INVERTER"],
  bms: [447, 200, 595, 68, "BATTERY MANAGEMENT"],
  gearbox: [160, 302, 65, 360, "REDUCTION GEAR"],
  thermal: [395, 130, 357, 44, "THERMAL LOOP"],
  dcdc: [523, 193, 704, 111, "DC/DC"],
  charger: [557, 157, 768, 191, "ONBOARD CHARGER"],
  port: [630, 215, 783, 296, "CHARGE PORT"],
  aux: [139, 239, 172, 452, "AUXILIARIES"],
};
export function anatomySVG(components, interactive = true) {
  return `<svg class="anatomy-svg" viewBox="0 0 880 520" role="group" aria-label="Original isometric EV component schematic. Illustrative locations, not to scale.">
 <defs><pattern id="draft-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="currentColor" stroke-width=".45"/></pattern></defs>
 <rect x="30" y="14" width="820" height="480" fill="url(#draft-grid)" class="draft-grid"/>
 <path class="chassis-shadow" d="m90 276 319-182 296 164-322 188Z"/>
 <g class="wheels"><ellipse cx="160" cy="293" rx="23" ry="40" transform="rotate(-30 160 293)"/><ellipse cx="351" cy="394" rx="23" ry="40" transform="rotate(-30 351 394)"/><ellipse cx="462" cy="105" rx="23" ry="40" transform="rotate(-30 462 105)"/><ellipse cx="654" cy="215" rx="23" ry="40" transform="rotate(-30 654 215)"/></g>
 <path class="chassis-side" d="m104 258 307-177 275 155v20L379 433 104 278Z"/>
 <path class="chassis-top" d="m104 258 307-177 275 155-307 177Z"/>
 <path class="frame-lines" d="m125 259 286-161 254 140-286 161Zm64-35 250 141m-181-180 250 141m-184-179 251 140m-270-44 243-138"/>
 <path class="thermal-lines" d="m246 258 138-80 140 80m-201-91 68-39"/>
 ${components
   .map((c, i) => {
     const [x, y, mx, my, label] = annotations[c.id];
     return `<g class="anatomy-component c-${c.id}" data-component="${c.id}" ${interactive ? `tabindex="0" role="button" aria-pressed="${i === 0}" aria-describedby="anatomy-tooltip"` : ""} aria-label="${c.number} ${c.name}"><title>${c.name}: ${c.function}</title>${shapes[c.id]}<path class="leader" d="M${x} ${y} L${mx} ${my}"/><circle class="anchor-dot" cx="${x}" cy="${y}" r="3"/><circle class="annotation" cx="${mx}" cy="${my}" r="13"/><text class="annotation-number" x="${mx}" y="${my + 4}" text-anchor="middle">${c.number}</text><text class="annotation-label" x="${mx}" y="${my + 29}" text-anchor="middle">${label}</text></g>`;
   })
   .join("")}
 <text x="32" y="506" class="drawing-note">EV / SYSTEMS STUDY 01</text><text x="848" y="506" text-anchor="end" class="drawing-note">CONCEPTUAL PLACEMENT · NOT TO SCALE</text></svg>`;
}
export function flowSVG(mode) {
  const flows = {
    propulsion: {
      path: "M160 160H340H510H615",
      label: "Battery → inverter → motor → reduction → wheels",
    },
    regeneration: {
      path: "M680 160H510H340H225",
      label:
        "Wheels → motor → inverter → battery, subject to acceptance limits",
    },
    charging: {
      path: "M160 350H340V420H80V160H95",
      label:
        "AC supply → onboard charger → battery. DC fast charging bypasses the onboard AC converter.",
    },
    auxiliary: {
      path: "M160 160V280H340H445",
      label: "HV battery → DC/DC → low-voltage auxiliaries",
    },
  };
  const f = flows[mode];
  return `<svg viewBox="30 90 780 390" class="flow-svg" role="img" aria-label="${f.label}"><defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 10 5 0 10Z" fill="currentColor"/></marker></defs><g class="flow-network"><path d="M160 160H340H510H680M160 350H340V420H80V160H160M160 160V280H340H510"/></g><path d="${f.path}" class="flow-active" marker-end="url(#flow-arrow)"/>${[
    [160, 160, "HV BATTERY"],
    [340, 160, "INVERTER"],
    [510, 160, "MOTOR"],
    [680, 160, "GEAR / WHEELS"],
    [160, 350, "AC SUPPLY"],
    [340, 350, "ONBOARD CHARGER"],
    [340, 280, "DC/DC"],
    [510, 280, "LV AUXILIARIES"],
  ]
    .map(
      ([x, y, t]) =>
        `<g><rect x="${x - 65}" y="${y - 26}" width="130" height="52" rx="5"/><text x="${x}" y="${y + 4}" text-anchor="middle">${t}</text></g>`,
    )
    .join(
      "",
    )}<text x="440" y="455" text-anchor="middle" class="drawing-note">SCHEMATIC PATH ONLY · NO POWER OR ENERGY CALCULATED</text></svg>`;
}

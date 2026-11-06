// A tiny hand-drawn line renderer.
//
// rough.js would do this, but its ESM build uses extensionless imports that
// Node refuses to resolve, and bundling a dependency to draw wobbly lines is
// not a trade worth making. This is the whole technique: draw every stroke
// twice along slightly different bezier paths, with the control points
// jittered. Two imperfect passes read as a pen; one reads as a mistake.
//
// The RNG is seeded, so regenerating produces byte-identical SVG and the
// diagrams do not churn the diff every build.

export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const n = (v) => Math.round(v * 100) / 100;

/** One wobbly pass between two points. */
function pass(x1, y1, x2, y2, rand, wobble) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  // Jitter scales with length, but is capped: a long edge should not bow.
  const amp = Math.min(wobble, len / 18);
  const off = () => (rand() * 2 - 1) * amp;
  // Perpendicular unit vector — bow the line sideways, not along itself.
  const px = -dy / len;
  const py = dx / len;
  const b1 = (rand() * 2 - 1) * amp;
  const b2 = (rand() * 2 - 1) * amp;
  const c1x = x1 + dx * 0.33 + px * b1 + off() * 0.3;
  const c1y = y1 + dy * 0.33 + py * b1 + off() * 0.3;
  const c2x = x1 + dx * 0.66 + px * b2 + off() * 0.3;
  const c2y = y1 + dy * 0.66 + py * b2 + off() * 0.3;
  return `M ${n(x1 + off() * 0.4)} ${n(y1 + off() * 0.4)} C ${n(c1x)} ${n(c1y)}, ${n(c2x)} ${n(c2y)}, ${n(x2 + off() * 0.4)} ${n(y2 + off() * 0.4)}`;
}

export function line(x1, y1, x2, y2, rand, { wobble = 1.6, passes = 2 } = {}) {
  return Array.from({ length: passes }, () => pass(x1, y1, x2, y2, rand, wobble));
}

/** A rounded rectangle, drawn edge by edge so the corners stay open-ish. */
export function rect(x, y, w, h, rand, opts = {}) {
  const r = Math.min(opts.radius ?? 10, w / 2, h / 2);
  return [
    ...line(x + r, y, x + w - r, y, rand, opts),
    ...line(x + w, y + r, x + w, y + h - r, rand, opts),
    ...line(x + w - r, y + h, x + r, y + h, rand, opts),
    ...line(x, y + h - r, x, y + r, rand, opts),
    // Corner arcs, drawn once each — doubling them looks blotchy.
    `M ${n(x + w - r)} ${n(y)} Q ${n(x + w)} ${n(y)}, ${n(x + w)} ${n(y + r)}`,
    `M ${n(x + w)} ${n(y + h - r)} Q ${n(x + w)} ${n(y + h)}, ${n(x + w - r)} ${n(y + h)}`,
    `M ${n(x + r)} ${n(y + h)} Q ${n(x)} ${n(y + h)}, ${n(x)} ${n(y + h - r)}`,
    `M ${n(x)} ${n(y + r)} Q ${n(x)} ${n(y)}, ${n(x + r)} ${n(y)}`,
  ];
}

/** A cylinder, for the datastores. */
export function cylinder(x, y, w, h, rand, opts = {}) {
  const ry = Math.min(10, h / 5);
  return [
    ...line(x, y + ry, x, y + h - ry, rand, opts),
    ...line(x + w, y + ry, x + w, y + h - ry, rand, opts),
    `M ${n(x)} ${n(y + ry)} A ${n(w / 2)} ${n(ry)} 0 0 1 ${n(x + w)} ${n(y + ry)}`,
    `M ${n(x)} ${n(y + ry)} A ${n(w / 2)} ${n(ry)} 0 0 0 ${n(x + w)} ${n(y + ry)}`,
    `M ${n(x)} ${n(y + h - ry)} A ${n(w / 2)} ${n(ry)} 0 0 0 ${n(x + w)} ${n(y + h - ry)}`,
  ];
}

/** An arrowhead at (x2,y2) pointing along the incoming direction. */
export function arrowHead(x1, y1, x2, y2, rand, size = 9) {
  const a = Math.atan2(y2 - y1, x2 - x1);
  const spread = 0.42;
  const p = (sign) =>
    `M ${n(x2)} ${n(y2)} L ${n(x2 - size * Math.cos(a + sign * spread))} ${n(y2 - size * Math.sin(a + sign * spread))}`;
  return [p(1), p(-1)];
}

export const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

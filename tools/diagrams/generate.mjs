// Generates the architecture SVGs in docs/diagrams/.
//
//   node tools/diagrams/generate.mjs
//
// Two diagrams, each in a light and a dark variant, because GitHub serves
// README images through <picture> and a single diagram legible on one theme is
// unreadable on the other.
//
// Layout is declarative and absolute. That is the trade against Mermaid: no
// layout engine to fight, and no layout engine to do the work either — moving
// a box means changing its coordinates here.

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { arrowHead, cylinder, esc, line, rect, rng } from "./rough.mjs";

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), "../../docs/diagrams");

const THEMES = {
  light: {
    bg: "transparent",
    text: "#1f2328",
    muted: "#57606a",
    edge: "#57606a",
    accents: {
      src: "#8250df",
      svc: "#0969da",
      bus: "#bf3989",
      eng: "#bc4c00",
      store: "#1a7f37",
      obs: "#57606a",
    },
    fills: {
      src: "#f5f0ff",
      svc: "#eef6ff",
      bus: "#fff0f7",
      eng: "#fff4ed",
      store: "#eefbf1",
      obs: "#f6f8fa",
    },
  },
  dark: {
    bg: "transparent",
    text: "#e6edf3",
    muted: "#9198a1",
    edge: "#8b949e",
    accents: {
      src: "#d2a8ff",
      svc: "#79c0ff",
      bus: "#ff9bce",
      eng: "#ffa657",
      store: "#56d364",
      obs: "#9198a1",
    },
    fills: {
      src: "#1d1b2e",
      svc: "#0d1b2a",
      bus: "#2b1222",
      eng: "#2a1a0c",
      store: "#0c2113",
      obs: "#161b22",
    },
  },
};

const FONT =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif';

function textBlock(node, theme) {
  const cx = node.x + node.w / 2;
  const lines = node.label;
  const lineH = 15;
  // Vertically centre the stack; the title line is a little taller.
  const total = lines.length * lineH;
  const top = node.y + node.h / 2 - total / 2 + 11;
  return lines
    .map((l, i) => {
      const bold = i === 0;
      const fill = bold ? theme.text : theme.muted;
      const size = bold ? 12.5 : 11;
      const weight = bold ? 600 : 400;
      return `  <text x="${cx}" y="${top + i * lineH}" text-anchor="middle" font-family='${FONT}' font-size="${size}" font-weight="${weight}" fill="${fill}">${esc(l)}</text>`;
    })
    .join("\n");
}

function drawNode(node, theme, rand) {
  const accent = theme.accents[node.kind] ?? theme.accents.obs;
  const fill = theme.fills[node.kind] ?? theme.fills.obs;
  const paths =
    node.shape === "cylinder"
      ? cylinder(node.x, node.y, node.w, node.h, rand)
      : rect(node.x, node.y, node.w, node.h, rand, { radius: node.shape === "bus" ? 3 : 12 });

  // A soft fill behind the sketched outline: the hand-drawn strokes do not
  // close cleanly, so filling the paths themselves leaks colour.
  const backing =
    node.shape === "cylinder"
      ? `  <rect x="${node.x}" y="${node.y + 8}" width="${node.w}" height="${node.h - 16}" rx="6" fill="${fill}"/>\n` +
        `  <ellipse cx="${node.x + node.w / 2}" cy="${node.y + 10}" rx="${node.w / 2}" ry="10" fill="${fill}"/>`
      : `  <rect x="${node.x}" y="${node.y}" width="${node.w}" height="${node.h}" rx="${node.shape === "bus" ? 3 : 12}" fill="${fill}"/>`;

  const stroke = paths
    .map(
      (d) =>
        `  <path d="${d}" fill="none" stroke="${accent}" stroke-width="1.6" stroke-linecap="round"/>`,
    )
    .join("\n");

  return `${backing}\n${stroke}\n${textBlock(node, theme)}`;
}

function drawEdge(edge, nodes, theme, rand) {
  const from = nodes[edge.from];
  const to = nodes[edge.to];
  const [x1, y1] = anchor(from, edge.fromSide ?? "right");
  const [x2, y2] = anchor(to, edge.toSide ?? "left");
  const dashed = edge.dashed ? ' stroke-dasharray="5 5"' : "";
  const colour = edge.dashed ? theme.muted : theme.edge;

  const segs = line(x1, y1, x2, y2, rand, { wobble: 2.2, passes: edge.dashed ? 1 : 2 });
  const head = arrowHead(x1, y1, x2, y2, rand);

  const label = edge.label
    ? `  <rect x="${(x1 + x2) / 2 - edge.label.length * 3.2 - 4}" y="${(y1 + y2) / 2 - 17}" width="${edge.label.length * 6.4 + 8}" height="14" rx="3" fill="${theme.fills.obs}"/>\n` +
      `  <text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 6}" text-anchor="middle" font-family='${FONT}' font-size="10" fill="${theme.muted}">${esc(edge.label)}</text>`
    : "";

  return (
    segs
      .map(
        (d) =>
          `  <path d="${d}" fill="none" stroke="${colour}" stroke-width="1.4" stroke-linecap="round"${dashed}/>`,
      )
      .join("\n") +
    "\n" +
    head
      .map(
        (d) =>
          `  <path d="${d}" fill="none" stroke="${colour}" stroke-width="1.4" stroke-linecap="round"/>`,
      )
      .join("\n") +
    (label ? "\n" + label : "")
  );
}

function anchor(node, side) {
  switch (side) {
    case "left":
      return [node.x - 4, node.y + node.h / 2];
    case "right":
      return [node.x + node.w + 4, node.y + node.h / 2];
    case "top":
      return [node.x + node.w / 2, node.y - 4];
    case "bottom":
      return [node.x + node.w / 2, node.y + node.h + 4];
    default:
      return [node.x + node.w / 2, node.y + node.h / 2];
  }
}

function render(scene, themeName) {
  const theme = THEMES[themeName];
  // One seed per diagram, so a regenerated file is byte-identical.
  const rand = rng(scene.seed);
  const body = [
    ...scene.edges.map((e) => drawEdge(e, scene.nodes, theme, rand)),
    ...Object.values(scene.nodes).map((nd) => drawNode(nd, theme, rand)),
  ].join("\n");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${scene.w} ${scene.h}" width="${scene.w}" height="${scene.h}" role="img" aria-label="${esc(scene.alt)}">
  <title>${esc(scene.alt)}</title>
${body}
</svg>
`;
}

// ───────────────────────────── diagram 1 ─────────────────────────────

const streaming = {
  seed: 20261106,
  w: 1180,
  h: 330,
  alt: "Streaming path: Coinbase and news feeds into ingest services, into Kafka, through Flink SQL event-time windows, out to ClickHouse and Iceberg.",
  nodes: {
    cb: { x: 20, y: 40, w: 160, h: 58, kind: "src", label: ["Coinbase WS", "public · keyless · 24/7"] },
    rss: { x: 20, y: 150, w: 160, h: 58, kind: "src", label: ["Crypto news RSS", "3 feeds"] },

    ic: { x: 235, y: 40, w: 160, h: 58, kind: "svc", label: ["ingest-crypto", "validate · normalise"] },
    inn: { x: 235, y: 150, w: 160, h: 58, kind: "svc", label: ["ingest-news", "tag · score sentiment"] },

    raw: { x: 450, y: 88, w: 150, h: 64, kind: "bus", shape: "bus", label: ["Kafka 4.3 · KRaft", "ticks.raw", "news.raw"] },
    dlq: { x: 450, y: 236, w: 150, h: 50, kind: "bus", shape: "bus", label: ["ticks.dlq", "unparseable"] },

    fl: { x: 655, y: 80, w: 170, h: 80, kind: "eng", label: ["Flink 2.1 · SQL", "event-time windows", "watermarks"] },

    der: { x: 880, y: 170, w: 160, h: 74, kind: "bus", shape: "bus", label: ["Kafka · derived", "bars · signals", "sentiment · late"] },
    ice: { x: 880, y: 40, w: 150, h: 70, kind: "store", shape: "cylinder", label: ["Iceberg on S3", "history · Parquet"] },

    ch: { x: 1055, y: 100, w: 110, h: 80, kind: "store", shape: "cylinder", label: ["ClickHouse", "hot"] },
  },
  edges: [
    { from: "cb", to: "ic" },
    { from: "rss", to: "inn" },
    { from: "ic", to: "raw" },
    { from: "inn", to: "raw" },
    { from: "ic", to: "dlq", fromSide: "bottom", toSide: "left", dashed: true },
    { from: "raw", to: "fl" },
    { from: "fl", to: "ice" },
    { from: "fl", to: "der", fromSide: "bottom", toSide: "left" },
    { from: "der", to: "ch" },
    { from: "ice", to: "ch" },
  ],
};

// ───────────────────────────── diagram 2 ─────────────────────────────

const serving = {
  seed: 20261107,
  w: 1180,
  h: 320,
  alt: "Serving and orchestration: batch loaders and ClickHouse into dbt marts, into FastAPI and the dashboard, with Airflow scheduling batch work and Prometheus, Grafana and Jaeger observing.",
  nodes: {
    sec: { x: 20, y: 30, w: 125, h: 44, kind: "src", label: ["SEC EDGAR"] },
    fred: { x: 20, y: 96, w: 125, h: 44, kind: "src", label: ["FRED"] },
    af: { x: 20, y: 200, w: 125, h: 58, kind: "eng", label: ["Airflow 3", "batch only"] },

    batch: { x: 210, y: 58, w: 150, h: 54, kind: "svc", label: ["batch loaders"] },
    ice: { x: 210, y: 200, w: 140, h: 62, kind: "store", shape: "cylinder", label: ["Iceberg"] },

    ch: { x: 420, y: 52, w: 130, h: 70, kind: "store", shape: "cylinder", label: ["ClickHouse"] },

    dbt: { x: 615, y: 46, w: 165, h: 78, kind: "bus", label: ["dbt", "staging → marts", "33 tests"] },

    api: { x: 840, y: 52, w: 155, h: 66, kind: "svc", label: ["FastAPI", "REST + WebSocket"] },

    ui: { x: 1035, y: 20, w: 130, h: 50, kind: "obs", label: ["Live dashboard"] },
    obs: { x: 1000, y: 180, w: 165, h: 74, kind: "obs", label: ["Prometheus · Grafana", "Jaeger / OTel", "5 SLO rules"] },
  },
  edges: [
    { from: "sec", to: "batch" },
    { from: "fred", to: "batch" },
    { from: "batch", to: "ch" },
    { from: "ch", to: "dbt" },
    { from: "dbt", to: "api" },
    { from: "api", to: "ui" },
    { from: "api", to: "obs", fromSide: "bottom", toSide: "left", dashed: true, label: "metrics" },
    { from: "af", to: "batch", fromSide: "top", toSide: "left", dashed: true, label: "schedules" },
    { from: "af", to: "ice", dashed: true, label: "expiry" },
    { from: "af", to: "dbt", fromSide: "bottom", toSide: "bottom", dashed: true, label: "schedules" },
  ],
};

mkdirSync(OUT, { recursive: true });
for (const [name, scene] of Object.entries({ streaming, serving })) {
  for (const theme of Object.keys(THEMES)) {
    const file = `${OUT}/${name}-${theme}.svg`;
    writeFileSync(file, render(scene, theme));
    console.log("wrote", file.replace(`${OUT}/`, "docs/diagrams/"));
  }
}

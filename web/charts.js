// Minimal dependency-free SVG charts with hover tooltips.
// Usage: <figure class="chart" data-chart="line|bar" data-src="id-of-json-script">
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const niceTicks = (lo, hi, n) => {
    const span = hi - lo || 1;
    const step0 = span / n;
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  };
  const fmt = (v, d) => (d === undefined ? (Math.abs(v) >= 100 ? v.toFixed(0) : +v.toPrecision(3)) : v.toFixed(d)).toString();

  function legend(fig, series, swatch) {
    if (series.length < 2) return;
    const lg = document.createElement("div");
    lg.className = "legend";
    series.forEach((s, i) => {
      const item = document.createElement("span");
      item.innerHTML = `<span class="key${swatch ? " sw" : ""}" style="background:var(--series-${(s.slot || i) + 1})"></span>${s.name}`;
      lg.appendChild(item);
    });
    fig.insertBefore(lg, fig.querySelector("svg"));
  }

  function tooltip(fig) {
    let t = fig.querySelector(".tooltip");
    if (!t) { t = document.createElement("div"); t.className = "tooltip"; fig.appendChild(t); }
    return t;
  }

  function line(fig, spec) {
    const W = 760, H = spec.height || 320, m = { l: 52, r: 70, t: 12, b: 40 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.aria || "" }, fig);
    legend(fig, spec.series);
    const xs = spec.series.flatMap((s) => s.points.map((p) => p[0]));
    const ys = spec.series.flatMap((s) => s.points.map((p) => p[1])).concat(spec.refs ? spec.refs.map((r) => r.y) : []);
    const x0 = spec.xmin ?? Math.min(...xs), x1 = spec.xmax ?? Math.max(...xs);
    const y0 = spec.ymin ?? Math.min(0, ...ys), y1 = spec.ymax ?? Math.max(...ys) * 1.05;
    const X = (v) => m.l + ((v - x0) / (x1 - x0)) * (W - m.l - m.r);
    const Y = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b);
    niceTicks(y0, y1, 5).forEach((v) => {
      el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: "gridline" }, svg);
      el("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end", class: "axis-text" }, svg).textContent = fmt(v);
    });
    niceTicks(x0, x1, 8).forEach((v) => {
      el("text", { x: X(v), y: H - m.b + 18, "text-anchor": "middle", class: "axis-text" }, svg).textContent = fmt(v);
    });
    if (spec.xlabel) el("text", { x: (m.l + W - m.r) / 2, y: H - 4, "text-anchor": "middle", class: "axis-text" }, svg).textContent = spec.xlabel;
    if (spec.ylabel) el("text", { x: 12, y: (m.t + H - m.b) / 2, transform: `rotate(-90 12 ${(m.t + H - m.b) / 2})`, "text-anchor": "middle", class: "axis-text" }, svg).textContent = spec.ylabel;
    (spec.refs || []).forEach((r) => {
      el("line", { x1: m.l, x2: W - m.r, y1: Y(r.y), y2: Y(r.y), class: "ref-line" }, svg);
      el("text", { x: W - m.r - 4, y: Y(r.y) - 5, "text-anchor": "end", class: "ref-text" }, svg).textContent = r.label;
    });
    (spec.vrefs || []).forEach((r) => {
      el("line", { x1: X(r.x), x2: X(r.x), y1: m.t, y2: H - m.b, class: "ref-line" }, svg);
      el("text", { x: X(r.x) + 4, y: m.t + 10, class: "ref-text" }, svg).textContent = r.label;
    });
    spec.series.forEach((s, i) => {
      const color = `var(--series-${(s.slot ?? i) + 1})`;
      if (s.area) {
        const d = s.points.map((p, j) => `${j ? "L" : "M"}${X(p[0])},${Y(p[1])}`).join("") + `L${X(s.points.at(-1)[0])},${Y(y0)}L${X(s.points[0][0])},${Y(y0)}Z`;
        el("path", { d, fill: color, "fill-opacity": 0.1, stroke: "none" }, svg);
      }
      const d = s.points.map((p, j) => `${j ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
      el("path", { d, fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
      const last = s.points.at(-1);
      el("circle", { cx: X(last[0]), cy: Y(last[1]), r: 4, fill: color, stroke: css("--surface"), "stroke-width": 2 }, svg);
      if (spec.endLabels !== false)
        el("text", { x: X(last[0]) + 8, y: Y(last[1]) + 4, class: "label-text" }, svg).textContent = s.endLabel ?? s.name;
    });
    // crosshair
    const tip = tooltip(fig);
    const cross = el("line", { y1: m.t, y2: H - m.b, stroke: css("--text-muted"), "stroke-width": 1, visibility: "hidden" }, svg);
    const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", (ev) => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      const p = pt.matrixTransform(svg.getScreenCTM().inverse());
      const xv = x0 + ((p.x - m.l) / (W - m.l - m.r)) * (x1 - x0);
      cross.setAttribute("x1", p.x); cross.setAttribute("x2", p.x); cross.setAttribute("visibility", "visible");
      const rows = spec.series.map((s, i) => {
        let best = s.points[0];
        for (const q of s.points) if (Math.abs(q[0] - xv) < Math.abs(best[0] - xv)) best = q;
        if (Math.abs(best[0] - xv) > (x1 - x0) * 0.05) return "";
        return `<div><span class="k" style="background:var(--series-${(s.slot ?? i) + 1})"></span>${s.name}: <b>${fmt(best[1], spec.ydp)}</b> ${spec.yunit || ""}</div>`;
      }).join("");
      tip.innerHTML = `<div>${spec.xlabel || "x"}: ${fmt(xv, spec.xdp)}</div>${rows}`;
      const r = fig.getBoundingClientRect();
      tip.style.display = "block";
      tip.style.left = Math.min(ev.clientX - r.left + 14, r.width - tip.offsetWidth - 8) + "px";
      tip.style.top = ev.clientY - r.top + 14 + "px";
    });
    hit.addEventListener("mouseleave", () => { tip.style.display = "none"; cross.setAttribute("visibility", "hidden"); });
  }

  // Horizontal grouped bars: spec.categories = [..], spec.series = [{name, values:[..]}]
  // Stacked horizontal bars: one bar per category, 2px surface gap between segments.
  function stacked(fig, spec) {
    const cats = spec.categories, band = 34, th = 18, m = { l: spec.left || 170, r: 70, t: 6, b: 30 };
    const W = 760, H = m.t + m.b + cats.length * band;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.aria || "" }, fig);
    legend(fig, spec.series, true);
    const totals = cats.map((_, ci) => spec.series.reduce((a, s) => a + s.values[ci], 0));
    const vmax = spec.xmax ?? Math.max(...totals, ...(spec.vrefs || []).map((r) => r.x)) * 1.12;
    const X = (v) => m.l + (v / vmax) * (W - m.l - m.r);
    niceTicks(0, vmax, 6).forEach((v) => {
      el("line", { x1: X(v), x2: X(v), y1: m.t, y2: H - m.b, class: "gridline" }, svg);
      el("text", { x: X(v), y: H - m.b + 16, "text-anchor": "middle", class: "axis-text" }, svg).textContent = fmt(v);
    });
    if (spec.xlabel) el("text", { x: (m.l + W - m.r) / 2, y: H - 2, "text-anchor": "middle", class: "axis-text" }, svg).textContent = spec.xlabel;
    const tip = tooltip(fig), surf = css("--surface");
    cats.forEach((c, ci) => {
      const y = m.t + ci * band + (band - th) / 2;
      el("text", { x: m.l - 8, y: y + th / 2 + 4, "text-anchor": "end", class: "label-text" }, svg).textContent = c;
      let acc = 0;
      const segs = spec.series.map((s, si) => ({ s, si, v: s.values[ci] })).filter((g) => g.v > 0);
      segs.forEach((g, k) => {
        const x0 = X(acc), x1 = X(acc + g.v), last = k === segs.length - 1;
        const w = Math.max(0, x1 - x0 - (last ? 0 : 2)), r = last ? Math.min(4, w / 2) : 0;
        const d = `M${x0},${y}H${x0 + w - r}Q${x0 + w},${y} ${x0 + w},${y + r}V${y + th - r}Q${x0 + w},${y + th} ${x0 + w - r},${y + th}H${x0}Z`;
        const color = `var(--series-${(g.s.slot ?? g.si) + 1})`;
        const p = el("path", { d, fill: color }, svg);
        const hitR = el("rect", { x: x0, y: y - 3, width: Math.max(w, 6), height: th + 6, fill: "transparent" }, svg);
        hitR.addEventListener("mousemove", (ev) => {
          tip.innerHTML = `<div>${c}</div><div><span class="k" style="background:${color}"></span>${g.s.name}: <b>${fmt(g.v, spec.dp)}</b> ${spec.unit || ""}</div><div>Total: ${fmt(totals[ci], spec.dp)} ${spec.unit || ""}</div>`;
          const rr = fig.getBoundingClientRect();
          tip.style.display = "block";
          tip.style.left = Math.min(ev.clientX - rr.left + 14, rr.width - tip.offsetWidth - 8) + "px";
          tip.style.top = ev.clientY - rr.top + 14 + "px";
        });
        hitR.addEventListener("mouseleave", () => (tip.style.display = "none"));
        acc += g.v;
      });
      el("text", { x: X(acc) + 6, y: y + th / 2 + 4, class: "label-text" }, svg).textContent = fmt(totals[ci], spec.dp) + (spec.unit ? " " + spec.unit : "");
    });
    (spec.vrefs || []).forEach((r) => {
      el("line", { x1: X(r.x), x2: X(r.x), y1: m.t, y2: H - m.b, class: "ref-line" }, svg);
      el("text", { x: X(r.x) + 4, y: H - m.b - 4, class: "ref-text" }, svg).textContent = r.label;
    });
  }

  function bar(fig, spec) {
    if (spec.stacked) return stacked(fig, spec);
    const cats = spec.categories, ns = spec.series.length;
    const band = Math.max(30, ns * 18 + 14), m = { l: spec.left || 170, r: 70, t: 6, b: 30 };
    const W = 760, H = m.t + m.b + cats.length * band;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.aria || "" }, fig);
    legend(fig, spec.series, true);
    const vmax = spec.xmax ?? Math.max(...spec.series.flatMap((s) => s.values)) * 1.08;
    const X = (v) => m.l + (v / vmax) * (W - m.l - m.r);
    niceTicks(0, vmax, 6).forEach((v) => {
      el("line", { x1: X(v), x2: X(v), y1: m.t, y2: H - m.b, class: "gridline" }, svg);
      el("text", { x: X(v), y: H - m.b + 16, "text-anchor": "middle", class: "axis-text" }, svg).textContent = fmt(v);
    });
    if (spec.xlabel) el("text", { x: (m.l + W - m.r) / 2, y: H - 2, "text-anchor": "middle", class: "axis-text" }, svg).textContent = spec.xlabel;
    const tip = tooltip(fig);
    const th = Math.min(16, (band - 12) / ns);
    cats.forEach((c, ci) => {
      const yb = m.t + ci * band + (band - ns * (th + 2)) / 2;
      el("text", { x: m.l - 8, y: m.t + ci * band + band / 2 + 4, "text-anchor": "end", class: "label-text" }, svg).textContent = c;
      spec.series.forEach((s, si) => {
        const v = s.values[ci], y = yb + si * (th + 2), w = Math.max(0, X(v) - X(0));
        const r = Math.min(4, w / 2, th / 2);
        const d = `M${X(0)},${y}H${X(0) + w - r}Q${X(0) + w},${y} ${X(0) + w},${y + r}V${y + th - r}Q${X(0) + w},${y + th} ${X(0) + w - r},${y + th}H${X(0)}Z`;
        const color = `var(--series-${(s.slot ?? si) + 1})`;
        el("path", { d, fill: color }, svg);
        if (ns === 1 || spec.labelAll) el("text", { x: X(0) + w + 6, y: y + th / 2 + 4, class: "label-text" }, svg).textContent = fmt(v, spec.dp) + (spec.unit ? " " + spec.unit : "");
        const hitR = el("rect", { x: m.l, y: y - 1, width: W - m.l - m.r, height: th + 2, fill: "transparent" }, svg);
        hitR.addEventListener("mousemove", (ev) => {
          tip.innerHTML = `<div>${c}</div><div><span class="k" style="background:${color}"></span>${s.name}: <b>${fmt(v, spec.dp)}</b> ${spec.unit || ""}</div>`;
          const rr = fig.getBoundingClientRect();
          tip.style.display = "block";
          tip.style.left = Math.min(ev.clientX - rr.left + 14, rr.width - tip.offsetWidth - 8) + "px";
          tip.style.top = ev.clientY - rr.top + 14 + "px";
        });
        hitR.addEventListener("mouseleave", () => (tip.style.display = "none"));
      });
    });
  }

  function render() {
    document.querySelectorAll("figure.chart[data-src]").forEach((fig) => {
      fig.querySelectorAll("svg, .legend").forEach((n) => n.remove());
      const spec = JSON.parse(document.getElementById(fig.dataset.src).textContent);
      ({ line, bar })[fig.dataset.chart](fig, spec);
    });
  }
  document.addEventListener("DOMContentLoaded", render);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
})();

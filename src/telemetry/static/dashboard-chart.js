/*!
 * dashboard-chart.js — Phase 2 per-turn cost chart init for the Layer B
 * telemetry dashboard (SPEC-20260607-183136 Phase 2, step 4).
 *
 * Same-origin first-party script loaded under the dashboard's existing
 * `script-src 'self'` CSP — NO `'unsafe-inline'` relaxation, NO CDN. The
 * file is integrity-pinned (SHA-384) in src/telemetry/static/README.md
 * mirroring the htmx/Chart.js vendoring discipline (session 11 + 10g
 * patterns).
 *
 * What it does:
 *   1. Looks up the canvas + JSON data block by their renderer-pinned ids
 *      (see _PER_TURN_COST_CANVAS_ID / _PER_TURN_COST_DATA_ELEMENT_ID in
 *      src/telemetry/dashboard.py — three sources of truth for these
 *      strings: Python constants, this file, regression tests).
 *   2. Parses the data block's textContent as JSON (the renderer escapes
 *      `</` -> `<\/` + `allow_nan=False`, so JSON.parse never sees a
 *      `</script>` close-tag and never sees a NaN/Inf token).
 *   3. Renders a Chart.js line chart — TWO datasets keyed by `uncosted`
 *      so priced and uncosted turns are visually distinct (priced = solid
 *      accent line + circle markers; uncosted = dashed border + cross
 *      markers, plotted at their actual cost of 0.0 on a y-axis-zero
 *      baseline). The "uncosted != $0" honesty discipline (ADR-0020) is
 *      preserved: uncosted points are NOT hidden, they are MARKED.
 *   4. On first successful draw, reveals the chart by removing the
 *      `hidden` attribute on the `.chart-rendering-target` wrapper,
 *      flipping the parent tile from `tile--loading` to `tile--data`
 *      (also flipping `data-state`), and hiding the loading copy.
 *
 * htmx integration:
 *   The live fragment is `outerHTML`-swapped every ~3 s by htmx (see
 *   render_live_shell_html in src/telemetry/dashboard.py). Each swap
 *   destroys the previous canvas, so we re-initialise on every
 *   `htmx:afterSwap` event whose target is `#live-section` (or, as a
 *   fallback, whenever the canvas DOM node identity changes).
 *
 * Guarantees:
 *   - No global pollution (IIFE).
 *   - Bails silently if the canvas, data block, or Chart.js global is
 *     missing (the renderer renders the absence tile when there are no
 *     priced turns; this script must not break the page when that happens).
 *   - Treats unknown JSON fields as opaque per the _ChartPoint
 *     schema-evolution rule (see src/telemetry/dashboard.py).
 *   - Honours `prefers-reduced-motion` by disabling Chart.js animations.
 */
(function () {
  "use strict";

  var CANVAS_ID = "per-turn-cost-chart";
  var DATA_ID = "per-turn-cost-data";
  var RENDER_TARGET_SELECTOR = ".chart-rendering-target";
  var LIVE_SECTION_ID = "live-section";

  // Palette mirrors src/telemetry/dashboard.py's _CSS variables — kept in
  // sync by code review, not by automated regen.
  var COLOR_ACCENT = "#58a6ff";
  var COLOR_MUTED = "#8b949e";
  var COLOR_INK = "#e6edf3";
  var COLOR_LINE = "#30363d";

  var chartInstance = null;
  var lastCanvas = null;
  // ux F1 fold (REV-20260608-042729): when the IIFE silently bails (Chart
  // global unavailable, JSON.parse failure, empty payload) the tile would
  // otherwise stay in tile--loading with the "initializing" pulse forever.
  // After FALLBACK_MS without a successful draw we swap the loading-copy
  // text to a recovery message that points the user at the live-stream
  // panel above (the chart is a derived view of the stream — the stream
  // is the source of truth, so the recovery action is "look up").
  var FALLBACK_MS = 10000;
  var fallbackTimerId = null;
  var fallbackDelivered = false;

  function parsePayload(dataBlock) {
    try {
      var raw = dataBlock.textContent || "[]";
      var arr = JSON.parse(raw);
      if (!Array.isArray(arr)) {
        return null;
      }
      return arr;
    } catch (err) {
      return null;
    }
  }

  function formatTimeLabel(isoString) {
    if (typeof isoString !== "string" || isoString.length < 19) {
      return String(isoString || "");
    }
    // ISO 8601 timestamp: "2026-06-08T17:42:13.123456+00:00" -> "17:42:13".
    // Plain substring keeps the chart self-contained (no Date parsing, no
    // adapter dependency, no timezone surprise) and matches the visual
    // density we want on a small live tile.
    return isoString.slice(11, 19);
  }

  function buildDatasets(points) {
    var priced = [];
    var uncosted = [];
    for (var i = 0; i < points.length; i++) {
      var p = points[i] || {};
      var cost = typeof p.cost === "number" ? p.cost : null;
      if (p.uncosted === true) {
        priced.push(null);
        uncosted.push(cost);
      } else {
        priced.push(cost);
        uncosted.push(null);
      }
    }
    return {
      priced: priced,
      uncosted: uncosted,
    };
  }

  function reduceMotionEnabled() {
    try {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (err) {
      return false;
    }
  }

  function revealChart(canvas) {
    var wrapper = canvas.closest(RENDER_TARGET_SELECTOR);
    if (wrapper) {
      wrapper.removeAttribute("hidden");
    }
    var tile = canvas.closest(".tile");
    if (tile) {
      tile.classList.remove("tile--loading");
      tile.classList.add("tile--data");
      tile.setAttribute("data-state", "data");
      var loading = tile.querySelector(".loading-copy");
      if (loading) {
        loading.hidden = true;
      }
    }
    // Successful draw — cancel any pending fallback.
    if (fallbackTimerId !== null) {
      clearTimeout(fallbackTimerId);
      fallbackTimerId = null;
    }
  }

  function deliverFallback() {
    if (fallbackDelivered) {
      return;
    }
    // Only swap copy if the chart is still in the loading state — a chart
    // that drew successfully and then was destroyed by a subsequent swap
    // should not have its loading copy rewritten (revealChart already
    // hid it). querySelectorAll lets us address the tile by its known
    // class without having to hold a reference to it.
    var loadingTiles = document.querySelectorAll(".tile--loading");
    for (var i = 0; i < loadingTiles.length; i++) {
      var lc = loadingTiles[i].querySelector(".loading-copy");
      if (!lc) {
        continue;
      }
      lc.textContent =
        "Chart rendering unavailable. Turn data is listed in the Live stream " +
        "panel above.";
    }
    fallbackDelivered = true;
  }

  function armFallback() {
    if (fallbackDelivered || fallbackTimerId !== null) {
      return;
    }
    fallbackTimerId = setTimeout(deliverFallback, FALLBACK_MS);
  }

  function renderChart() {
    if (typeof window.Chart === "undefined") {
      return;
    }
    var canvas = document.getElementById(CANVAS_ID);
    var dataBlock = document.getElementById(DATA_ID);
    if (!canvas || !dataBlock) {
      return;
    }

    // htmx's outerHTML swap destroys the previous canvas; same DOM node
    // means nothing changed and re-instantiating would noisily error.
    if (canvas === lastCanvas && chartInstance) {
      return;
    }

    var points = parsePayload(dataBlock);
    if (!points || points.length === 0) {
      // Defensive: the Python renderer never emits an empty data block
      // (it renders the honest-absence tile instead), but if a future
      // regression slips one through we leave the loading state visible
      // rather than draw a fabricated axes-only chart.
      return;
    }

    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
      // arch F2 fold (REV-20260608-042729): clear lastCanvas in lockstep
      // with chartInstance so the two module-level vars never disagree.
      // If a future change ever destroys without immediately re-creating,
      // a stale lastCanvas would block the next render via the equality
      // guard above. Releasing it here closes that door.
      lastCanvas = null;
    }
    lastCanvas = canvas;

    var labels = points.map(function (p) {
      return formatTimeLabel((p && p.t) || "");
    });
    var datasets = buildDatasets(points);

    var animations = reduceMotionEnabled() ? false : { duration: 200 };

    chartInstance = new window.Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Priced turn (API-equivalent USD)",
            data: datasets.priced,
            borderColor: COLOR_ACCENT,
            backgroundColor: "rgba(88, 166, 255, 0.18)",
            pointBackgroundColor: COLOR_ACCENT,
            pointBorderColor: COLOR_ACCENT,
            pointStyle: "circle",
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.2,
            spanGaps: true,
          },
          {
            // qa F7 fold (REV-20260608-042729): borderDash removed — it is
            // dead config when showLine: false (no line drawn = nothing to
            // dash). Uncosted turns render as cross markers only, at their
            // actual cost of 0.0 on the y-axis baseline. The visual
            // distinction (priced line vs uncosted markers) is the SHAPE
            // channel of WCAG 1.4.1's multi-channel signal.
            label: "Uncosted turn (model tier unpriced; not zero-rated)",
            data: datasets.uncosted,
            borderColor: COLOR_MUTED,
            backgroundColor: "rgba(139, 148, 158, 0.15)",
            pointBackgroundColor: COLOR_MUTED,
            pointBorderColor: COLOR_MUTED,
            pointStyle: "crossRot",
            pointRadius: 6,
            pointHoverRadius: 8,
            showLine: false,
            spanGaps: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: animations,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: COLOR_INK, boxWidth: 14 },
          },
          tooltip: {
            callbacks: {
              // ux F2 fold (REV-20260608-042729): tooltip prefix shortened
              // (the full 55-char "Uncosted turn (...)" dataset label wraps
              // on narrow tiles and is redundant in the hover context — the
              // legend below carries the full framing). Returning ``null``
              // for absent values suppresses the tooltip item entirely in
              // Chart.js 4.x (the prior ``""`` rendered a visible blank
              // line).
              label: function (ctx) {
                var v = ctx.parsed && ctx.parsed.y;
                if (v === null || v === undefined) {
                  return null;
                }
                if (ctx.datasetIndex === 1) {
                  return "Uncosted (no list price for this tier)";
                }
                return "Cost: $" + Number(v).toFixed(4);
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: COLOR_MUTED, maxRotation: 0, autoSkip: true },
            grid: { color: COLOR_LINE },
          },
          y: {
            beginAtZero: true,
            ticks: {
              color: COLOR_MUTED,
              callback: function (value) {
                return "$" + Number(value).toFixed(4);
              },
            },
            grid: { color: COLOR_LINE },
          },
        },
      },
    });

    revealChart(canvas);
  }

  function handleHtmxAfterSwap(evt) {
    // The live fragment swaps `outerHTML` on `#live-section`. Other swaps
    // on the page do not touch the chart, so this filter keeps us idle
    // unless our subtree just changed.
    //
    // security F2 fold (REV-20260608-042729): the previous filter form
    // was ``if (target && target.id && target.id !== LIVE_SECTION_ID)``,
    // which let events whose target.id is the empty string (an element
    // with no ``id`` attribute) fall through and trigger a spurious
    // renderChart. The tightened form ``if (target && target.id !==
    // LIVE_SECTION_ID)`` makes a target with no id correctly skip the
    // handler. Targets with no target object (initial-load events) still
    // proceed to renderChart.
    var target = evt && evt.detail && evt.detail.target;
    if (target && target.id !== LIVE_SECTION_ID) {
      return;
    }
    renderChart();
  }

  document.addEventListener("htmx:afterSwap", handleHtmxAfterSwap);
  // Also handle the htmx `:load` event variant on first paint (some htmx
  // versions fire `htmx:load` after the initial trigger swap instead of
  // `afterSwap`); the renderChart guard makes repeat calls idempotent.
  document.addEventListener("htmx:load", handleHtmxAfterSwap);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      renderChart();
      armFallback();
    });
  } else {
    renderChart();
    armFallback();
  }
})();

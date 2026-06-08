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
 *      src/telemetry/dashboard.py — each of these strings lives in three
 *      locations: the Python constants (source of truth), this file
 *      (copy), and the regression tests (anchor). The Python constants
 *      are authoritative; the others are kept in lockstep by code review).
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
  var WEEKLY_CANVAS_ID = "weekly-trends-chart";
  var WEEKLY_DATA_ID = "weekly-trends-data";
  var RENDER_TARGET_SELECTOR = ".chart-rendering-target";
  var LIVE_SECTION_ID = "live-section";

  // Palette mirrors src/telemetry/dashboard.py's _CSS variables — kept in
  // sync by code review, not by automated regen.
  var COLOR_ACCENT = "#58a6ff";
  var COLOR_MUTED = "#8b949e";
  var COLOR_INK = "#e6edf3";
  var COLOR_LINE = "#30363d";

  // Per-tier palette for the weekly stacked bar chart. The 'unknown' tier
  // (uncosted slice) reuses COLOR_MUTED so its visual treatment matches the
  // per-turn chart's uncosted markers — one project-wide convention for
  // "this is uncosted". Other tier colors come from the same palette family
  // as COLOR_ACCENT but offset in hue so adjacent stack slices stay
  // distinguishable on a dim display.
  var WEEKLY_TIER_COLORS = {
    opus: "#58a6ff",
    sonnet: "#3fb950",
    haiku: "#a371f7",
    unknown: "#8b949e",
  };
  // Fallback for any tier not in WEEKLY_TIER_COLORS (forward-compat: a future
  // tier added to config/model_pricing.yaml will render in a neutral color
  // rather than disappearing).
  var WEEKLY_TIER_FALLBACK_COLOR = "#6e7681";

  // Per-turn chart singletons.
  var chartInstance = null;
  var lastCanvas = null;
  // Weekly chart singletons — parallel pair (arch L2 from REV-20260608-053032:
  // parallel at N=2, NOT a per-canvas-id map; the map IS the deferred
  // generalization for a future third chart).
  var weeklyChartInstance = null;
  var lastWeeklyCanvas = null;
  // ux F1 fold (REV-20260608-042729 + REV-20260608-053507): when the IIFE
  // silently bails (Chart global unavailable, JSON.parse failure, empty
  // payload) the tile would otherwise stay in tile--loading with the
  // "initializing" pulse forever. After FALLBACK_MS without a successful
  // draw we swap the loading-copy text to a per-chart recovery message.
  //
  // Per-chart state (REV-20260608-053507 ux F1 fold): a single shared timer
  // was a bug — if the per-turn chart drew successfully, revealChart()
  // cleared the shared timer and the weekly chart could strand in the
  // loading state permanently. Each chart now owns its own timer + delivered
  // flag + canvas-id + tile-targeted recovery copy, so a successful draw on
  // one chart does NOT cancel the other chart's fallback.
  var FALLBACK_MS = 10000;
  var perTurnFallback = {
    timerId: null,
    delivered: false,
    canvasId: CANVAS_ID,
    copy:
      "Chart rendering unavailable. Turn data is listed in the Live stream " +
      "panel above.",
  };
  var weeklyFallback = {
    timerId: null,
    delivered: false,
    canvasId: WEEKLY_CANVAS_ID,
    copy:
      "Chart rendering unavailable. Weekly aggregates are also shown in the " +
      "retrospective cost view.",
  };

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
    // qa F6 (REV-20260608-044128) defensive guard: the Python renderer's
    // _ChartPoint contract pins `t` as a full ISO 8601 timestamp
    // (`"YYYY-MM-DDTHH:MM:SS..."`, always >= 19 chars), so the < 19 branch
    // is unreachable today. The guard exists for future schema evolution —
    // if a later slice ever shortens the time field (e.g. to `"HH:MM:SS"`
    // for a denser view), the substring slice below would silently truncate
    // mid-character or return an empty string. Falling back to a String()
    // round-trip preserves a usable axis label until the contract change
    // is reflected here.
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

  function revealChart(canvas, fallback) {
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
    // Successful draw — cancel ONLY this chart's pending fallback. A shared
    // timer here was the source of the REV-20260608-053507 ux F1 stranding
    // bug: clearing the per-turn timer also disarmed the weekly fallback.
    if (fallback && fallback.timerId !== null) {
      clearTimeout(fallback.timerId);
      fallback.timerId = null;
    }
  }

  function deliverFallback(fallback) {
    if (fallback.delivered) {
      return;
    }
    // Target ONLY this chart's tile by its known canvas id. The prior
    // implementation walked every `.tile--loading` element on the page,
    // which meant the per-turn copy could be stamped onto the weekly tile
    // (and vice versa) — a misdirected recovery message that pointed the
    // user at the wrong place to find their data.
    var canvas = document.getElementById(fallback.canvasId);
    if (canvas) {
      var tile = canvas.closest(".tile");
      if (tile && tile.classList.contains("tile--loading")) {
        var lc = tile.querySelector(".loading-copy");
        if (lc) {
          lc.textContent = fallback.copy;
        }
      }
    }
    fallback.delivered = true;
  }

  function armFallback(fallback) {
    if (fallback.delivered || fallback.timerId !== null) {
      return;
    }
    fallback.timerId = setTimeout(function () {
      deliverFallback(fallback);
    }, FALLBACK_MS);
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
            // ux F3 (REV-20260608-044128): `autoSkip: true` lets Chart.js
            // thin x-axis tick labels when they would overlap. The Live
            // panel is bounded to ~100 events by the LiveState rolling
            // window (see src/telemetry/live.py), so even at full
            // density the auto-skipped axis remains readable on a tile
            // narrower than ~800 px. If a future slice widens the
            // rolling window past ~250 events, revisit (denser tile
            // wants `maxTicksLimit` to bound the label count explicitly).
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

    revealChart(canvas, perTurnFallback);
  }

  function parseWeeklyPayload(dataBlock) {
    // Mirrors parsePayload's discipline: defensive parse, return null on any
    // failure so the renderer leaves the loading state visible rather than
    // drawing a fabricated chart.
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

  function buildWeeklyDatasets(points) {
    // Stacked bar by tier. Each tier becomes its own dataset; bars stack on
    // the x-axis (one bar per week). The uncosted slice is built from each
    // week's by_tier entry whose cost_usd is null — the Python aggregator
    // groups uncosted tokens under the 'unknown' tier so this discrimination
    // matches the renderer's contract. The uncosted slice's legend label
    // names the honesty discipline ("Uncosted (model tier unpriced)") so a
    // reader at the chart alone understands why that slice has no cost
    // figure in the tooltip.
    var tiers = {}; // tier -> {data: [...], uncosted: bool}
    var orderedTiers = [];
    for (var i = 0; i < points.length; i++) {
      var week = points[i] || {};
      var byTier = Array.isArray(week.by_tier) ? week.by_tier : [];
      for (var j = 0; j < byTier.length; j++) {
        var slice = byTier[j] || {};
        var tier = typeof slice.tier === "string" ? slice.tier : "unknown";
        if (!tiers.hasOwnProperty(tier)) {
          tiers[tier] = {
            data: new Array(points.length).fill(0),
            costs: new Array(points.length).fill(null),
            uncosted: slice.cost_usd === null,
          };
          orderedTiers.push(tier);
        }
        tiers[tier].data[i] =
          typeof slice.tokens === "number" ? slice.tokens : 0;
        tiers[tier].costs[i] =
          typeof slice.cost_usd === "number" ? slice.cost_usd : null;
        // If any week marks this tier as uncosted, treat the whole dataset
        // as uncosted (cost_usd === null is the renderer's honest signal).
        if (slice.cost_usd === null) {
          tiers[tier].uncosted = true;
        }
      }
    }
    return { tiers: tiers, orderedTiers: orderedTiers };
  }

  function tierColor(tier) {
    if (WEEKLY_TIER_COLORS.hasOwnProperty(tier)) {
      return WEEKLY_TIER_COLORS[tier];
    }
    return WEEKLY_TIER_FALLBACK_COLOR;
  }

  function tierLabel(tier, uncosted) {
    if (uncosted) {
      return tier + " (uncosted — model tier unpriced)";
    }
    return tier;
  }

  function formatWeekLabel(isoDate) {
    // Defensive: the renderer pins week_start as "YYYY-MM-DD" (10 chars). A
    // future schema shortening would land in the < 10 branch; fall back to a
    // String() round-trip so the axis still has usable text.
    if (typeof isoDate !== "string" || isoDate.length < 10) {
      return String(isoDate || "");
    }
    return isoDate.slice(0, 10);
  }

  function renderWeeklyChart() {
    if (typeof window.Chart === "undefined") {
      return;
    }
    var canvas = document.getElementById(WEEKLY_CANVAS_ID);
    var dataBlock = document.getElementById(WEEKLY_DATA_ID);
    if (!canvas || !dataBlock) {
      return;
    }
    if (canvas === lastWeeklyCanvas && weeklyChartInstance) {
      return;
    }
    var points = parseWeeklyPayload(dataBlock);
    if (!points || points.length === 0) {
      return;
    }
    if (weeklyChartInstance) {
      weeklyChartInstance.destroy();
      weeklyChartInstance = null;
      lastWeeklyCanvas = null;
    }
    lastWeeklyCanvas = canvas;

    var labels = points.map(function (p) {
      return formatWeekLabel((p && p.week_start) || "");
    });
    var built = buildWeeklyDatasets(points);
    var datasets = built.orderedTiers.map(function (tier) {
      var entry = built.tiers[tier];
      var color = tierColor(tier);
      return {
        label: tierLabel(tier, entry.uncosted),
        data: entry.data,
        backgroundColor: color,
        // ux F5 fold (REV-20260608-053507): 1px border in the tile bg color
        // gives adjacent stack slices a non-color separation channel. Two
        // tiers with similar luminance under colorblind simulation (e.g.
        // opus #58a6ff vs haiku #a371f7 under deuteranopia) would otherwise
        // merge visually. WCAG 1.4.1 — information must not be conveyed by
        // color alone.
        borderColor: "#0d1117",
        borderWidth: 1,
        // Carry the per-week costs on the dataset for the tooltip callback.
        // Stored under a non-Chart.js key so the library does not touch it.
        _perWeekCosts: entry.costs,
        _uncosted: entry.uncosted,
      };
    });

    var animations = reduceMotionEnabled() ? false : { duration: 200 };

    weeklyChartInstance = new window.Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: datasets,
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
              label: function (ctx) {
                var ds = ctx.dataset || {};
                var tokens = ctx.parsed && ctx.parsed.y;
                if (tokens === null || tokens === undefined) {
                  return null;
                }
                var costs = ds._perWeekCosts || [];
                var cost = costs[ctx.dataIndex];
                var tokenLabel =
                  Number(tokens).toLocaleString() + " tokens";
                if (ds._uncosted || cost === null || cost === undefined) {
                  return (
                    ds.label + ": " + tokenLabel + " (no list price)"
                  );
                }
                return (
                  ds.label +
                  ": " +
                  tokenLabel +
                  " · $" +
                  Number(cost).toFixed(4)
                );
              },
            },
          },
        },
        scales: {
          x: {
            stacked: true,
            ticks: { color: COLOR_MUTED, maxRotation: 0, autoSkip: true },
            grid: { color: COLOR_LINE },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: {
              color: COLOR_MUTED,
              callback: function (value) {
                // Token counts can grow large; compact the y-axis labels.
                var n = Number(value);
                if (n >= 1e6) {
                  return (n / 1e6).toFixed(1) + "M";
                }
                if (n >= 1e3) {
                  return (n / 1e3).toFixed(1) + "k";
                }
                return String(n);
              },
            },
            grid: { color: COLOR_LINE },
          },
        },
      },
    });

    revealChart(canvas, weeklyFallback);
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
    renderWeeklyChart();
  }

  document.addEventListener("htmx:afterSwap", handleHtmxAfterSwap);
  // Also handle the htmx `:load` event variant on first paint (some htmx
  // versions fire `htmx:load` after the initial trigger swap instead of
  // `afterSwap`); the renderChart guard makes repeat calls idempotent.
  document.addEventListener("htmx:load", handleHtmxAfterSwap);

  function armBothFallbacks() {
    armFallback(perTurnFallback);
    armFallback(weeklyFallback);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      renderChart();
      renderWeeklyChart();
      armBothFallbacks();
    });
  } else {
    renderChart();
    renderWeeklyChart();
    armBothFallbacks();
  }
})();

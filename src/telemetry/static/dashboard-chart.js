/*!
 * dashboard-chart.js — chart init for the Layer B telemetry dashboard
 * (SPEC-20260607-183136 Phase 2 step 4 per-turn chart; Phase 2 weekly
 * trends chart; SPEC-20260610-015114 Phase 4 model-cost donut).
 *
 * Same-origin first-party script loaded under the dashboard's existing
 * `script-src 'self'` CSP — NO `'unsafe-inline'` relaxation, NO CDN. The
 * file is integrity-pinned (SHA-384) in src/telemetry/static/README.md
 * mirroring the htmx/Chart.js vendoring discipline (session 11 + 10g
 * patterns).
 *
 * What it does:
 *   1. Looks up each chart's canvas + JSON data block by their
 *      renderer-pinned ids (see _PER_TURN_COST_* / _WEEKLY_TRENDS_* /
 *      _MODEL_COST_DONUT_* in src/telemetry/dashboard.py — each of these
 *      strings lives in three locations: the Python constants (source of
 *      truth), this file (copy), and the regression tests (anchor). The
 *      Python constants are authoritative; the others are kept in
 *      lockstep by code review).
 *   2. Parses the data block's textContent as JSON (the renderer escapes
 *      `</` -> `<\/` + `allow_nan=False`, so JSON.parse never sees a
 *      `</script>` close-tag and never sees a NaN/Inf token).
 *   3. Renders the charts:
 *      - Per-turn line chart: TWO datasets keyed by `uncosted` so priced
 *        and uncosted turns are visually distinct (priced = solid accent
 *        line + circle markers; uncosted = cross markers at the
 *        y-axis-zero baseline). The "uncosted != $0" honesty discipline
 *        (ADR-0020) is preserved: uncosted points are NOT hidden, they
 *        are MARKED.
 *      - Weekly stacked bar chart: token volume per ISO week by tier;
 *        the uncosted slice is its own stack slice.
 *      - Model-cost donut: doughnut of API-equivalent USD per PRICED
 *        tier only. Uncosted tiers are never drawn as $0 slices — the
 *        Python renderer names them in a caption below the chart, and
 *        they remain in the JSON payload flagged `uncosted: true`
 *        (ADR-0020: marked in copy, never fabricated in geometry).
 *   4. On first successful draw, reveals the chart by removing the
 *      `hidden` attribute on the `.chart-rendering-target` wrapper,
 *      flipping the parent tile from `tile--loading` to `tile--data`
 *      (also flipping `data-state`), and hiding the loading copy.
 *
 * htmx integration:
 *   The live fragment is `outerHTML`-swapped every ~3 s by htmx (see
 *   render_live_shell_html in src/telemetry/dashboard.py). Each swap
 *   destroys the previous canvases, so we re-initialise on every
 *   `htmx:afterSwap` event whose target is `#live-section` (or, as a
 *   fallback, whenever a canvas DOM node identity changes).
 *
 * Guarantees:
 *   - No global pollution (IIFE).
 *   - Bails silently if a canvas, data block, or the Chart.js global is
 *     missing (the renderer renders the absence tile when there is no
 *     data; this script must not break the page when that happens).
 *   - Treats unknown JSON fields as opaque per the _ChartPoint /
 *     _DonutSlice schema-evolution rules (see src/telemetry/dashboard.py).
 *   - Never writes payload-origin strings as keys into a plain object
 *     (SPEC-20260610-015114 sec F2): the donut builds parallel ARRAYS,
 *     and the weekly accumulator guards every keyed write with
 *     hasOwnProperty — a tier named "__proto__" cannot touch the
 *     prototype chain.
 *   - Honours `prefers-reduced-motion` by disabling Chart.js animations.
 */
(function () {
  "use strict";

  var CANVAS_ID = "per-turn-cost-chart";
  var DATA_ID = "per-turn-cost-data";
  var WEEKLY_CANVAS_ID = "weekly-trends-chart";
  var WEEKLY_DATA_ID = "weekly-trends-data";
  var DONUT_CANVAS_ID = "model-cost-donut-chart";
  var DONUT_DATA_ID = "model-cost-donut-data";
  var RENDER_TARGET_SELECTOR = ".chart-rendering-target";
  var LIVE_SECTION_ID = "live-section";

  // Palette mirrors src/telemetry/dashboard.py's _CSS variables — kept in
  // sync by code review, not by automated regen.
  var COLOR_ACCENT = "#58a6ff";
  var COLOR_MUTED = "#8b949e";
  var COLOR_INK = "#e6edf3";
  var COLOR_LINE = "#30363d";

  // Per-tier palette shared by the weekly stacked bar chart and the
  // model-cost donut (one palette source in JS — spec AC13). The 'unknown'
  // tier (uncosted slice) reuses COLOR_MUTED so its visual treatment
  // matches the per-turn chart's uncosted markers — one project-wide
  // convention for "this is uncosted". Other tier colors come from the
  // same palette family as COLOR_ACCENT but offset in hue so adjacent
  // slices stay distinguishable on a dim display.
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

  // Per-chart state registry, keyed by canvas id.
  //
  // Rule-of-Three fold (SPEC-20260610-015114): the trigger pinned at N=2
  // in REV-20260608-053032 arch L2 ("parallel at N=2, NOT a per-canvas-id
  // map; the map IS the deferred generalization for a future third chart")
  // fired when the model-cost donut landed as the third chart. Each entry
  // owns its Chart.js instance, its last-seen canvas node, and its
  // fallback-timer state. The fallback state stays PER-CHART
  // (REV-20260608-053507 ux F1: a shared timer let one chart's successful
  // draw permanently strand another chart in tile--loading).
  //
  // After FALLBACK_MS without a successful draw (Chart global unavailable,
  // JSON.parse failure, empty payload) we swap that chart's loading-copy
  // text to its recovery message.
  var FALLBACK_MS = 10000;
  var CHART_STATES = {};

  function registerChart(canvasId, recoveryCopy) {
    CHART_STATES[canvasId] = {
      canvasId: canvasId,
      instance: null,
      lastCanvas: null,
      timerId: null,
      delivered: false,
      copy: recoveryCopy,
    };
    return CHART_STATES[canvasId];
  }

  var perTurnState = registerChart(
    CANVAS_ID,
    "Chart rendering unavailable. Turn data is listed in the Live stream " +
      "panel above."
  );
  var weeklyState = registerChart(
    WEEKLY_CANVAS_ID,
    "Chart rendering unavailable. Weekly aggregates are also shown in the " +
      "retrospective cost view."
  );
  var donutState = registerChart(
    DONUT_CANVAS_ID,
    "Chart rendering unavailable. Per-tier cost totals are also shown in " +
      "the retrospective cost panel."
  );

  // Shared JSON-array parse for every chart data block (Rule-of-Three
  // extraction: two prior copies existed — parsePayload + parseWeeklyPayload
  // — and the donut landing as the THIRD caller is what fires the trigger;
  // extracting at N=2 would have been premature). Defensive parse — return
  // null on any failure so the caller leaves the loading state visible
  // rather than drawing a fabricated chart.
  function parseJsonArray(dataBlock) {
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

  function revealChart(canvas, state) {
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
    if (state && state.timerId !== null) {
      clearTimeout(state.timerId);
      state.timerId = null;
    }
  }

  function deliverFallback(state) {
    if (state.delivered) {
      return;
    }
    // Target ONLY this chart's tile by its known canvas id. The prior
    // implementation walked every `.tile--loading` element on the page,
    // which meant the per-turn copy could be stamped onto the weekly tile
    // (and vice versa) — a misdirected recovery message that pointed the
    // user at the wrong place to find their data.
    var canvas = document.getElementById(state.canvasId);
    if (canvas) {
      var tile = canvas.closest(".tile");
      if (tile && tile.classList.contains("tile--loading")) {
        var lc = tile.querySelector(".loading-copy");
        if (lc) {
          lc.textContent = state.copy;
        }
      }
    }
    state.delivered = true;
  }

  function armFallback(state) {
    if (state.delivered || state.timerId !== null) {
      return;
    }
    state.timerId = setTimeout(function () {
      deliverFallback(state);
    }, FALLBACK_MS);
  }

  // Shared per-swap render guards. htmx's outerHTML swap destroys the
  // previous canvas; the same DOM node means nothing changed and
  // re-instantiating would noisily error.
  function shouldSkipRender(state, canvas) {
    return canvas === state.lastCanvas && state.instance !== null;
  }

  function destroyChart(state) {
    if (state.instance) {
      state.instance.destroy();
      state.instance = null;
      // arch F2 fold (REV-20260608-042729): clear lastCanvas in lockstep
      // with the instance so the two fields never disagree. If a future
      // change ever destroys without immediately re-creating, a stale
      // lastCanvas would block the next render via shouldSkipRender.
      // Releasing it here closes that door.
      state.lastCanvas = null;
    }
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
    if (shouldSkipRender(perTurnState, canvas)) {
      return;
    }

    var points = parseJsonArray(dataBlock);
    if (!points || points.length === 0) {
      // Defensive: the Python renderer never emits an empty data block
      // (it renders the honest-absence tile instead), but if a future
      // regression slips one through we leave the loading state visible
      // rather than draw a fabricated axes-only chart.
      return;
    }

    destroyChart(perTurnState);
    perTurnState.lastCanvas = canvas;

    var labels = points.map(function (p) {
      return formatTimeLabel((p && p.t) || "");
    });
    var datasets = buildDatasets(points);

    var animations = reduceMotionEnabled() ? false : { duration: 200 };

    perTurnState.instance = new window.Chart(canvas.getContext("2d"), {
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

    revealChart(canvas, perTurnState);
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
    if (shouldSkipRender(weeklyState, canvas)) {
      return;
    }
    var points = parseJsonArray(dataBlock);
    if (!points || points.length === 0) {
      return;
    }
    destroyChart(weeklyState);
    weeklyState.lastCanvas = canvas;

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

    weeklyState.instance = new window.Chart(canvas.getContext("2d"), {
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

    revealChart(canvas, weeklyState);
  }

  function buildDonutSlices(points) {
    // Parallel ARRAYS only — no plain object is ever keyed by a
    // payload-origin tier string here (SPEC-20260610-015114 sec F2:
    // prototype-pollution surface closed by construction; the only keyed
    // lookup is tierColor's hasOwnProperty-guarded read). Slices are drawn
    // for PRICED tiers only (`uncosted: false` and a numeric cost_usd) —
    // the Python renderer guarantees at least one priced entry when the
    // chart tile is emitted, and carries uncosted tiers in the caption
    // (ADR-0020: a USD donut has no honest slice size for an unpriced
    // tier, so the slice is never fabricated).
    var labels = [];
    var data = [];
    var colors = [];
    for (var i = 0; i < points.length; i++) {
      var s = points[i] || {};
      if (s.uncosted === true || typeof s.cost_usd !== "number") {
        continue;
      }
      var tier = typeof s.tier === "string" ? s.tier : "unknown";
      labels.push(tier);
      data.push(s.cost_usd);
      colors.push(tierColor(tier));
    }
    return { labels: labels, data: data, colors: colors };
  }

  function renderModelCostDonut() {
    if (typeof window.Chart === "undefined") {
      return;
    }
    var canvas = document.getElementById(DONUT_CANVAS_ID);
    var dataBlock = document.getElementById(DONUT_DATA_ID);
    if (!canvas || !dataBlock) {
      return;
    }
    if (shouldSkipRender(donutState, canvas)) {
      return;
    }
    var points = parseJsonArray(dataBlock);
    if (!points || points.length === 0) {
      return;
    }
    var built = buildDonutSlices(points);
    if (built.data.length === 0) {
      // Defensive: the Python renderer emits the chart tile only when at
      // least one priced tier exists (otherwise the "nothing priced to
      // chart" data tile renders instead) — but if a regression slips an
      // all-uncosted payload through, leave the loading state visible
      // rather than draw an empty ring.
      return;
    }
    destroyChart(donutState);
    donutState.lastCanvas = canvas;

    var animations = reduceMotionEnabled() ? false : { duration: 200 };

    donutState.instance = new window.Chart(canvas.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: built.labels,
        datasets: [
          {
            data: built.data,
            backgroundColor: built.colors,
            // Same WCAG 1.4.1 non-color separation channel as the weekly
            // stacked bars (ux F5, REV-20260608-053507): a 1px border in
            // the tile bg color keeps adjacent slices distinguishable
            // under colorblind simulation.
            borderColor: "#0d1117",
            borderWidth: 1,
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
              label: function (ctx) {
                var v = ctx.parsed;
                if (v === null || v === undefined) {
                  return null;
                }
                // Chart.js tooltips draw via canvas fillText — plain text,
                // never HTML (spec sec F3-INFO) — so the tier label needs
                // no escaping here.
                return ctx.label + ": $" + Number(v).toFixed(4);
              },
            },
          },
        },
      },
    });

    revealChart(canvas, donutState);
  }

  function handleHtmxAfterSwap(evt) {
    // The live fragment swaps `outerHTML` on `#live-section`. Other swaps
    // on the page do not touch the charts, so this filter keeps us idle
    // unless our subtree just changed.
    //
    // security F2 fold (REV-20260608-042729): the previous filter form
    // was ``if (target && target.id && target.id !== LIVE_SECTION_ID)``,
    // which let events whose target.id is the empty string (an element
    // with no ``id`` attribute) fall through and trigger a spurious
    // renderChart. The tightened form ``if (target && target.id !==
    // LIVE_SECTION_ID)`` makes a target with no id correctly skip the
    // handler. Targets with no target object (initial-load events) still
    // proceed to the render calls.
    var target = evt && evt.detail && evt.detail.target;
    if (target && target.id !== LIVE_SECTION_ID) {
      return;
    }
    renderChart();
    renderWeeklyChart();
    renderModelCostDonut();
  }

  document.addEventListener("htmx:afterSwap", handleHtmxAfterSwap);
  // Also handle the htmx `:load` event variant on first paint (some htmx
  // versions fire `htmx:load` after the initial trigger swap instead of
  // `afterSwap`); the render guards make repeat calls idempotent.
  document.addEventListener("htmx:load", handleHtmxAfterSwap);

  function armAllFallbacks() {
    var ids = Object.keys(CHART_STATES);
    for (var i = 0; i < ids.length; i++) {
      armFallback(CHART_STATES[ids[i]]);
    }
  }

  function renderAllCharts() {
    renderChart();
    renderWeeklyChart();
    renderModelCostDonut();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      renderAllCharts();
      armAllFallbacks();
    });
  } else {
    renderAllCharts();
    armAllFallbacks();
  }
})();

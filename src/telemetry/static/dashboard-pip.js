/*!
 * dashboard-pip.js — Picture-in-Picture pop-out for the Layer B telemetry
 * dashboard (SPEC-20260610-031224 Phase 4 Unit 4.4).
 *
 * Same-origin first-party script loaded under the dashboard's existing
 * `script-src 'self'` CSP — NO `'unsafe-inline'` relaxation, NO CDN. The
 * file is integrity-pinned (SHA-384) in src/telemetry/static/README.md
 * mirroring the htmx/Chart.js/dashboard-chart.js vendoring discipline.
 *
 * What it does (mirror-clone design — SPEC §Design decision):
 *   1. Feature-detects the Document Picture-in-Picture API
 *      (`documentPictureInPicture` on `window`, Chromium >= 116). When the
 *      API is absent the pop-out button stays server-rendered `hidden` —
 *      honest absence, never a broken control. When present, the button
 *      (id `pip-toggle` — pinned by `_PIP_TOGGLE_BUTTON_ID` in
 *      src/telemetry/dashboard.py, the source of truth; this literal and
 *      the regression tests are the other two lockstep locations) is
 *      revealed.
 *   2. On click, opens a compact always-on-top PiP window, copies the main
 *      document's `<style>` text into it, tags its body `pip-body` (the
 *      `_LIVE_CSS` single-column override), and seeds it with a deep clone
 *      of `#live-section`.
 *   3. While open, each `htmx:afterSwap` on `#live-section` re-clones the
 *      freshly swapped section into the PiP window. The MAIN window stays
 *      the ONLY fetcher of `/fragments/live` — the PiP window runs no
 *      htmx, no fetch loop, and no timers (single data path, R15 spirit).
 *   4. Chart canvases mirror as bitmap snapshots: after each clone, the
 *      pixels of every main-window canvas are copied into the cloned
 *      canvas via `drawImage` inside a requestAnimationFrame callback.
 *
 * LOAD-ORDER CONTRACT (SPEC R8): this script's `<script>` tag MUST come
 * AFTER dashboard-chart.js in render_live_shell_html — both register
 * `htmx:afterSwap` listeners on `document`, and listener registration
 * order guarantees the charts re-initialise BEFORE the mirror clones them
 * (see dashboard-chart.js handleHtmxAfterSwap). The order is pinned by a
 * regression test (AC2).
 *
 * Guarantees:
 *   - No global pollution (IIFE).
 *   - Bails silently when the button or `#live-section` is absent (the
 *     static/retrospective render has no live shell — Unit 5.1 contract).
 *   - The mirror listener is registered ONCE at module init and gated by
 *     a `pipWindow` null check at entry — listener accumulation across
 *     open/close cycles is impossible by construction (SPEC R5 / sec F1).
 *   - The PiP `pagehide` handler's FIRST synchronous action is nulling
 *     `pipWindow`, closing the close-during-swap race (sec F1).
 *   - The PiP document is populated EXCLUSIVELY via cloneNode/importNode +
 *     replaceChildren of nodes the main document already rendered through
 *     `_esc`. No `innerHTML`/`insertAdjacentHTML` on any string — there is
 *     no payload-derived string-to-markup path in this file (sec Q1).
 *   - `requestWindow` rejections (e.g. NotAllowedError when another PiP is
 *     open) are caught; the handler logs a STATIC sentinel only — never
 *     the rejection message — and reverts the button (sec F2).
 */
(function () {
  "use strict";

  var BUTTON_ID = "pip-toggle";
  var STATUS_ID = "pip-status";
  var LIVE_SECTION_ID = "live-section";
  var PIP_WINDOW_TITLE = "Telemetry live";
  var PIP_BODY_CLASS = "pip-body";
  var OPEN_LABEL = "Pop out live view";
  var CLOSE_LABEL = "Close pop-out";
  // Shown briefly when the browser refuses to open the window (e.g. another
  // PiP is already open). Static copy — never derived from the rejection
  // (sec F2). A silent revert would read as a broken button to a
  // non-engineer (CP2 ux fold, Nielsen #1 visibility of system status).
  var REJECTED_LABEL = "Pop-out unavailable right now";
  var REJECTED_LABEL_REVERT_MS = 4000;
  var PIP_WIDTH = 440;
  var PIP_HEIGHT = 560;

  // Feature-detect FIRST (AC7: this literal precedes every requestWindow
  // call site). Without the API there is nothing to wire up — the button
  // stays hidden and this module is inert.
  if (!("documentPictureInPicture" in window)) {
    return;
  }

  // Module-scoped handle to the open PiP window. `null` means "no PiP
  // open" and is the single gate every mirror update checks (sec F1).
  var pipWindow = null;

  function getButton() {
    return document.getElementById(BUTTON_ID);
  }

  function getLiveSection() {
    return document.getElementById(LIVE_SECTION_ID);
  }

  function setButtonState(open) {
    var btn = getButton();
    if (!btn) {
      return;
    }
    btn.textContent = open ? CLOSE_LABEL : OPEN_LABEL;
    btn.setAttribute("aria-pressed", open ? "true" : "false");
  }

  function setStatus(text) {
    // Status-only messages go through the visually-hidden role="status"
    // span (REV ux F1: aria-live on the button itself double-announces
    // every label change in NVDA/VoiceOver). Static strings only.
    var status = document.getElementById(STATUS_ID);
    if (status) {
      status.textContent = text;
    }
  }

  function copyStyles(pipDoc) {
    // The main document's stylesheets are inline <style> blocks rendered
    // by dashboard.py (_CSS + _LIVE_CSS). Document PiP inherits the
    // opener's CSP, where inline <style> is already permitted. textContent
    // assignment is a text node write, not markup parsing.
    var styles = document.querySelectorAll("style");
    for (var i = 0; i < styles.length; i++) {
      var copy = pipDoc.createElement("style");
      // textContent, not innerHTML — text node write, not markup parsing.
      copy.textContent = styles[i].textContent;
      pipDoc.head.appendChild(copy);
    }
  }

  function copyCanvasBitmaps(sourceRoot, cloneRoot) {
    // Cloned <canvas> nodes are blank by spec — copy pixels from each
    // main-window canvas into its positional twin. Zero canvases (charts
    // in loading/absent state) makes this a natural no-op. A canvas whose
    // backing store is empty or zero-sized throws on drawImage in some
    // engines — bail per-canvas, silently: the next 3 s swap retries.
    var sources = sourceRoot.querySelectorAll("canvas");
    var clones = cloneRoot.querySelectorAll("canvas");
    for (var i = 0; i < sources.length && i < clones.length; i++) {
      try {
        var ctx = clones[i].getContext("2d");
        if (ctx) {
          ctx.drawImage(sources[i], 0, 0);
        }
      } catch (drawErr) {
        // Static sentinel only — never the error message (sec F2 pattern).
        console.warn("dashboard-pip: canvas snapshot skipped");
      }
    }
  }

  function mirrorLiveSection() {
    // Entry guard (sec F1): a close-during-swap race means this can fire
    // with the window already gone — `pipWindow` is nulled synchronously
    // in the pagehide handler, so the null check is authoritative.
    if (pipWindow === null) {
      return;
    }
    var section = getLiveSection();
    if (!section) {
      return;
    }
    var pipDoc = pipWindow.document;
    var clone = pipDoc.importNode(section, true);
    pipDoc.body.replaceChildren(clone);
    // Charts re-initialise in dashboard-chart.js's listener, which runs
    // BEFORE this one (load-order contract, header comment). rAF lets the
    // first chart paint land before the snapshot; a mid-animation frame
    // is acceptable — the next swap refreshes it. The rAF MUST be the PiP
    // window's, not the main window's: the primary PiP use case is a
    // backgrounded main tab, where the MAIN window's rAF is suspended and
    // a queued callback would never run. The PiP window is always visible,
    // so its rAF always fires; drawImage reads the main canvas's backing
    // store regardless of the opener tab's visibility.
    pipWindow.requestAnimationFrame(function () {
      if (pipWindow === null) {
        return;
      }
      var liveNow = getLiveSection();
      var cloneNow = pipWindow.document.getElementById(LIVE_SECTION_ID);
      if (liveNow && cloneNow) {
        copyCanvasBitmaps(liveNow, cloneNow);
      }
    });
  }

  function handlePipPagehide() {
    // FIRST synchronous action: drop the handle (sec F1). Everything that
    // observes `pipWindow` — the mirror listener, the rAF callback, the
    // toggle — sees the closed state immediately.
    pipWindow = null;
    setButtonState(false);
  }

  function openPip() {
    window.documentPictureInPicture
      .requestWindow({ width: PIP_WIDTH, height: PIP_HEIGHT })
      .then(function (win) {
        pipWindow = win;
        copyStyles(win.document);
        // Anchor the floating window for multi-monitor ambient oversight
        // (REV ux F2, Nielsen #6) — without it the title bar is blank or
        // inherits the opener's title depending on the Chromium version.
        win.document.title = PIP_WINDOW_TITLE;
        win.document.body.className = PIP_BODY_CLASS;
        win.addEventListener("pagehide", handlePipPagehide);
        setButtonState(true);
        mirrorLiveSection();
      })
      .catch(function () {
        // Static sentinel only — never the rejection message (sec F2).
        console.warn("dashboard-pip: PiP request rejected");
        setButtonState(false);
        // Visible feedback (CP2 ux fold): a transient static label so the
        // click is not a silent no-op. The role="status" span announces it
        // once for SR users (REV ux F1); the button is disabled for the
        // window so a rapid re-click cannot re-trigger a doomed request
        // (REV ux F3). Reverts unless a PiP opened meanwhile.
        var btn = getButton();
        if (btn) {
          btn.textContent = REJECTED_LABEL;
          btn.setAttribute("disabled", "");
          setStatus(REJECTED_LABEL);
          window.setTimeout(function () {
            btn.removeAttribute("disabled");
            setStatus("");
            if (pipWindow === null) {
              setButtonState(false);
            }
          }, REJECTED_LABEL_REVERT_MS);
        }
      });
  }

  function closePip() {
    if (pipWindow !== null) {
      // close() fires the PiP window's pagehide, which nulls the handle
      // and resets the button (handlePipPagehide).
      pipWindow.close();
    }
  }

  function handleToggleClick() {
    if (pipWindow !== null) {
      closePip();
    } else {
      openPip();
    }
  }

  function handleHtmxAfterSwap(evt) {
    // Same target filter as dashboard-chart.js (security F2 fold,
    // REV-20260608-042729): a target with no id correctly skips; events
    // without a target object still proceed.
    var target = evt && evt.detail && evt.detail.target;
    if (target && target.id !== LIVE_SECTION_ID) {
      return;
    }
    mirrorLiveSection();
  }

  // Registered ONCE at module init (never per-open) and gated by the
  // `pipWindow` null check inside mirrorLiveSection — repeated open/close
  // cycles cannot accumulate listeners (SPEC R5 / sec F1 / qa F3).
  // `htmx:load` is registered alongside `htmx:afterSwap` deliberately —
  // defensive symmetry with dashboard-chart.js (some htmx versions fire
  // `htmx:load` instead of `afterSwap` for certain swap variants); the
  // mirror is idempotent and null-gated, so the duplicate event at worst
  // re-clones the same content (CP2 qa F1 — both registrations are pinned
  // by count in the regression tests).
  document.addEventListener("htmx:afterSwap", handleHtmxAfterSwap);
  document.addEventListener("htmx:load", handleHtmxAfterSwap);

  // The browser closes a Document PiP window with its opener, but close
  // explicitly on main-window teardown so no rAF/mirror callback runs
  // against a dying opener (qa edge case: main tab navigates away).
  window.addEventListener("pagehide", closePip);

  function init() {
    var btn = getButton();
    if (!btn || !getLiveSection()) {
      // No live shell (static/retrospective render) — stay inert.
      return;
    }
    btn.hidden = false;
    setButtonState(false);
    btn.addEventListener("click", handleToggleClick);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

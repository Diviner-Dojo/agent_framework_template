/* ============================================================================
   Diviner Dojo — framework docs site behaviour.
   Theme persistence, scroll progress, TOC scroll-spy, reveal-on-scroll.
   No dependencies. Safe to load with `defer`.
   ========================================================================= */
(function () {
  'use strict';

  /* ---- theme ------------------------------------------------------------ */
  // The inline boot script in each page sets data-theme before paint to avoid
  // a flash; this only wires the toggle.
  var root = document.documentElement;
  var btn = document.querySelector('.theme-btn');
  if (btn) {
    btn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('dd-theme', next); } catch (e) { /* private mode */ }
      btn.setAttribute('aria-label', next === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
    });
  }

  /* ---- scroll progress -------------------------------------------------- */
  var bar = document.querySelector('.progress');
  var ticking = false;

  function onScroll() {
    if (bar) {
      var max = document.documentElement.scrollHeight - window.innerHeight;
      var pct = max > 0 ? (window.scrollY / max) * 100 : 0;
      bar.style.width = pct.toFixed(2) + '%';
    }
    ticking = false;
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { window.requestAnimationFrame(onScroll); ticking = true; }
  }, { passive: true });
  onScroll();

  /* ---- TOC scroll-spy --------------------------------------------------- */
  var links = Array.prototype.slice.call(document.querySelectorAll('.rail a[href^="#"]'));
  if (links.length && 'IntersectionObserver' in window) {
    var byId = {};
    var targets = [];
    links.forEach(function (a) {
      var el = document.getElementById(decodeURIComponent(a.hash.slice(1)));
      if (el) { byId[el.id] = a; targets.push(el); }
    });

    var visible = new Set();
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { visible.add(e.target.id); } else { visible.delete(e.target.id); }
      });
      // highlight the first visible section in document order
      var winner = null;
      for (var i = 0; i < targets.length; i++) {
        if (visible.has(targets[i].id)) { winner = targets[i].id; break; }
      }
      if (winner) {
        links.forEach(function (a) { a.classList.remove('is-active'); });
        if (byId[winner]) { byId[winner].classList.add('is-active'); }
      }
    }, { rootMargin: '-84px 0px -62% 0px', threshold: 0 });

    targets.forEach(function (t) { spy.observe(t); });
  }

  /* ---- reveal on scroll ------------------------------------------------- */
  // The boot script only sets `reveal-on` when revealing is safe (top-level
  // window, motion allowed, IntersectionObserver present). If it is absent the
  // content is already visible and there is nothing to do — never add hiding
  // here, or a failure below would leave the page blank.
  var reveals = Array.prototype.slice.call(document.querySelectorAll('.reveal'));
  function showAll() { reveals.forEach(function (el) { el.classList.add('in'); }); }

  if (!root.classList.contains('reveal-on')) {
    showAll();
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
    reveals.forEach(function (el) { io.observe(el); });

    // Failsafe: if anything is still hidden after 2.5s — an observer that never
    // fired, a viewport smaller than the page expects — show it. A missed
    // animation is a cosmetic loss; invisible content is a broken page.
    setTimeout(showAll, 2500);
  }

  /* ---- copy buttons ----------------------------------------------------- */
  document.querySelectorAll('[data-copy]').forEach(function (el) {
    el.addEventListener('click', function () {
      var text = el.getAttribute('data-copy');
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(text).then(function () {
        var prev = el.getAttribute('data-label') || el.textContent;
        el.setAttribute('data-label', prev);
        el.textContent = 'copied';
        setTimeout(function () { el.textContent = prev; }, 1400);
      }).catch(function () { /* clipboard blocked — no-op */ });
    });
  });
})();

/*
 * interaction.js — s2h page interactions
 *
 * Handles: collapsible panels, tab switching, pipeline step navigation,
 * scroll-to-section, analytics beacon.
 *
 * Zero dependencies. Loaded at end of <body>.
 */

(function () {
  'use strict';

  // === Collapsible panels ===
  document.querySelectorAll('.s2h-collapse-head').forEach(function (head) {
    head.addEventListener('click', function () {
      head.parentElement.classList.toggle('open');
    });
  });

  // === Tab switching ===
  document.querySelectorAll('.s2h-tabs').forEach(function (tabBar) {
    var tabs = tabBar.querySelectorAll('.s2h-tab');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        var group = tab.dataset.group;
        var target = tab.dataset.target;
        if (!group || !target) return;

        // deactivate siblings
        tabBar.querySelectorAll('.s2h-tab').forEach(function (t) {
          t.classList.remove('on');
        });
        tab.classList.add('on');

        // show/hide panels
        document.querySelectorAll('[data-tab-group="' + group + '"]').forEach(function (panel) {
          panel.style.display = panel.dataset.tabId === target ? '' : 'none';
        });
      });
    });
  });

  // === Pipeline step navigation ===
  document.querySelectorAll('.s2h-pipe').forEach(function (pipe) {
    var items = pipe.querySelectorAll('.s2h-pipe-item');
    items.forEach(function (item) {
      item.addEventListener('click', function () {
        var target = item.dataset.step;
        if (!target) return;

        // highlight active
        items.forEach(function (i) { i.classList.remove('on'); });
        item.classList.add('on');

        // show/hide step panels
        var parent = pipe.parentElement;
        parent.querySelectorAll('.s2h-step').forEach(function (step) {
          step.classList.toggle('vis', step.id === target);
        });
      });
    });

    // activate first step by default
    if (items.length > 0) {
      items[0].click();
    }
  });

  // === Smooth scroll for anchor links ===
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var id = link.getAttribute('href').slice(1);
      var el = document.getElementById(id);
      if (el) {
        e.preventDefault();
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // === Analytics beacon (opt-in, no-op if endpoint missing) ===
  var beacon = document.querySelector('meta[name="s2h-beacon"]');
  if (beacon && beacon.content && typeof navigator.sendBeacon === 'function') {
    var endpoint = beacon.content;

    // page view
    navigator.sendBeacon(endpoint, JSON.stringify({
      type: 'view',
      skill: document.title,
      ts: new Date().toISOString(),
      ua: navigator.userAgent
    }));

    // section engagement via IntersectionObserver
    if (typeof IntersectionObserver === 'function') {
      var seen = {};
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !seen[entry.target.id]) {
            seen[entry.target.id] = true;
            navigator.sendBeacon(endpoint, JSON.stringify({
              type: 'section',
              id: entry.target.id,
              skill: document.title,
              ts: new Date().toISOString()
            }));
          }
        });
      }, { threshold: 0.3 });

      document.querySelectorAll('.s2h-section[id]').forEach(function (sec) {
        observer.observe(sec);
      });
    }
  }

})();

/**
 * UX-P1 Phase 2 — Guided Simulation Onboarding (production client layer).
 * Teaches Replay → Plan → Review → Journal without durable trade/journal writes.
 * Never calls POST /api/session/start without an explicit instrument_id (A1).
 */
(function (global) {
  "use strict";

  var STORAGE_KEY = "octomarket.onboarding.v1";
  var TOUR_VERSION = 2;
  var DEFAULT_INSTRUMENT = "AAPL";

  var STATES = [
    "NOT_STARTED",
    "WELCOME",
    "REPLAY_INTRO",
    "MARKET_EVENT",
    "PLAN_CREATION",
    "CONTROLS",
    "DECISION_REVIEW",
    "JOURNAL_LOOP",
    "COMPLETE",
  ];

  var ACTIVE_FLOW = [
    "WELCOME",
    "REPLAY_INTRO",
    "MARKET_EVENT",
    "PLAN_CREATION",
    "CONTROLS",
    "DECISION_REVIEW",
    "JOURNAL_LOOP",
  ];

  var host = {
    getInstrumentId: function () {
      return DEFAULT_INSTRUMENT;
    },
    startReplay: null,
    stepOnce: null,
    pauseReplay: null,
    refreshUi: null,
  };

  var busy = false;
  var marketBeat = 0;
  var listenersBound = false;
  var onResize = null;

  var STEP_META = {
    WELCOME: {
      title: "Practice before you risk capital",
      body:
        "OctoMarket is a paper trading terminal. This guided session shows how Replay, planning, Decision Review, and Journal fit together — without placing real practice trades into your history.",
      target: null,
      nextLabel: "Begin",
      eyebrow: "Guided simulation",
    },
    REPLAY_INTRO: {
      title: "Replay is your practice arena",
      body:
        "Replay walks historical bars so you can practice decisions in context. We will start Replay with an explicit instrument — never a silent default.",
      target: "#startSessionBtn",
      nextLabel: "Start Replay",
      eyebrow: "Step 1 · Replay",
    },
    MARKET_EVENT: {
      title: "Markets move — decisions need structure",
      body: "Watch three beats as bars advance with Step.",
      target: "#stepSessionBtn",
      nextLabel: "Advance bars",
      eyebrow: "Step 2 · Decision point",
    },
    PLAN_CREATION: {
      title: "A plan turns an idea into a decision",
      body:
        "Define why you enter and when you are wrong: instrument, thesis, entry, stop, target. We fill the form temporarily for teaching — nothing is saved and no order is placed.",
      target: ".trade-plan-section",
      nextLabel: "Show plan fields",
      eyebrow: "Step 3 · Plan",
    },
    CONTROLS: {
      title: "Controls you will use constantly",
      body:
        "Play advances the simulation. Step inspects one bar. Pause gives you time to think. Reset / Close leave Replay and return to LIVE PAPER.",
      target: "#playSessionBtn",
      nextLabel: "Next",
      eyebrow: "Step 4 · Controls",
    },
    DECISION_REVIEW: {
      title: "Review closes the loop",
      body:
        "After a real planned trade closes, Decision Review shows what you expected, what happened, and what you can learn. Below is an example only — this tour does not create a review record.",
      target: "#replayReviewPanel",
      nextLabel: "Next",
      eyebrow: "Step 5 · Review",
    },
    JOURNAL_LOOP: {
      title: "Journal is where lessons accumulate",
      body:
        "Your real planned trades create lessons here. Open Journal to see the destination. Onboarding never writes journal entries.",
      target: null,
      nextLabel: "Finish tour",
      eyebrow: "Step 6 · Journal",
    },
  };

  var MARKET_BEATS = [
    "Beat 1 — Markets move. Price advances bar by bar.",
    "Beat 2 — Conditions change. Context shifts as you Step.",
    "Beat 3 — Decisions need a plan. Do not click without invalidation.",
  ];

  function loadPersisted() {
    try {
      var raw = global.localStorage.getItem(STORAGE_KEY);
      if (!raw) return { version: TOUR_VERSION, state: "NOT_STARTED" };
      var data = JSON.parse(raw);
      if (!data) return { version: TOUR_VERSION, state: "NOT_STARTED" };
      var state = data.state;
      if (STATES.indexOf(state) < 0 && state !== "SKIPPED") {
        state = "NOT_STARTED";
      }
      if (data.version !== TOUR_VERSION) {
        if (state === "COMPLETE" || state === "SKIPPED") {
          return { version: TOUR_VERSION, state: state };
        }
        return { version: TOUR_VERSION, state: "NOT_STARTED" };
      }
      return { version: TOUR_VERSION, state: state, updated_at: data.updated_at };
    } catch (e) {
      return { version: TOUR_VERSION, state: "NOT_STARTED" };
    }
  }

  function persist(state) {
    var payload = {
      version: TOUR_VERSION,
      state: state,
      updated_at: new Date().toISOString(),
    };
    try {
      global.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (e) {
      /* ignore */
    }
    return payload;
  }

  function flowIndex(state) {
    return ACTIVE_FLOW.indexOf(state);
  }

  function resolveInstrumentId() {
    var id = "";
    try {
      id = (host.getInstrumentId && host.getInstrumentId()) || "";
    } catch (e) {
      id = "";
    }
    id = String(id || "").trim().toUpperCase();
    return id || DEFAULT_INSTRUMENT;
  }

  function createOverlay() {
    var root = document.createElement("div");
    root.id = "onboardingTourRoot";
    root.className = "om-tour-root";
    root.setAttribute("data-tour-version", String(TOUR_VERSION));
    root.setAttribute("data-tour-phase", "2");
    root.innerHTML =
      '<div class="om-tour-backdrop" data-tour-backdrop tabindex="-1"></div>' +
      '<div class="om-tour-spotlight" data-tour-spotlight hidden></div>' +
      '<div class="om-tour-card" role="dialog" aria-modal="true" aria-labelledby="omTourTitle">' +
      '  <div class="om-tour-eyebrow" data-tour-eyebrow></div>' +
      '  <div class="om-tour-progress" data-tour-progress></div>' +
      '  <h2 id="omTourTitle" class="om-tour-title" data-tour-title></h2>' +
      '  <p class="om-tour-body" data-tour-body></p>' +
      '  <div class="om-tour-status" data-tour-status hidden></div>' +
      '  <div class="om-tour-demo" data-tour-demo hidden></div>' +
      '  <div class="om-tour-actions">' +
      '    <button type="button" class="om-tour-btn om-tour-btn-secondary" data-tour-skip>Skip</button>' +
      '    <div class="om-tour-actions-right">' +
      '      <button type="button" class="om-tour-btn om-tour-btn-ghost" data-tour-journal hidden>Open Journal</button>' +
      '      <button type="button" class="om-tour-btn om-tour-btn-secondary" data-tour-back>Back</button>' +
      '      <button type="button" class="om-tour-btn om-tour-btn-primary" data-tour-next>Next</button>' +
      "    </div>" +
      "  </div>" +
      '  <div class="om-tour-hint">Enter = continue · Esc = skip</div>' +
      "</div>";
    document.body.appendChild(root);
    return root;
  }

  function setStatus(text, isError) {
    var el = document.querySelector("[data-tour-status]");
    if (!el) return;
    if (!text) {
      el.hidden = true;
      el.textContent = "";
      el.classList.remove("is-error");
      return;
    }
    el.hidden = false;
    el.textContent = text;
    el.classList.toggle("is-error", !!isError);
  }

  function setBusy(flag) {
    busy = !!flag;
    var nextBtn = document.querySelector("[data-tour-next]");
    var backBtn = document.querySelector("[data-tour-back]");
    var skipBtn = document.querySelector("[data-tour-skip]");
    if (nextBtn) nextBtn.disabled = busy;
    if (backBtn) backBtn.disabled = busy || flowIndex(loadPersisted().state) <= 0;
    if (skipBtn) skipBtn.disabled = busy;
  }

  function clearHighlight() {
    document.querySelectorAll("[data-tour-highlighted]").forEach(function (el) {
      el.removeAttribute("data-tour-highlighted");
      el.classList.remove("om-tour-highlight");
    });
  }

  function applyHighlight(selector) {
    clearHighlight();
    var spot = document.querySelector("[data-tour-spotlight]");
    if (!selector) {
      if (spot) spot.hidden = true;
      return;
    }
    var el = document.querySelector(selector);
    if (!el) {
      if (spot) spot.hidden = true;
      return;
    }
    el.setAttribute("data-tour-highlighted", "1");
    el.classList.add("om-tour-highlight");
    try {
      el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    } catch (e) {
      /* ignore */
    }
    if (!spot) return;
    var rect = el.getBoundingClientRect();
    spot.hidden = false;
    spot.style.top = Math.max(0, rect.top - 8) + "px";
    spot.style.left = Math.max(0, rect.left - 8) + "px";
    spot.style.width = Math.max(24, rect.width + 16) + "px";
    spot.style.height = Math.max(24, rect.height + 16) + "px";
  }

  function fillTemporaryPlanExample() {
    var thesis = document.getElementById("planThesis");
    var entry = document.getElementById("planEntry");
    var stop = document.getElementById("planStop");
    var target = document.getElementById("planTarget");
    var qty = document.getElementById("planQty");
    var base = 100;
    if (entry && entry.value) base = parseFloat(entry.value) || base;
    else if (global.document.getElementById("orderPrice")) {
      base = parseFloat(document.getElementById("orderPrice").value) || base;
    }
    if (thesis && !thesis.value.trim()) {
      thesis.value = "Tour example: enter only with a clear thesis and invalidation.";
      thesis.dataset.tourTemp = "1";
    }
    if (entry && !entry.value) {
      entry.value = String(base.toFixed(2));
      entry.dataset.tourTemp = "1";
    }
    if (stop && !stop.value) {
      stop.value = String((base * 0.97).toFixed(2));
      stop.dataset.tourTemp = "1";
    }
    if (target && !target.value) {
      target.value = String((base * 1.04).toFixed(2));
      target.dataset.tourTemp = "1";
    }
    if (qty && !qty.value) {
      qty.value = "1";
      qty.dataset.tourTemp = "1";
    }
  }

  function renderDemo(state) {
    var demo = document.querySelector("[data-tour-demo]");
    var journalBtn = document.querySelector("[data-tour-journal]");
    if (journalBtn) journalBtn.hidden = state !== "JOURNAL_LOOP";
    if (!demo) return;

    if (state === "MARKET_EVENT") {
      demo.hidden = false;
      demo.innerHTML =
        '<ol class="om-tour-beats">' +
        MARKET_BEATS.map(function (line, i) {
          var active = i === Math.min(marketBeat, MARKET_BEATS.length - 1);
          return (
            '<li class="' +
            (active ? "is-active" : "") +
            (i < marketBeat ? " is-done" : "") +
            '">' +
            line +
            "</li>"
          );
        }).join("") +
        "</ol>";
      return;
    }

    if (state === "PLAN_CREATION") {
      demo.hidden = false;
      demo.innerHTML =
        '<div class="om-tour-checklist">' +
        "<div><strong>Instrument</strong> — what you are trading</div>" +
        "<div><strong>Thesis</strong> — why you enter</div>" +
        "<div><strong>Entry / Stop / Target</strong> — levels</div>" +
        "<div><strong>Invalidation</strong> — when you are wrong</div>" +
        '<div class="om-tour-muted">Temporary form fill only — no save, no order.</div>' +
        "</div>";
      return;
    }

    if (state === "CONTROLS") {
      demo.hidden = false;
      demo.innerHTML =
        '<div class="om-tour-controls-grid">' +
        "<div><strong>Play</strong><span>Advance simulation</span></div>" +
        "<div><strong>Step</strong><span>One decision point</span></div>" +
        "<div><strong>Pause</strong><span>Think</span></div>" +
        "<div><strong>Reset / Close</strong><span>Leave Replay cleanly</span></div>" +
        "</div>";
      return;
    }

    if (state === "DECISION_REVIEW") {
      demo.hidden = false;
      demo.innerHTML =
        '<div class="om-tour-example-card">' +
        "<strong>Example Decision Review</strong>" +
        "<div class=\"om-tour-example-row\"><span>Expected</span><span>Plan thesis + levels</span></div>" +
        "<div class=\"om-tour-example-row\"><span>What happened</span><span>Outcome &amp; R-multiple</span></div>" +
        "<div class=\"om-tour-example-row\"><span>What you learned</span><span>Decision quality notes</span></div>" +
        '<div class="om-tour-muted">Illustration only — no ReplayRecord or journal write.</div>' +
        "</div>";
      var reviewPanel = document.getElementById("replayReviewPanel");
      if (reviewPanel) {
        reviewPanel.style.display = "block";
        reviewPanel.setAttribute("data-tour-demo-open", "1");
      }
      return;
    }

    var reviewPanelReset = document.getElementById("replayReviewPanel");
    if (reviewPanelReset && reviewPanelReset.getAttribute("data-tour-demo-open") === "1") {
      reviewPanelReset.style.display = "none";
      reviewPanelReset.removeAttribute("data-tour-demo-open");
    }

    if (state === "JOURNAL_LOOP") {
      demo.hidden = false;
      demo.innerHTML =
        '<div class="om-tour-example-card">' +
        "<strong>Journal destination</strong>" +
        "<div>Real planned trades create lessons you can search and review later.</div>" +
        '<div class="om-tour-muted">This tour does not create entries.</div>' +
        "</div>";
      return;
    }

    demo.hidden = true;
    demo.innerHTML = "";
  }

  function render(state) {
    var root = document.getElementById("onboardingTourRoot");
    if (!root) return;

    if (state === "NOT_STARTED" || state === "COMPLETE" || state === "SKIPPED") {
      root.hidden = true;
      document.body.classList.remove("om-tour-active");
      clearHighlight();
      setStatus("");
      return;
    }

    root.hidden = false;
    document.body.classList.add("om-tour-active");
    var meta = STEP_META[state] || { title: state, body: "", target: null, nextLabel: "Next", eyebrow: "" };
    var title = root.querySelector("[data-tour-title]");
    var body = root.querySelector("[data-tour-body]");
    var progress = root.querySelector("[data-tour-progress]");
    var eyebrow = root.querySelector("[data-tour-eyebrow]");
    var backBtn = root.querySelector("[data-tour-back]");
    var nextBtn = root.querySelector("[data-tour-next]");
    var idx = flowIndex(state);
    var total = ACTIVE_FLOW.length;

    if (title) title.textContent = meta.title;
    if (body) body.textContent = meta.body;
    if (eyebrow) eyebrow.textContent = meta.eyebrow || "";
    if (progress) {
      progress.innerHTML =
        '<span class="om-tour-progress-bar"><i style="width:' +
        (((idx + 1) / total) * 100).toFixed(1) +
        '%"></i></span>' +
        "<span>Step " +
        (idx + 1) +
        " of " +
        total +
        "</span>";
    }
    if (backBtn) backBtn.disabled = busy || idx <= 0;
    if (nextBtn) {
      nextBtn.disabled = busy;
      nextBtn.textContent = meta.nextLabel || (idx >= total - 1 ? "Finish" : "Next");
    }
    renderDemo(state);
    applyHighlight(meta.target);
    if (nextBtn && !busy) {
      try {
        nextBtn.focus({ preventScroll: true });
      } catch (e) {
        try {
          nextBtn.focus();
        } catch (e2) {
          /* ignore */
        }
      }
    }
  }

  function setState(state) {
    if (STATES.indexOf(state) < 0 && state !== "SKIPPED") return;
    if (state === "MARKET_EVENT") marketBeat = 0;
    persist(state);
    render(state);
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  async function ensureReplayStarted() {
    var instrumentId = resolveInstrumentId();
    if (!instrumentId) {
      throw new Error("instrument_id is required to start Replay");
    }
    if (!host.startReplay) {
      throw new Error("Replay host is not bound");
    }
    setStatus("Starting Replay for " + instrumentId + "…");
    await host.startReplay(instrumentId);
    if (host.refreshUi) await host.refreshUi();
    setStatus("Replay active · " + instrumentId);
  }

  async function runMarketBeats() {
    if (!host.stepOnce) {
      throw new Error("Step host is not bound");
    }
    for (var i = 0; i < MARKET_BEATS.length; i++) {
      marketBeat = i;
      renderDemo("MARKET_EVENT");
      setStatus(MARKET_BEATS[i]);
      await host.stepOnce();
      if (host.refreshUi) await host.refreshUi();
      await sleep(380);
    }
    marketBeat = MARKET_BEATS.length;
    renderDemo("MARKET_EVENT");
    setStatus("Decision Point reached — planning comes next.");
  }

  async function runPrimaryAction(state) {
    if (state === "REPLAY_INTRO") {
      await ensureReplayStarted();
      return;
    }
    if (state === "MARKET_EVENT") {
      await runMarketBeats();
      return;
    }
    if (state === "PLAN_CREATION") {
      fillTemporaryPlanExample();
      setStatus("Plan fields filled temporarily — not saved.");
      return;
    }
  }

  async function next() {
    if (busy) return;
    var current = loadPersisted().state;
    var idx = flowIndex(current);
    if (idx < 0) {
      setState("WELCOME");
      return;
    }

    setBusy(true);
    try {
      await runPrimaryAction(current);
      if (loadPersisted().state === "SKIPPED" || loadPersisted().state === "COMPLETE") {
        return;
      }
      if (idx >= ACTIVE_FLOW.length - 1) {
        setState("COMPLETE");
        setStatus("");
        return;
      }
      setState(ACTIVE_FLOW[idx + 1]);
      setStatus("");
    } catch (err) {
      if (loadPersisted().state === "SKIPPED") return;
      setStatus((err && err.message) || "Tour action failed", true);
    } finally {
      setBusy(false);
      render(loadPersisted().state);
    }
  }

  function back() {
    if (busy) return;
    var current = loadPersisted().state;
    var idx = flowIndex(current);
    if (idx <= 0) return;
    setStatus("");
    setState(ACTIVE_FLOW[idx - 1]);
  }

  function skip() {
    setBusy(false);
    setState("SKIPPED");
  }

  function start() {
    marketBeat = 0;
    setState("WELCOME");
  }

  function restart() {
    persist("NOT_STARTED");
    start();
  }

  function openJournal() {
    global.location.href = "/journal";
  }

  function onKeydown(e) {
    var root = document.getElementById("onboardingTourRoot");
    if (!root || root.hidden) return;
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      skip();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      var tag = (e.target && e.target.tagName) || "";
      if (tag === "TEXTAREA" || tag === "INPUT") return;
      e.preventDefault();
      e.stopPropagation();
      next();
    }
  }

  function bind(root) {
    if (listenersBound) return;
    listenersBound = true;
    root.querySelector("[data-tour-next]").addEventListener("click", function () {
      next();
    });
    root.querySelector("[data-tour-back]").addEventListener("click", back);
    root.querySelector("[data-tour-skip]").addEventListener("click", skip);
    var journalBtn = root.querySelector("[data-tour-journal]");
    if (journalBtn) journalBtn.addEventListener("click", openJournal);
    global.addEventListener("keydown", onKeydown);
    onResize = function () {
      var state = loadPersisted().state;
      var meta = STEP_META[state];
      if (meta) applyHighlight(meta.target);
    };
    global.addEventListener("resize", onResize);
  }

  function bindHost(partial) {
    if (!partial) return;
    Object.keys(partial).forEach(function (key) {
      host[key] = partial[key];
    });
  }

  function init() {
    if (document.getElementById("onboardingTourRoot")) return;
    var root = createOverlay();
    root.hidden = true;
    bind(root);

    var params = new URLSearchParams(global.location.search || "");
    if (params.get("tour") === "restart") {
      restart();
      return;
    }
    if (params.get("tour") === "1") {
      start();
      return;
    }

    var persisted = loadPersisted().state;
    if (persisted === "NOT_STARTED") {
      start();
      return;
    }
    if (ACTIVE_FLOW.indexOf(persisted) >= 0) {
      setState(persisted);
    }
  }

  global.OctoOnboarding = {
    STATES: STATES,
    ACTIVE_FLOW: ACTIVE_FLOW,
    STORAGE_KEY: STORAGE_KEY,
    TOUR_VERSION: TOUR_VERSION,
    DEFAULT_INSTRUMENT: DEFAULT_INSTRUMENT,
    loadPersisted: loadPersisted,
    persist: persist,
    setState: setState,
    next: next,
    back: back,
    skip: skip,
    start: start,
    restart: restart,
    bindHost: bindHost,
    resolveInstrumentId: resolveInstrumentId,
    init: init,
  };
})(typeof window !== "undefined" ? window : globalThis);

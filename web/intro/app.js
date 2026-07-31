(() => {
  "use strict";

  const FALLBACK_SCENES = [
    {
      caption: "2024.07.29 · 밤",
      image: "intro/scene_rain_cctv.jpg",
      text: "폭우가 도시를 삼킨 밤.\n사내 건물 옥외·복도 CCTV가\n차례로 먹통이 된다.",
    },
    {
      caption: "서버실 · 사내망",
      image: "intro/scene_server_theft.jpg",
      text: "그 사이 —\n프로젝트 Omega 핵심 가중치 파일이\n불법 반출된다.\n추정 피해, 약 100억.",
    },
    {
      caption: "잔류 인원",
      image: "intro/scene_trio.jpg",
      text: "당시 건물에 남은 사람은\n단 세 명뿐이었다.\n\n김팀장 · 이대리 · 박신입.",
    },
    {
      caption: "외부 감사관",
      image: "intro/scene_auditor.jpg",
      text: "당신은 외부 디지털 포렌식 감사관이다.\nRAG로 단서를 모으고,\n심문으로 알리바이를 무너뜨려라.",
    },
    {
      caption: "수사 개시",
      image: "intro/scene_truth_door.jpg",
      text: "진범은 셋 중 한 명.\n결정적 증거를 조합해 지목하라.\n\n진실의 방이 열렸다.",
    },
  ];

  const params = new URLSearchParams(window.location.search);
  const API_BASE = (params.get("api") || "/api").replace(/\/$/, "");
  const ASSET_BASE = (params.get("assets") || "/assets").replace(/\/$/, "");

  function defaultGameBase() {
    const fromQuery = params.get("game");
    if (fromQuery) return fromQuery.replace(/\/$/, "");
    // 로컬 uvicorn(8000)만 쓸 때 → Streamlit 기본 포트
    if (location.port === "8000") return "http://127.0.0.1:8501";
    // docker/nginx
    return "/game";
  }
  const GAME_BASE = defaultGameBase();

  const pinRoot = document.getElementById("pinRoot");
  const scrollHint = document.getElementById("scrollHint");
  const introBgm = document.getElementById("introBgm");
  const gameBgm = document.getElementById("gameBgm");
  const bgmToggle = document.getElementById("bgmToggle");

  let scenes = FALLBACK_SCENES;
  let caseMeta = { case_id: "case_01", title: "진실의 방" };
  let sessionId = null;
  let startingGame = false;
  let bgmUserMuted = false;
  let bgmStarted = false;
  let bgmFading = false;
  const BGM_VOL = 0.45;
  let fadeToken = 0;
  /** 씬당 체류 후 자동 스크롤 (7~8초) — 마지막 씬은 제외 */
  const AUTO_SCENE_MS = 7500;
  const AUTO_SCROLL_MS = 1100;
  let autoTimer = null;
  let autoSceneIndex = -1;
  let autoScrolling = false;
  let ctaRevealTimer = null;
  /** 마지막 씬 카드가 뜬 뒤 CTA 페이드인까지 */
  const CTA_REVEAL_MS = 2800;
  const CTA_REVEAL_REDUCED_MS = 400;

  if (introBgm) introBgm.volume = BGM_VOL;
  if (gameBgm) gameBgm.volume = BGM_VOL;

  function setBgmUi(on) {
    if (!bgmToggle) return;
    bgmToggle.setAttribute("aria-pressed", on ? "true" : "false");
    bgmToggle.setAttribute("aria-label", on ? "배경음악 끄기" : "배경음악 켜기");
    bgmToggle.title = on ? "BGM ON" : "BGM OFF";
  }

  function pauseEl(el) {
    if (!el) return;
    el.pause();
  }

  async function tryStartTrack(el) {
    if (!el || bgmUserMuted || bgmFading || startingGame) return false;
    try {
      el.muted = false;
      el.volume = BGM_VOL;
      await el.play();
      bgmStarted = true;
      setBgmUi(true);
      return true;
    } catch (err) {
      bgmStarted = false;
      setBgmUi(false);
      return false;
    }
  }

  async function tryStartBgm() {
    if (startingGame) return false;
    return tryStartTrack(introBgm);
  }

  function fadeOutEl(el, ms = 900) {
    return new Promise((resolve) => {
      if (!el || el.paused) {
        pauseEl(el);
        resolve();
        return;
      }
      const token = ++fadeToken;
      bgmFading = true;
      const start = el.volume;
      const t0 = performance.now();
      function step(now) {
        if (token !== fadeToken) {
          resolve();
          return;
        }
        const t = Math.min(1, (now - t0) / ms);
        el.volume = Math.max(0, start * (1 - t));
        if (t < 1) {
          requestAnimationFrame(step);
          return;
        }
        pauseEl(el);
        el.volume = BGM_VOL;
        bgmFading = false;
        resolve();
      }
      requestAnimationFrame(step);
    });
  }

  function bindBgmGestures() {
    const unlock = () => {
      if (!bgmUserMuted && !startingGame && introBgm && (introBgm.paused || !bgmStarted)) {
        tryStartBgm();
      }
    };
    ["pointerdown", "touchstart", "keydown", "scroll", "wheel"].forEach((ev) => {
      window.addEventListener(ev, unlock, { passive: true });
    });
    if (bgmToggle) {
      bgmToggle.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!introBgm) return;
        if (!introBgm.paused && !bgmUserMuted) {
          bgmUserMuted = true;
          fadeToken += 1;
          bgmFading = false;
          pauseEl(introBgm);
          pauseEl(gameBgm);
          setBgmUi(false);
          return;
        }
        bgmUserMuted = false;
        bgmFading = false;
        introBgm.volume = BGM_VOL;
        await tryStartBgm();
      });
    }
  }

  async function autoplayBgm() {
    if (await tryStartBgm()) return;
    if (introBgm) {
      introBgm.addEventListener(
        "canplaythrough",
        () => {
          tryStartBgm();
        },
        { once: true }
      );
    }
    setTimeout(() => tryStartBgm(), 300);
    setTimeout(() => tryStartBgm(), 1000);
  }

  function assetUrl(imageKey) {
    const key = String(imageKey || "").replace(/^\/+/, "");
    if (!key) return "";
    if (key.startsWith("http")) return key;
    if (key.startsWith("assets/")) return `/${key}`;
    return `${ASSET_BASE}/${key}`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderScenes(list) {
    const last = list.length - 1;
    pinRoot.innerHTML = list
      .map((scene, i) => {
        const img = assetUrl(scene.image);
        const caption = escapeHtml(scene.caption || "");
        const text = escapeHtml(scene.text || "");
        const isFinal = i === last;
        const src = img
          ? `<img src="${escapeHtml(img)}" alt="${caption || `scene ${i + 1}`}" />`
          : "";
        const cta = isFinal
          ? `<div class="scene-cta">
               <button type="button" class="scene-start-btn" data-start-game>
                 수사 시작
               </button>
               <p class="scene-start-hint" data-start-status></p>
             </div>`
          : "";
        return `
        <section class="scene${isFinal ? " scene--final" : ""}" data-index="${i}">
          <div class="scene-sticky">
            <div class="scene-visual" data-visual>
              ${src}
            </div>
            <div class="scene-veil" aria-hidden="true"></div>
            <div class="scene-copy">
              <p class="scene-kicker">CASE · ${escapeHtml(
                caseMeta.case_id || "case_01"
              )} · SCENE ${i + 1}/${list.length}</p>
              ${caption ? `<h2 class="scene-caption">${caption}</h2>` : ""}
              <p class="scene-text">${text}</p>
            </div>
            ${cta}
            <div class="scene-progress">${i + 1} / ${list.length}</div>
          </div>
        </section>`;
      })
      .join("");
  }

  function sceneProgress(el) {
    const rect = el.getBoundingClientRect();
    const total = el.offsetHeight - window.innerHeight;
    if (total <= 0) return 1;
    const scrolled = -rect.top;
    return Math.min(1, Math.max(0, scrolled / total));
  }

  function activeSceneIndex(nodes) {
    let best = -1;
    nodes.forEach((scene, i) => {
      if (scene.classList.contains("is-active")) best = i;
    });
    if (best >= 0) return best;
    for (let i = 0; i < nodes.length; i += 1) {
      const mid = nodes[i].getBoundingClientRect();
      if (mid.top < window.innerHeight * 0.55 && mid.bottom > window.innerHeight * 0.35) {
        return i;
      }
    }
    return nodes.length ? 0 : -1;
  }

  function clearAutoAdvance() {
    if (autoTimer) {
      clearTimeout(autoTimer);
      autoTimer = null;
    }
  }

  function scrollToY(y) {
    autoScrolling = true;
    clearAutoAdvance();
    window.scrollTo({ top: Math.max(0, y), behavior: "smooth" });
    window.setTimeout(() => {
      autoScrolling = false;
      onScroll();
    }, AUTO_SCROLL_MS + 80);
  }

  function advanceFromScene(idx) {
    const nodes = [...document.querySelectorAll(".scene")];
    if (!nodes.length || startingGame) return;
    // 마지막 씬: 자동으로 게임 진입하지 않음 — 「수사 시작」 클릭만
    if (idx >= nodes.length - 1) {
      clearAutoAdvance();
      return;
    }
    scrollToY(nodes[idx + 1].offsetTop);
  }

  function scheduleAutoAdvance(idx) {
    clearAutoAdvance();
    if (startingGame || autoScrolling) return;
    if (idx < 0) return;
    const nodes = document.querySelectorAll(".scene");
    if (idx >= nodes.length - 1) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    autoTimer = window.setTimeout(() => {
      autoTimer = null;
      if (startingGame || autoScrolling) return;
      advanceFromScene(idx);
    }, AUTO_SCENE_MS);
  }

  function clearCtaReveal() {
    if (ctaRevealTimer) {
      clearTimeout(ctaRevealTimer);
      ctaRevealTimer = null;
    }
    document.querySelectorAll(".scene-cta.is-ready").forEach((el) => {
      el.classList.remove("is-ready");
    });
  }

  function scheduleCtaReveal(finalScene) {
    const cta = finalScene && finalScene.querySelector(".scene-cta");
    if (!cta || cta.classList.contains("is-ready")) return;
    if (ctaRevealTimer) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const delay = reduced ? CTA_REVEAL_REDUCED_MS : CTA_REVEAL_MS;
    ctaRevealTimer = window.setTimeout(() => {
      ctaRevealTimer = null;
      if (!finalScene.classList.contains("is-active") || startingGame) return;
      cta.classList.add("is-ready");
      if (scrollHint) {
        scrollHint.textContent = "「수사 시작」을 눌러 심문으로 이동";
        scrollHint.classList.remove("is-hide");
      }
    }, delay);
  }

  function onScroll() {
    const nodes = [...document.querySelectorAll(".scene")];
    nodes.forEach((scene) => {
      const p = sceneProgress(scene);
      const visual = scene.querySelector("[data-visual]");
      if (visual) {
        const scale = 1.18 - p * 0.18;
        const brightness = 0.72 + p * 0.28;
        visual.style.transform = `scale(${scale.toFixed(4)})`;
        visual.style.filter = `brightness(${brightness.toFixed(3)})`;
      }
      const mid = scene.getBoundingClientRect();
      const active =
        mid.top < window.innerHeight * 0.55 && mid.bottom > window.innerHeight * 0.35;
      scene.classList.toggle("is-active", active);
    });

    if (window.scrollY > 40) scrollHint.classList.add("is-hide");
    else scrollHint.classList.remove("is-hide");

    if (!startingGame && !autoScrolling) {
      const idx = activeSceneIndex(nodes);
      const last = nodes.length - 1;
      if (idx !== autoSceneIndex) {
        autoSceneIndex = idx;
        scheduleAutoAdvance(idx);
        if (idx === last && last >= 0) {
          scheduleCtaReveal(nodes[last]);
        } else {
          clearCtaReveal();
        }
      } else if (idx === last && last >= 0) {
        scheduleCtaReveal(nodes[last]);
      }
      if (scrollHint && idx === last && last >= 0) {
        const ctaReady = nodes[last].querySelector(".scene-cta.is-ready");
        if (!ctaReady) {
          scrollHint.textContent = "브리핑을 읽어 주세요";
          scrollHint.classList.remove("is-hide");
        }
      } else if (scrollHint && idx >= 0) {
        scrollHint.textContent = "잠시 후 자동 진행 · 스크롤로도 이동";
      }
    }
  }

  async function fetchPublicCase() {
    try {
      const res = await fetch(`${API_BASE}/v1/case/public`, { credentials: "omit" });
      if (!res.ok) throw new Error(`case ${res.status}`);
      const data = await res.json();
      caseMeta = {
        case_id: data.case_id || "case_01",
        title: data.title || "진실의 방",
      };
      if (Array.isArray(data.intro_scenes) && data.intro_scenes.length) {
        scenes = data.intro_scenes.filter((s) => s && (s.text || s.caption));
      }
    } catch (err) {
      console.warn("[intro] public case fallback", err);
    }
  }

  function gameUrl(sid) {
    const q = new URLSearchParams({
      intro_done: "1",
      session_id: sid,
    });
    return `${GAME_BASE}/?${q.toString()}`;
  }

  async function startInvestigation(btn) {
    if (startingGame) return;
    startingGame = true;
    clearAutoAdvance();
    const status = document.querySelector("[data-start-status]");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "세션 준비 중…";
    }
    if (status) status.textContent = "";

    try {
      await fadeOutEl(introBgm, 700);
      pauseEl(gameBgm);
      setBgmUi(false);

      if (!sessionId) {
        const res = await fetch(`${API_BASE}/v1/session`, {
          method: "POST",
          credentials: "omit",
        });
        if (!res.ok) throw new Error(`session ${res.status}`);
        const data = await res.json();
        sessionId = data.session_id;
      }

      // iframe embed 없이 Streamlit 전체 페이지로 이동
      window.location.href = gameUrl(sessionId);
    } catch (err) {
      console.error(err);
      startingGame = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = "수사 시작";
      }
      if (status) {
        status.textContent =
          "세션 생성에 실패했습니다. 다시 시도하거나 /game 으로 이동하세요.";
      }
    }
  }

  function bindStartButton() {
    if (!pinRoot) return;
    pinRoot.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-start-game]");
      if (!btn) return;
      e.preventDefault();
      startInvestigation(btn);
    });
  }

  async function boot() {
    setBgmUi(false);
    bindBgmGestures();
    autoplayBgm();
    await fetchPublicCase();
    renderScenes(scenes);
    bindStartButton();
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
  }

  boot();
})();

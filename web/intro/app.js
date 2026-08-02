(() => {
  "use strict";

  const FALLBACK_SCENES = [
    {
      caption: "2026.07.29 · 밤",
      image: "intro/scene_rain_cctv.webp",
      text: "폭우가 도시를 삼킨 밤.\n사내 건물 옥외·복도 CCTV가\n차례로 먹통이 된다.",
    },
    {
      caption: "서버실 · 사내망",
      image: "intro/scene_server_theft.webp",
      text: "그 사이 —\n프로젝트 Omega 핵심 가중치 파일이\n불법 반출된다.\n추정 피해, 약 100억.",
    },
    {
      caption: "잔류 인원",
      image: "intro/scene_trio.webp",
      text: "당시 건물에 남은 사람은\n단 세 명뿐이었다.\n\n김팀장 · 이대리 · 박신입.",
    },
    {
      caption: "외부 감사관",
      image: "intro/scene_auditor.webp",
      text: "당신은 외부 디지털 포렌식 감사관이다.\nRAG로 단서를 모으고,\n심문으로 알리바이를 무너뜨려라.",
    },
    {
      caption: "수사 개시",
      image: "intro/scene_truth_door_closed.webp",
      image_open: "intro/scene_truth_door.webp",
      text: "진범은 셋 중 한 명.\n결정적 증거를 조합해 지목하라.\n\n진실의 방이 열렸다.",
    },
  ];

  const params = new URLSearchParams(window.location.search);
  const API_BASE = (params.get("api") || "/api").replace(/\/$/, "");
  const ASSET_BASE = (params.get("assets") || "/assets").replace(/\/$/, "");

  function defaultGameBase() {
    const fromQuery = params.get("game");
    if (fromQuery) return fromQuery.replace(/\/$/, "");
    // legacy Streamlit 백업
    if (params.get("legacy") === "1") return "http://127.0.0.1:8501";
    // React 본편 (nginx /game 또는 Vite :5173)
    if (location.port === "8000") return "http://127.0.0.1:5173/game";
    return "/game";
  }
  const GAME_BASE = defaultGameBase();

  const pinRoot = document.getElementById("pinRoot");
  const scrollHint = document.getElementById("scrollHint");
  const introBgm = document.getElementById("introBgm");
  const gameBgm = document.getElementById("gameBgm");
  const bgmToggle = document.getElementById("bgmToggle");
  const bgmUnlockBtn = document.getElementById("bgmUnlock");

  let scenes = FALLBACK_SCENES;
  let caseMeta = { case_id: "case_01", title: "진실의 방" };
  let sessionId = null;
  let startingGame = false;
  let bgmUserMuted = false;
  /** media element가 play 중인지 (무음 포함) */
  let bgmPlaying = false;
  /** 실제 소리가 나는지 */
  let bgmAudible = false;
  let bgmFading = false;
  let bgmUnlockBound = false;
  const BGM_VOL = 0.12;
  const BGM_FADE_IN_MS = 900;
  let fadeToken = 0;
  const AUTO_SCROLL_MS = 1100;
  let autoSceneIndex = -1;
  let autoScrolling = false;
  let ctaRevealTimer = null;
  /** 마지막 씬 카드가 뜬 뒤 CTA 페이드인까지 */
  const CTA_REVEAL_MS = 2800;
  const CTA_REVEAL_REDUCED_MS = 400;
  /** 입장하기 → 문 열림 페이드·효과음 길이 */
  const DOOR_REVEAL_MS = 1450;
  const DOOR_REVEAL_REDUCED_MS = 200;

  if (introBgm) {
    introBgm.volume = 0;
    introBgm.muted = true;
  }
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

  function hideBgmUnlock() {
    if (bgmUnlockBtn) bgmUnlockBtn.classList.add("is-gone");
  }

  function showBgmUnlock() {
    if (bgmUnlockBtn && !bgmAudible && !bgmUserMuted) {
      bgmUnlockBtn.classList.remove("is-gone");
    }
  }

  function fadeInEl(el, ms = BGM_FADE_IN_MS) {
    if (!el || bgmUserMuted) return Promise.resolve(false);
    const token = ++fadeToken;
    bgmFading = true;
    el.muted = false;
    el.volume = 0;
    return el
      .play()
      .then(
        () =>
          new Promise((resolve) => {
            bgmPlaying = true;
            const t0 = performance.now();
            function step(now) {
              if (token !== fadeToken) {
                resolve(false);
                return;
              }
              const t = Math.min(1, (now - t0) / ms);
              el.volume = BGM_VOL * t;
              if (t < 1) {
                requestAnimationFrame(step);
                return;
              }
              bgmFading = false;
              el.volume = BGM_VOL;
              bgmAudible = true;
              setBgmUi(true);
              hideBgmUnlock();
              resolve(true);
            }
            requestAnimationFrame(step);
          })
      )
      .catch(() => {
        bgmFading = false;
        bgmAudible = false;
        setBgmUi(false);
        showBgmUnlock();
        return false;
      });
  }

  /** Chrome: 소리 있는 autoplay는 차단 → 무음 play는 허용되는 경우가 많음 */
  async function armMutedBgm() {
    if (!introBgm || bgmUserMuted || startingGame) return false;
    try {
      introBgm.muted = true;
      introBgm.volume = 0;
      await introBgm.play();
      bgmPlaying = true;
      setBgmUi(false);
      return true;
    } catch (err) {
      bgmPlaying = false;
      return false;
    }
  }

  /** 첫 제스처 이후 — 무음 해제 + 볼륨 페이드인 */
  async function unlockAudibleBgm() {
    if (!introBgm || bgmUserMuted || startingGame || bgmAudible) return false;
    if (bgmPlaying && !introBgm.paused) {
      return fadeInEl(introBgm, BGM_FADE_IN_MS);
    }
    try {
      introBgm.muted = false;
      introBgm.volume = 0;
      await introBgm.play();
      bgmPlaying = true;
      return fadeInEl(introBgm, BGM_FADE_IN_MS);
    } catch (err) {
      bgmAudible = false;
      setBgmUi(false);
      return false;
    }
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
        el.muted = true;
        el.volume = BGM_VOL;
        bgmFading = false;
        bgmPlaying = false;
        bgmAudible = false;
        resolve();
      }
      requestAnimationFrame(step);
    });
  }

  function bindBgmGestures() {
    if (bgmUnlockBound) return;
    bgmUnlockBound = true;
    // wheel/scroll은 Chrome에서 미디어 활성화로 인정되지 않음 → 클릭·탭·키만
    const unlock = () => {
      if (bgmUserMuted || startingGame || bgmAudible) return;
      unlockAudibleBgm();
    };
    ["pointerdown", "touchstart", "keydown", "click"].forEach((ev) => {
      window.addEventListener(ev, unlock, { passive: true });
    });
    if (bgmUnlockBtn) {
      bgmUnlockBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        unlockAudibleBgm();
      });
    }
    if (bgmToggle) {
      bgmToggle.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!introBgm) return;
        if (bgmAudible && !bgmUserMuted && !introBgm.paused) {
          bgmUserMuted = true;
          fadeToken += 1;
          bgmFading = false;
          pauseEl(introBgm);
          pauseEl(gameBgm);
          bgmPlaying = false;
          bgmAudible = false;
          setBgmUi(false);
          showBgmUnlock();
          return;
        }
        bgmUserMuted = false;
        bgmFading = false;
        await unlockAudibleBgm();
      });
    }
  }

  async function bootBgm() {
    let armed = await armMutedBgm();
    if (!armed && introBgm) {
      introBgm.addEventListener(
        "canplaythrough",
        () => {
          armMutedBgm();
        },
        { once: true }
      );
      setTimeout(() => armMutedBgm(), 400);
      setTimeout(() => armMutedBgm(), 1200);
    }
    bindBgmGestures();
    showBgmUnlock();
  }

  function assetUrl(imageKey) {
    const key = String(imageKey || "").replace(/^\/+/, "");
    if (!key) return "";
    if (key.startsWith("http")) return key;
    if (key.startsWith("assets/")) return `/${key}`;
    // jpg/png 요청이어도 webp가 있으면 우선 (용량·로딩)
    const webpKey = key.replace(/\.(jpe?g|png)$/i, ".webp");
    if (webpKey !== key) {
      return `${ASSET_BASE}/${webpKey}`;
    }
    return `${ASSET_BASE}/${key}`;
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function playDoorOpenSfx() {
    const a = new Audio(`${ASSET_BASE}/audio/sfx_door_open.mp3?v=1`);
    a.volume = 0.72;
    a.play().catch(() => {});
  }

  function resolveFinalDoorLayers(scene) {
    const image = String(scene.image || "").trim();
    const imageOpen = String(scene.image_open || "").trim();
    if (!image) return { closed: "", open: "" };
    if (imageOpen) return { closed: image, open: imageOpen };
    if (/truth_door_closed/i.test(image)) {
      return {
        closed: image,
        open: image.replace(/_closed(\.\w+)$/i, "$1"),
      };
    }
    // API가 예전처럼 열린 문만 내려줘도 닫힌 문→열림 페이드 적용
    if (/truth_door/i.test(image)) {
      return {
        closed: image.replace(/scene_truth_door(\.\w+)$/i, "scene_truth_door_closed$1"),
        open: image,
      };
    }
    return { closed: image, open: "" };
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
        const caption = escapeHtml(scene.caption || "");
        const text = escapeHtml(scene.text || "");
        const isFinal = i === last;
        const layers = isFinal ? resolveFinalDoorLayers(scene) : null;
        const baseKey = layers ? layers.closed : String(scene.image || "").trim();
        const openKey = layers ? layers.open : "";
        const baseImg = baseKey ? assetUrl(baseKey) : "";
        const openImg = openKey ? assetUrl(openKey) : "";
        let src = "";
        if (isFinal && baseImg && openImg && openImg !== baseImg) {
          src = `<img class="door-base" src="${escapeHtml(baseImg)}" alt="${caption || `scene ${i + 1}`}" />
              <img class="door-open" src="${escapeHtml(openImg)}" alt="" aria-hidden="true" />`;
        } else if (baseImg) {
          src = `<img src="${escapeHtml(baseImg)}" alt="${caption || `scene ${i + 1}`}" />`;
        }
        const cta = isFinal
          ? `<div class="scene-cta">
               <button type="button" class="scene-start-btn" data-start-game>
                 입장하기
               </button>
               <p class="scene-start-hint" data-start-status></p>
             </div>`
          : "";
        return `
        <section class="scene${isFinal ? " scene--final" : ""}" data-index="${i}">
          <div class="scene-sticky">
            <div class="scene-visual${isFinal && openImg && openImg !== baseImg ? " has-door-layers" : ""}" data-visual>
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

  function scrollToY(y) {
    autoScrolling = true;
    window.scrollTo({ top: Math.max(0, y), behavior: "smooth" });
    window.setTimeout(() => {
      autoScrolling = false;
      onScroll();
    }, AUTO_SCROLL_MS + 80);
  }

  function advanceFromScene(idx) {
    const nodes = [...document.querySelectorAll(".scene")];
    if (!nodes.length || startingGame) return;
    if (idx >= nodes.length - 1) return;
    scrollToY(nodes[idx + 1].offsetTop);
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
        scrollHint.textContent = "「입장하기」를 눌러 심문으로 이동";
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
        scrollHint.textContent = "화면을 클릭하거나 스크롤로 이동";
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

  async function revealFinalDoor() {
    const finalScene = document.querySelector(".scene--final");
    const visual = finalScene && finalScene.querySelector("[data-visual].has-door-layers");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (visual) {
      visual.classList.add("is-door-open");
      playDoorOpenSfx();
      await sleep(reduced ? DOOR_REVEAL_REDUCED_MS : DOOR_REVEAL_MS);
    } else {
      playDoorOpenSfx();
      await sleep(reduced ? 120 : 450);
    }
  }

  async function startInvestigation(btn) {
    if (startingGame) return;
    startingGame = true;
    hideBgmUnlock();
    const status = document.querySelector("[data-start-status]");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "입장하는 중…";
    }
    if (status) status.textContent = "";

    try {
      const doorReveal = revealFinalDoor();

      if (!sessionId) {
        const res = await fetch(`${API_BASE}/v1/session`, {
          method: "POST",
          credentials: "omit",
        });
        if (!res.ok) throw new Error(`session ${res.status}`);
        const data = await res.json();
        sessionId = data.session_id;
      }

      await doorReveal;
      await fadeOutEl(introBgm, 700);
      pauseEl(gameBgm);
      setBgmUi(false);

      try {
        sessionStorage.setItem("truth_room_enter", "1");
      } catch (e) {}
      window.location.href = gameUrl(sessionId);
    } catch (err) {
      console.error(err);
      startingGame = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = "입장하기";
      }
      if (status) {
        status.textContent =
          "세션 생성에 실패했습니다. 다시 시도하거나 /game 으로 이동하세요.";
      }
    }
  }

  function bindSceneInteractions() {
    if (!pinRoot) return;
    const cursorEl = document.getElementById("sceneCursor");
    const coarse =
      window.matchMedia("(hover: none), (pointer: coarse)").matches;

    const setCursorOn = (on) => {
      if (!cursorEl || coarse) return;
      cursorEl.classList.toggle("is-on", on);
    };

    const moveCursor = (e) => {
      if (!cursorEl || coarse) return;
      cursorEl.style.transform = `translate3d(${e.clientX - 8}px, ${e.clientY - 4}px, 0)`;
    };

    const syncCursorFromTarget = (target) => {
      if (!target || !(target instanceof Element)) {
        setCursorOn(false);
        return;
      }
      const scene = target.closest(".scene");
      const onTapScene =
        Boolean(scene) &&
        !scene.classList.contains("scene--final") &&
        Boolean(scene.classList.contains("is-active")) &&
        !target.closest("a, button, input, textarea, select, label, .topbar, .bgm-unlock");
      setCursorOn(onTapScene);
    };

    if (cursorEl && !coarse) {
      window.addEventListener(
        "pointermove",
        (e) => {
          moveCursor(e);
          syncCursorFromTarget(e.target);
        },
        { passive: true },
      );
      window.addEventListener(
        "pointerover",
        (e) => syncCursorFromTarget(e.target),
        { passive: true },
      );
      document.addEventListener("mouseleave", () => setCursorOn(false));
    }

    pinRoot.addEventListener("click", (e) => {
      const startBtn = e.target.closest("[data-start-game]");
      if (startBtn) {
        e.preventDefault();
        startInvestigation(startBtn);
        return;
      }
      if (startingGame || autoScrolling) return;
      if (e.target.closest(".scene--final")) return;
      if (e.target.closest("a, button, input, textarea, select, label")) return;
      const scene = e.target.closest(".scene");
      if (!scene || scene.classList.contains("scene--final")) return;
      const idx = Number(scene.getAttribute("data-index"));
      if (!Number.isFinite(idx) || idx < 0) return;
      e.preventDefault();
      advanceFromScene(idx);
    });
  }

  async function boot() {
    setBgmUi(false);
    await bootBgm();
    await fetchPublicCase();
    renderScenes(scenes);
    bindSceneInteractions();
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
  }

  boot();
})();

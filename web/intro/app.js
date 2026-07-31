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
    // docker/nginx 원페이지
    return "/game";
  }
  const GAME_BASE = defaultGameBase();

  const pinRoot = document.getElementById("pinRoot");
  const scrollHint = document.getElementById("scrollHint");
  const gameCurtain = document.getElementById("gameCurtain");
  const gameFrame = document.getElementById("gameFrame");
  const enterGameBtn = document.getElementById("enterGameBtn");
  const gameSection = document.getElementById("gameSection");
  const introBgm = document.getElementById("introBgm");
  const gameBgm = document.getElementById("gameBgm");
  const bgmToggle = document.getElementById("bgmToggle");

  let scenes = FALLBACK_SCENES;
  let caseMeta = { case_id: "case_01", title: "진실의 방" };
  let sessionId = null;
  let gameReady = false;
  let bgmUserMuted = false;
  let bgmStarted = false;
  let bgmFading = false;
  let inGameZone = false;
  const BGM_VOL = 0.45;
  let fadeToken = 0;
  /** 씬당 체류 후 자동 스크롤 (7~8초) */
  const AUTO_SCENE_MS = 7500;
  const AUTO_SCROLL_MS = 1100;
  let autoTimer = null;
  let autoSceneIndex = -1;
  let autoScrolling = false;

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
    if (!el || bgmUserMuted || bgmFading || inGameZone) return false;
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
    if (inGameZone) return false;
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

  function fadeInEl(el, ms = 800) {
    if (!el || bgmUserMuted) return Promise.resolve(false);
    const token = ++fadeToken;
    bgmFading = true;
    el.volume = 0;
    return el
      .play()
      .then(
        () =>
          new Promise((resolve) => {
            bgmStarted = true;
            setBgmUi(true);
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
              resolve(true);
            }
            requestAnimationFrame(step);
          })
      )
      .catch(() => {
        bgmFading = false;
        bgmStarted = false;
        setBgmUi(false);
        return false;
      });
  }

  async function crossfadeToGame() {
    // 게임 화면 BGM 비활성 — 인트로만 페이드아웃
    await fadeOutEl(introBgm, 900);
    pauseEl(gameBgm);
    setBgmUi(false);
  }

  async function crossfadeToIntro() {
    pauseEl(gameBgm);
    if (inGameZone || bgmUserMuted) {
      setBgmUi(false);
      return;
    }
    await fadeInEl(introBgm, 800);
  }

  function bindBgmGestures() {
    const unlock = () => {
      if (!bgmUserMuted && !inGameZone && introBgm && (introBgm.paused || !bgmStarted)) {
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
        if (inGameZone) {
          // 게임 구간에서는 BGM 없음
          bgmUserMuted = true;
          fadeToken += 1;
          bgmFading = false;
          pauseEl(introBgm);
          pauseEl(gameBgm);
          setBgmUi(false);
          return;
        }
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
    pinRoot.innerHTML = list
      .map((scene, i) => {
        const img = assetUrl(scene.image);
        const caption = escapeHtml(scene.caption || "");
        const text = escapeHtml(scene.text || "");
        const src = img
          ? `<img src="${escapeHtml(img)}" alt="${caption || `scene ${i + 1}`}" />`
          : "";
        return `
        <section class="scene" data-index="${i}">
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
    // 활성 판정 전이/직후 폴백
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
    if (!nodes.length || inGameZone) return;
    if (idx >= nodes.length - 1) {
      scrollToY(gameSection.offsetTop);
      return;
    }
    scrollToY(nodes[idx + 1].offsetTop);
  }

  function scheduleAutoAdvance(idx) {
    clearAutoAdvance();
    if (inGameZone || autoScrolling) return;
    if (idx < 0) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    autoTimer = window.setTimeout(() => {
      autoTimer = null;
      if (inGameZone || autoScrolling) return;
      advanceFromScene(idx);
    }, AUTO_SCENE_MS);
  }

  function onScroll() {
    const nodes = [...document.querySelectorAll(".scene")];
    let anyActive = false;
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
      if (active) anyActive = true;
    });

    if (window.scrollY > 40) scrollHint.classList.add("is-hide");
    else scrollHint.classList.remove("is-hide");

    const gameTop = gameSection.getBoundingClientRect().top;
    const nowInGame = gameTop < window.innerHeight * 0.75;
    if (nowInGame && !inGameZone) {
      inGameZone = true;
      clearAutoAdvance();
      autoSceneIndex = -1;
      crossfadeToGame();
      ensureGameSession();
    } else if (!nowInGame && inGameZone) {
      inGameZone = false;
      crossfadeToIntro();
    }

    if (!inGameZone && !autoScrolling) {
      const idx = activeSceneIndex(nodes);
      if (idx !== autoSceneIndex) {
        autoSceneIndex = idx;
        scheduleAutoAdvance(idx);
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

  async function ensureGameSession() {
    if (gameReady) return;
    gameReady = true;
    const sub = gameCurtain.querySelector(".game-curtain-sub");
    try {
      if (!sessionId) {
        const res = await fetch(`${API_BASE}/v1/session`, {
          method: "POST",
          credentials: "omit",
        });
        if (!res.ok) throw new Error(`session ${res.status}`);
        const data = await res.json();
        sessionId = data.session_id;
      }
      const url =
        `${GAME_BASE}/?intro_done=1&session_id=${encodeURIComponent(sessionId)}` +
        `&embed=1`;
      gameFrame.src = url;
      gameFrame.addEventListener(
        "load",
        () => {
          gameCurtain.classList.add("is-gone");
        },
        { once: true }
      );
      // iframe load 이벤트가 막히는 환경 대비
      setTimeout(() => gameCurtain.classList.add("is-gone"), 2500);
      if (sub) sub.textContent = "심문 UI를 불러오는 중…";
    } catch (err) {
      console.error(err);
      if (sub) sub.textContent = "세션 생성에 실패했습니다. 아래 버튼으로 이동하세요.";
      enterGameBtn.hidden = false;
      enterGameBtn.onclick = () => {
        window.location.href = `${GAME_BASE}/`;
      };
    }
  }

  async function boot() {
    setBgmUi(false);
    bindBgmGestures();
    autoplayBgm();
    await fetchPublicCase();
    renderScenes(scenes);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
  }

  boot();
})();

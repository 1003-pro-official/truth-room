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

  let scenes = FALLBACK_SCENES;
  let caseMeta = { case_id: "case_01", title: "진실의 방" };
  let sessionId = null;
  let gameReady = false;

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
    if (gameTop < window.innerHeight * 0.75) {
      ensureGameSession();
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
    await fetchPublicCase();
    renderScenes(scenes);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
  }

  boot();
})();

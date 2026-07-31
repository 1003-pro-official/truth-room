/**
 * Cloudflare Worker → Container (Streamlit UI + 내부 FastAPI)
 * WebSocket은 Container.fetch() 로만 프록시 (Streamlit 필수)
 */
import { Container, getContainer } from "@cloudflare/containers";

export interface Env {
  TRUTH_ROOM: DurableObjectNamespace;
  OPENAI_API_KEY?: string;
  APP_NAME?: string;
}

export class TruthRoomContainer extends Container<Env> {
  /** Streamlit public port (entrypoint) */
  defaultPort = 8080;
  /** 데모 세션 유지 — idle 후 sleep */
  sleepAfter = "30m";
  enableInternet = true;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.envVars = {
      API_URL: "http://127.0.0.1:8000",
      CORS_ALLOW_ALL: "1",
      OPENAI_API_KEY: env.OPENAI_API_KEY ?? "",
    };
  }

  override onStart(): void {
    console.log("truth-room container started");
  }

  override onStop(): void {
    console.log("truth-room container stopped");
  }

  override onError(error: unknown): void {
    console.error("truth-room container error", error);
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // 단일 데모 인스턴스 — 세션 상태(인메모리) 공유
    const container = getContainer(env.TRUTH_ROOM, "demo");
    return container.fetch(request);
  },
};

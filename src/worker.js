/**
 * Cloudflare Worker 入口 — 把所有請求轉給 Flask 容器
 * 容器閒置 15 分鐘後自動休眠（省費用），下次請求自動喚醒（冷啟動數秒）
 */
import { Container, getContainer } from "@cloudflare/containers";

export class PaperTradeContainer extends Container {
  defaultPort = 5000;
  sleepAfter = "15m";

  constructor(ctx, env) {
    super(ctx, env);
    // 把 Worker secret 傳進容器（wrangler secret put FINMIND_TOKEN）
    this.envVars = {
      PORT: "5000",
      FINMIND_TOKEN: env.FINMIND_TOKEN ?? "",
    };
  }
}

export default {
  async fetch(request, env) {
    return getContainer(env.PAPERTRADE).fetch(request);
  },
};

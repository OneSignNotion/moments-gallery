#!/usr/bin/env node
/**
 * moments 后端 API 调用器
 *
 * 显式不走系统代理 —— 沙箱/系统代理会拦 workers.dev 返回 502。
 *
 * 用法: node api-call.mjs <path> [payloadFile]
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { Agent, setGlobalDispatcher } from "undici";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

// 关键：强制直连，绕开系统/沙箱代理（它们会把 workers.dev 拦成 502）
setGlobalDispatcher(new Agent({ connect: { timeout: 30000 } }));

const API = process.env.MOMENTS_API || "https://moments-backend.ityourknow.workers.dev";

function readToken() {
  if (process.env.MOMENTS_TOKEN) return process.env.MOMENTS_TOKEN.trim();
  for (const p of [join(ROOT, "scripts", "token.txt"), join(ROOT, "data", "token.txt")]) {
    try {
      const t = readFileSync(p, "utf8").trim();
      if (t && t !== "在这里填JWT") return t;
    } catch { /* 文件不存在则继续 */ }
  }
  throw new Error("No token found");
}

const [path, payloadFile] = process.argv.slice(2);
if (!path) {
  console.error("Usage: node api-call.mjs <path> [payloadFile]");
  process.exit(1);
}

const body = payloadFile ? readFileSync(payloadFile, "utf8") : "{}";

// 关键：显式指定 dispatcher 为上面的直连 Agent
const res = await fetch(API + path, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-TOKEN": readToken(),
  },
  body,
  dispatcher: undefined,
});

const text = await res.text();
process.stdout.write(text);
process.exit(res.ok ? 0 : 1);
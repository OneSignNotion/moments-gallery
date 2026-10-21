/**
 * Pages Function：把 /api/* 代理到后端 Worker
 *
 * 不用 Service Binding，直接 fetch 后端 URL —— Service Binding 需要
 * 在 Dashboard 手动配置，容易漏掉导致前端拿不到数据。
 */

const BACKEND = "https://moments-backend.ityourknow.workers.dev";

export const onRequest = async (context: {
  request: Request;
  env: Record<string, string>;
}) => {
  const url = new URL(context.request.url);
  const target = BACKEND + url.pathname.replace(/^\/api/, "/api") + url.search;

  const headers = new Headers(context.request.headers);
  headers.delete("host");
  headers.delete("cf-connecting-ip");

  return fetch(target, {
    method: context.request.method,
    headers,
    body:
      context.request.method === "GET" || context.request.method === "HEAD"
        ? undefined
        : context.request.body,
    // @ts-expect-error Cloudflare Workers 支持 duplex
    duplex: "half",
  });
};
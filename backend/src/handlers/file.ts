import { Env, AppContext, ErrorCodes } from '../types';
import { successResp, failResp } from '../utils/response';

/**
 * 图片不再由后端存储 —— 媒体文件托管在 Pages 静态目录 (/media/)。
 * 这里只保留上传接口的兼容占位，避免旧调用方报错。
 *
 * 真正的媒体同步由 scripts/sync.py 完成：把文件复制到
 * frontend/public/media/ 后重新部署 Pages。
 */

export async function uploadFile(request: Request, env: Env, ctx: AppContext): Promise<Response> {
  return failResp(ErrorCodes.PARAM_ERROR, '图片已改为 Pages 静态托管，请运行 scripts/sync.py 同步');
}

export async function getFile(request: Request, env: Env, key: string): Promise<Response> {
  // 图片由 Pages 直接提供，不再经过 Worker
  return new Response('Not Found', { status: 404 });
}
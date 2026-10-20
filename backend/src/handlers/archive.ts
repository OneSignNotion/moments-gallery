import { Env, AppContext, ErrorCodes, Memo } from '../types';
import { successResp, failResp } from '../utils/response';

/**
 * 自动归档导入接口
 *
 * 由本地定时任务调用，把 Twitter 导出的 日期/推文ID/媒体 目录
 * 批量灌成「动态」。通过 Archive 表做幂等，重复调用不会重复导入。
 *
 * POST /api/archive/import
 * body: {
 *   author: string,        // 作者用户名
 *   date: string,          // 日期目录名，如 2026-10-20
 *   tweets: [{
 *     tweetId: string,
 *     createdAt?: string,  // ISO 时间，默认用 date 的当天 12:00
 *     content?: string,
 *     imgs: string[],      // 已在 R2 中的路径，形如 archive/<author>/<date>/<tweetId>/<file>
 *     tags?: string[],
 *   }]
 * }
 *
 * POST /api/archive/upload  —— 单文件上传（multipart，字段名 file，附加字段 key）
 *   用于把本地媒体文件传到 R2，返回可写入 imgs 的路径。
 */

export async function importArchive(request: Request, env: Env, ctx: AppContext): Promise<Response> {
  try {
    if (!ctx.user) {
      return failResp(ErrorCodes.TOKEN_MISSING);
    }

    const body = await request.json() as {
      author?: string;
      date?: string;
      tweets?: Array<{
        tweetId?: string;
        createdAt?: string;
        content?: string;
        imgs?: string[];
        tags?: string[];
      }>;
    };

    const author = body.author;
    const date = body.date;
    const tweets = body.tweets || [];

    if (!author || !date || !tweets.length) {
      return failResp(ErrorCodes.PARAM_ERROR, '缺少 author / date / tweets');
    }

    // 查已导入过的推文，实现幂等
    const ids = tweets.map(t => t.tweetId).filter(Boolean) as string[];
    if (!ids.length) {
      return failResp(ErrorCodes.PARAM_ERROR, 'tweets 中缺少 tweetId');
    }

    const placeholders = ids.map(() => '?').join(',');
    const existing = await env.DB.prepare(
      `SELECT tweetId FROM Archive WHERE author = ? AND tweetId IN (${placeholders})`
    ).bind(author, ...ids).all<{ tweetId: string }>();

    const done = new Set((existing.results || []).map(r => r.tweetId));

    let imported = 0;
    let skipped = 0;
    const now = new Date().toISOString();

    for (const t of tweets) {
      const tweetId = t.tweetId!;
      if (done.has(tweetId)) {
        skipped++;
        continue;
      }

      const imgs = (t.imgs || []).filter(Boolean);
      if (!imgs.length) {
        skipped++;
        continue;
      }

      // 归档动态一律公开(1)，挂在当前登录用户下
      const createdAt = t.createdAt || defaultTimeFor(date);
      const tags = t.tags && t.tags.length ? t.tags.join(',') + ',' : null;
      const content = t.content || '';

      const ins = await env.DB.prepare(
        `INSERT INTO Memo (
          content, imgs, userId, externalFavicon, pinned, ext, showType,
          tags, createdAt, updatedAt, favCount, commentCount
        ) VALUES (?, ?, ?, ?, 0, '{}', 1, ?, ?, ?, 0, 0)`
      ).bind(content, imgs.join(','), ctx.user.id, '/favicon.png', tags, createdAt, now).run();

      const memoId = ins.meta?.last_row_id as number | undefined;

      await env.DB.prepare(
        `INSERT OR IGNORE INTO Archive (author, tweetId, date, memoId, itemCount, createdAt)
         VALUES (?, ?, ?, ?, ?, ?)`
      ).bind(author, tweetId, date, memoId ?? null, imgs.length, now).run();

      imported++;
    }

    return successResp({
      total: tweets.length,
      imported,
      skipped,
      author,
      date,
    });
  } catch (error) {
    console.error('Import archive error:', error);
    return failResp(ErrorCodes.FAIL);
  }
}

function defaultTimeFor(date: string): string {
  // 'YYYY-M-D' 或 'YYYY-MM-DD' -> 当天 12:00:00Z
  const parts = date.split('-').map(Number);
  const [y, m, d] = parts.length === 3 ? parts : [1970, 1, 1];
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${y}-${pad(m)}-${pad(d)}T12:00:00.000Z`;
}

/**
 * 单文件上传到 R2，key 由调用方指定
 * 这样本地脚本能控制文件路径，保持 日期/推文ID/文件名 的结构
 */
export async function uploadArchiveFile(request: Request, env: Env, ctx: AppContext): Promise<Response> {
  try {
    if (!ctx.user) {
      return failResp(ErrorCodes.TOKEN_MISSING);
    }

    const formData = await request.formData();
    const file = formData.get('file');
    const key = formData.get('key');

    if (!file || typeof file === 'string' || !key || typeof key === 'string') {
      return failResp(ErrorCodes.PARAM_ERROR, '缺少 file 或 key');
    }

    const uploadFile = file as unknown as File;
    const MAX = 50 * 1024 * 1024;
    if (uploadFile.size > MAX) {
      return failResp(ErrorCodes.PARAM_ERROR, `文件超过 ${MAX / 1024 / 1024}MB`);
    }

    await env.BUCKET.put(key, uploadFile.stream(), {
      httpMetadata: { contentType: uploadFile.type || guessType(key) },
      customMetadata: {
        userId: String(ctx.user.id),
        originalName: uploadFile.name,
        uploadedAt: new Date().toISOString(),
      },
    });

    return successResp({ key, url: `/r2/${key}`, size: uploadFile.size });
  } catch (error) {
    console.error('Upload archive file error:', error);
    return failResp(ErrorCodes.FAIL, '上传失败');
  }
}

function guessType(key: string): string {
  const ext = key.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png',
    gif: 'image/gif', webp: 'image/webp',
    mp4: 'video/mp4', mov: 'video/quicktime', webm: 'video/webm',
  };
  return map[ext || ''] || 'application/octet-stream';
}

/** 查询导入统计 */
export async function archiveStats(request: Request, env: Env, ctx: AppContext): Promise<Response> {
  try {
    if (!ctx.user) {
      return failResp(ErrorCodes.TOKEN_MISSING);
    }
    const url = new URL(request.url);
    const author = url.searchParams.get('author');

    if (author) {
      const r = await env.DB.prepare(
        `SELECT date, COUNT(*) as cnt FROM Archive WHERE author = ?
         GROUP BY date ORDER BY date DESC`
      ).bind(author).all();
      return successResp({ author, days: r.results || [] });
    }

    const total = await env.DB.prepare(
      'SELECT author, COUNT(*) as tweets, SUM(itemCount) as items FROM Archive GROUP BY author'
    ).all();
    return successResp({ authors: total.results || [] });
  } catch (error) {
    console.error('Archive stats error:', error);
    return failResp(ErrorCodes.FAIL);
  }
}
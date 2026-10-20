import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { Env, AppContext, User } from './types';
import { verifyToken } from './utils/jwt';
import * as userHandler from './handlers/user';
import * as memoHandler from './handlers/memo';
import * as fileHandler from './handlers/file';
import * as archiveHandler from './handlers/archive';
import * as sysConfigHandler from './handlers/sysConfig';
import * as tagHandler from './handlers/tag';

const app = new Hono<{ Bindings: Env; Variables: { user?: User } }>();

// CORS middleware
app.use('/*', cors({
  origin: '*',
  allowMethods: ['GET', 'POST', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'X-API-TOKEN'],
  credentials: true,
}));

// Handle all OPTIONS requests
app.options('/*', (c) => {
  return c.body(null, 204);
});

// Auth middleware
app.use('/api/*', async (c, next) => {
  const token = c.req.header('X-API-TOKEN');

  if (token) {
    try {
      const payload = await verifyToken(token, c.env.JWT_SECRET);
      if (payload) {
        const user = await c.env.DB.prepare(
          'SELECT * FROM User WHERE id = ?'
        ).bind(payload.userId).first<User>();

        if (user) {
          c.set('user', user);
        }
      }
    } catch (error) {
      console.error('Auth middleware error:', error);
    }
  }

  await next();
});

// User routes
app.post('/api/user/login', async (c) => {
  return userHandler.login(c.req.raw, c.env);
});

app.post('/api/user/reg', async (c) => {
  return userHandler.register(c.req.raw, c.env);
});

app.post('/api/user/profile', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  return userHandler.getProfile(c.req.raw, c.env, ctx);
});

app.post('/api/user/profile/:username', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  const username = c.req.param('username');
  return userHandler.getProfileByUsername(c.req.raw, c.env, username);
});

app.post('/api/user/saveProfile', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  return userHandler.saveProfile(c.req.raw, c.env, ctx);
});

// Memo routes
app.post('/api/memo/list', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  return memoHandler.listMemos(c.req.raw, c.env, ctx);
});

app.post('/api/memo/get', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  const id = c.req.query('id') || '';
  return memoHandler.getMemo(c.req.raw, c.env, ctx, id);
});

app.post('/api/memo/like', async (c) => {
  const id = c.req.query('id') || '';
  return memoHandler.likeMemo(c.req.raw, c.env, id);
});

app.post('/api/memo/setPinned', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  const id = c.req.query('id') || '';
  return memoHandler.setPinned(c.req.raw, c.env, ctx, id);
});

app.post('/api/memo/getFaviconAndTitle', async (c) => {
  return memoHandler.getFaviconAndTitle(c.req.raw, c.env);
});

// Archive routes (自动归档导入)
app.post('/api/archive/import', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  return archiveHandler.importArchive(c.req.raw, c.env, ctx);
});

app.post('/api/archive/stats', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  return archiveHandler.archiveStats(c.req.raw, c.env, ctx);
});

// File routes
// 图片托管在 Pages 静态目录 (/media/)，这里只保留兼容占位
app.post('/api/file/upload', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  return fileHandler.uploadFile(c.req.raw, c.env, ctx);
});

// SysConfig routes (站点标题、主题等)
app.post('/api/sysConfig/get', async (c) => {
  return sysConfigHandler.getSysConfig(c.req.raw, c.env);
});

app.post('/api/sysConfig/getFull', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  return sysConfigHandler.getFullSysConfig(c.req.raw, c.env, ctx);
});

app.post('/api/sysConfig/save', async (c) => {
  const ctx: AppContext = { user: c.get('user') };
  return sysConfigHandler.saveSysConfig(c.req.raw, c.env, ctx);
});

// Tag routes (按作者筛选)
app.post('/api/tag/list', async (c) => {
  return tagHandler.listTags(c.req.raw, c.env);
});

// Health check
app.get('/', (c) => {
  return c.json({ message: 'Moments API is running', version: c.env.APP_VERSION || '1.0.0' });
});

export default app;
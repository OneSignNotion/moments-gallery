# Moments 图库 · 部署指南

Twitter 图片归档成朋友圈时间线。**GitHub LFS 存图 + Cloudflare Pages 自动部署**，全程免费、无需信用卡。

## 架构

```
D:\Devops\TwitterPhoto\<作者>\日期\推文ID\文件
        │  scripts\import-data.ps1（每天定时）
        │
        ├──→ frontend\public\media\...\     图片，走 Git LFS 提交
        │              ↓
        │         git push
        │              ↓
        │    GitHub 仓库
        │              ↓ 自动触发
        │    Cloudflare Pages（构建 → 静态托管 /media/）
        │
        └──→ POST /api/archive/import       元数据，写 D1
                       ↓
                  后端 Worker（读 D1）
                       ↑
              Pages Functions 代理 /api/*
```

**关键点**：图片不在 Cloudflare 上传，而是推到 GitHub，Pages 拉代码时一并带上。Cloudflare 只负责构建和托管。

## 资源

| 项 | 值 |
|---|---|
| Cloudflare 账号 | `ityourknow@163.com` / `3cf8bd9abc6ac865fdb361b4b4decece` |
| D1 数据库 | `moments-db` / `42674d6d-e9e9-4543-8a36-0f45ec195d8b` |
| 后端 Worker | `https://moments-backend.ityourknow.workers.dev` |
| Pages 项目 | `moments-gallery` |
| GitHub 仓库 | `OneSignNotion/moments-gallery`（待创建） |
| admin 密码 | `Still@2026Gallery` |

## 首次配置（需要你操作）

### 1. 在 GitHub 建仓库

访问 https://github.com/new

- 仓库名：`moments-gallery`
- **Public**（重要：私有仓库的 Pages 要付费）
- 不要勾选 README / .gitignore / License

### 2. 推送代码

```bash
cd C:\Users\Still\WorkBuddy\2026-10-20-16-51-06\moments-src
git push -u origin main
```

会要求登录 GitHub（Personal Access Token 或浏览器授权）。

### 3. Cloudflare 接GitHub + API Token

**建 API Token**（自动部署必须，自带的 build token 权限不足）：

Dashboard → My Profile → API Tokens → Create Custom Token

| 权限 | 级别 |
|---|---|
| Account → Cloudflare Pages | Edit |
| Account → Account Settings | Read |
| Account → Workers Scripts | Edit |

Account Resources 选 **All accounts**。IP filtering 留空，TTL 留空。

**填进构建配置**：项目 Settings → Builds & deployments → API token 换成新建的。

**GitHub Secrets**（供 GitHub Actions 备用）：

仓库 Settings → Secrets and variables → Actions → New repository secret

| Name | Value |
|---|---|
| `CLOUDFLARE_API_TOKEN` | 新建的 token |
| `CLOUDFLARE_ACCOUNT_ID` | `3cf8bd9abc6ac865fdb361b4b4decece` |

**构建配置**：

| 配置项 | 值 |
|---|---|
| Build command | `cd frontend && npm install && npm run build` |
| Deploy command | `npm install && npx wrangler pages deploy frontend/.output/public --project-name moments-gallery --branch main --commit-dirty=true` |
| Path | `/` |
| Enable Preview builds | 关闭（省 LFS 流量） |
| API token | 换成新建的 |

⚠️ **deploy command 里的 `npm install` 不能省**。构建环境没有预装 wrangler，会现场下载最新版，认证行为会变导致 `code: 10000`。根目录 `package.json` 固定了 `wrangler@4.151.2`，这个 `npm install` 就是把它装上。

⚠️ **`wrangler.toml` 必须在仓库根目录**。Workers Builds 的 deploy command 在仓库根执行 wrangler，配置放子目录会找不到，走不同代码路径。

## 日常使用

### 手动同步

```powershell
cd C:\Users\Still\WorkBuddy\2026-10-20-16-51-06\moments-src

# 导入一天并推送
.\scripts\import-data.ps1 -Author 4KAestheticHQ

# 导入全部并推送
.\scripts\import-data.ps1 -Author 4KAestheticHQ -AllDates

# 只导文件不推送（调试用）
.\scripts\import-data.ps1 -Author 4KAestheticHQ -Limit 5 -SkipPush
```

脚本会：复制文件 → 写 D1 → `git add` → `git commit` → `git push`，Pages 自动部署。

### 定时任务

```powershell
$root = "C:\Users\Still\WorkBuddy\2026-10-20-16-51-06\moments-src"
$action = New-ScheduledTaskAction -Execute "$root\scripts\daily-sync.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName "MomentsSync" -Action $action -Trigger $trigger `
  -Description "每日同步 Twitter 归档到图库"
```

删除：

```powershell
Unregister-ScheduledTask -TaskName "MomentsSync" -Confirm:$false
```

## 配额核对

| 项 | 你的数据 | 上限 | 占比 |
|---|---|---|---|
| LFS 存储 | 304 MB | 10 GB | 3% |
| LFS 带宽 | 按需 | 10 GB/月 | 低 |
| Pages 文件数 | 908 | 20,000 | 4.5% |
| Pages 最大单文件 | 15 MB | 25 MiB | 60% |
| Pages 流量 | — | 无限 | — |

**注意**：Pages 每次构建会重新拉整个仓库，LFS 流量随之消耗。构建越频繁消耗越大。脚本在无新文件时会跳过提交，所以不会触发无谓构建。

## 踩过的坑

### 1. 当天数据不显示（重要）

**症状**：当天导入的动态，后端能查到但页面空白。

**原因**：`listMemos` 对未登录访客过滤 `datetime(createdAt) <= datetime('now')`。原本把归档时间写成当天 `12:00:00Z`，而当前才上午，这条就成了「未来」被隐藏。

**修复**：`archive.ts` 加了 `clampToNow()`，写入时把时间压到当前时间以内。数据库里的存量记录用这条 SQL 修正：

```bash
npx wrangler d1 execute moments-db --remote \
  --command="UPDATE Memo SET createdAt = datetime('now') WHERE datetime(createdAt) > datetime('now')"
```

### 2. Service Binding 不可靠

原设计用 Pages Functions + `BACKEND` Service Binding 转发到后端。这个绑定要在 Dashboard 手动配，漏了就静默失败（前端返回 0 条但不报错）。

**修复**：`functions/api/[[path]].ts` 改成直接 `fetch` 后端 URL，硬编码在代码里，不依赖 Dashboard 配置。

### 3. 换 Cloudflare 账号要清缓存

```bash
rm -rf .wrangler backend/.wrangler frontend/.wrangler
```

否则沿用旧 account id，报 `code: 10000 Authentication error`。

### 4. 本机 DNS 被污染

`nslookup moments-backend.ityourknow.workers.dev` 返回 `199.16.158.104`（Twitter IP 段）。

**症状**：curl exit 56 / 502、Node `getaddrinfo ENOTFOUND`。

**解决**：脚本里设 `$env:NO_PROXY="*"` 并清代理环境变量（`import-data.ps1` 已内置）。这只影响脚本调用，不影响浏览器访问。

### 5. .ps1 必须是 UTF-8 with BOM

Windows PowerShell 5.1 默认按 GBK 读，中文乱码报「缺少 Catch 或 Finally 块」。

```bash
python scripts\fix-encoding.py scripts\import-data.ps1
```

保险起见，`import-data.ps1` 里的提示文字全用英文。

### 6. Pages 私有仓库要付费

GitHub 仓库必须是 **Public**，否则 Pages 无法使用。

### 7. Cloudflare Workers Builds 认证失败

**症状**：构建成功（日志有 `✓ Build complete`），但部署阶段报：

```
X [ERROR] /accounts/xxx/pages/projects/moments-gallery failed.
  Authentication error [code: 10000]
```

日志里会有一行提示：

```
Membership roles in "xxx's Account": Contact account super admin to change your permissions.
```

**根因**：Cloudflare 自动生成的 build token 是 **User API Token**，调 Pages API 时权限受账号成员角色限制，权限不足。

**修复**：自建 API Token（Pages:Edit + Account Settings:Read + Workers Scripts:Edit），在构建配置里替换掉默认的 build token。

**顺带的两个坑**（即使换了 token 也要处理）：

1. deploy command 里的 `npx wrangler` 会现场下载**最新版**，新版认证行为变化 → 加 `npm install` 前置，根 `package.json` 固定版本
2. `wrangler.toml` 必须在**仓库根目录**，否则 wrangler 找不到配置会走不同代码路径

### 8. Git Provider 显示 No

`wrangler pages project list` 里 Git Provider 显示 `No`，说明 Cloudflare 与 GitHub 的绑定没建立（通常是没完成 OAuth 授权），此时 push 不会触发构建。

## 数据映射

```
本地                                       moments
D:\...\2026-10-20\2112213296166445469\     Memo.createdAt = 2026-10-20
  └─ HVAWyL5WQAAMp4D.jpg                   Memo.tags = "4KAestheticHQ,"
                                           Memo.imgs = /media/4KAestheticHQ/2026-10-20/2112.../HVAWyL5WQAAMp4D.jpg
                                           git: frontend/public/media/4KAestheticHQ/2026-10-20/2112.../
Archive 表                                 (author, tweetId) 唯一约束
```

一条推文 = 一条动态。

## 幂等

1. **文件级**：目标文件已存在就跳过复制
2. **推文级**：`Archive` 表 `(author, tweetId)` 唯一约束

定时任务可安全重复运行。

## 已知限制

**mp4 不显示**。`UploadImagePreview.vue` 只渲染 `<img>`，遇到视频显示破图。你有 45 个 mp4，需改组件加视频标签。

## 新增作者

```powershell
.\scripts\import-data.ps1 -Author Sn0opyLove85186 -AllDates
```

前端会自动出现标签切换。

## 目录结构

```
moments-src/
├── backend/              Workers 后端（Hono + D1）
│   ├── src/handlers/     archive / memo / file / sysConfig / tag / user
│   ├── schema.sql        含 Archive 幂等表
│   └── wrangler.toml     无 R2
├── frontend/             Nuxt 3 前端
│   ├── components/       Memo / Header / MobileNav / UploadImagePreview
│   ├── functions/api/    Pages Function 代理到后端
│   ├── public/media/     ★ 图片（走 LFS）
│   └── wrangler.toml
├── scripts/
│   ├── import-data.ps1   导入 + git push（主脚本）
│   ├── daily-sync.bat    定时任务入口
│   └── fix-encoding.py   .ps1 转 UTF-8 BOM
├── data/token.txt        JWT（已 gitignore）
└── DEPLOY.md
```
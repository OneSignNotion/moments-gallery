# Moments 图库部署指南

基于 [Moretti815/moments](https://github.com/Moretti815/moments)，把 Twitter 导出的图片自动归档成朋友圈时间线。

**无信用卡方案**：不使用 R2，图片放 Pages 静态目录 `/media/`，元数据放 D1。全程免费。

## 架构

```
D:\Devops\TwitterPhoto\<作者>\日期\推文ID\文件
        │  scripts\import-data.ps1（PowerShell，绕过代理）
        ├──→ frontend\public\media\<作者>\日期\推文ID\文件   媒体文件
        └──→ POST /api/archive/import                       D1 元数据
                        ↓
        Cloudflare Pages（前端 + 媒体，一次部署）
                        ↓
                    你的域名
```

## 资源状态

| 项 | 值 |
|---|---|
| Cloudflare 账号 | `ityourknow@163.com` / `3cf8bd9abc6ac865fdb361b4b4decece` |
| D1 数据库 | `moments-db` / `42674d6d-e9e9-4543-8a36-0f45ec195d8b` |
| 后端 Worker | `https://moments-backend.ityourknow.workers.dev` |
| admin 密码 | `Still@2026Gallery` |
| Pages 项目 | `moments-gallery`（待创建） |
| R2 | **不使用**（免绑卡） |

## 已删除的功能

按需求精简为纯图片浏览：评论、友链、豆瓣、网易云、Bilibili、注册、发布动态、后台管理。

保留：时间线、标签筛选、日历检索、灯箱、深色模式、点赞、系统设置。

## Pages 配额核对

| 项 | 你的数据 | Pages 免费限制 | 占比 |
|---|---|---|---|
| 文件数 | 908 | 20,000 | 4.5% |
| 最大单文件 | 15 MB | 25 MiB | 60% |
| 总容量 | 304 MB | 无限制 | — |
| 带宽 | — | 无限 | — |

## 常用命令

```powershell
# 导入全部（先只导一天试试）
.\scripts\import-data.ps1 -Author 4KAestheticHQ
.\scripts\import-data.ps1 -Author 4KAestheticHQ -AllDates

# 只导指定日期
.\scripts\import-data.ps1 -Author 4KAestheticHQ -Date 2026-10-20

# 限量试跑
.\scripts\import-data.ps1 -Author 4KAestheticHQ -Limit 10

# 查导入统计
Invoke-RestMethod -Uri "$api/api/archive/stats" -Method POST -Body '{}' `
  -Headers @{ "X-API-TOKEN" = $token } -ContentType "application/json"
```

## 部署

```powershell
cd frontend
npm run build
npx wrangler pages deploy .output/public --project-name moments-gallery
```

首次需要先建项目：

```powershell
npx wrangler pages project create moments-gallery --production-branch main
```

## 定时任务

`scripts\daily-sync.bat` 会在每天定时执行：导入 → 构建 → 部署。

```bash
schtasks /create /tn "MomentsSync" ^
  /tr "C:\...\moments-src\scripts\daily-sync.bat" /sc daily /st 03:00
```

## 踩过的坑

### 1. 换账号后必须清缓存

```bash
rm -rf .wrangler backend/.wrangler frontend/.wrangler
```

否则 wrangler 沿用旧 account id，报 `code: 10000 Authentication error`。

### 2. 沙箱/系统 DNS 被污染

`nslookup moments-backend.ityourknow.workers.dev` 返回 `199.16.158.104`（Twitter IP 段），不是 Cloudflare。

**表现为**：curl exit 56、502 Bad Gateway、Node `getaddrinfo ENOTFOUND`。

**解决**：用 PowerShell 设 `$env:NO_PROXY="*"` 并清掉代理环境变量。`scripts\import-data.ps1` 已内置。

### 3. .ps1 文件必须是 UTF-8 with BOM

Windows PowerShell 5.1 默认按 GBK 读文件，中文会乱码导致「缺少 Catch 或 Finally 块」语法错误。

转换：`python scripts\fix-encoding.py scripts\import-data.ps1`

### 4. Pages 部署命令要带项目名

```
X [ERROR] The Pages project "xxx" does not exist.
```

先 `npx wrangler pages project create <name> --production-branch main`。

### 5. 从 Bash 调 PowerShell 会被拦

`Command blocked for security: Invoking PowerShell from Bash`。改用 PowerShell 工具直接执行。

## 数据映射

```
本地                                       moments
D:\...\2026-10-20\2112213296166445469\     Memo.createdAt = 2026-10-20 12:00Z
  └─ HVAWyL5WQAAMp4D.jpg                   Memo.tags = "4KAestheticHQ,"
                                           Memo.imgs = /media/4KAestheticHQ/2026-10-20/2112.../HVAWyL5WQAAMp4D.jpg
                                           frontend\public\media\4KAestheticHQ\2026-10-20\2112...\
Archive 表                                 (author, tweetId) 唯一约束，防重复导入
```

一条推文 = 一条动态。

## 幂等机制

1. **文件级**：文件已存在且大小一致 → 跳过复制
2. **推文级**：`Archive` 表 `(author, tweetId)` 唯一约束 → 跳过写库

定时任务可安全每天重复运行。

## 已知限制

**mp4 视频不显示**。`UploadImagePreview.vue` 只渲染 `<img>` 标签，遇到 mp4 会显示破图。

解决需要改前端，加视频标签判断。这是下一步要做的。

## 新增作者

```powershell
.\scripts\import-data.ps1 -Author Sn0opyLove85186 -AllDates
```

前端会自动出现标签切换按钮。
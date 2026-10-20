# Moments 归档部署指南

基于 [Moretti815/moments](https://github.com/Moretti815/moments)，把 Twitter 导出的图片自动归档成朋友圈时间线。

## 当前进度

| 环节 | 状态 |
|---|---|
| Cloudflare 登录 | 已完成 — `ityourknow@163.com`，Account `3cf8bd9abc6ac865fdb361b4b4decece` |
| D1 数据库 | 已创建 `moments-db`，6 张表 + 10 索引就绪，`42674d6d-e9e9-4543-8a36-0f45ec195d8b` |
| Archive 幂等表 | 已建 |
| 3 个导入接口 | 已写完，类型检查零错误 |
| `sync.py` 导入脚本 | 已写完，扫描验证通过 |
| JWT 密钥 | 已设为 Worker secret |
| **后端 Worker** | **已上线** `https://moments-backend.ityourknow.workers.dev` |
| **R2 存储桶** | **待开通 —— 唯一阻塞项** |
| Pages 前端 | 依赖已装，待部署 |

> 当前部署的 Worker 临时不含 R2 绑定（因 R2 未开通）。开通后重新 `wrangler deploy` 即可带上绑定。

## 第一步：开通 R2（必须手动）

Dashboard → R2 → **Enable R2 / 开通**

会要求绑定支付方式（信用卡/PayPal），**仅用于身份验证，不产生费用**。开通后免费额度 10GB。

开通后创建桶：

```bash
cd moments-src/backend
npx wrangler r2 bucket create moments-storage
```

## 第二步：部署后端

⚠️ **换过账号的话，必须先清缓存**，否则 wrangler 会用旧账号的 ID：

```bash
rm -rf .wrangler backend/.wrangler frontend/.wrangler
```

JWT 密钥（走 secret，不进 git）：

```bash
cd moments-src/backend
npx wrangler secret put JWT_SECRET
```

粘贴这串随机值（或自己生成更长的）：
```
SZ8vliOMi5bdXcvwsk_yUcU6ladrB7A7CIPM7bF8WHEpKxWkTxuSStzaLIF-k03M
```

部署：

```bash
npx wrangler deploy
```

记下输出的 Worker 地址，形如：
`https://moments-backend.xxx.workers.dev`

> **如果 R2 还没开通**，部署会因 `wrangler.toml` 里的 R2 绑定而失败。
> 临时解法：注释掉 `[[r2_buckets]]` 整段再部署，Worker 能上去，
> 但图片相关接口会报错。开通 R2 后删掉注释重新部署即可。

## 第三步：拿登录 Token

先在 D1 里给 admin 改密码（默认 `admin/admin123`，**必须改**）：

```bash
cd moments-src/backend
npx wrangler d1 execute moments-db --remote --command="UPDATE User SET password='<bcrypt新hash>' WHERE id=1"
```

> bcrypt hash 可以在 https://www.security.org/hash-api/ 生成，或者用 node 的 bcryptjs。

然后登录拿 Token：

```bash
curl -X POST https://moments-backend.xxx.workers.dev/api/user/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"admin\",\"password\":\"你的新密码\"}"
```

返回里的 `data.token` 就是 JWT。

## 第四步：配置脚本

```bash
cd moments-src/scripts
cp sync.local.cmd.example sync.local.cmd
```

编辑 `sync.local.cmd`，填入 API 地址和 Token。

## 第五步：试跑

```bash
cd moments-src
python scripts/sync.py --author 4KAestheticHQ --date 2026-10-20 --limit 3
```

先只导 3 条推文验证。打开 Worker 地址应该能看到动态。

全量导入：

```bash
python scripts/sync.py --author 4KAestheticHQ --all
```

## 第六步：部署前端

```bash
cd moments-src/frontend
npm run build
npx wrangler pages deploy .output/public --project-name moments-cloudflare
```

Pages 项目设置里确认 Service Binding `BACKEND` → `moments-backend`。

## 第七步：绑域名

Pages 项目 → Custom domains → 填你的域名。

## 第八步：定时任务

```bash
schtasks /create /tn "MomentsSync" ^
  /tr "C:\...\moments-src\scripts\daily-sync.bat" /sc daily /st 03:00
```

删除：

```bash
schtasks /delete /tn "MomentsSync" /f
```

## 数据映射规则

```
本地                                    moments
D:\...\4KAestheticHQ\2026-10-20\         Memo.createdAt = 2026-10-20 12:00Z
  └─ 2112213296166445469\                Memo.tags = "4KAestheticHQ,"
     └─ HVAWyL5WQAAMp4D.jpg             R2: 4KAestheticHQ/2026-10-20/2112.../HVAWyL5WQAAMp4D.jpg
                                        Memo.imgs = 逗号分隔的上述路径
Archive 表                              记录 (author, tweetId) 保证不重复导入
```

一条推文 = 一条动态，日期目录 = 发布日期。前端的日历视图、标签筛选都能直接用。

## 幂等机制（双保险）

1. **本地** `data/manifest.json` — 记录每个文件的大小和修改时间，没变就跳过上传
2. **云端** `Archive` 表 — `(author, tweetId)` 唯一约束，重复导入会被跳过

所以定时任务可以放心每天跑，不会产生重复内容。

## 常见问题

| 现象 | 处理 |
|---|---|
| `code: 10042 Please enable R2` | 去 Dashboard 开通 R2 |
| `code: 10000 Authentication error` 且 URL 里是陌生 account id | 换过账号，缓存没清：`rm -rf .wrangler backend/.wrangler` |
| 本地 curl 报 502 / exit 56 | 沙箱代理不通。改用本机代理 `--proxy socks5h://127.0.0.1:1080`，或在沙箱外执行 |
| 导入报 401 | Token 过期或密码改过，重新登录拿 Token |
| 图片 404 | 检查 R2 里文件是否存在，`imgs` 路径是否以 `/r2/` 开头 |
| 视频不显示 | `UploadImagePreview.vue` 只渲染 img，视频需走 `ext.video` 字段 |
| 想加作者 | 改 `daily-sync.bat` 里的 `--author`，前端会出现标签切换 |
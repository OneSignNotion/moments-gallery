#!/usr/bin/env bash
# Cloudflare 自动部署用的 API Token
#
# 供 GitHub Actions 使用（通过 Secrets 注入）。
# 本文件仅供记录，Token 本身请勿提交到 git。
#
# Cloudflare Dashboard → My Profile → API Tokens → Create Custom Token
# 所需权限：
#   Account → Cloudflare Pages  → Edit
#   Account → Account Settings  → Read
#   Account → Workers Scripts   → Edit
#   Account Resources           → All accounts
#
# 同时需要 CLOUDFLARE_ACCOUNT_ID = 3cf8bd9abc6ac865fdb361b4b4decece

CLOUDFLARE_ACCOUNT_ID=3cf8bd9abc6ac865fdb361b4b4decece

# Token 请在 GitHub 仓库 Settings → Secrets and variables → Actions 中配置：
#   CLOUDFLARE_API_TOKEN
# 不要把 Token 明文写进任何提交的文件。

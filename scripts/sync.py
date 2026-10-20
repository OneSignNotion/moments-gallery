#!/usr/bin/env python3
"""
Twitter 归档 -> moments 导入器（Pages 静态托管版）

流程：
  1. 扫描 D:\\Devops\\TwitterPhoto\\<作者>\\ 的 日期/推文ID/媒体
  2. 把媒体文件复制到 frontend/public/media/<作者>/<日期>/<推文ID>/
  3. 调用后端 API 把推文写成动态（D1 元数据）

图片不进后端 —— 由 Pages 静态托管，跟前端一起部署。
幂等靠两层：本地 manifest.json（文件级）+ 云端 Archive 表（推文级）。

用法:
  python sync.py --author 4KAestheticHQ --date 2026-10-20
  python sync.py --author 4KAestheticHQ --all
  python sync.py --author 4KAestheticHQ --all --dry-run
  python sync.py --author 4KAestheticHQ --all --limit 5    # 试跑
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
MANIFEST = DATA_DIR / "manifest.json"
LOG_DIR = BASE / "logs"
MEDIA_OUT = BASE / "frontend" / "public" / "media"

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".m4v", ".webm"}

API_BASE = os.environ.get("MOMENTS_API", "")
API_TOKEN = os.environ.get("MOMENTS_TOKEN", "")


def log(msg):
    print(msg, flush=True)


def load_manifest():
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log("[!] manifest 损坏，重建")
    return {}


def save_manifest(m):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(MANIFEST)


def api_post_json(path, payload):
    """调用后端 API。

    默认用 urllib；若设置 MOMENTS_API_CMD（如 scripts/call-api.ps1），
    则改用外部命令调用，便于绕过系统代理。
    """
    external = os.environ.get("MOMENTS_API_CMD", "")
    if external:
        tmp = DATA_DIR / "_payload.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        try:
            r = subprocess.run(
                f'{external} -Path "{path}" -BodyFile "{tmp}"',
                capture_output=True, text=True, timeout=300, shell=True,
            )
        finally:
            tmp.unlink(missing_ok=True)
        out = (r.stdout or "").strip()
        if r.returncode != 0 or not out:
            raise RuntimeError(f"外部命令失败: {(r.stderr or out)[:200]}")
        return json.loads(out)

    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-TOKEN": API_TOKEN},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def scan(source_root: Path, author: str, date_filter=None):
    """扫描 日期/推文ID/文件 结构"""
    author_dir = source_root / author
    if not author_dir.is_dir():
        log(f"[x] 目录不存在: {author_dir}")
        return []

    days = []
    for date_dir in sorted(author_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        date = date_dir.name
        if date_filter and date != date_filter:
            continue

        tweet_dirs = [d for d in sorted(date_dir.iterdir()) if d.is_dir()]
        loose = [f for f in sorted(date_dir.iterdir())
                 if f.is_file() and f.suffix.lower() in MEDIA_EXTS]

        tweets = []
        if tweet_dirs:
            for td in tweet_dirs:
                files = [f for f in sorted(td.iterdir())
                         if f.is_file() and f.suffix.lower() in MEDIA_EXTS]
                if files:
                    tweets.append({"tweetId": td.name, "files": files})
        elif loose:
            tweets.append({"tweetId": "", "files": loose})

        if tweets:
            days.append({"date": date, "tweets": tweets})

    return days


def date_to_iso(date: str) -> str:
    parts = date.split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    return datetime(y, m, d, 12, 0, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=r"D:\Devops\TwitterPhoto")
    p.add_argument("--author", required=True)
    p.add_argument("--date")
    p.add_argument("--all", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="只扫描，不复制不写库")
    p.add_argument("--force", action="store_true", help="忽略 manifest 重新复制")
    p.add_argument("--limit", type=int, help="最多处理多少条推文")
    p.add_argument("--api")
    p.add_argument("--token")
    args = p.parse_args()

    global API_BASE, API_TOKEN
    if args.api:
        API_BASE = args.api
    if args.token:
        API_TOKEN = args.token

    if not args.date and not args.all:
        log("[x] 请指定 --date 或 --all")
        sys.exit(1)
    if not args.dry_run:
        if not API_TOKEN:
            log("[x] 缺少 API token。用 --token 传入，或设置 MOMENTS_TOKEN")
            sys.exit(1)
        if not API_BASE:
            log("[x] 缺少 API 地址。用 --api 传入，或设置 MOMENTS_API")
            sys.exit(1)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    days = scan(Path(args.source), args.author, args.date)
    if not days:
        log(f"[!] {args.author} 下没找到媒体文件")
        return

    total_tweets = sum(len(d["tweets"]) for d in days)
    total_files = sum(len(t["files"]) for d in days for t in d["tweets"])
    log(f"扫描 {args.author}: {len(days)} 天, {total_tweets} 条推文, {total_files} 个文件")

    if args.limit:
        count = 0
        trimmed = []
        for d in days:
            keep = []
            for t in d["tweets"]:
                if count >= args.limit:
                    break
                keep.append(t)
                count += 1
            if keep:
                trimmed.append({"date": d["date"], "tweets": keep})
        days = trimmed
        log(f"--limit 生效: 只处理前 {args.limit} 条推文")

    if args.dry_run:
        for d in days:
            log(f"  {d['date']}: {len(d['tweets'])} 条")
            for t in d["tweets"][:3]:
                sz = sum(f.stat().st_size for f in t["files"])
                log(f"    {t['tweetId'] or '(无ID)'}  {len(t['files'])} 个文件  {sz//1024}KB")
        log("[dry-run] 未做任何写入")
        return

    manifest = load_manifest()
    t0 = time.time()
    copied = skipped = 0
    grand_imp = grand_sskip = 0

    for d in days:
        date = d["date"]
        log(f"\n=== {date} ===")

        tweet_payload = []
        day_copied = day_skipped = 0

        for t in d["tweets"]:
            tid = t["tweetId"]
            rel_dir = f"{args.author}/{date}/{tid}" if tid else f"{args.author}/{date}"
            out_dir = MEDIA_OUT / rel_dir
            keys = []

            for f in t["files"]:
                rel = f"{rel_dir}/{f.name}"
                dest = MEDIA_OUT / rel
                mk = f"{args.author}|{rel}"
                st = f.stat()

                if dest.exists() and not args.force:
                    rec = manifest.get(mk)
                    if rec and rec.get("size") == st.st_size:
                        skipped += 1
                        day_skipped += 1
                        keys.append(f"/media/{rel}")
                        continue

                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
                    manifest[mk] = {
                        "size": st.st_size,
                        "mtime": int(st.st_mtime),
                        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    copied += 1
                    day_copied += 1
                    keys.append(f"/media/{rel}")
                except Exception as e:
                    log(f"  [x] 复制失败 {rel}: {e}")

            if keys:
                tweet_payload.append({
                    "tweetId": tid or f"{date}-{len(tweet_payload)}",
                    "createdAt": date_to_iso(date),
                    "content": "",
                    "imgs": keys,
                    "tags": [args.author],
                })

        save_manifest(manifest)
        log(f"  复制: 新增 {day_copied}, 跳过 {day_skipped}")

        if not tweet_payload:
            log("  无可导入内容")
            continue

        try:
            r = api_post_json("/api/archive/import", {
                "author": args.author,
                "date": date,
                "tweets": tweet_payload,
            })
            if r.get("code") != 0:
                log(f"  [x] 导入失败: {r.get('message')}")
                continue
            data = r["data"]
            log(f"  导入: 新增 {data['imported']}, 已存在跳过 {data['skipped']}")
            grand_imp += data["imported"]
            grand_sskip += data["skipped"]
        except urllib.error.HTTPError as e:
            log(f"  [x] 导入 HTTP {e.code}")
            try:
                log(f"      {e.read().decode('utf-8')[:200]}")
            except Exception:
                pass
        except Exception as e:
            log(f"  [x] 导入异常 {type(e).__name__}: {e}")

    elapsed = time.time() - t0
    log(f"\n{'='*50}")
    log(f"完成 耗时 {elapsed:.0f}s")
    log(f"文件: 复制 {copied}, 跳过 {skipped}")
    log(f"动态: 新增 {grand_imp}, 已存在 {grand_sskip}")
    log(f"媒体目录: {MEDIA_OUT}")
    log("接下来执行: cd frontend && npm run build && wrangler pages deploy .output/public")


if __name__ == "__main__":
    main()
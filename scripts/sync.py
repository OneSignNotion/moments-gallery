#!/usr/bin/env python3
"""
Twitter 归档 -> moments-cloudflare 导入器

调用已部署的 moments 后端 API：
  1. POST /api/archive/upload  逐个把媒体文件传到 R2（key 由本脚本指定，保持目录结构）
  2. POST /api/archive/import  批量把推文写成动态

本地 manifest.json 记录已上传的文件，重复运行自动跳过。
后端 Archive 表做第二层幂等，保证不会重复导入。

用法:
  python sync.py --author 4KAestheticHQ --date 2026-10-20
  python sync.py --author 4KAestheticHQ --all
  python sync.py --author 4KAestheticHQ --all --dry-run
  python sync.py --author 4KAestheticHQ --all --limit 20    # 测试用
"""

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
MANIFEST = DATA_DIR / "manifest.json"
LOG_DIR = BASE / "logs"

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".m4v", ".webm"}

# moments 后端地址，部署后填入
API_BASE = os.environ.get("MOMENTS_API", "https://moments-backend.你的子域.workers.dev")
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
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-TOKEN": API_TOKEN},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def api_upload(path, key, local: Path):
    """上传单个文件到 R2"""
    ctype = mimetypes.guess_type(str(local))[0] or "application/octet-stream"
    boundary = uuid.uuid4().hex
    body = bytearray()

    def field(k, v):
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.extend(f"{v}\r\n".encode())

    field("key", key)
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{local.name}"\r\n'.encode()
    )
    body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
    with open(local, "rb") as f:
        body.extend(f.read())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        API_BASE + path,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-API-TOKEN": API_TOKEN,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def scan(source_root: Path, author: str, date_filter=None):
    """扫描 日期/推文ID/文件 结构，返回按日期分组的推文列表"""
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
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="忽略 manifest 重传")
    p.add_argument("--limit", type=int, help="最多处理多少个推文（测试用）")
    p.add_argument("--api", help="覆盖 API 地址")
    p.add_argument("--token", help="覆盖 API token")
    args = p.parse_args()

    global API_BASE, API_TOKEN
    if args.api:
        API_BASE = args.api
    if args.token:
        API_TOKEN = args.token

    if not args.date and not args.all:
        log("[x] 请指定 --date 或 --all")
        sys.exit(1)
    if not API_TOKEN:
        log("[x] 缺少 API token。用 --token 传入，或设置环境变量 MOMENTS_TOKEN")
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
    grand_up = grand_skip = grand_imp = grand_sskip = 0

    for d in days:
        date = d["date"]
        log(f"\n=== {date} ===")

        # 第一步：上传媒体
        uploaded, skipped = 0, 0
        tweet_payload = []

        for t in d["tweets"]:
            keys = []
            for f in t["files"]:
                rel = f"{args.author}/{date}/{t['tweetId']}/{f.name}" if t["tweetId"] \
                    else f"{args.author}/{date}/{f.name}"
                mk = f"{args.author}|{rel}"

                rec = manifest.get(mk)
                st = f.stat()
                if not args.force and rec and rec.get("size") == st.st_size:
                    skipped += 1
                    keys.append(rel)
                    continue

                try:
                    r = api_upload("/api/archive/upload", rel, f)
                    if r.get("code") != 0:
                        log(f"  [x] 上传返回错误 {rel}: {r.get('message')}")
                        continue
                    manifest[mk] = {
                        "size": st.st_size,
                        "mtime": int(st.st_mtime),
                        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    uploaded += 1
                    keys.append(rel)
                except urllib.error.HTTPError as e:
                    log(f"  [x] HTTP {e.code} 上传失败 {rel}")
                except Exception as e:
                    log(f"  [x] {type(e).__name__} {rel}: {e}")

            if keys:
                tweet_payload.append({
                    "tweetId": t["tweetId"] or f"{date}-{len(tweet_payload)}",
                    "createdAt": date_to_iso(date),
                    "content": "",
                    "imgs": keys,
                    "tags": [args.author],
                })

        save_manifest(manifest)
        log(f"  上传: 新增 {uploaded}, 跳过 {skipped}")

        if not tweet_payload:
            log("  无可导入内容")
            continue

        # 第二步：写入动态
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
            body = ""
            try:
                body = e.read().decode("utf-8")[:200]
            except Exception:
                pass
            log(f"      {body}")
        except Exception as e:
            log(f"  [x] 导入异常 {type(e).__name__}: {e}")

        grand_up += uploaded
        grand_skip += skipped

    elapsed = time.time() - t0
    log(f"\n{'='*50}")
    log(f"完成 耗时 {elapsed:.0f}s")
    log(f"文件: 新传 {grand_up}, 跳过 {grand_skip}")
    log(f"动态: 新增 {grand_imp}, 已存在 {grand_sskip}")


if __name__ == "__main__":
    main()
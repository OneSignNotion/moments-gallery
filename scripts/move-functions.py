"""把 Pages Functions 从 frontend/ 移到仓库根。

Cloudflare Pages 编译 Functions 时只看仓库根的 functions/ 目录，
放在 frontend/functions/ 不会被编译，表现为 /api/* 返回 405。
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src = root / "frontend" / "functions"
dst = root / "functions"

if not src.exists():
    print(f"[skip] {src} 不存在，无需移动")
    raise SystemExit(0)

dst.mkdir(parents=True, exist_ok=True)
moved = 0

for f in src.rglob("*"):
    if not f.is_file():
        continue
    rel = f.relative_to(src)
    target = dst / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(f), str(target))
    print(f"  moved: {rel}")
    moved += 1

shutil.rmtree(src)
print(f"完成，移动 {moved} 个文件到 {dst}")
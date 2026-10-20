"""把 .ps1 文件转成 UTF-8 with BOM —— Windows PowerShell 5.1 必需，
否则中文会被按 GBK 解析导致语法错误。"""
import sys
from pathlib import Path

for name in sys.argv[1:]:
    p = Path(name)
    s = p.read_text(encoding="utf-8")
    p.write_text(s, encoding="utf-8-sig")
    head = p.read_bytes()[:3]
    print(f"{p.name}: BOM={head == bytes([0xEF, 0xBB, 0xBF])}")
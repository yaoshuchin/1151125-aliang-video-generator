#!/usr/bin/env python3
"""consistency-checker 環境檢查"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys


def check() -> dict:
    return {
        "GEMINI_API_KEY": bool(os.environ.get("GEMINI_API_KEY")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "python_version": sys.version.split()[0],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    r = check()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for k, v in r.items():
            flag = "✅" if v else "❌"
            print(f"  {flag} {k}: {v}")
    return 0 if r["ffmpeg"] else 1


if __name__ == "__main__":
    sys.exit(main())

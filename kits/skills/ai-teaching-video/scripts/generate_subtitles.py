#!/usr/bin/env python3
"""
SRT 字幕生成器

從 JSON 腳本與語音檔案生成 SRT 字幕檔，支援燒錄字幕至影片。

使用方式：
    python generate_subtitles.py --input script.json --audio-dir audio/ --output subs.srt
    python generate_subtitles.py --burn --video video.mp4 --srt subs.srt --output output.mp4

作者：阿亮老師・3A科技研究社
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def get_audio_duration(audio_path: Path) -> float:
    """使用 ffprobe 取得音檔時長（秒）。"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def format_srt_time(seconds: float) -> str:
    """將秒數格式化為 SRT 時間格式 HH:MM:SS,mmm。"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def split_narration_lines(narration: str, max_chars: int = 30) -> list[str]:
    """將旁白文字拆分為適合字幕顯示的短行。

    中文約 15-20 字一行，英文約 40 字元一行。
    """
    lines = []
    # 依標點符號先拆分
    punctuation_splits = []
    current = ""
    for char in narration:
        current += char
        if char in "。，！？；、.!?,;":
            punctuation_splits.append(current.strip())
            current = ""
    if current.strip():
        punctuation_splits.append(current.strip())

    # 再依長度拆分
    for segment in punctuation_splits:
        while len(segment) > max_chars:
            # 尋找合適的斷點
            break_pos = max_chars
            for i in range(max_chars, max_chars // 2, -1):
                if segment[i] in "，。！？；、,. ":
                    break_pos = i + 1
                    break
            lines.append(segment[:break_pos].strip())
            segment = segment[break_pos:].strip()
        if segment:
            lines.append(segment)

    return lines if lines else [narration]


def generate_srt(
    sections: list[dict],
    audio_dir: Path,
    max_chars_per_line: int = 30,
) -> str:
    """從腳本和音檔生成 SRT 字幕內容。

    根據每段音檔的實際時長，計算字幕出現的精確時間戳。
    """
    srt_entries = []
    entry_index = 1
    cumulative_time = 0.0

    for i, section in enumerate(sections, 1):
        narration = section.get("narration", "").strip()
        if not narration:
            continue

        # 取得該段語音的時長
        audio_path = audio_dir / f"audio_{i:02d}.mp3"
        if audio_path.is_file():
            duration = get_audio_duration(audio_path)
        else:
            # 估算：中文每字約 0.25 秒
            duration = max(3.0, len(narration) * 0.25)

        # 拆分旁白為字幕行
        lines = split_narration_lines(narration, max_chars_per_line)
        total_chars = sum(len(line) for line in lines)

        # 依每行字數比例分配時長
        line_start = cumulative_time
        for line in lines:
            if total_chars > 0:
                line_duration = duration * (len(line) / total_chars)
            else:
                line_duration = duration / len(lines)

            # 最短 1 秒
            line_duration = max(1.0, line_duration)
            line_end = line_start + line_duration

            srt_entries.append(
                f"{entry_index}\n"
                f"{format_srt_time(line_start)} --> {format_srt_time(line_end)}\n"
                f"{line}\n"
            )
            entry_index += 1
            line_start = line_end

        cumulative_time += duration

    return "\n".join(srt_entries)


def burn_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    font_size: int = 24,
    font_name: str = "Noto Sans TC",
    margin_v: int = 40,
) -> bool:
    """使用 ffmpeg 將 SRT 字幕燒錄至影片中。"""
    # ffmpeg 字幕濾鏡（使用 subtitles 或 ass 格式）
    # 注意：Windows 路徑中的反斜線和冒號需要跳脫
    srt_str = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")

    subtitle_filter = (
        f"subtitles='{srt_str}'"
        f":force_style='FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour=&HFFFFFF,"
        f"OutlineColour=&H000000,"
        f"Outline=2,"
        f"Shadow=1,"
        f"MarginV={margin_v},"
        f"Alignment=2'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", subtitle_filter,
        "-c:a", "copy",
        str(output_path),
    ]

    try:
        print(f"  [字幕] 燒錄字幕至影片...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0 and output_path.is_file():
            print(f"  [字幕] 完成: {output_path}")
            return True
        print(f"  [錯誤] 字幕燒錄失敗: {result.stderr[:300]}", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("  [錯誤] ffmpeg 字幕燒錄逾時", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="SRT 字幕生成器 — AI 教學影片生成器"
    )
    subparsers = parser.add_subparsers(dest="command")

    # 生成字幕子命令（預設）
    gen_parser = subparsers.add_parser("generate", help="從腳本生成 SRT 字幕")
    gen_parser.add_argument("--input", "-i", required=True, help="輸入的 JSON 腳本檔案路徑")
    gen_parser.add_argument("--audio-dir", "-a", default="audio", help="語音檔案目錄")
    gen_parser.add_argument("--output", "-o", default="subtitles.srt", help="輸出 SRT 檔案路徑")
    gen_parser.add_argument("--max-chars", type=int, default=30, help="每行最大字元數（預設: 30）")

    # 燒錄字幕子命令
    burn_parser = subparsers.add_parser("burn", help="將 SRT 字幕燒錄至影片")
    burn_parser.add_argument("--video", "-v", required=True, help="輸入影片路徑")
    burn_parser.add_argument("--srt", "-s", required=True, help="SRT 字幕檔路徑")
    burn_parser.add_argument("--output", "-o", required=True, help="輸出影片路徑")
    burn_parser.add_argument("--font-size", type=int, default=24, help="字幕字體大小（預設: 24）")
    burn_parser.add_argument("--font", default="Noto Sans TC", help="字幕字體名稱")
    burn_parser.add_argument("--margin-v", type=int, default=40, help="字幕底部邊距（預設: 40）")

    args = parser.parse_args()

    # 若無子命令，預設為 generate（相容舊版呼叫方式）
    if args.command is None:
        # 重新解析，支援直接使用 --input 等參數
        parser2 = argparse.ArgumentParser(
            description="SRT 字幕生成器 — AI 教學影片生成器"
        )
        parser2.add_argument("--input", "-i", help="輸入的 JSON 腳本檔案路徑")
        parser2.add_argument("--audio-dir", "-a", default="audio", help="語音檔案目錄")
        parser2.add_argument("--output", "-o", default="subtitles.srt", help="輸出 SRT 檔案路徑")
        parser2.add_argument("--max-chars", type=int, default=30, help="每行最大字元數")
        parser2.add_argument("--burn", action="store_true", help="燒錄模式")
        parser2.add_argument("--video", "-v", help="輸入影片路徑（燒錄模式）")
        parser2.add_argument("--srt", "-s", help="SRT 字幕檔路徑（燒錄模式）")
        parser2.add_argument("--font-size", type=int, default=24, help="字幕字體大小")
        parser2.add_argument("--font", default="Noto Sans TC", help="字幕字體名稱")
        parser2.add_argument("--margin-v", type=int, default=40, help="字幕底部邊距")
        args = parser2.parse_args()

        if args.burn:
            if not args.video or not args.srt:
                print("[錯誤] 燒錄模式需要 --video 和 --srt 參數", file=sys.stderr)
                sys.exit(1)
            ok = burn_subtitles(
                Path(args.video), Path(args.srt), Path(args.output),
                args.font_size, args.font, args.margin_v,
            )
            sys.exit(0 if ok else 1)
        elif args.input:
            args.command = "generate"
        else:
            parser.print_help()
            sys.exit(1)

    if args.command == "generate":
        # 讀取腳本
        input_path = Path(args.input)
        with open(input_path, "r", encoding="utf-8") as f:
            script = json.load(f)

        sections = script.get("sections", [])
        if not sections:
            print("[錯誤] JSON 腳本中沒有 sections", file=sys.stderr)
            sys.exit(1)

        audio_dir = Path(args.audio_dir)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"[字幕生成] 共 {len(sections)} 段")
        print(f"[音檔目錄] {audio_dir}")

        srt_content = generate_srt(sections, audio_dir, args.max_chars)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # 計算統計
        entry_count = srt_content.count("\n\n") + 1
        print(f"\n[完成] 字幕已輸出: {output_path}")
        print(f"  共 {entry_count} 條字幕")

    elif args.command == "burn":
        ok = burn_subtitles(
            Path(args.video), Path(args.srt), Path(args.output),
            args.font_size, args.font, args.margin_v,
        )
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

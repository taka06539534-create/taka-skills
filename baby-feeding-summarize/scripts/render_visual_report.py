#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render newborn feeding summary data into SVG, optional PNG, and Markdown."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


WIDTH = 1200
HEIGHT = 1860
LEFT = 86
RIGHT = WIDTH - 70
TIMELINE_TOP = 475
TIMELINE_HEIGHT = 270
BAR_TOP = 880
BAR_HEIGHT = 300
COMPARE_TOP = 1295

COLORS = {
    "text": "#1f2937",
    "muted": "#64748b",
    "grid": "#d9e2ec",
    "panel": "#f8fafc",
    "border": "#cbd5e1",
    "bottle_breastmilk": "#0f766e",
    "formula": "#b45309",
    "direct_breastfeeding": "#2563eb",
    "diaper": "#7c3aed",
    "urine": "#0284c7",
    "stool": "#a16207",
    "sleep": "#475569",
    "reference": "#dbeafe",
    "warning": "#fef3c7",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def time_to_minutes(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if ":" not in text:
        return None
    hour_text, minute_text = text.split(":", 1)
    if minute_text == "":
        minute_text = "0"
    try:
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def x_for_minute(minute: int | None) -> float:
    if minute is None:
        return LEFT
    return LEFT + (RIGHT - LEFT) * minute / (24 * 60)


def svg_text(x: float, y: float, text: Any, size: int = 22, weight: int = 400,
             color: str = COLORS["text"], anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}" '
        f'font-family="Arial, Microsoft YaHei, sans-serif">{esc(text)}</text>'
    )


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none",
         radius: int = 10, opacity: float | None = None) -> str:
    attrs = f'x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius}" fill="{fill}"'
    if stroke != "none":
        attrs += f' stroke="{stroke}"'
    if opacity is not None:
        attrs += f' opacity="{opacity}"'
    return f"<rect {attrs}/>"


def line(x1: float, y1: float, x2: float, y2: float, color: str = COLORS["grid"], width: float = 1) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"/>'


def card(x: float, y: float, w: float, h: float, title: str, value: Any, note: str = "",
         accent: str = COLORS["direct_breastfeeding"]) -> str:
    parts = [rect(x, y, w, h, "#ffffff", COLORS["border"], 14)]
    parts.append(rect(x, y, 6, h, accent, radius=14))
    parts.append(svg_text(x + 22, y + 32, title, 18, 600, COLORS["muted"]))
    parts.append(svg_text(x + 22, y + 74, value, 32, 700, COLORS["text"]))
    if note:
        parts.append(svg_text(x + 22, y + 106, note, 17, 400, COLORS["muted"]))
    return "\n".join(parts)


def metric(data: dict[str, Any], key: str, default: Any = 0) -> Any:
    return data.get("metrics", {}).get(key, default)


def folder_slug(value: Any) -> str:
    text = str(value or "").strip() or "日期未记录"
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", text)
    text = re.sub(r"\s+", "-", text)
    text = text.strip(" .-_")
    return text or "日期未记录"


def create_report_dir(parent: Path, data: dict[str, Any], basename: str) -> Path:
    date = data.get("date") or "日期未记录"
    base_name = f"{folder_slug(date)}-{folder_slug(basename)}"
    candidate = parent / base_name
    if not candidate.exists():
        candidate.mkdir(parents=True)
        return candidate
    for index in range(2, 1000):
        numbered = parent / f"{base_name}-{index:02d}"
        if not numbered.exists():
            numbered.mkdir(parents=True)
            return numbered
    raise RuntimeError(f"Unable to create unique report directory under {parent}")


def render_header(data: dict[str, Any]) -> list[str]:
    title = data.get("title", "新生儿喂养可视化日报")
    date = data.get("date", "日期未记录")
    summary = data.get("summary", [])[:4]
    parts = [
        svg_text(58, 72, title, 38, 800),
        svg_text(58, 112, date, 21, 400, COLORS["muted"]),
    ]
    for idx, item in enumerate(summary):
        y = 156 + idx * 30
        parts.append(svg_text(70, y, f"- {item}", 20, 400, COLORS["text"]))
    return parts


def render_cards(data: dict[str, Any]) -> list[str]:
    y = 285
    w = 250
    gap = 24
    return [
        card(58, y, w, 118, "瓶喂总量", f"{metric(data, 'bottle_total_ml')} ml",
             f"母乳 {metric(data, 'bottle_breastmilk_ml')} / 奶粉 {metric(data, 'formula_ml')}",
             COLORS["bottle_breastmilk"]),
        card(58 + (w + gap), y, w, 118, "亲喂", f"{metric(data, 'direct_feeding_count')} 次",
             f"约 {metric(data, 'direct_total_min')} 分钟", COLORS["direct_breastfeeding"]),
        card(58 + 2 * (w + gap), y, w, 118, "尿便", f"尿 {metric(data, 'wet_diapers')} / 便 {metric(data, 'stool_count')}",
             "含换尿布口径", COLORS["diaper"]),
        card(58 + 3 * (w + gap), y, w, 118, "睡眠", f"{metric(data, 'sleep_sessions')} 次入睡",
             "缺醒来则只作推测", COLORS["sleep"]),
    ]


def render_timeline(data: dict[str, Any]) -> list[str]:
    parts = [
        svg_text(58, TIMELINE_TOP - 25, "24 小时时间轴", 28, 700),
        svg_text(58, TIMELINE_TOP + 20, "喂养", 19, 600, COLORS["muted"]),
        svg_text(58, TIMELINE_TOP + 105, "尿便", 19, 600, COLORS["muted"]),
        svg_text(58, TIMELINE_TOP + 190, "睡眠", 19, 600, COLORS["muted"]),
    ]
    for hour in range(0, 25, 3):
        x = x_for_minute(hour * 60 if hour < 24 else 24 * 60)
        parts.append(line(x, TIMELINE_TOP, x, TIMELINE_TOP + TIMELINE_HEIGHT, COLORS["grid"]))
        parts.append(svg_text(x, TIMELINE_TOP + TIMELINE_HEIGHT + 26, f"{hour:02d}:00", 15, 400, COLORS["muted"], "middle"))
    for y in (TIMELINE_TOP + 24, TIMELINE_TOP + 109, TIMELINE_TOP + 194):
        parts.append(line(LEFT, y, RIGHT, y, "#94a3b8", 2))

    for item in data.get("sleep", []):
        start = time_to_minutes(item.get("start"))
        end = time_to_minutes(item.get("end"))
        if start is None:
            continue
        x = x_for_minute(start)
        if end is not None and end >= start:
            w = max(8, x_for_minute(end) - x)
            parts.append(rect(x, TIMELINE_TOP + 172, w, 44, COLORS["sleep"], radius=12, opacity=0.18))
            parts.append(rect(x, TIMELINE_TOP + 172, w, 8, COLORS["sleep"], radius=8, opacity=0.55))
        else:
            parts.append(f'<circle cx="{x:.1f}" cy="{TIMELINE_TOP + 194}" r="8" fill="{COLORS["sleep"]}"/>')

    for item in data.get("feedings", []):
        minute = time_to_minutes(item.get("time"))
        if minute is None:
            continue
        x = x_for_minute(minute)
        kind = item.get("type", "")
        color = COLORS.get(kind, COLORS["direct_breastfeeding"])
        radius = 8 if item.get("amount_ml") is None else 6 + min(float(item.get("amount_ml", 0)), 80) / 16
        parts.append(f'<circle cx="{x:.1f}" cy="{TIMELINE_TOP + 24}" r="{radius:.1f}" fill="{color}" opacity="0.9"/>')

    for item in data.get("diapers", []):
        minute = time_to_minutes(item.get("time"))
        if minute is None:
            continue
        x = x_for_minute(minute)
        urine = item.get("urine")
        stool = item.get("stool")
        if urine is True and stool is True:
            color = COLORS["diaper"]
        elif urine is True:
            color = COLORS["urine"]
        elif stool is True:
            color = COLORS["stool"]
        else:
            color = "#94a3b8"
        points = f"{x:.1f},{TIMELINE_TOP + 95} {x + 11:.1f},{TIMELINE_TOP + 109} {x:.1f},{TIMELINE_TOP + 123} {x - 11:.1f},{TIMELINE_TOP + 109}"
        parts.append(f'<polygon points="{points}" fill="{color}" opacity="0.9"/>')

    parts.extend([
        svg_text(LEFT, TIMELINE_TOP + TIMELINE_HEIGHT + 58, "图例：蓝=亲喂，绿=瓶喂母乳，橙=奶粉，紫/蓝/棕=尿便，灰=睡眠推测", 16, 400, COLORS["muted"]),
    ])
    return parts


def render_bottle_chart(data: dict[str, Any]) -> list[str]:
    feedings = [x for x in data.get("feedings", []) if x.get("amount_ml") is not None]
    values = [float(x.get("amount_ml", 0)) for x in feedings]
    max_value = max(values + [80])
    chart_left = LEFT
    chart_right = RIGHT
    chart_bottom = BAR_TOP + BAR_HEIGHT
    chart_top = BAR_TOP + 45
    chart_height = chart_bottom - chart_top
    ref = data.get("reference", {}).get("bottle_single_ml", {})
    ref_min = float(ref.get("min", 0) or 0)
    ref_max = float(ref.get("max", 0) or 0)

    def y_for_value(value: float) -> float:
        return chart_bottom - chart_height * value / max_value

    parts = [
        svg_text(58, BAR_TOP - 18, "瓶喂量与参考区间", 28, 700),
        svg_text(58, BAR_TOP + 15, ref.get("label", "参考区间需结合日龄、体重和医嘱"), 17, 400, COLORS["muted"]),
        line(chart_left, chart_bottom, chart_right, chart_bottom, "#94a3b8", 2),
        line(chart_left, chart_top, chart_left, chart_bottom, "#94a3b8", 2),
    ]
    if ref_min and ref_max and ref_max <= max_value:
        y_top = y_for_value(ref_max)
        y_bottom = y_for_value(ref_min)
        parts.append(rect(chart_left, y_top, chart_right - chart_left, y_bottom - y_top, COLORS["reference"], radius=0, opacity=0.8))
        parts.append(svg_text(chart_right - 4, y_top - 8, "常见参考带", 15, 500, "#1d4ed8", "end"))

    for value in range(0, int(max_value) + 1, 20):
        y = y_for_value(value)
        parts.append(line(chart_left, y, chart_right, y, COLORS["grid"]))
        parts.append(svg_text(chart_left - 12, y + 5, f"{value}", 14, 400, COLORS["muted"], "end"))

    if feedings:
        bar_gap = 12
        bar_w = max(18, min(58, (chart_right - chart_left - bar_gap * (len(feedings) - 1)) / len(feedings)))
        start_x = chart_left + max(0, (chart_right - chart_left - (bar_w * len(feedings) + bar_gap * (len(feedings) - 1))) / 2)
        for idx, item in enumerate(feedings):
            value = float(item.get("amount_ml", 0))
            x = start_x + idx * (bar_w + bar_gap)
            y = y_for_value(value)
            kind = item.get("type", "")
            color = COLORS.get(kind, COLORS["formula"])
            parts.append(rect(x, y, bar_w, chart_bottom - y, color, radius=6, opacity=0.88))
            parts.append(svg_text(x + bar_w / 2, y - 8, f"{int(value)}", 14, 600, COLORS["text"], "middle"))
            parts.append(svg_text(x + bar_w / 2, chart_bottom + 22, item.get("time", ""), 13, 400, COLORS["muted"], "middle"))
    else:
        parts.append(svg_text((chart_left + chart_right) / 2, (chart_top + chart_bottom) / 2, "未记录可量化瓶喂量", 20, 500, COLORS["muted"], "middle"))
    return parts


def render_comparisons(data: dict[str, Any]) -> list[str]:
    parts = [svg_text(58, COMPARE_TOP - 18, "参考区间对比", 28, 700)]
    parts.append(svg_text(58, COMPARE_TOP + 14, "仅作常见参考，需结合日龄、体重、喂养方式、医嘱和宝宝状态。", 17, 400, COLORS["muted"]))
    headers = ["指标", "今日记录", "常见参考", "对比", "备注"]
    widths = [160, 180, 310, 140, 340]
    x = 58
    y = COMPARE_TOP + 48
    parts.append(rect(x, y, sum(widths), 42, "#eef2ff", COLORS["border"], 0))
    cursor = x
    for header, width in zip(headers, widths):
        parts.append(svg_text(cursor + 12, y + 27, header, 16, 700, COLORS["text"]))
        cursor += width
    rows = data.get("comparisons", [])[:6]
    for row_index, row in enumerate(rows):
        y = COMPARE_TOP + 90 + row_index * 58
        fill = "#ffffff" if row_index % 2 == 0 else COLORS["panel"]
        parts.append(rect(x, y, sum(widths), 58, fill, COLORS["border"], 0))
        values = [row.get("indicator", ""), row.get("value", ""), row.get("reference", ""), row.get("status", ""), row.get("note", "")]
        cursor = x
        for idx, (value, width) in enumerate(zip(values, widths)):
            color = COLORS["text"]
            if idx == 3 and str(value) not in {"接近参考", "相近"}:
                color = "#92400e"
            parts.append(svg_text(cursor + 12, y + 35, value, 15, 500 if idx in {0, 3} else 400, color))
            cursor += width
    return parts


def render_svg(data: dict[str, Any]) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        rect(0, 0, WIDTH, HEIGHT, "#f1f5f9", radius=0),
        rect(34, 34, WIDTH - 68, HEIGHT - 68, "#ffffff", COLORS["border"], 24),
    ]
    parts.extend(render_header(data))
    parts.extend(render_cards(data))
    parts.extend(render_timeline(data))
    parts.extend(render_bottle_chart(data))
    parts.extend(render_comparisons(data))
    parts.append(svg_text(58, HEIGHT - 50, "说明：图表用于趋势观察，不替代医生诊断；记录缺失会影响对比结论。", 16, 400, COLORS["muted"]))
    parts.append("</svg>")
    return "\n".join(parts)


def write_html(svg_name: str, html_path: Path) -> None:
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>宝宝喂养可视化报告</title>
  <style>
    body {{ margin: 0; background: #f1f5f9; }}
    img {{ display: block; width: {WIDTH}px; height: {HEIGHT}px; }}
  </style>
</head>
<body>
  <img src="{esc(svg_name)}" alt="宝宝喂养可视化报告">
</body>
</html>
"""
    html_path.write_text(html_text, encoding="utf-8")


def browser_candidates() -> list[str]:
    env_path = os.environ.get("BROWSER_PATH")
    candidates: list[str] = []
    if env_path:
        candidates.append(env_path)
    for name in ("msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    if os.name == "nt":
        program_files = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
        suffixes = [
            r"Microsoft\Edge\Application\msedge.exe",
            r"Google\Chrome\Application\chrome.exe",
            r"Chromium\Application\chrome.exe",
        ]
        for root in program_files:
            if root:
                for suffix in suffixes:
                    path = str(Path(root) / suffix)
                    if Path(path).exists():
                        candidates.append(path)
    deduped: list[str] = []
    for item in candidates:
        if item not in deduped:
            deduped.append(item)
    return deduped


def screenshot_with_browser(html_path: Path, png_path: Path) -> tuple[bool, str]:
    for browser in browser_candidates():
        profile_dir = html_path.parent / ".browser-profile"
        shutil.rmtree(profile_dir, ignore_errors=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--no-first-run",
            f"--user-data-dir={profile_dir.resolve()}",
            f"--window-size={WIDTH},{HEIGHT}",
            f"--screenshot={png_path.resolve()}",
            html_path.resolve().as_uri(),
        ]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception as exc:  # pragma: no cover - environment-specific
            last_error = f"{browser}: {exc}"
            shutil.rmtree(profile_dir, ignore_errors=True)
            continue
        if result.returncode == 0 and png_path.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)
            return True, f"Screenshot generated with {browser}"
        fallback = command.copy()
        fallback[1] = "--headless"
        try:
            result = subprocess.run(
                fallback,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception as exc:  # pragma: no cover - environment-specific
            last_error = f"{browser}: {exc}"
            shutil.rmtree(profile_dir, ignore_errors=True)
            continue
        if result.returncode == 0 and png_path.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)
            return True, f"Screenshot generated with {browser}"
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        last_error = f"{browser}: {stderr or stdout or 'unknown browser error'}"
        shutil.rmtree(profile_dir, ignore_errors=True)
    return False, locals().get("last_error", "No Chrome/Edge/Chromium browser found")


def write_markdown(data: dict[str, Any], md_path: Path, svg_path: Path, png_path: Path | None, note: str) -> None:
    title = data.get("title", "新生儿喂养可视化日报")
    date = str(data.get("date", "")).strip()
    report_markdown = str(data.get("report_markdown", "")).strip()
    lines = [
        f"# {title}",
        "",
    ]
    if not date or date in {"日期未记录", "未记录日期", "未提供", "未识别"}:
        lines.extend([
            "> 提醒：这份记录未写明日期，请补充记录日期，便于判断是否跨日并做更准确的参考区间对比。",
            "",
        ])
    if report_markdown:
        lines.extend([
            report_markdown,
            "",
        ])
    lines.extend([
        "## 说明",
        "",
        "- PNG 截图优先用于 Markdown 预览；SVG 保留为可缩放源图。",
        "- PNG 依赖本地可用的 Chrome、Edge、Chromium headless 或浏览器插件截图能力。",
        "- 图表仅用于趋势观察，参考区间不能替代医生诊断。",
        "",
        "## 可视化图表",
        "",
    ])
    if png_path and png_path.exists():
        lines.extend([
            f"![宝宝喂养可视化图表]({png_path.name})",
            "",
            f"SVG 源文件：[{svg_path.name}]({svg_path.name})",
            "",
        ])
    else:
        lines.extend([
            f"![宝宝喂养可视化图表]({svg_path.name})",
            "",
            f"> 未生成 PNG 截图：{note}",
            "",
        ])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def load_data(path_text: str) -> dict[str, Any]:
    if path_text == "-":
        return json.load(sys.stdin)
    with Path(path_text).open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render newborn feeding visual report into a dated folder with SVG, optional PNG, structured JSON, and index.md.")
    parser.add_argument("--input", "-i", required=True, help="Input JSON path, or '-' for stdin.")
    parser.add_argument("--output-dir", "-o", required=True, help="Parent directory for generated report folders.")
    parser.add_argument("--basename", default="baby-feeding-report", help="Output filename prefix. Default: baby-feeding-report.")
    parser.add_argument("--screenshot", choices=["auto", "always", "never"], default="auto", help="PNG screenshot mode. Default: auto.")
    args = parser.parse_args()

    data = load_data(args.input)
    parent_dir = Path(args.output_dir)
    parent_dir.mkdir(parents=True, exist_ok=True)
    out_dir = create_report_dir(parent_dir, data, args.basename)
    base = args.basename
    json_path = out_dir / "structured-data.json"
    svg_path = out_dir / f"{base}.svg"
    html_path = out_dir / f"{base}.html"
    png_path = out_dir / f"{base}.png"
    md_path = out_dir / "index.md"

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    svg_path.write_text(render_svg(data), encoding="utf-8")
    write_html(svg_path.name, html_path)

    screenshot_note = "screenshot disabled"
    if args.screenshot != "never":
        ok, screenshot_note = screenshot_with_browser(html_path, png_path)
        if not ok and args.screenshot == "always":
            write_markdown(data, md_path, svg_path, None, screenshot_note)
            print(json.dumps({
                "report_dir": str(out_dir),
                "entry": str(md_path),
                "structured_data": str(json_path),
                "svg": str(svg_path),
                "html": str(html_path),
                "markdown": str(md_path),
                "png": None,
                "warning": screenshot_note,
            }, ensure_ascii=False, indent=2))
            return 2
    else:
        ok = False

    final_png = png_path if png_path.exists() else None
    write_markdown(data, md_path, svg_path, final_png, screenshot_note)
    print(json.dumps({
        "report_dir": str(out_dir),
        "entry": str(md_path),
        "structured_data": str(json_path),
        "svg": str(svg_path),
        "html": str(html_path),
        "markdown": str(md_path),
        "png": str(final_png) if final_png else None,
        "warning": None if final_png or args.screenshot == "never" else screenshot_note,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

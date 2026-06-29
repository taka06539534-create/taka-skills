#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate a moonlight-girl-companion Markdown article package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def extract_numbered_section(text: str, number: int, title: str) -> str:
    pattern = re.compile(rf"^##\s*{number}\.\s*{re.escape(title)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s*\d+\.\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def count_chapters(body_text: str) -> int:
    if not body_text:
        return 0
    pattern = re.compile(
        r"^###\s*(?:0?[1-9]|[一二三四五六七八九十]+|第[一二三四五六七八九十\d]+[章节])(?:\s|\b)",
        re.MULTILINE,
    )
    return len(pattern.findall(body_text))


def count_topic_candidates(text: str) -> int:
    return len(re.findall(r"^###\s*候选\s*\d+", text, re.MULTILINE))


def count_illustration_prompts(text: str) -> int:
    illustration_section = extract_numbered_section(text, 8, "章节插图 Prompt")
    search_text = illustration_section or text
    heading_count = len(re.findall(r"^###\s*插图\s*\d+", search_text, re.MULTILINE))
    prompt_count = len(re.findall(r"生图\s*Prompt\s*[:：]\s*\S+", search_text))
    return max(heading_count, prompt_count)


def parse_final_topic_score(text: str) -> float | None:
    matches = re.findall(r"最终评分\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def parse_article_permission(text: str) -> str | None:
    match = re.search(r"是否允许进入正文创作\s*[:：]?\s*([^\n\r]+)", text)
    if not match:
        return None
    return match.group(1).strip()


def permission_is_negative(value: str) -> bool:
    normalized = re.sub(r"\s+", "", value).lower()
    return normalized in {"否", "不允许", "no", "false", "n"} or normalized.startswith("否")


def validate_text(text: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    required_phrases = [
        ("正文", "缺少“正文”模块。"),
        ("故事设定卡", "缺少“故事设定卡”模块。"),
        ("角色视觉设定卡", "缺少“角色视觉设定卡”模块。"),
        ("公众号摘要", "缺少“公众号摘要”模块。"),
        ("封面图 Prompt", "缺少“封面图 Prompt”模块。"),
        ("质量验收报告", "缺少“质量验收报告”模块。"),
        ("Goal 模式迭代日志", "缺少“Goal 模式迭代日志”模块。"),
        ("最终状态", "缺少“最终状态”模块。"),
        ("角色一致性设定", "缺少“角色一致性设定”。"),
        ("统一美术风格", "缺少“统一美术风格”。"),
        ("统一色彩系统", "缺少“统一色彩系统”。"),
    ]
    for phrase, message in required_phrases:
        if phrase not in text:
            errors.append(message)

    if not has_any(text, ["章节插图 Prompt", "插图 Prompt"]):
        errors.append("缺少“章节插图 Prompt”或“插图 Prompt”模块。")

    body_text = extract_numbered_section(text, 5, "正文")
    count_source = body_text or text
    chinese_chars = len(HAN_RE.findall(count_source))
    chapter_count = count_chapters(body_text)
    illustration_placeholder_count = len(re.findall(r"【\s*插图占位\s*[:：]\s*插图\s*\d+\s*】", text))
    illustration_prompt_count = count_illustration_prompts(text)
    topic_candidate_count = count_topic_candidates(text)

    if chapter_count < 5:
        errors.append(f"章节标题不足：检测到 {chapter_count} 个，至少需要 5 个。")
    if illustration_placeholder_count < 5:
        errors.append(f"插图占位不足：检测到 {illustration_placeholder_count} 个，至少需要 5 个。")
    if illustration_prompt_count < 5:
        errors.append(f"插图 Prompt 不足：检测到 {illustration_prompt_count} 个，至少需要 5 个。")

    if chinese_chars < 2600:
        errors.append(f"正文字数过低：检测到约 {chinese_chars} 个中文字符，Hard Gate 要求不低于 2600。")
    elif chinese_chars < 2800:
        warnings.append(f"正文字数偏低：检测到约 {chinese_chars} 个中文字符，建议达到 2800 到 3600。")
    elif chinese_chars > 3800:
        errors.append(f"正文字数过高：检测到约 {chinese_chars} 个中文字符，Hard Gate 要求不高于 3800。")
    elif chinese_chars > 3600:
        warnings.append(f"正文字数偏高：检测到约 {chinese_chars} 个中文字符，建议控制在 2800 到 3600。")

    autonomous_mode = "自主选题模式" in text
    if autonomous_mode:
        autonomous_required = [
            ("自主选题报告", "自主选题模式下缺少“自主选题报告”。"),
            ("最终选择", "自主选题模式下缺少“最终选择”。"),
            ("最终评分", "自主选题模式下缺少“最终评分”。"),
            ("是否允许进入正文创作", "自主选题模式下缺少“是否允许进入正文创作”。"),
            ("关键物件", "自主选题模式下缺少“关键物件”。"),
            ("核心冲突", "自主选题模式下缺少“核心冲突”。"),
            ("女主身份", "自主选题模式下缺少“女主身份”。"),
        ]
        for phrase, message in autonomous_required:
            if phrase not in text:
                errors.append(message)
        if topic_candidate_count < 5:
            errors.append(f"自主选题候选不足：检测到 {topic_candidate_count} 个，至少需要 5 个。")
        final_score = parse_final_topic_score(text)
        if final_score is not None and final_score < 80:
            errors.append(f"最终选题评分过低：{final_score:g} 分，必须不低于 80 分。")
        permission = parse_article_permission(text)
        if permission and permission_is_negative(permission):
            errors.append("“是否允许进入正文创作”为否，不能通过结构校验。")

    stats = {
        "chinese_chars": chinese_chars,
        "chapter_count": chapter_count,
        "illustration_placeholder_count": illustration_placeholder_count,
        "illustration_prompt_count": illustration_prompt_count,
        "topic_candidate_count": topic_candidate_count,
    }

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Validate a Markdown article package generated by moonlight-girl-companion."
    )
    parser.add_argument("markdown_file", help="Path to the generated Markdown article package.")
    args = parser.parse_args(argv)

    path = Path(args.markdown_file)
    if not path.exists():
        result = {
            "passed": False,
            "errors": [f"文件不存在：{path}"],
            "warnings": [],
            "stats": {
                "chinese_chars": 0,
                "chapter_count": 0,
                "illustration_placeholder_count": 0,
                "illustration_prompt_count": 0,
                "topic_candidate_count": 0,
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    text = path.read_text(encoding="utf-8-sig")
    result = validate_text(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate a moonlight-girl-companion publish-ready article package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def empty_stats() -> dict[str, Any]:
    return {
        "chinese_chars": 0,
        "chapter_count": 0,
        "illustration_placeholder_count": 0,
        "illustration_prompt_count": 0,
        "topic_candidate_count": 0,
        "metadata_present": False,
        "cover_image_count": 0,
        "chapter_image_file_count": 0,
        "markdown_image_reference_count": 0,
        "deep_night_message_present": False,
        "interaction_topic_present": False,
        "more_articles_entry_present": False,
        "ending_sections_order_valid": False,
    }


def image_signature_is_valid(path: Path) -> bool:
    try:
        header = path.read_bytes()[:16]
    except OSError:
        return False

    suffix = path.suffix.lower()
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix == ".webp":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return False


def resolve_package_path(package_dir: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw_path = Path(value.strip())
    return raw_path if raw_path.is_absolute() else package_dir / raw_path


def normalized_existing_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


def read_metadata(package_dir: Path, errors: list[str]) -> dict[str, Any]:
    metadata_path = package_dir / "metadata.json"
    if not metadata_path.exists():
        errors.append("缺少公众号发布元数据文件：metadata.json。")
        return {}

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        errors.append(f"metadata.json 不是有效 JSON：{exc}")
        return {}
    except OSError as exc:
        errors.append(f"无法读取 metadata.json：{exc}")
        return {}

    if not isinstance(data, dict):
        errors.append("metadata.json 顶层结构必须是对象。")
        return {}
    return data


def normalize_illustration_entries(entries: Any) -> list[Any]:
    if not isinstance(entries, list):
        return []

    paths: list[Any] = []
    for item in entries:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict):
            paths.append(item.get("path") or item.get("file") or item.get("image"))
    return paths


def collect_convention_chapter_images(package_dir: Path) -> list[Path]:
    images_dir = package_dir / "images"
    if not images_dir.exists():
        return []

    paths: list[Path] = []
    for pattern in ("chapter-*", "chapter_*", "illustration-*", "illustration_*"):
        paths.extend(
            path
            for path in images_dir.glob(pattern)
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
    return sorted(set(paths))


def markdown_image_references(text: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)


def local_markdown_image_paths(text: str, package_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for raw_ref in markdown_image_references(text):
        ref = raw_ref.strip().split()[0].strip("<>")
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", ref):
            continue
        path = resolve_package_path(package_dir, ref)
        if path and path.suffix.lower() in IMAGE_EXTENSIONS:
            paths.append(path)
    return paths


def load_article_input(input_path: Path) -> tuple[Path, Path | None, str, list[str]]:
    errors: list[str] = []

    if not input_path.exists():
        return input_path.parent, None, "", [f"文件不存在：{input_path}"]

    if input_path.is_dir():
        article_candidates = [input_path / "article.md", input_path / "index.md"]
        article_path = next((path for path in article_candidates if path.exists()), None)
        if article_path is None:
            return input_path, None, "", ["发布包目录中缺少 article.md 或 index.md。"]
        package_dir = input_path
    else:
        article_path = input_path
        package_dir = input_path.parent

    try:
        text = article_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        errors.append(f"无法读取文章文件：{article_path}，原因：{exc}")
        text = ""

    return package_dir, article_path, text, errors


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


def markdown_heading_index(text: str, title: str) -> int:
    pattern = re.compile(rf"^###\s*{re.escape(title)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    return match.start() if match else -1


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
    return validate_package_text(text, Path("."))


def validate_package_text(text: str, package_dir: Path) -> dict[str, Any]:
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
    illustration_placeholder_count = len(
        re.findall(r"【\s*插图占位\s*[:：]\s*插图\s*\d+\s*】", text)
    )
    illustration_prompt_count = count_illustration_prompts(text)
    topic_candidate_count = count_topic_candidates(text)
    required_chapter_image_count = max(5, chapter_count)
    deep_night_message_index = markdown_heading_index(body_text, "深夜寄语")
    interaction_topic_index = markdown_heading_index(body_text, "互动话题")
    more_articles_entry_index = markdown_heading_index(body_text, "更多文章入口")
    deep_night_message_present = deep_night_message_index != -1
    interaction_topic_present = interaction_topic_index != -1
    more_articles_entry_present = more_articles_entry_index != -1
    ending_sections_order_valid = (
        deep_night_message_present
        and interaction_topic_present
        and more_articles_entry_present
        and deep_night_message_index < interaction_topic_index < more_articles_entry_index
    )

    metadata = read_metadata(package_dir, errors)
    metadata_present = bool(metadata)
    if metadata:
        title = metadata.get("title")
        description = metadata.get("description")
        if not isinstance(title, str) or not title.strip():
            errors.append("metadata.json 缺少非空 title 字段。")
        if not isinstance(description, str) or not description.strip():
            errors.append("metadata.json 缺少非空 description 字段。")

    cover_paths: list[Path] = []
    cover_from_metadata = resolve_package_path(package_dir, metadata.get("cover_image")) if metadata else None
    if cover_from_metadata:
        cover_paths.append(cover_from_metadata)
    elif metadata:
        errors.append("metadata.json 缺少 cover_image 字段。")

    convention_cover_paths = [
        package_dir / f"cover{suffix}"
        for suffix in sorted(IMAGE_EXTENSIONS)
        if (package_dir / f"cover{suffix}").exists()
    ]
    cover_paths.extend(convention_cover_paths)
    valid_cover_paths = sorted(
        {path for path in cover_paths if path.exists() and image_signature_is_valid(path)}
    )
    if not valid_cover_paths:
        errors.append("缺少真实可用的封面图片文件，需要提供 cover.png/jpg/webp 或 metadata.json 中的 cover_image。")

    metadata_illustration_paths = [
        path
        for path in (
            resolve_package_path(package_dir, value)
            for value in normalize_illustration_entries(metadata.get("illustrations")) if metadata
        )
        if path is not None
    ]
    convention_illustration_paths = collect_convention_chapter_images(package_dir)
    all_chapter_image_paths = sorted(set(metadata_illustration_paths + convention_illustration_paths))
    valid_chapter_image_paths = [
        path for path in all_chapter_image_paths if path.exists() and image_signature_is_valid(path)
    ]
    if len(valid_chapter_image_paths) < required_chapter_image_count:
        errors.append(
            f"真实章节插图文件不足：检测到 {len(valid_chapter_image_paths)} 个，"
            f"至少需要 {required_chapter_image_count} 个。"
        )

    valid_chapter_image_set = {
        normalized_existing_path(path) for path in valid_chapter_image_paths
    }
    article_image_paths = local_markdown_image_paths(text, package_dir)
    valid_article_chapter_paths = [
        path
        for path in article_image_paths
        if path.exists()
        and image_signature_is_valid(path)
        and (
            normalized_existing_path(path) in valid_chapter_image_set
            or re.search(r"(chapter|illustration)[-_]?\d+", path.stem, re.IGNORECASE)
        )
    ]
    if len(valid_article_chapter_paths) < required_chapter_image_count:
        errors.append(
            f"正文中引用的真实章节插图不足：检测到 {len(valid_article_chapter_paths)} 个，"
            f"至少需要 {required_chapter_image_count} 个。"
        )

    if chapter_count < 5:
        errors.append(f"章节标题不足：检测到 {chapter_count} 个，至少需要 5 个。")
    if illustration_placeholder_count < 5:
        errors.append(f"插图占位不足：检测到 {illustration_placeholder_count} 个，至少需要 5 个。")
    if illustration_prompt_count < 5:
        errors.append(f"插图 Prompt 不足：检测到 {illustration_prompt_count} 个，至少需要 5 个。")
    if not deep_night_message_present:
        errors.append("正文结尾缺少“深夜寄语”章节。")
    if not interaction_topic_present:
        errors.append("正文结尾缺少“互动话题”章节。")
    if not more_articles_entry_present:
        errors.append("正文结尾缺少“更多文章入口”章节。")
    if (
        deep_night_message_present
        and interaction_topic_present
        and more_articles_entry_present
        and not ending_sections_order_valid
    ):
        errors.append("正文结尾章节顺序错误，必须依次为“深夜寄语”->“互动话题”->“更多文章入口”。")

    if chinese_chars < 2600:
        errors.append(f"正文字数过低：检测到约 {chinese_chars} 个中文字，Hard Gate 要求不低于 2600。")
    elif chinese_chars < 2800:
        warnings.append(f"正文字数偏低：检测到约 {chinese_chars} 个中文字，建议达到 2800 到 3600。")
    elif chinese_chars > 3800:
        errors.append(f"正文字数过高：检测到约 {chinese_chars} 个中文字，Hard Gate 要求不高于 3800。")
    elif chinese_chars > 3600:
        warnings.append(f"正文字数偏高：检测到约 {chinese_chars} 个中文字，建议控制在 2800 到 3600。")

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
        "metadata_present": metadata_present,
        "cover_image_count": len(valid_cover_paths),
        "chapter_image_file_count": len(valid_chapter_image_paths),
        "markdown_image_reference_count": len(valid_article_chapter_paths),
        "deep_night_message_present": deep_night_message_present,
        "interaction_topic_present": interaction_topic_present,
        "more_articles_entry_present": more_articles_entry_present,
        "ending_sections_order_valid": ending_sections_order_valid,
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
        description="Validate a publish-ready article package generated by moonlight-girl-companion."
    )
    parser.add_argument(
        "article_package",
        help="Path to a publish package directory, or to article.md/index.md inside that package.",
    )
    args = parser.parse_args(argv)

    path = Path(args.article_package)
    package_dir, _article_path, text, input_errors = load_article_input(path)
    if input_errors:
        result = {
            "passed": False,
            "errors": input_errors,
            "warnings": [],
            "stats": empty_stats(),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    result = validate_package_text(text, package_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

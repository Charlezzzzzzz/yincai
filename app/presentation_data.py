"""Pure, source-preserving data projections for brief updates 21 and 22.

No inference, database access, layout code or file mutation belongs here.
Raw protocol values remain in ``source_json``; display labels are Chinese.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
import re
from typing import Any


CAUSE_IDS = tuple(f"M{number}" for number in range(1, 11))
STATISTICS_METHOD = "每名模拟学生只记一个主要错因，按 classroom.json 的 top_cause 现算"
DISPLAY_STATISTICS_METHOD = "每名模拟学生只记一个主要错因，按班级记录中的主要错因字段现算"

VERDICT_LABELS = {
    "reject": "退回",
    "approve": "通过",
    "pending": "待定",
    "unknown": "待定",
}
ERROR_TYPE_LABELS = {
    "direct_answer": "直接给出答案",
    "final_answer": "直接给出答案",
    "answer_leak": "泄露答案",
    "other_answer": "泄露其他学生答案",
    "other_student_answer": "泄露其他学生答案",
    "other_student_answers": "泄露其他学生答案",
    "other_student_info": "泄露其他学生信息",
    "other_student_information": "泄露其他学生信息",
    "internal_code": "出现内部代号",
    "internal_codes": "出现内部代号",
    "internal_terms": "出现内部术语",
    "internal_implementation": "暴露内部实现信息",
    "math_error": "数学内容有误",
    "mathematical_error": "数学内容有误",
    "inconsistent_math": "数学表达不一致",
    "narration_formula_mismatch": "旁白与公式不一致",
    "not_age_appropriate": "不符合学段要求",
    "age_inappropriate": "不符合学段要求",
    "format_error": "格式不符合要求",
    "missing_fields": "信息不完整",
    "duration": "时长不符合要求",
    "duration_out_of_range": "时长不符合要求",
    "form_mismatch": "讲解形式不符合要求",
}


def localize_verdict(value: object) -> str:
    """Return a display-only label; unknown protocol values never leak out."""
    key = value.strip().lower() if isinstance(value, str) else ""
    return VERDICT_LABELS.get(key, "待定")


def localize_error_type(value: object) -> str:
    """Keep an unknown error visible as unclassified, rather than hiding it."""
    key = value.strip().lower() if isinstance(value, str) else ""
    return ERROR_TYPE_LABELS.get(key, "未分类问题")


def compute_classroom_distribution(
    classroom: Mapping[str, Any], cause_labels: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Count exactly one valid primary cause for every uniquely identified row.

    The full ten-cause protocol includes zero-count categories. The chart data
    includes every observed category (currently five), without an invented
    remainder. Invalid or missing data raises instead of reducing a numerator
    while silently retaining an incorrect denominator.
    """
    if not isinstance(classroom, Mapping):
        raise ValueError("班级记录必须是对象")
    roster = classroom.get("roster")
    if not isinstance(roster, list):
        raise ValueError("班级名册必须是列表")
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    for row in roster:
        if not isinstance(row, Mapping):
            raise ValueError("每条名册记录必须是对象")
        identity = row.get("id")
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("模拟学生记录缺少有效身份标识")
        identity = identity.strip()
        if identity in seen:
            raise ValueError("模拟学生身份重复，不能重复计数")
        seen.add(identity)
        cause = row.get("top_cause")
        if not isinstance(cause, str) or cause not in CAUSE_IDS:
            raise ValueError("每名模拟学生必须且只能有一个有效主要错因")
        counts[cause] += 1
    total = len(roster)
    labels = cause_labels or {}
    all_rows = []
    for cause_id in CAUSE_IDS:
        count = counts[cause_id]
        label = labels.get(cause_id)
        if not isinstance(label, str) or not label.strip():
            label = "未命名错因"
        proportion = count / total if total else 0.0
        all_rows.append({
            "cause_id": cause_id, "label": label, "count": count,
            "proportion": proportion, "percentage": round(proportion * 100, 1),
            "denominator": total, "unit": "人",
        })
    chart_rows = sorted(
        (dict(row) for row in all_rows if row["count"]),
        key=lambda row: (-row["count"], int(row["cause_id"][1:])),
    )
    top_three_count = sum(row["count"] for row in chart_rows[:3])
    result = deepcopy(dict(classroom))
    result.update({
        "student_count": total, "total_people": total,
        "top_three_count": top_three_count, "unit": "人", "denominator": total,
        "distribution_title": "错因分布",
        "cause_distribution": chart_rows, "cause_distribution_all": all_rows,
        "statistics_source": "□ 模拟班级",
        "statistics_method": STATISTICS_METHOD,
        "display_statistics_method": DISPLAY_STATISTICS_METHOD,
        "source_json": deepcopy(dict(classroom)),
    })
    return result


def summary_excerpt(text: str, *, chars_per_line: int = 32, max_lines: int = 2) -> dict[str, Any]:
    """Return the exact prefix ending at the last allowed clause boundary.

    Character counts are an explicit approximation, not a claim about rendered
    line count; the eventual layout can set ``chars_per_line``. With no complete
    sentence/clause within the budget, no invented or mid-clause text is shown.
    """
    if not isinstance(text, str):
        raise ValueError("摘要原文必须是字符串")
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in (chars_per_line, max_lines)):
        raise ValueError("每行字数和行数必须是正整数")
    limit = chars_per_line * max_lines
    prefix = text[:limit]
    positions = [index for index, character in enumerate(prefix) if character in "，；。"]
    end = positions[-1] + 1 if positions else 0
    excerpt = text[:end]
    return {
        "text": excerpt, "start": 0, "end": end,
        "chars_per_line": chars_per_line, "max_lines": max_lines, "limit": limit,
        "boundary_found": bool(positions), "truncated": end < len(text),
        "reason": "已按原文分句边界截取" if positions else "预算内找不到完整句子或分句边界，未生成摘要",
        "method": "逐字取原文开头，止于字数预算内最后一个逗号、分号或句号",
    }


def plan_title(parsed: Mapping[str, Any]) -> dict[str, str]:
    """Preserve an actual title; otherwise derive only an original first clause."""
    value = parsed.get("title")
    if isinstance(value, str) and value.strip():
        return {"title": value, "title_source": "教师助理真实生成（标题原文）"}
    summary = parsed.get("teacher_summary", "")
    summary = summary if isinstance(summary, str) else ""
    ending = re.search(r"[。！？!?]|(?<![0-9])\.(?![0-9])", summary)
    sentence = summary[:ending.end()] if ending else summary
    return {
        "title": sentence.rstrip("。！？!?；;，,.：:"),
        "title_source": "标题取教师助理原文首句",
    }

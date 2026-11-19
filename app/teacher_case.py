"""Read-only teacher projections derived from the original teaching case."""
import json
from pathlib import Path
from typing import Any

from .case_files import ROOT, case_index, read_cache
from .cockpit_comparison import read_demo_context
from .presentation_data import compute_classroom_distribution, plan_title, summary_excerpt

def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cache_meta(record: dict[str, Any], cache_path: Path) -> dict[str, Any]:
    return {
        "model": record.get("model_name", record.get("model")),
        "source": "cache",
        "elapsed_ms": record.get("elapsed_ms"),
        "prompt_version": record.get("prompt_version"),
        "created_at": record.get("created_at", record.get("timestamp")),
        "input_hash": record.get("input_hash"),
        "cache_path": str(cache_path),
    }


def computed_classroom(root: Path = ROOT) -> dict[str, Any]:
    """Count the actual roster rather than trusting authored display totals."""
    classroom = read_json(root / "data" / "classroom.json")["classroom"]
    labels = {row["id"]: row["name"] for row in read_json(root / "data" / "causes.json")["causes"]}
    return compute_classroom_distribution(classroom, labels)


def _plan_diagnosis(student: dict[str, Any], record: dict[str, Any], path: Path, cause_labels: dict[str, str], root: Path) -> dict[str, Any]:
    """Read explicit misconception fields and keep their provenance separate.

    Prefer an existing analyst diagnosis, then the matching neutral handwriting
    diagnosis. The final allowed source is the canonical simulated student
    record; it remains labelled as simulation, never independent inference.
    Text summaries, rule_precheck and classroom counts cannot supply a link.
    """
    empty = {"cause_id": None, "cause_label": None, "diagnosis_source": None,
             "diagnosis_evidence": None, "diagnosis_provenance": None}
    if record.get("deprecated"):
        return empty
    context = record.get("request", {}).get("context", {})
    context_student = context.get("student", {})
    if context_student.get("id") not in (None, student["id"]):
        return empty
    analyst = context.get("analyst", {})
    cause_id = analyst.get("misconception_id") if isinstance(analyst, dict) else None
    evidence = analyst.get("evidence") if isinstance(analyst, dict) else None
    if isinstance(cause_id, str) and cause_id in cause_labels and isinstance(evidence, str) and evidence.strip():
        return {"cause_id": cause_id, "cause_label": cause_labels[cause_id],
                "diagnosis_source": "教师助理真实缓存中的学情分析师诊断原文", "diagnosis_evidence": evidence,
                "diagnosis_provenance": {"cache_path": str(path), "input_hash": record.get("input_hash"),
                    "prompt_version": record.get("prompt_version"), "field_path": "request.context.analyst.misconception_id + request.context.analyst.evidence"}}

    # The red-team archive identifies the actual neutral-image cache. Match
    # its own student_name rather than a handwritten S2 -> M4 association.
    vision_path = case_index(root)["vision"]
    vision = read_cache(root, vision_path)
    vision_context = vision.get("request", {}).get("context", {})
    if vision_context.get("task") == "photo_diagnosis" and vision_context.get("student_name") == student["name"]:
        parsed = vision["parsed"]
        cause_id = parsed.get("misconception_id")
        evidence = parsed.get("evidence")
        if vision.get("deprecated") or cause_id not in cause_labels or not isinstance(evidence, str) or not evidence.strip():
            return empty
        return {"cause_id": cause_id, "cause_label": cause_labels[cause_id],
                "diagnosis_source": "无批注手写样例的真实视觉诊断缓存", "diagnosis_evidence": evidence,
                "diagnosis_provenance": {"cache_path": vision_path, "input_hash": vision["input_hash"],
                    "prompt_version": vision.get("prompt_version"), "field_path": "parsed.misconception_id + parsed.evidence",
                    "model_meta": cache_meta(vision, Path(vision_path))}}

    content_path = root / "data" / "content-v1.1.json"
    if not content_path.exists():
        return empty
    recorded_student = next((row for row in read_json(content_path).get("students", []) if row.get("id") == student["id"]), None)
    cause_id = recorded_student.get("misconception") if recorded_student else None
    if not isinstance(cause_id, str) or cause_id not in cause_labels:
        return empty
    return {"cause_id": cause_id, "cause_label": cause_labels[cause_id],
            "diagnosis_source": "□ 模拟学生记录（非模型独立诊断）",
            "diagnosis_evidence": json.dumps({"id": recorded_student["id"], "misconception": cause_id}, ensure_ascii=False),
            "diagnosis_provenance": {"cache_path": None, "file_path": str(content_path.relative_to(root)), "input_hash": None,
                "prompt_version": None, "field_path": f"students[id={student['id']}].misconception", "model_meta": None}}


def _plan_from_record(student: dict[str, Any], record: dict[str, Any], path: Path, *, cause_labels: dict[str, str] | None = None, root: Path = ROOT) -> dict[str, Any]:
    parsed = record.get("parsed")
    if not isinstance(parsed, dict) or not isinstance(parsed.get("recommendation"), str) or not parsed["recommendation"].strip():
        raise ValueError(f"{student['id']} 教师助理缓存缺少真实 recommendation")
    summary = parsed.get("teacher_summary", "")
    summary = summary if isinstance(summary, str) else ""
    projected_title = plan_title(parsed)
    return {
        "student_id": student["id"],
        "student_name": student["name"],
        "status": "ready",
        **projected_title,
        "teacher_summary": summary,
        "recommendation": parsed["recommendation"],
        "recommendation_source": "教师助理建议 · 真实缓存",
        "evidence": parsed.get("evidence", []),
        "student_safe": parsed.get("student_safe"),
        "model_meta": cache_meta(record, path),
        **_plan_diagnosis(student, record, path, cause_labels or {}, root),
    }


def overview(root: Path = ROOT, *, summary_chars_per_line: int = 32, summary_max_lines: int = 2) -> dict[str, Any]:
    content = read_json(root / "data" / "content-v1.1.json")
    cause_labels = {row["id"]: row["name"] for row in read_json(root / "data" / "causes.json")["causes"]}
    plans = []
    for student in content["students"]:
        path = case_index(root)["teacher_plans"][student["id"]]
        record = read_cache(root, path)
        plans.append(_plan_from_record(student, record, Path(path), cause_labels=cause_labels, root=root))
    for plan in plans:
        plan["decision"] = None
        plan["verification_reflection"] = None
        plan["decision_status"] = "待定"
        excerpt = summary_excerpt(plan["recommendation"], chars_per_line=summary_chars_per_line, max_lines=summary_max_lines)
        plan["recommendation_excerpt"] = {**excerpt, "source_field": "parsed.recommendation"}
        meta = plan.get("model_meta") or {}
        plan["display"] = {
            "标题": plan["title"], "标题来源": plan["title_source"],
            "摘要": excerpt["text"], "摘要说明": excerpt["reason"],
            "来源": "○ 真实缓存" if plan["status"] == "ready" else "□ 尚未生成",
            "状态": plan["decision_status"], "针对错因": plan.get("cause_label"),
            "详情": {"方案全文": plan["recommendation"], "模型": meta.get("model"),
                "耗时": f"{meta['elapsed_ms'] / 1000:.1f} s" if isinstance(meta.get("elapsed_ms"), (int, float)) else None,
                "缓存路径": meta.get("cache_path"), "提示词版本": meta.get("prompt_version"),
                "生成时间": meta.get("created_at"), "关联依据": plan.get("diagnosis_source"),
                "下发说明": "本工作台的决定仅在教师端保存。"},
        }
    classroom = computed_classroom(root)
    return {
        "classroom": classroom,
        "knowledge_points": read_json(root / "data" / "unit.json")["knowledge_points"],
        "plans": plans,
        "display": {"班级": {"标题": "错因分布", "来源": "□ 模拟班级",
            "总人数": classroom["student_count"], "前三类合计": classroom["top_three_count"], "单位": "人",
            "计算方法": classroom["display_statistics_method"],
            "错因分布": [{"错因": row["label"], "人数": row["count"], "占比": f"{row['percentage']:.1f}%"}
                for row in classroom["cause_distribution"]]}},
    }


def _student(root: Path, student_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    content = read_json(root / "data" / "content-v1.1.json")
    student = next((row for row in content["students"] if row["id"] == student_id), None)
    if student is None:
        raise ValueError("未知模拟学生")
    return content, student


def verification_question(student_id: str, *, root: Path = ROOT) -> dict[str, Any]:
    _, student = _student(root, student_id)
    return {"student_id": student_id, "student_name": student["name"], "stem": student["transfer"]["q"], "input_type": "text", "input_hint": "输入未知数的数值，或写成 x=…", "source": "内容数据 v1.1"}



def bootstrap(root: Path = ROOT) -> dict:
    return {
        **{name: read_json(root / "data" / f"{name}.json") for name in ("unit", "causes", "students", "questions")},
        "classroom": {"classroom": computed_classroom(root)},
        "demo_label": "演示数据 · 模拟学生",
        "content_version": "v1.1",
        "demo_context": read_demo_context(root)["display"],
    }


def microcourses(root: Path = ROOT) -> dict:
    rows = []
    for student_id, course in case_index(root)["microcourses"].items():
        path = course["cache_path"]
        record = read_cache(root, path)
        rows.append({"student_id": student_id, "duration_sec": course["duration_sec"],
                     "video_url": f"/microcourses/microcourse-{student_id}.mp4",
                     "model_meta": cache_meta(record, Path(path))})
    return {"microcourses": rows}

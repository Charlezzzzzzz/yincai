"""Read-only evidence for the cached eight-step cockpit comparison.

This module never calls a model and never writes a cache. Display projections
are distinct from the original protocol objects so field names cannot leak
into the minimal interface by accidentally rendering raw cache JSON.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .case_files import ROOT, case_index, read_cache_bytes
MAIN_STEP_LABELS = {
    "01": "学情分析师诊断", "02": "学科专家校验", "03": "教学设计师设计",
    "04": "多模态制作人初稿", "05": "核查员退回", "06": "多模态制作人修订",
    "07": "核查员通过", "08": "教师助理交付",
}
VISIBLE_FIELDS = ("steps", "voiceover", "summary", "title", "student_safe_diagnosis", "visual_plan", "migration_question")


def _visible_strings(payload: dict[str, Any]):
    for key in VISIBLE_FIELDS:
        value = payload.get(key)
        if isinstance(value, str):
            yield key, value
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    yield f"{key}[{index}]", item


def _sentences(text: str):
    """Return unmodified sentence spans, preserving all punctuation."""
    start = 0
    for match in re.finditer(r"[。！？!?]+", text):
        end = match.end()
        yield start, end, text[start:end]
        start = end
    if start < len(text):
        yield start, len(text), text[start:]


def _quoted_evidence(reason: str) -> list[str]:
    matches = re.finditer(r'“([^”\n]+)”|「([^」\n]+)」|『([^』\n]+)』|"([^"\n]+)"', reason)
    return list(dict.fromkeys(next(group for group in match.groups() if group is not None) for match in matches))


def locate_supported_highlight(draft: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """Only highlight a draft sentence supported by an exact reviewer quote.

    All offsets use Python Unicode-code-point indices into the named field.
    Multiple exact matches are preserved; steps precede voiceover for the
    primary display. A missing match is data, never permission to invent one.
    """
    result: dict[str, Any] = {"matched": False, "highlight": None, "matches": [], "reason": ""}
    if review.get("verdict") != "reject" or "direct_answer" not in review.get("violations", []):
        result["reason"] = "核查记录没有明确的直接给出答案退回判定，未生成高亮。"
        return result
    reason = review.get("reason")
    if not isinstance(reason, str):
        result["reason"] = "核查记录缺少原话，无法核对高亮。"
        return result
    quotes = _quoted_evidence(reason)
    if not quotes:
        result["reason"] = "核查原话没有引用可逐字定位的泄题片段，未生成高亮。"
        return result
    for field, text in _visible_strings(draft):
        for start, end, sentence in _sentences(text):
            for quote in quotes:
                offset = sentence.find(quote)
                if offset < 0:
                    continue
                # Full sentence and supporting substring are both exact spans.
                result["matches"].append({
                    "field_path": field, "start": start, "end": end, "sentence": sentence,
                    "checker_quote": quote, "quote_start": start + offset,
                    "quote_end": start + offset + len(quote), "verbatim": True,
                })
    if not result["matches"]:
        result["reason"] = "核查引用无法在初稿可见正文中逐字定位，未生成高亮。"
        return result
    result.update(matched=True, highlight=result["matches"][0], reason="高亮为初稿原句，且包含核查员逐字引用的证据。")
    return result


def extract_revision_sentence(highlight: dict[str, Any] | None, draft: dict[str, Any], repaired: dict[str, Any]) -> dict[str, Any]:
    """Find a verifiable same-step counterpart, not a semantic paraphrase."""
    empty = {"matched": False, "sentence": None, "field_path": None, "start": None, "end": None,
             "reason": "没有可验证的初稿高亮位置，未指定修订对应句。"}
    if not highlight:
        return empty
    match = re.fullmatch(r"steps\[(\d+)\]", str(highlight.get("field_path", "")))
    if not match:
        empty["reason"] = "初稿证据不在可按序号核对的步骤字段，未猜测修订对应句。"
        return empty
    index = int(match.group(1))
    old_steps, new_steps = draft.get("steps"), repaired.get("steps")
    if not isinstance(old_steps, list) or not isinstance(new_steps, list) or index >= min(len(old_steps), len(new_steps)):
        empty["reason"] = "修订稿缺少初稿对应序号，未指定修订对应句。"
        return empty
    old, new = old_steps[index], new_steps[index]
    if not isinstance(old, str) or not isinstance(new, str):
        return empty
    old_title = re.split(r"[：:]", old, maxsplit=1)[0]
    new_title = re.split(r"[：:]", new, maxsplit=1)[0]
    if old_title != new_title or not re.match(r"^\s*\d+[.、．]\s*", old_title):
        empty["reason"] = "同序号步骤标题不一致，未按语义猜测或强接修订句。"
        return empty
    quoted = str(highlight.get("checker_quote", ""))
    if not quoted or quoted in new:
        empty["reason"] = "修订同一步仍含核查引用，未将其当作已移除的安全对应句。"
        return empty
    spans = list(_sentences(new))
    if len(spans) != 1:
        empty["reason"] = "修订同一步含多句，无法仅凭序号确定对应的那一句。"
        return empty
    start, end, sentence = spans[0]
    return {"matched": True, "sentence": sentence, "field_path": f"steps[{index}]", "start": start, "end": end,
            "reason": "按相同步骤序号及相同段落标题对应；原泄题句已删除，展示修订该步的逐字原句。"}


def _read_main_chain(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    ledger = json.loads((root / "artifacts/evidence/sources.json").read_text(encoding="utf-8"))
    selected: dict[str, dict[str, Any]] = {}
    for row in ledger:
        matched = re.match(r"^(0[1-8])\s", str(row.get("step", "")))
        if not matched:
            continue
        number = matched.group(1)
        if number in selected:
            if selected[number] != row:
                raise ValueError(f"缓存主链第{number}步有冲突来源")
            continue
        selected[number] = row
    if set(selected) != set(MAIN_STEP_LABELS):
        raise ValueError("缓存主链必须完整包含八步")
    records = []
    source_files = case_index(root)["records"]
    seen_hashes: set[str] = set()
    for number in MAIN_STEP_LABELS:
        row = selected[number]
        path = Path(row["cache_path"])
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        if not path.is_relative_to(root / "cache/model"):
            raise ValueError("主链来源不在约定的本地模型缓存目录")
        relative = path.relative_to(root).as_posix()
        raw = read_cache_bytes(root, relative)
        record = json.loads(raw)
        input_hash = record.get("input_hash")
        if input_hash in seen_hashes:
            raise ValueError("缓存主链的不同步骤复用了同一输入哈希，不能重复计时")
        seen_hashes.add(input_hash)
        if not input_hash or input_hash != row["input_hash"] or path.stem != input_hash:
            raise ValueError("来源表与真实缓存输入哈希不一致")
        if Decimal(str(record["elapsed_ms"])) != Decimal(str(row["elapsed_ms"])):
            raise ValueError("来源表与真实缓存耗时不一致")
        if record.get("deprecated") or not isinstance(record.get("parsed"), dict):
            raise ValueError("主链缓存已弃用或缺少模型原文")
        for left, right in ((record.get("model_name", record.get("model")), row.get("model")),
                            (record.get("prompt_version"), row.get("prompt_version")),
                            (record.get("created_at", record.get("timestamp")), row.get("generated_at"))):
            if left != right:
                raise ValueError("来源表与真实缓存元数据不一致")
        records.append({"number": number, "label": MAIN_STEP_LABELS[number], "row": row, "record": record,
                        "cache_path": relative, "file_sha256": hashlib.sha256(raw).hexdigest(),
                        "original_sha256": source_files[relative]["original_sha256"]})
    return records


def read_demo_context(root: Path = ROOT) -> dict[str, Any]:
    """Resolve the displayed problem from content files, never from a label."""
    canonical_path = root / "data/content-v1.1.json"
    questions_path = root / "data/questions.json"
    students_path = root / "data/students.json"
    try:
        canonical_data = json.loads(canonical_path.read_text(encoding="utf-8"))
        question_data = json.loads(questions_path.read_text(encoding="utf-8"))
        student_data = json.loads(students_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("演示题来源文件不可读取，题号及算式待核对") from exc
    question_id = canonical_data.get("demo_item")
    if not isinstance(question_id, str) or not question_id:
        raise ValueError("主数据演示题编号缺失，题号待核对")
    if question_data.get("demo_question_id") != question_id:
        raise ValueError("适配层演示题编号与主数据不一致，题号待核对")
    items = canonical_data.get("items")
    if not isinstance(items, list):
        raise ValueError("主数据题目列表缺失，题目待核对")
    source_matches = [(index, row) for index, row in enumerate(items)
                      if isinstance(row, dict) and row.get("id") == question_id]
    if len(source_matches) != 1:
        raise ValueError("主数据演示题必须唯一对应题目，题目待核对")
    canonical_index, canonical_item = source_matches[0]
    numbered = re.fullmatch(r"Q([1-9]\d*)", question_id)
    if not numbered:
        raise ValueError("演示题编号无法解析题序，题号待核对")
    questions = question_data.get("questions", [])
    if not isinstance(questions, list):
        raise ValueError("适配层题目列表缺失，题目待核对")
    matches = [row for row in questions if isinstance(row, dict) and row.get("id") == question_id]
    if len(matches) != 1:
        raise ValueError("演示题编号必须唯一对应题目，题号待核对")
    for field, label in (("stem", "题干"), ("answer", "答案")):
        if field not in canonical_item or field not in matches[0]:
            raise ValueError(f"演示题{label}缺失，主数据与适配层待核对")
        original, adapted = canonical_item[field], matches[0][field]
        if original is None or (isinstance(original, str) and not original.strip()):
            raise ValueError(f"主数据演示题{label}为空，题目待核对")
        if type(original) is not type(adapted) or original != adapted:
            raise ValueError(f"演示题{label}在主数据与适配层的值或类型不一致，题目待核对")
    stem = canonical_item["stem"]
    if not isinstance(stem, str) or not stem.strip():
        raise ValueError("演示题缺少题目原文，算式待核对")
    students = student_data.get("students", [])
    if not isinstance(students, list) or not students:
        raise ValueError("模拟学生记录缺失，演示题号待核对")
    student_sources = []
    seen = set()
    for index, student in enumerate(students):
        if not isinstance(student, dict) or not student.get("id") or student["id"] in seen:
            raise ValueError("模拟学生编号缺失或重复，演示题号待核对")
        seen.add(student["id"])
        attempt = student.get("latest_attempt")
        if not isinstance(attempt, dict) or attempt.get("question_id") != question_id:
            raise ValueError("学生最近作答的题号与演示题不一致，题号及算式待核对")
        student_sources.append({"student_id": student["id"], "student_name": student.get("name", ""),
                                "question_id": attempt["question_id"],
                                "field_path": f"students[{index}].latest_attempt.question_id"})
    label = f"第{int(numbered.group(1))}题"
    return {
        "display": {"题号": label, "题号标识": question_id, "题目": stem,
                    "来源": "□ 内容数据 · 模拟学生记录",
                    "来源说明": "以内容包为主数据，核对适配层题干及答案逐字和类型一致，再逐一核对模拟学生最近作答题号。",
                    "来源明细": [
                        {"文件": "data/content-v1.1.json", "读取内容": "主数据演示题编号，以及对应题目原始编号、题干、答案"},
                        {"文件": "data/questions.json", "读取内容": "适配层演示题编号、题干及答案，与主数据完全一致"},
                        {"文件": "data/students.json", "读取内容": "每名模拟学生最近作答的题号"},
                    ]},
        "protocol": {"question_id": question_id, "question_number": int(numbered.group(1)),
                     "question_label": label, "stem": stem, "answer": canonical_item["answer"], "students": student_sources,
                     "canonical_item_index": canonical_index,
                     "source_fields": {"canonical_demo_id": "data/content-v1.1.json:demo_item",
                                       "canonical_item": f"data/content-v1.1.json:items[{canonical_index}](id/stem/answer)",
                                       "demo_question_id": "data/questions.json:demo_question_id",
                                       "stem": f"data/questions.json:questions[id={question_id}].stem",
                                       "student_question_id": "data/students.json:students[].latest_attempt.question_id"}},
    }


def _body_display(payload: dict[str, Any]) -> dict[str, Any]:
    # Only known protocol fields receive human-facing Chinese labels. Unknown
    # fields remain in protocol; never dump an unreviewed schema into the UI.
    labels = {"title": "标题", "summary": "摘要", "student_safe_diagnosis": "诊断说明", "steps": "步骤",
              "visual_plan": "画面方案", "voiceover": "旁白", "migration_question": "迁移题",
              "evidence": "证据", "rationale": "设计理由", "teacher_summary": "教师摘要",
              "recommendation": "教研建议", "reason": "核查原话", "misconception_id": "错因",
              "confidence": "置信度", "learner_state": "学情判断", "knowledge_points": "知识点",
              "student_safe_summary": "学生可见说明", "strategy_name": "策略名称", "media_form": "呈现形式"}
    body = {label: payload[key] for key, label in labels.items() if key in payload}
    if isinstance(payload.get("violations"), list):
        from .presentation_data import localize_error_type
        body["错误类型"] = [localize_error_type(value) for value in payload["violations"]]
    return body


def build_cockpit_comparison(root: Path = ROOT) -> dict[str, Any]:
    """Return Chinese display fields plus separately retained raw protocol."""
    records = _read_main_chain(root)
    context = read_demo_context(root)
    cache_question_ids = {}
    for row in records:
        question = row["record"].get("request", {}).get("context", {}).get("question")
        if not isinstance(question, dict) or question.get("id") != context["protocol"]["question_id"]:
            raise ValueError(f"缓存第{row['number']}步的题号与主数据演示题不一致，题目待核对")
        cache_question_ids[row["number"]] = question["id"]
    context["protocol"]["main_cache_question_ids"] = cache_question_ids
    by_number = {row["number"]: row for row in records}
    draft, checker, repaired = (by_number[number]["record"]["parsed"] for number in ("04", "05", "06"))
    checker_context = by_number["05"]["record"].get("request", {}).get("context", {})
    repair_context = by_number["06"]["record"].get("request", {}).get("context", {})
    if checker_context.get("draft") != draft:
        raise ValueError("核查缓存的实际输入不是所选初稿，无法建立对比证据")
    if repair_context.get("rejected_draft") != draft or repair_context.get("checker_output") != checker:
        raise ValueError("修订缓存的实际输入与所选初稿或核查意见不一致")
    located = locate_supported_highlight(draft, checker)
    revision = extract_revision_sentence(located["highlight"], draft, repaired)
    total = sum((Decimal(str(row["record"]["elapsed_ms"])) for row in records), Decimal("0")) / Decimal("1000")
    from .presentation_data import localize_verdict, localize_error_type
    provenance = []
    step_details = {}
    for row in records:
        parsed = row["record"]["parsed"]
        has_verdict = bool(parsed.get("verdict"))
        metadata = {"步骤": row["number"], "名称": row["label"], "来源": "○ 真实缓存",
                    "判定": localize_verdict(parsed["verdict"]) if has_verdict else "完成",
                    "判定来源": "模型原始判定" if has_verdict else "界面完成状态（非模型判定）",
                    "模型": row["row"]["model"], "耗时": f"{Decimal(str(row['record']['elapsed_ms'])) / Decimal('1000'):.1f} s",
                    "提示词版本": row["row"]["prompt_version"], "生成时间": row["row"]["generated_at"],
                    "缓存路径": row["cache_path"], "输入哈希": row["row"]["input_hash"], "文件哈希": row["file_sha256"],
                    "原始归档文件哈希": row["original_sha256"]}
        provenance.append(metadata)
        step_details[row["number"]] = {**metadata, "正文": _body_display(parsed)}
    high = located["highlight"]
    return {
        "display": {
            "来源": "○ 真实缓存", "说明": "演示用反例",
            "context": context["display"],
            "证据链": "已核对核查实际输入为该初稿，修订实际输入包含同一初稿和核查意见。",
            "初稿": {"步骤": "04", "名称": MAIN_STEP_LABELS["04"], "原文": _body_display(draft)},
            "核查": {"步骤": "05", "名称": MAIN_STEP_LABELS["05"], "原话": checker.get("reason", ""),
                     "判定": localize_verdict(checker.get("verdict")),
                     "错误类型": [localize_error_type(value) for value in checker.get("violations", [])]},
            "修订": {"步骤": "06", "名称": MAIN_STEP_LABELS["06"], "原文": _body_display(repaired)},
            "高亮": {"已定位": located["matched"], "原句": high["sentence"] if high else None,
                     "核查引用": high["checker_quote"] if high else None, "逐字匹配": bool(high), "说明": located["reason"]},
            "修订对应句": {"已定位": revision["matched"], "原句": revision["sentence"], "说明": revision["reason"]},
            "总耗时": {"标签": "缓存轮八步合计", "来源": "○ 真实缓存", "秒": float(total),
                      "显示": f"{total:.1f} s", "计算方法": "该缓存轮八个不同输入哈希的模型耗时各计一次，不含现场实时生成任务。"},
            "来源明细": provenance,
            "步骤详情": step_details,
        },
        "protocol": {"context": context["protocol"], "draft": draft, "review": checker, "repaired": repaired,
                     "highlight": located, "revision_match": revision,
                     "main_step_input_hashes": [row["row"]["input_hash"] for row in records],
                     "cache_round_elapsed_seconds": float(total),
                     "steps": {row["number"]: row["record"]["parsed"] for row in records}},
    }

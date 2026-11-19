"""Evidence envelopes for the eight-step cached teaching case."""
import json

from app.cockpit_comparison import build_cockpit_comparison
from student_alias import display_alias

STEPS = (
    ("analyst", "诊断"), ("expert", "校验"), ("designer", "设计"),
    ("producer", "初稿"), ("checker", "核查退回"), ("producer", "修订"),
    ("checker", "复核通过"), ("assistant", "交付"),
)
NAMES = {"analyst":"学情分析师", "expert":"学科专家", "designer":"教学设计师",
         "producer":"多模态制作人", "checker":"核查员", "assistant":"教师助理", "teacher":"任课教师"}


def destinations(role):
    return {STEPS[i+1][0] for i in range(len(STEPS)-1) if STEPS[i][0] == role}


def cache_events(comparison):
    """Build deterministic message IDs from the original verified file digest."""
    details = comparison["display"]["步骤详情"]
    protocol = comparison["protocol"]
    events = []
    for i, (sender, stage) in enumerate(STEPS):
        number = f"{i+1:02d}"
        meta = details[number]
        target = STEPS[i+1][0] if i+1 < len(STEPS) else "teacher"
        events.append({
            "event_id": f"cache:{number}:{meta['原始归档文件哈希']}", "seq": i+1,
            "type": "case.handoff", "case_id": protocol["context"]["question_id"],
            "sender": sender, "recipient": target, "stage": stage, "source": "cache",
            "routing_source": "rule", "visibility": "teaching_case", "previous_event_id": events[-1]["event_id"] if events else None,
            "model": meta["模型"], "generated_at": meta["生成时间"], "evidence_path":meta["缓存路径"],
            "input_hash": meta["输入哈希"], "file_sha256":meta["文件哈希"],
            "archived_file_sha256": meta["原始归档文件哈希"],
        })
    return events


def role_context(root, role):
    comparison = build_cockpit_comparison(root)
    protocol = comparison["protocol"]
    # Deliver only the incoming and outgoing case records at this role's edges.
    evidence = []
    for event in cache_events(comparison):
        if role in (event["sender"], event["recipient"]):
            body = display_alias(protocol["steps"][f"{event['seq']:02d}"])
            # Bound each exhibit independently so a long early draft cannot hide a later verdict.
            evidence.append({"step":f"{event['seq']:02d}", "from":event["sender"], "to":event["recipient"],
                             "stage":event["stage"], "source":"cache", "evidence_path":event["evidence_path"],
                             "excerpt":json.dumps(body, ensure_ascii=False)[:1800]})
    return protocol["cache_round_elapsed_seconds"], json.dumps(evidence, ensure_ascii=False)

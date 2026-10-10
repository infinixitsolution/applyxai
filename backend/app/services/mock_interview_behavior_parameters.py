"""On-camera behavioral analysis parameter catalog (55 parameters)."""

from __future__ import annotations

from dataclasses import dataclass

BEHAVIOR_ANALYSIS_VERSION = 1


@dataclass(frozen=True)
class BehaviorParameter:
    id: int
    category_id: str
    category_label: str
    key: str
    label: str
    criteria: str
    modality: str = "video"  # video | audio | video_limited


BEHAVIOR_PARAMETERS: tuple[BehaviorParameter, ...] = (
    # 1. Eye contact & gaze (1–5)
    BehaviorParameter(1, "eye_gaze", "Eye Contact & Gaze Behavior", "camera_gaze_frequency", "Camera gaze frequency", "How often the candidate looks toward the camera"),
    BehaviorParameter(2, "eye_gaze", "Eye Contact & Gaze Behavior", "gaze_stability", "Gaze stability", "Whether gaze is reasonably stable or frequently shifts"),
    BehaviorParameter(3, "eye_gaze", "Eye Contact & Gaze Behavior", "screen_attention", "Screen attention", "Observable attention toward the interviewer or screen"),
    BehaviorParameter(4, "eye_gaze", "Eye Contact & Gaze Behavior", "gaze_shift_frequency", "Gaze shift frequency", "Frequency of looking away from the screen"),
    BehaviorParameter(5, "eye_gaze", "Eye Contact & Gaze Behavior", "head_camera_orientation", "Head-to-camera orientation", "Whether the head is generally oriented toward the camera"),
    # 2. Facial expression & engagement (6–10)
    BehaviorParameter(6, "facial_engagement", "Facial Expression & Engagement", "facial_visibility", "Facial visibility", "Whether the face is sufficiently visible"),
    BehaviorParameter(7, "facial_engagement", "Facial Expression & Engagement", "expression_variation", "Expression variation", "Observable changes in facial expression"),
    BehaviorParameter(8, "facial_engagement", "Facial Expression & Engagement", "smile_frequency", "Smile frequency", "Frequency of smiling, reported descriptively"),
    BehaviorParameter(9, "facial_engagement", "Facial Expression & Engagement", "engagement_cues", "Visible engagement cues", "Observable responses while listening or speaking"),
    BehaviorParameter(
        10,
        "facial_engagement",
        "Facial Expression & Engagement",
        "expression_context_alignment",
        "Expression-context alignment",
        "Whether visible expressions appear consistent with the immediate conversational context, without inferring internal emotions",
    ),
    # 3. Posture & body language (11–15)
    BehaviorParameter(11, "posture", "Posture & Body Language", "upright_posture", "Upright posture", "Whether the upper body is generally upright"),
    BehaviorParameter(12, "posture", "Posture & Body Language", "posture_stability", "Posture stability", "Frequency of major posture changes"),
    BehaviorParameter(13, "posture", "Posture & Body Language", "head_movement", "Head movement", "Frequency and range of head movements"),
    BehaviorParameter(14, "posture", "Posture & Body Language", "body_orientation", "Body orientation", "Whether the upper body generally faces the camera"),
    BehaviorParameter(15, "posture", "Posture & Body Language", "excessive_movement", "Excessive movement", "Frequency of repeated or distracting movements within the frame"),
    # 4. Hand gestures (16–20)
    BehaviorParameter(16, "gestures", "Hand Gestures & Movement", "gesture_frequency", "Gesture frequency", "How often visible hand gestures occur"),
    BehaviorParameter(17, "gestures", "Hand Gestures & Movement", "gesture_visibility", "Gesture visibility", "Whether gestures are visible in the camera frame"),
    BehaviorParameter(18, "gestures", "Hand Gestures & Movement", "gesture_repetition", "Gesture repetition", "Frequency of repeated gestures"),
    BehaviorParameter(19, "gestures", "Hand Gestures & Movement", "movement_distraction", "Movement distraction", "Whether movement repeatedly obstructs communication"),
    BehaviorParameter(20, "gestures", "Hand Gestures & Movement", "gesture_speech_timing", "Gesture-speech timing", "Whether visible gestures occur alongside relevant speech segments"),
    # 5. Camera presence & video quality (21–25)
    BehaviorParameter(21, "video_quality", "Camera Presence & Video Quality", "face_in_frame", "Face-in-frame consistency", "Whether the face remains inside the frame"),
    BehaviorParameter(22, "video_quality", "Camera Presence & Video Quality", "camera_distance", "Camera distance", "Whether framing makes the face sufficiently visible"),
    BehaviorParameter(23, "video_quality", "Camera Presence & Video Quality", "lighting_adequacy", "Lighting adequacy", "Whether lighting allows facial features to be seen"),
    BehaviorParameter(24, "video_quality", "Camera Presence & Video Quality", "video_stability", "Video stability", "Whether camera shake disrupts visibility"),
    BehaviorParameter(
        25,
        "video_quality",
        "Camera Presence & Video Quality",
        "av_synchronization",
        "Audio-video synchronization",
        "Whether visible speech movements broadly align with audio timing",
        modality="video_limited",
    ),
    # 6. Prohibited activities (26–33)
    BehaviorParameter(26, "prohibited", "Prohibited Activities", "smoking_detection", "Smoking detection", "Visible smoking activity or a cigarette/vape being used"),
    BehaviorParameter(27, "prohibited", "Prohibited Activities", "eating_during_interview", "Eating during interview", "Repeatedly eating food while answering"),
    BehaviorParameter(28, "prohibited", "Prohibited Activities", "drinking_during_interview", "Drinking during interview", "Drinking from a cup or bottle"),
    BehaviorParameter(29, "prohibited", "Prohibited Activities", "mobile_phone_usage", "Mobile phone usage", "Looking at, holding, or operating a phone"),
    BehaviorParameter(30, "prohibited", "Prohibited Activities", "secondary_device_usage", "Secondary device usage", "Visible use of a tablet, smartwatch, or another device"),
    BehaviorParameter(31, "prohibited", "Prohibited Activities", "unauthorized_assistance", "Unauthorized person assistance", "Another person visibly prompting or answering for the candidate"),
    BehaviorParameter(32, "prohibited", "Prohibited Activities", "leaving_interview_area", "Leaving interview area", "Candidate leaves the camera view for an extended period"),
    BehaviorParameter(33, "prohibited", "Prohibited Activities", "camera_obstruction", "Repeated camera obstruction", "Camera is repeatedly covered or the view is deliberately blocked"),
    # 7. Distracting / unprofessional (34–43)
    BehaviorParameter(34, "distracting", "Distracting or Unprofessional Behaviors", "hair_adjustment", "Repeated hair adjustment", "Frequently touching or setting hair"),
    BehaviorParameter(35, "distracting", "Distracting or Unprofessional Behaviors", "face_touching", "Face touching", "Repeated touching of the face"),
    BehaviorParameter(36, "distracting", "Distracting or Unprofessional Behaviors", "nose_touching", "Nose touching or rubbing", "Repeated visible nose contact"),
    BehaviorParameter(37, "distracting", "Distracting or Unprofessional Behaviors", "beard_adjustment", "Beard or moustache adjustment", "Repeated grooming during answers"),
    BehaviorParameter(38, "distracting", "Distracting or Unprofessional Behaviors", "clothing_adjustment", "Clothing adjustment", "Repeatedly adjusting clothes"),
    BehaviorParameter(39, "distracting", "Distracting or Unprofessional Behaviors", "accessory_adjustment", "Accessory adjustment", "Repeatedly adjusting glasses, headphones, or jewelry"),
    BehaviorParameter(40, "distracting", "Distracting or Unprofessional Behaviors", "nail_biting", "Nail biting", "Visible nail biting"),
    BehaviorParameter(41, "distracting", "Distracting or Unprofessional Behaviors", "object_fidgeting", "Object fidgeting", "Repeatedly playing with pens or other objects"),
    BehaviorParameter(42, "distracting", "Distracting or Unprofessional Behaviors", "excessive_body_movement", "Excessive body movement", "Repetitive movement that visibly disrupts the interview"),
    BehaviorParameter(43, "distracting", "Distracting or Unprofessional Behaviors", "camera_adjustment", "Repeated camera adjustment", "Frequently repositioning the webcam or device"),
    # 8. Interview integrity (44–50)
    BehaviorParameter(44, "integrity", "Potential Interview Integrity Concerns", "off_screen_glances", "Repeated off-screen glances", "Frequent gaze shifts away from the interview screen"),
    BehaviorParameter(45, "integrity", "Potential Interview Integrity Concerns", "suspected_script_reading", "Suspected script reading", "Repeated reading-like gaze patterns combined with other evidence"),
    BehaviorParameter(46, "integrity", "Potential Interview Integrity Concerns", "notes_consultation", "Visible notes consultation", "Looking at or handling notes while answering"),
    BehaviorParameter(47, "integrity", "Potential Interview Integrity Concerns", "multiple_people", "Multiple people in frame", "More than one person appears in the camera view"),
    BehaviorParameter(
        48,
        "integrity",
        "Potential Interview Integrity Concerns",
        "off_camera_voice",
        "Off-camera voice assistance",
        "Another voice is detected in the audio",
        modality="audio",
    ),
    BehaviorParameter(49, "integrity", "Potential Interview Integrity Concerns", "interview_interruptions", "Repeated interview interruptions", "Unexplained interruptions or prolonged pauses"),
    BehaviorParameter(50, "integrity", "Potential Interview Integrity Concerns", "external_help", "Possible use of external help", "Observable use of another device or person during an answer"),
    # 9. Camera / feed integrity (51–55)
    BehaviorParameter(51, "feed_integrity", "Camera and Interview Integrity Events", "face_disappearance", "Face disappearance", "Face becomes undetectable for a specified duration"),
    BehaviorParameter(52, "feed_integrity", "Camera and Interview Integrity Events", "video_feed_interruption", "Video feed interruption", "Camera feed freezes or disconnects"),
    BehaviorParameter(
        53,
        "feed_integrity",
        "Camera and Interview Integrity Events",
        "repeated_audio_muting",
        "Repeated audio muting",
        "Audio repeatedly becomes unavailable",
        modality="audio",
    ),
    BehaviorParameter(
        54,
        "feed_integrity",
        "Camera and Interview Integrity Events",
        "suspected_video_replay",
        "Suspected video replay or injection",
        "Potential prerecorded or manipulated video indicators requiring technical verification",
        modality="video_limited",
    ),
    BehaviorParameter(55, "feed_integrity", "Camera and Interview Integrity Events", "environment_changes", "Repeated environment changes", "Camera view or interview location changes unexpectedly"),
)

_BY_ID = {p.id: p for p in BEHAVIOR_PARAMETERS}

PROHIBITED_TO_CONDUCT: dict[str, str] = {
    "smoking_detection": "smoking",
    "eating_during_interview": "eating",
    "drinking_during_interview": "off_camera_behavior",
    "mobile_phone_usage": "phone_use",
    "secondary_device_usage": "phone_use",
    "unauthorized_assistance": "off_camera_behavior",
    "leaving_interview_area": "off_camera_behavior",
    "camera_obstruction": "off_camera_behavior",
}


def behavior_prompt_catalog() -> str:
    lines: list[str] = []
    last_cat = ""
    for p in BEHAVIOR_PARAMETERS:
        if p.category_label != last_cat:
            lines.append(f"\n## {p.category_label}")
            last_cat = p.category_label
        mod = f" [{p.modality}]" if p.modality != "video" else ""
        lines.append(f"{p.id}. {p.label} ({p.key}){mod}: {p.criteria}")
    return "\n".join(lines)


def empty_behavior_scores() -> list[dict]:
    return [
        {
            "id": p.id,
            "category_id": p.category_id,
            "category_label": p.category_label,
            "key": p.key,
            "label": p.label,
            "score": None,
            "status": "not_observable",
            "detected": False,
            "notes": "Not assessed.",
        }
        for p in BEHAVIOR_PARAMETERS
    ]


def normalize_behavior_scores(raw: list | None) -> list[dict]:
    by_id: dict[int, dict] = {}
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            try:
                pid = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            if pid in _BY_ID:
                by_id[pid] = row

    out: list[dict] = []
    for p in BEHAVIOR_PARAMETERS:
        row = by_id.get(p.id, {})
        status = str(row.get("status") or "not_observable").lower().replace(" ", "_")
        if status not in ("ok", "concern", "not_observable", "na"):
            status = "concern" if row.get("detected") else "not_observable"
        score = row.get("score")
        try:
            score = int(score) if score is not None else None
            if score is not None:
                score = max(0, min(100, score))
        except (TypeError, ValueError):
            score = None
        detected = bool(row.get("detected")) or status == "concern"
        if p.category_id == "prohibited" and detected and score is None:
            score = 15
        if status == "ok" and score is None:
            score = 80
        if status == "not_observable" or status == "na":
            score = None
            detected = False if status == "not_observable" else bool(row.get("detected"))
        notes = str(row.get("notes") or "").strip() or ("Not observable from stills." if status == "not_observable" else "")
        out.append(
            {
                "id": p.id,
                "category_id": p.category_id,
                "category_label": p.category_label,
                "key": p.key,
                "label": p.label,
                "score": score,
                "status": status,
                "detected": detected,
                "notes": notes,
            }
        )
    return out


def behavior_categories_from_scores(scores: list[dict]) -> list[dict]:
    order: list[tuple[str, str]] = []
    seen: set[str] = set()
    for p in BEHAVIOR_PARAMETERS:
        if p.category_id not in seen:
            seen.add(p.category_id)
            order.append((p.category_id, p.category_label))
    buckets: dict[str, list[int]] = {cid: [] for cid, _ in order}
    concerns: dict[str, int] = {cid: 0 for cid, _ in order}
    for row in scores:
        cid = row.get("category_id")
        if cid not in buckets:
            continue
        if row.get("status") == "concern" or row.get("detected"):
            concerns[cid] = concerns.get(cid, 0) + 1
        if row.get("score") is not None:
            buckets[cid].append(int(row["score"]))
    out: list[dict] = []
    for cid, label in order:
        vals = buckets[cid]
        avg = round(sum(vals) / len(vals)) if vals else None
        total = sum(1 for p in BEHAVIOR_PARAMETERS if p.category_id == cid)
        scored = len(vals)
        out.append(
            {
                "category_id": cid,
                "category_label": label,
                "average_score": avg,
                "parameters_scored": scored,
                "parameters_total": total,
                "concerns_detected": concerns.get(cid, 0),
            }
        )
    return out


def conduct_issues_from_behavior(scores: list[dict]) -> list[str]:
    issues: list[str] = []
    for row in scores:
        if row.get("category_id") != "prohibited":
            continue
        if not (row.get("detected") or row.get("status") == "concern"):
            continue
        code = PROHIBITED_TO_CONDUCT.get(str(row.get("key")), "")
        if code and code not in issues:
            issues.append(code)
        if str(row.get("key")) == "smoking_detection" and "smoking" not in issues:
            issues.append("smoking")
    return issues

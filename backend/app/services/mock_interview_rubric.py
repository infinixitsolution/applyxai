"""100-parameter mock interview analysis rubric (10 categories × 10 parameters)."""

from __future__ import annotations

from dataclasses import dataclass

RUBRIC_VERSION = 1


@dataclass(frozen=True)
class RubricParameter:
    id: int
    key: str
    label: str
    criteria: str
    category_id: str
    category_label: str


def _cat(cat_id: str, cat_label: str, items: list[tuple[str, str, str]]) -> list[RubricParameter]:
    out: list[RubricParameter] = []
    for key, label, criteria in items:
        pid = len(out) + sum(10 * i for i in range(int(cat_id.split("_")[1]) - 1))  # wrong
        out.append(RubricParameter(0, key, label, criteria, cat_id, cat_label))
    return out


# Built explicitly with global ids 1–100
_PARAMETERS: list[tuple[int, str, str, str, str, str]] = [
    # Category 1: Communication Skills (1–10)
    (1, "communication", "Communication Skills", "communication_clarity", "Communication clarity", "Clear and understandable answers"),
    (2, "communication", "Communication Skills", "verbal_fluency", "Verbal fluency", "Smoothness of speech"),
    (3, "communication", "Communication Skills", "grammar_accuracy", "Grammar accuracy", "Correct sentence construction"),
    (4, "communication", "Communication Skills", "vocabulary", "Vocabulary", "Appropriate word selection"),
    (5, "communication", "Communication Skills", "speaking_pace", "Speaking pace", "Suitable speaking speed"),
    (6, "communication", "Communication Skills", "filler_word_usage", "Filler word usage", "Frequency of unnecessary filler words"),
    (7, "communication", "Communication Skills", "articulation", "Articulation", "Clear pronunciation of words"),
    (8, "communication", "Communication Skills", "conciseness", "Conciseness", "Avoiding unnecessary details"),
    (9, "communication", "Communication Skills", "explanation_ability", "Explanation ability", "Explaining ideas in understandable terms"),
    (10, "communication", "Communication Skills", "professional_language", "Professional language", "Appropriate workplace communication"),
    # Category 2: Technical Knowledge (11–20)
    (11, "technical_knowledge", "Technical Knowledge", "fundamental_knowledge", "Fundamental knowledge", "Understanding of core concepts"),
    (12, "technical_knowledge", "Technical Knowledge", "technical_accuracy", "Technical accuracy", "Correctness of answers"),
    (13, "technical_knowledge", "Technical Knowledge", "conceptual_depth", "Conceptual depth", "Understanding beyond memorization"),
    (14, "technical_knowledge", "Technical Knowledge", "practical_implementation", "Practical implementation", "Applying concepts to real tasks"),
    (15, "technical_knowledge", "Technical Knowledge", "tool_proficiency", "Tool proficiency", "Knowledge of relevant tools"),
    (16, "technical_knowledge", "Technical Knowledge", "troubleshooting_knowledge", "Troubleshooting knowledge", "Diagnosing technical problems"),
    (17, "technical_knowledge", "Technical Knowledge", "coding_configuration_ability", "Coding/configuration ability", "Quality of code or configurations"),
    (18, "technical_knowledge", "Technical Knowledge", "best_practices", "Best practices", "Awareness of industry standards"),
    (19, "technical_knowledge", "Technical Knowledge", "technology_selection", "Technology selection", "Choosing appropriate technologies"),
    (20, "technical_knowledge", "Technical Knowledge", "technical_terminology", "Technical terminology", "Correct use of domain terminology"),
    # Category 3: Logical Reasoning (21–30)
    (21, "logical_reasoning", "Logical Reasoning", "logical_consistency", "Logical consistency", "Coherent reasoning"),
    (22, "logical_reasoning", "Logical Reasoning", "analytical_thinking", "Analytical thinking", "Breaking problems into components"),
    (23, "logical_reasoning", "Logical Reasoning", "critical_thinking", "Critical thinking", "Evaluating evidence and alternatives"),
    (24, "logical_reasoning", "Logical Reasoning", "root_cause_analysis", "Root cause analysis", "Finding underlying causes"),
    (25, "logical_reasoning", "Logical Reasoning", "decision_making", "Decision-making", "Selecting suitable solutions"),
    (26, "logical_reasoning", "Logical Reasoning", "solution_efficiency", "Solution efficiency", "Resource and time efficiency"),
    (27, "logical_reasoning", "Logical Reasoning", "creative_problem_solving", "Creative problem-solving", "Generating alternative approaches"),
    (28, "logical_reasoning", "Logical Reasoning", "handling_ambiguity", "Handling ambiguity", "Working with incomplete information"),
    (29, "logical_reasoning", "Logical Reasoning", "pattern_recognition", "Pattern recognition", "Identifying relevant patterns"),
    (30, "logical_reasoning", "Logical Reasoning", "risk_assessment", "Risk assessment", "Recognizing possible consequences"),
    # Category 4: Answer Quality (31–40)
    (31, "answer_quality", "Answer Quality", "answer_relevance", "Answer relevance", "Addressing the actual question"),
    (32, "answer_quality", "Answer Quality", "answer_completeness", "Answer completeness", "Covering essential points"),
    (33, "answer_quality", "Answer Quality", "answer_structure", "Answer structure", "Logical organization"),
    (34, "answer_quality", "Answer Quality", "explanation_depth", "Explanation depth", "Appropriate level of detail"),
    (35, "answer_quality", "Answer Quality", "use_of_examples", "Use of examples", "Supporting answers with examples"),
    (36, "answer_quality", "Answer Quality", "evidence_based_answers", "Evidence-based answers", "Using verifiable evidence"),
    (37, "answer_quality", "Answer Quality", "follow_up_handling", "Follow-up handling", "Responding to probing questions"),
    (38, "answer_quality", "Answer Quality", "uncertainty_acknowledgment", "Uncertainty acknowledgment", "Admitting knowledge gaps appropriately"),
    (39, "answer_quality", "Answer Quality", "answer_consistency", "Answer consistency", "Avoiding contradictions across responses"),
    (40, "answer_quality", "Answer Quality", "question_interpretation", "Question interpretation", "Correctly understanding the question"),
    # Category 5: Coding and Technical Execution (41–50)
    (41, "technical_execution", "Coding and Technical Execution", "algorithm_design", "Algorithm design", "Designing suitable algorithms"),
    (42, "technical_execution", "Coding and Technical Execution", "code_correctness", "Code correctness", "Producing functionally correct code"),
    (43, "technical_execution", "Coding and Technical Execution", "code_readability", "Code readability", "Writing understandable code"),
    (44, "technical_execution", "Coding and Technical Execution", "code_efficiency", "Code efficiency", "Time and space complexity"),
    (45, "technical_execution", "Coding and Technical Execution", "debugging_ability", "Debugging ability", "Identifying and fixing errors"),
    (46, "technical_execution", "Coding and Technical Execution", "testing_methodology", "Testing methodology", "Selecting appropriate test cases"),
    (47, "technical_execution", "Coding and Technical Execution", "edge_case_handling", "Edge-case handling", "Accounting for unusual inputs"),
    (48, "technical_execution", "Coding and Technical Execution", "security_awareness", "Security awareness", "Identifying security risks"),
    (49, "technical_execution", "Coding and Technical Execution", "maintainability", "Maintainability", "Producing code that can be maintained"),
    (50, "technical_execution", "Coding and Technical Execution", "technical_tradeoff_analysis", "Technical trade-off analysis", "Explaining implementation trade-offs"),
    # Category 6: Experience and Project Evaluation (51–60)
    (51, "experience", "Experience and Project Evaluation", "project_explanation", "Project explanation", "Describing project purpose and design"),
    (52, "experience", "Experience and Project Evaluation", "individual_contribution", "Individual contribution", "Explaining personal responsibilities"),
    (53, "experience", "Experience and Project Evaluation", "architecture_understanding", "Architecture understanding", "Understanding system components"),
    (54, "experience", "Experience and Project Evaluation", "challenge_resolution", "Challenge resolution", "Explaining how obstacles were addressed"),
    (55, "experience", "Experience and Project Evaluation", "measurable_outcomes", "Measurable outcomes", "Providing evidence of results"),
    (56, "experience", "Experience and Project Evaluation", "ownership", "Ownership", "Demonstrating responsibility for assigned work"),
    (57, "experience", "Experience and Project Evaluation", "experience_relevance", "Experience relevance", "Relating experience to the target role"),
    (58, "experience", "Experience and Project Evaluation", "production_experience", "Production experience", "Understanding real-world deployment and operations"),
    (59, "experience", "Experience and Project Evaluation", "lessons_learned", "Lessons learned", "Explaining insights gained from past work"),
    (60, "experience", "Experience and Project Evaluation", "project_decision_rationale", "Project decision rationale", "Justifying important design choices"),
    # Category 7: Behavioral Competencies (61–70)
    (61, "behavioral", "Behavioral Competencies", "teamwork", "Teamwork", "Effective collaboration"),
    (62, "behavioral", "Behavioral Competencies", "conflict_resolution", "Conflict resolution", "Handling disagreements constructively"),
    (63, "behavioral", "Behavioral Competencies", "adaptability", "Adaptability", "Responding to changing circumstances"),
    (64, "behavioral", "Behavioral Competencies", "accountability", "Accountability", "Taking responsibility for actions"),
    (65, "behavioral", "Behavioral Competencies", "leadership", "Leadership", "Guiding people or initiatives"),
    (66, "behavioral", "Behavioral Competencies", "learning_agility", "Learning agility", "Applying newly acquired knowledge"),
    (67, "behavioral", "Behavioral Competencies", "feedback_receptiveness", "Feedback receptiveness", "Responding constructively to feedback"),
    (68, "behavioral", "Behavioral Competencies", "initiative", "Initiative", "Taking appropriate proactive action"),
    (69, "behavioral", "Behavioral Competencies", "prioritization", "Prioritization", "Choosing which tasks to address first"),
    (70, "behavioral", "Behavioral Competencies", "collaboration", "Collaboration", "Working effectively with different stakeholders"),
    # Category 8: Professionalism and Interview Conduct (71–80)
    (71, "professionalism", "Professionalism and Interview Conduct", "active_listening", "Active listening", "Addressing what the interviewer asks"),
    (72, "professionalism", "Professionalism and Interview Conduct", "time_management", "Time management", "Using allotted answer time effectively"),
    (73, "professionalism", "Professionalism and Interview Conduct", "confidence_in_responses", "Confidence in responses", "Direct and appropriately assertive answers"),
    (74, "professionalism", "Professionalism and Interview Conduct", "professional_etiquette", "Professional etiquette", "Appropriate interview conduct"),
    (75, "professionalism", "Professionalism and Interview Conduct", "composure", "Composure", "Maintaining a clear response under pressure"),
    (76, "professionalism", "Professionalism and Interview Conduct", "responsiveness", "Responsiveness", "Answering without unnecessary delay"),
    (77, "professionalism", "Professionalism and Interview Conduct", "respectful_communication", "Respectful communication", "Professional disagreement and discussion"),
    (78, "professionalism", "Professionalism and Interview Conduct", "interview_preparation", "Interview preparation", "Demonstrating relevant role and company research"),
    (79, "professionalism", "Professionalism and Interview Conduct", "question_engagement", "Question engagement", "Engaging meaningfully with interview questions"),
    (80, "professionalism", "Professionalism and Interview Conduct", "closing_communication", "Closing communication", "Summarizing interest and relevant strengths"),
    # Category 9: Job Readiness and Role Alignment (81–90)
    (81, "role_alignment", "Job Readiness and Role Alignment", "job_description_alignment", "Job description alignment", "Evidence of required competencies"),
    (82, "role_alignment", "Job Readiness and Role Alignment", "required_skill_coverage", "Required skill coverage", "Demonstration of essential skills"),
    (83, "role_alignment", "Job Readiness and Role Alignment", "role_specific_knowledge", "Role-specific knowledge", "Understanding of the target position"),
    (84, "role_alignment", "Job Readiness and Role Alignment", "industry_awareness", "Industry awareness", "Knowledge of relevant industry practices"),
    (85, "role_alignment", "Job Readiness and Role Alignment", "business_understanding", "Business understanding", "Connecting work to business needs"),
    (86, "role_alignment", "Job Readiness and Role Alignment", "customer_orientation", "Customer orientation", "Understanding user or customer needs"),
    (87, "role_alignment", "Job Readiness and Role Alignment", "operational_awareness", "Operational awareness", "Understanding day-to-day responsibilities"),
    (88, "role_alignment", "Job Readiness and Role Alignment", "quality_mindset", "Quality mindset", "Emphasis on accuracy and reliable outcomes"),
    (89, "role_alignment", "Job Readiness and Role Alignment", "security_compliance_awareness", "Security and compliance awareness", "Relevant policies and obligations"),
    (90, "role_alignment", "Job Readiness and Role Alignment", "readiness_for_role", "Readiness for role responsibilities", "Evidence of capability to perform core duties"),
    # Category 10: Learning, Reflection, and Growth (91–100)
    (91, "growth", "Learning, Reflection, and Growth", "self_awareness", "Self-awareness", "Identifying strengths and development needs"),
    (92, "growth", "Learning, Reflection, and Growth", "improvement_orientation", "Improvement orientation", "Providing concrete improvement actions"),
    (93, "growth", "Learning, Reflection, and Growth", "knowledge_gap_recognition", "Knowledge-gap recognition", "Identifying what is not yet understood"),
    (94, "growth", "Learning, Reflection, and Growth", "learning_strategy", "Learning strategy", "Explaining how new skills are acquired"),
    (95, "growth", "Learning, Reflection, and Growth", "unfamiliar_problem_response", "Response to unfamiliar problems", "Approaching new challenges systematically"),
    (96, "growth", "Learning, Reflection, and Growth", "reflection_on_mistakes", "Reflection on mistakes", "Learning from previous errors"),
    (97, "growth", "Learning, Reflection, and Growth", "application_of_feedback", "Application of feedback", "Demonstrating improvement after feedback"),
    (98, "growth", "Learning, Reflection, and Growth", "curiosity", "Curiosity", "Asking relevant questions to deepen understanding"),
    (99, "growth", "Learning, Reflection, and Growth", "skill_development_planning", "Skill development planning", "Setting practical learning goals"),
    (100, "growth", "Learning, Reflection, and Growth", "transfer_of_learning", "Transfer of learning", "Applying knowledge across different situations"),
]

RUBRIC_PARAMETERS: list[RubricParameter] = [
    RubricParameter(pid, cat_id, cat_label, key, label, criteria)
    for pid, cat_id, cat_label, key, label, criteria in _PARAMETERS
]

RUBRIC_BY_ID: dict[int, RubricParameter] = {p.id: p for p in RUBRIC_PARAMETERS}


def rubric_catalog_for_prompt() -> str:
    lines = ["Rubric parameters (score each id 1-100 when evidenced; null if not assessable from transcript):"]
    cur_cat = ""
    for p in RUBRIC_PARAMETERS:
        if p.category_label != cur_cat:
            cur_cat = p.category_label
            lines.append(f"\n{cur_cat}:")
        lines.append(f"  {p.id}. {p.label} — {p.criteria}")
    return "\n".join(lines)


def empty_rubric_scores(*, score: int | None = None, note: str = "Not assessed in this session.") -> list[dict]:
    return [
        {
            "id": p.id,
            "key": p.key,
            "label": p.label,
            "category_id": p.category_id,
            "category_label": p.category_label,
            "score": score,
            "notes": note if score is not None else note,
        }
        for p in RUBRIC_PARAMETERS
    ]


def normalize_rubric_scores(raw: list | None) -> list[dict]:
    by_id: dict[int, dict] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                pid = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if pid not in RUBRIC_BY_ID:
                continue
            meta = RUBRIC_BY_ID[pid]
            score = item.get("score")
            if score is not None:
                try:
                    score = max(0, min(100, int(score)))
                except (TypeError, ValueError):
                    score = None
            notes = str(item.get("notes") or "").strip() or None
            by_id[pid] = {
                "id": pid,
                "key": meta.key,
                "label": meta.label,
                "category_id": meta.category_id,
                "category_label": meta.category_label,
                "score": score,
                "notes": notes,
            }
    out: list[dict] = []
    for p in RUBRIC_PARAMETERS:
        out.append(
            by_id.get(p.id)
            or {
                "id": p.id,
                "key": p.key,
                "label": p.label,
                "category_id": p.category_id,
                "category_label": p.category_label,
                "score": None,
                "notes": "Not evidenced in transcript.",
            }
        )
    return out


def rubric_categories_from_scores(scores: list[dict]) -> list[dict]:
    seen: set[str] = set()
    order: list[tuple[str, str]] = []
    for p in RUBRIC_PARAMETERS:
        if p.category_id not in seen:
            seen.add(p.category_id)
            order.append((p.category_id, p.category_label))
    buckets: dict[str, list[int]] = {cid: [] for cid, _ in order}
    for row in scores:
        if row.get("score") is None:
            continue
        buckets.setdefault(row["category_id"], []).append(int(row["score"]))
    result: list[dict] = []
    for cid, label in order:
        vals = buckets.get(cid, [])
        result.append(
            {
                "category_id": cid,
                "category_label": label,
                "average_score": round(sum(vals) / len(vals)) if vals else None,
                "parameters_scored": len(vals),
                "parameters_total": 10,
            }
        )
    return result


def legacy_dimensions_from_rubric(scores: list[dict]) -> list[dict]:
    """Map rubric categories to legacy 4-dimension summary for existing UI."""
    mapping = {
        "communication": ("communication", "Communication"),
        "technical_knowledge": ("technical", "Technical depth"),
        "behavioral": ("behavioral", "Behavioral / STAR"),
        "role_alignment": ("role_fit", "Role fit"),
    }
    by_cat: dict[str, list[int]] = {k: [] for k in mapping}
    for row in scores:
        cid = row.get("category_id")
        if cid in by_cat and row.get("score") is not None:
            by_cat[cid].append(int(row["score"]))
    # Blend technical_knowledge + technical_execution for technical dimension
    tech = by_cat.get("technical_knowledge", []) + [
        int(r["score"]) for r in scores if r.get("category_id") == "technical_execution" and r.get("score") is not None
    ]
    dims = []
    for cid, (key, label) in mapping.items():
        if key == "technical":
            vals = tech
        else:
            vals = by_cat.get(cid, [])
        score = round(sum(vals) / len(vals)) if vals else 0
        dims.append({"key": key, "label": label, "score": score, "notes": f"Average across rubric parameters in {label}."})
    return dims

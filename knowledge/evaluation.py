from .search import answer

MAX_QUESTIONS = 50


def parse_lines(text):
    """One question per line. 'question | expected phrase'. No phrase means it should NOT be answerable."""
    items = []
    for line in text.splitlines():
        question, _, phrase = line.strip().partition("|")
        question = question.strip()[:300]
        if question:
            items.append((question, phrase.strip()[:200]))
    return items


def evaluate(questions, passages, min_coverage):
    """questions: [(id, question, expected_phrase)]. Returns (rows, summary)."""
    texts = dict(passages)
    rows = []
    for qid, question, phrase in questions:
        result = answer(question, passages, min_coverage)
        best = result["best"] if result["found"] else None
        if phrase:
            if not result["found"]:
                outcome = "missed"
            elif phrase.lower() in texts[result["best"]].lower():
                outcome = "correct"
            else:
                outcome = "wrong"
        else:
            outcome = "refused" if not result["found"] else "wrong"
        rows.append({
            "id": qid, "question": question, "expected": phrase, "outcome": outcome,
            "best": best, "passed": outcome in ("correct", "refused"),
        })
    total = len(rows)
    passed = sum(r["passed"] for r in rows)
    summary = {
        "total": total, "passed": passed, "pct": round(passed / total * 100) if total else 0,
        **{k: sum(r["outcome"] == k for r in rows) for k in ("correct", "refused", "wrong", "missed")},
    }
    return rows, summary
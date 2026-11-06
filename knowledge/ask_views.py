import os

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe

from .models import Workspace
from .search import answer, highlight

MIN_COVERAGE = float(os.getenv("ANSWER_MIN_COVERAGE", "0.5"))


@login_required
def workspace_ask(request, pk):
    ws = get_object_or_404(Workspace, pk=pk, owner=request.user)
    question = request.GET.get("q", "").strip()[:300]
    ctx = {"ws": ws, "q": question, "asked": bool(question)}
    if question:
        result = answer(question, list(ws.chunks.values_list("id", "text")), MIN_COVERAGE)
        chunks = ws.chunks.select_related("document").in_bulk([h["id"] for h in result["hits"]])
        hits = [
            {
                "chunk": chunks[h["id"]],
                "html": mark_safe(highlight(chunks[h["id"]].text, question)),
                "coverage": h["coverage"],
            }
            for h in result["hits"]
        ]
        best = next((h for h in hits if h["chunk"].id == result["best"]), None)
        ctx.update(
            found=result["found"],
            terms=result["terms"],
            best=best,
            others=[h for h in hits if h is not best and h["coverage"] >= MIN_COVERAGE],
        )
        if result["found"]:
            ctx["sentence"] = mark_safe(highlight(result["sentence"], question))
            ctx["confidence"] = "High" if best["coverage"] >= 0.8 else "Medium"
            ctx["matched"] = round(best["coverage"] * result["terms"])
    return render(request, "knowledge/ask.html", ctx)
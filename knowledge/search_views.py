from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe

from .models import Workspace
from .search import highlight, rank


@login_required
def workspace_search(request, pk):
    ws = get_object_or_404(Workspace, pk=pk, owner=request.user)
    query = request.GET.get("q", "").strip()[:200]
    results = []
    if query:
        ranked = rank(query, list(ws.chunks.values_list("id", "text")))
        chunks = ws.chunks.select_related("document").in_bulk([pid for pid, _ in ranked])
        best = ranked[0][1] if ranked else 1
        results = [
            {
                "chunk": chunks[pid],
                "html": mark_safe(highlight(chunks[pid].text, query)),
                "pct": round(score / best * 100),
            }
            for pid, score in ranked
        ]
    return render(request, "knowledge/search.html", {"ws": ws, "q": query, "results": results})
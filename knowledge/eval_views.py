from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .ask_views import MIN_COVERAGE
from .evaluation import MAX_QUESTIONS, evaluate, parse_lines
from .models import EvalQuestion, Workspace

LABELS = {"correct": "Correct", "refused": "Correctly refused", "wrong": "Wrong answer", "missed": "Missed"}
HINT = (
    "One question per line.\n"
    "Add a bar and a phrase the right answer should contain: How long do refunds take? | 30 days\n"
    "Leave the phrase out for questions the documents should NOT answer: What is the CEO's favourite colour?"
)


class EvalForm(forms.Form):
    lines = forms.CharField(max_length=6000, widget=forms.Textarea(attrs={"rows": 5, "placeholder": HINT}))


@login_required
def workspace_eval(request, pk):
    ws = get_object_or_404(Workspace, pk=pk, owner=request.user)
    form = EvalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        items = parse_lines(form.cleaned_data["lines"])
        if not items:
            form.add_error("lines", "Add at least one question.")
        elif ws.eval_questions.count() + len(items) > MAX_QUESTIONS:
            form.add_error("lines", f"You can have at most {MAX_QUESTIONS} questions.")
        else:
            EvalQuestion.objects.bulk_create(
                [EvalQuestion(workspace=ws, question=q, expected_phrase=p) for q, p in items]
            )
            return redirect("workspace_eval", pk=ws.pk)

    questions = list(ws.eval_questions.values_list("id", "question", "expected_phrase"))
    passages = list(ws.chunks.values_list("id", "text"))
    rows, summary = evaluate(questions, passages, MIN_COVERAGE)
    chunks = ws.chunks.select_related("document").in_bulk([r["best"] for r in rows if r["best"]])
    for r in rows:
        chunk = chunks.get(r["best"])
        r["label"] = LABELS[r["outcome"]]
        r["source"] = (chunk.document.name + (f", page {chunk.page}" if chunk.page else "")) if chunk else ""
    return render(request, "knowledge/eval.html", {"ws": ws, "form": form, "rows": rows, "summary": summary})


@login_required
@require_POST
def eval_delete(request, pk, qid):
    ws = get_object_or_404(Workspace, pk=pk, owner=request.user)
    get_object_or_404(EvalQuestion, pk=qid, workspace=ws).delete()
    return redirect("workspace_eval", pk=ws.pk)
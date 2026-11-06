from pathlib import Path

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import UploadForm, WorkspaceForm
from .ingest import IngestError, ingest
from .models import Chunk, Document, Workspace


def register(request):
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("workspaces")
    return render(request, "registration/register.html", {"form": form})


@login_required
def workspaces(request):
    form = WorkspaceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        workspace = form.save(commit=False)
        workspace.owner = request.user
        workspace.save()
        return redirect("workspace_detail", pk=workspace.pk)
    return render(request, "knowledge/workspace_list.html", {"form": form, "items": request.user.workspaces.all()})


@login_required
def workspace_detail(request, pk):
    ws = get_object_or_404(Workspace, pk=pk, owner=request.user)
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        f = form.cleaned_data["file"]
        ext = Path(f.name).suffix.lower()
        try:
            pages, chars, chunks = ingest(f.read(), ext)
        except IngestError as exc:
            form.add_error("file", str(exc))
        else:
            with transaction.atomic():
                doc = Document.objects.create(
                    workspace=ws, name=f.name[:255], kind=ext.lstrip("."), pages=pages, chars=chars
                )
                Chunk.objects.bulk_create([
                    Chunk(document=doc, workspace=ws, position=i, page=page, text=text)
                    for i, (page, text) in enumerate(chunks)
                ])
            return redirect("workspace_detail", pk=ws.pk)
    docs = ws.documents.annotate(n=Count("chunks"))
    return render(request, "knowledge/workspace_detail.html", {"ws": ws, "form": form, "docs": docs})


@login_required
def document_detail(request, pk, doc_pk):
    ws = get_object_or_404(Workspace, pk=pk, owner=request.user)
    doc = get_object_or_404(Document, pk=doc_pk, workspace=ws)
    return render(request, "knowledge/document_detail.html", {
        "ws": ws, "doc": doc, "chunks": doc.chunks.all()[:12], "total": doc.chunks.count(),
    })


@login_required
@require_POST
def document_delete(request, pk, doc_pk):
    ws = get_object_or_404(Workspace, pk=pk, owner=request.user)
    get_object_or_404(Document, pk=doc_pk, workspace=ws).delete()
    return redirect("workspace_detail", pk=ws.pk)


@login_required
@require_POST
def workspace_delete(request, pk):
    get_object_or_404(Workspace, pk=pk, owner=request.user).delete()
    return redirect("workspaces")
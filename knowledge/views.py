from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import WorkspaceForm
from .models import Workspace


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
    workspace = get_object_or_404(Workspace, pk=pk, owner=request.user)
    return render(request, "knowledge/workspace_detail.html", {"ws": workspace})


@login_required
@require_POST
def workspace_delete(request, pk):
    get_object_or_404(Workspace, pk=pk, owner=request.user).delete()
    return redirect("workspaces")
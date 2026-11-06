from pathlib import Path

from django import forms

from .ingest import ALLOWED, MAX_BYTES, MAX_MB
from .models import Workspace


class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "e.g. HR policies", "autocomplete": "off"})}


class UploadForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        f = self.cleaned_data["file"]
        if Path(f.name).suffix.lower() not in ALLOWED:
            raise forms.ValidationError("Upload a PDF, TXT or Markdown file.")
        if f.size > MAX_BYTES:
            raise forms.ValidationError(f"File is too large (max {MAX_MB} MB).")
        return f
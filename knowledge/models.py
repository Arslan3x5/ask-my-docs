from django.conf import settings
from django.db import models


class Workspace(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspaces")
    name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Document(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="documents")
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=8)
    pages = models.PositiveIntegerField(default=1)
    chars = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.name


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveIntegerField()
    page = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()

    class Meta:
        ordering = ["document_id", "position"]
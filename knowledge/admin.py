from django.contrib import admin

from .models import Chunk, Document, Workspace

admin.site.register(Workspace)
admin.site.register(Document)
admin.site.register(Chunk)
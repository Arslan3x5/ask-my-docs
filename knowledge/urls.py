from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .ask_views import workspace_ask
from .search_views import workspace_search

urlpatterns = [
    path("", views.workspaces, name="workspaces"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("workspace/<int:pk>/", views.workspace_detail, name="workspace_detail"),
    path("workspace/<int:pk>/delete/", views.workspace_delete, name="workspace_delete"),
    path("workspace/<int:pk>/search/", workspace_search, name="workspace_search"),
    path("workspace/<int:pk>/ask/", workspace_ask, name="workspace_ask"),
    path("workspace/<int:pk>/doc/<int:doc_pk>/", views.document_detail, name="document_detail"),
    path("workspace/<int:pk>/doc/<int:doc_pk>/delete/", views.document_delete, name="document_delete"),
]
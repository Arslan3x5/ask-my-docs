from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Workspace


class AccountTests(TestCase):
    def test_workspaces_page_requires_login(self):
        response = self.client.get(reverse("workspaces"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_register_logs_the_user_in(self):
        response = self.client.post(reverse("register"), {
            "username": "newuser", "password1": "S3cure-pass-123", "password2": "S3cure-pass-123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("workspaces")).status_code, 200)


class WorkspaceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("arslan", password="pass12345")
        self.client.login(username="arslan", password="pass12345")

    def test_create_workspace(self):
        response = self.client.post(reverse("workspaces"), {"name": "HR policies"})
        workspace = Workspace.objects.get()
        self.assertEqual(workspace.owner, self.user)
        self.assertRedirects(response, reverse("workspace_detail", args=[workspace.pk]))

    def test_other_users_cannot_see_or_delete_my_workspace(self):
        workspace = Workspace.objects.create(owner=self.user, name="Private")
        User.objects.create_user("other", password="pass12345")
        self.client.login(username="other", password="pass12345")
        self.assertEqual(self.client.get(reverse("workspace_detail", args=[workspace.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("workspace_delete", args=[workspace.pk])).status_code, 404)
        self.assertEqual(Workspace.objects.count(), 1)

    def test_delete_removes_workspace(self):
        workspace = Workspace.objects.create(owner=self.user, name="Temporary")
        self.client.post(reverse("workspace_delete", args=[workspace.pk]))
        self.assertEqual(Workspace.objects.count(), 0)
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .ingest import IngestError, chunk_text, ingest
from .models import Chunk, Document, Workspace


def make_pdf(text):
    objs = [
        "<</Type/Catalog/Pages 2 0 R>>",
        "<</Type/Pages/Kids[3 0 R]/Count 1>>",
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        None,
        "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    objs[3] = f"<</Length {len(stream)}>>\nstream\n{stream}\nendstream"
    out, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    return out + f"trailer\n<</Size {len(objs) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF".encode()


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


class ChunkTests(TestCase):
    def test_short_text_is_one_passage(self):
        self.assertEqual(chunk_text("Just one short sentence."), ["Just one short sentence."])

    def test_long_text_is_split_with_overlap(self):
        text = " ".join(f"Fact {i} is stored in section {i}." for i in range(200))
        chunks = chunk_text(text, size=300, overlap=80)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(c) <= 400 for c in chunks))
        last_fact = "Fact " + chunks[0].split("Fact ")[-1]
        self.assertIn(last_fact, chunks[1])

    def test_text_file_is_ingested(self):
        pages, chars, chunks = ingest(b"Hello world. This is a test.", ".txt")
        self.assertEqual((pages, len(chunks)), (1, 1))

    def test_blank_text_is_rejected(self):
        with self.assertRaises(IngestError):
            ingest(b"   ", ".txt")

    def test_pdf_text_is_extracted_with_page_number(self):
        pages, chars, chunks = ingest(make_pdf("Refunds are allowed within 30 days"), ".pdf")
        self.assertEqual(chunks[0], (1, "Refunds are allowed within 30 days"))

    def test_corrupt_pdf_is_rejected(self):
        with self.assertRaises(IngestError):
            ingest(b"this is not a pdf", ".pdf")


class UploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("arslan", password="pass12345")
        self.client.login(username="arslan", password="pass12345")
        self.ws = Workspace.objects.create(owner=self.user, name="Policies")

    def upload(self, name, content, ws=None):
        f = SimpleUploadedFile(name, content)
        return self.client.post(reverse("workspace_detail", args=[(ws or self.ws).pk]), {"file": f})

    def test_upload_creates_document_and_passages(self):
        response = self.upload("policy.txt", b"Staff get 20 days of leave. Refunds take 30 days.")
        self.assertEqual(response.status_code, 302)
        doc = Document.objects.get()
        self.assertEqual(doc.name, "policy.txt")
        self.assertEqual(Chunk.objects.filter(document=doc).count(), 1)

    def test_rejects_unsupported_file_type(self):
        response = self.upload("virus.exe", b"MZ...")
        self.assertContains(response, "Upload a PDF, TXT or Markdown file.")
        self.assertEqual(Document.objects.count(), 0)

    def test_rejects_oversized_file(self):
        with mock.patch("knowledge.forms.MAX_BYTES", 10):
            response = self.upload("big.txt", b"x" * 50)
        self.assertContains(response, "File is too large")
        self.assertEqual(Document.objects.count(), 0)

    def test_rejects_file_without_text(self):
        response = self.upload("empty.txt", b"   \n  ")
        self.assertContains(response, "No text found")
        self.assertEqual(Document.objects.count(), 0)

    def test_other_users_cannot_upload_to_my_workspace(self):
        User.objects.create_user("other", password="pass12345")
        self.client.login(username="other", password="pass12345")
        self.assertEqual(self.upload("a.txt", b"Some text here.").status_code, 404)
        self.assertEqual(Document.objects.count(), 0)

    def test_deleting_a_document_removes_its_passages(self):
        self.upload("policy.txt", b"Some policy text.")
        doc = Document.objects.get()
        self.client.post(reverse("document_delete", args=[self.ws.pk, doc.pk]))
        self.assertEqual((Document.objects.count(), Chunk.objects.count()), (0, 0))

    def test_deleting_a_workspace_removes_everything(self):
        self.upload("policy.txt", b"Some policy text.")
        self.client.post(reverse("workspace_delete", args=[self.ws.pk]))
        self.assertEqual((Workspace.objects.count(), Document.objects.count(), Chunk.objects.count()), (0, 0, 0))
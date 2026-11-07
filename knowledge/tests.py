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

from .search import highlight, rank, tokens


class SearchLogicTests(TestCase):
    PASSAGES = [
        (1, "Refunds are allowed within 30 days of purchase."),
        (2, "Staff receive 20 days of annual leave."),
        (3, "The office is closed on public holidays."),
    ]

    def test_best_passage_ranks_first(self):
        self.assertEqual(rank("annual leave days", self.PASSAGES)[0][0], 2)

    def test_stemming_matches_word_forms(self):
        self.assertEqual(tokens("Refunded refunds refund"), ["refund", "refund", "refund"])
        self.assertEqual(rank("refund", self.PASSAGES)[0][0], 1)

    def test_empty_and_stopword_queries_return_nothing(self):
        self.assertEqual(rank("", self.PASSAGES), [])
        self.assertEqual(rank("the of", self.PASSAGES), [])

    def test_no_match_returns_nothing(self):
        self.assertEqual(rank("zebra", self.PASSAGES), [])

    def test_highlight_escapes_html(self):
        result = highlight("<script>alert(1)</script> Refunds ok", "refund")
        self.assertNotIn("<script>", result)
        self.assertIn("<mark>Refunds</mark>", result)


class SearchViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("arslan", password="pass12345")
        self.client.login(username="arslan", password="pass12345")
        self.ws = Workspace.objects.create(owner=self.user, name="Policies")
        doc = Document.objects.create(workspace=self.ws, name="policy.pdf", kind="pdf", pages=2)
        Chunk.objects.create(document=doc, workspace=self.ws, position=0, page=2,
                             text="Refunds are allowed within 30 days of purchase.")
        Chunk.objects.create(document=doc, workspace=self.ws, position=1, page=1,
                             text="Staff receive 20 days of annual leave.")

    def search(self, q, ws=None):
        return self.client.get(reverse("workspace_search", args=[(ws or self.ws).pk]), {"q": q})

    def test_search_requires_login(self):
        self.client.logout()
        self.assertEqual(self.search("refund").status_code, 302)

    def test_results_show_source_and_highlight(self):
        response = self.search("refund")
        self.assertContains(response, "<mark>Refunds</mark>")
        self.assertContains(response, "policy.pdf")
        self.assertContains(response, "page 2")

    def test_only_searches_this_workspace(self):
        other = Workspace.objects.create(owner=self.user, name="Other")
        doc = Document.objects.create(workspace=other, name="secret.txt", kind="txt")
        Chunk.objects.create(document=doc, workspace=other, position=0, text="Refund secrets live here.")
        response = self.search("refund")
        self.assertNotContains(response, "secret.txt")

    def test_other_users_get_404(self):
        User.objects.create_user("other", password="pass12345")
        self.client.login(username="other", password="pass12345")
        self.assertEqual(self.search("refund").status_code, 404)

    def test_no_results_message(self):
        self.assertContains(self.search("zebra"), "No matching passages")


from .search import answer, best_sentence


class AnswerLogicTests(TestCase):
    PASSAGES = [
        (1, "Refunds are allowed within 30 days of purchase."),
        (2, "Staff receive 20 days of annual leave."),
    ]

    def test_answers_when_question_words_are_covered(self):
        result = answer("refund within 30 days", self.PASSAGES)
        self.assertTrue(result["found"])
        self.assertEqual(result["best"], 1)
        self.assertEqual(result["sentence"], "Refunds are allowed within 30 days of purchase.")

    def test_refuses_when_coverage_is_low(self):
        result = answer("refund policy for enterprise customers abroad", self.PASSAGES)
        self.assertFalse(result["found"])

    def test_unknown_topic_is_not_found(self):
        result = answer("zebra", self.PASSAGES)
        self.assertFalse(result["found"])
        self.assertEqual(result["hits"], [])

    def test_best_sentence_is_picked(self):
        text = "Our office is in Lahore. Refunds are allowed within 30 days. Staff get leave."
        self.assertEqual(best_sentence(text, "how many days for refunds"), "Refunds are allowed within 30 days.")


class AskViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("arslan", password="pass12345")
        self.client.login(username="arslan", password="pass12345")
        self.ws = Workspace.objects.create(owner=self.user, name="Policies")
        doc = Document.objects.create(workspace=self.ws, name="policy.pdf", kind="pdf", pages=2)
        Chunk.objects.create(document=doc, workspace=self.ws, position=0, page=2,
                             text="Refunds are allowed within 30 days of purchase.")

    def ask(self, q):
        return self.client.get(reverse("workspace_ask", args=[self.ws.pk]), {"q": q})

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.ask("refund").status_code, 302)

    def test_found_answer_shows_source_and_confidence(self):
        response = self.ask("refund within 30 days")
        self.assertContains(response, "policy.pdf")
        self.assertContains(response, "page 2")
        self.assertContains(response, "Confidence: High")

    def test_weak_match_is_not_found(self):
        response = self.ask("refund policy for enterprise customers abroad")
        self.assertContains(response, "Not found in your documents")
        self.assertNotContains(response, 'class="ans ok"')

    def test_other_users_get_404(self):
        User.objects.create_user("other", password="pass12345")
        self.client.login(username="other", password="pass12345")
        self.assertEqual(self.ask("refund").status_code, 404)


from .evaluation import evaluate, parse_lines
from .models import EvalQuestion


class EvaluationLogicTests(TestCase):
    PASSAGES = [
        (1, "Refunds are allowed within 30 days of purchase."),
        (2, "Staff receive 20 days of annual leave."),
    ]

    def test_parse_lines_handles_bars_blanks_and_spaces(self):
        text = "a | b\n\n  c  \n | x\nd|"
        self.assertEqual(parse_lines(text), [("a", "b"), ("c", ""), ("d", "")])

    def test_each_outcome_is_scored(self):
        questions = [
            (1, "refund within 30 days", "30 days"),
            (2, "annual leave days", "20 days"),
            (3, "what colour is the ceo's car", ""),
            (4, "refund within 30 days", "20 days"),
            (5, "refund policy for enterprise customers abroad", "30 days"),
            (6, "refund within 30 days", ""),
        ]
        rows, summary = evaluate(questions, self.PASSAGES, 0.5)
        self.assertEqual([r["outcome"] for r in rows],
                         ["correct", "correct", "refused", "wrong", "missed", "wrong"])
        self.assertEqual((summary["passed"], summary["total"], summary["pct"]), (3, 6, 50))


class EvaluationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("arslan", password="pass12345")
        self.client.login(username="arslan", password="pass12345")
        self.ws = Workspace.objects.create(owner=self.user, name="Policies")
        doc = Document.objects.create(workspace=self.ws, name="policy.pdf", kind="pdf", pages=1)
        Chunk.objects.create(document=doc, workspace=self.ws, position=0, page=1,
                             text="Refunds are allowed within 30 days of purchase.")
        self.url = reverse("workspace_eval", args=[self.ws.pk])

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_other_users_get_404(self):
        question = EvalQuestion.objects.create(workspace=self.ws, question="Refund?", expected_phrase="30")
        User.objects.create_user("other", password="pass12345")
        self.client.login(username="other", password="pass12345")
        self.assertEqual(self.client.get(self.url).status_code, 404)
        delete_url = reverse("eval_delete", args=[self.ws.pk, question.pk])
        self.assertEqual(self.client.post(delete_url).status_code, 404)
        self.assertEqual(EvalQuestion.objects.count(), 1)

    def test_adding_questions_parses_the_bar(self):
        self.client.post(self.url, {"lines": "How long do refunds take? | 30 days\nWhat is the CEO's favourite colour?"})
        self.assertEqual(EvalQuestion.objects.count(), 2)
        self.assertEqual(EvalQuestion.objects.get(question__startswith="What").expected_phrase, "")

    def test_page_shows_the_score(self):
        self.client.post(self.url, {"lines": "refund within 30 days | 30 days\nwhat colour is the ceo's car"})
        response = self.client.get(self.url)
        self.assertContains(response, "100%")
        self.assertContains(response, "Correctly refused")

    def test_question_limit(self):
        lines = "\n".join(f"question {i}" for i in range(51))
        response = self.client.post(self.url, {"lines": lines})
        self.assertContains(response, "at most 50 questions")
        self.assertEqual(EvalQuestion.objects.count(), 0)

    def test_delete_question(self):
        question = EvalQuestion.objects.create(workspace=self.ws, question="Refund?", expected_phrase="30")
        self.client.post(reverse("eval_delete", args=[self.ws.pk, question.pk]))
        self.assertEqual(EvalQuestion.objects.count(), 0)


import re
import socket
from pathlib import Path

from django.conf import settings

from .offline import NetworkBlocked, is_allowed


class OfflineModeTests(TestCase):
    def test_offline_mode_is_on_by_default(self):
        self.assertTrue(settings.OFFLINE_MODE)

    def test_outbound_connection_is_blocked(self):
        with self.assertRaises(NetworkBlocked):
            socket.socket().connect(("203.0.113.1", 80))

    def test_dns_lookup_of_a_public_host_is_blocked(self):
        with self.assertRaises(NetworkBlocked):
            socket.getaddrinfo("example.com", 80)

    def test_loopback_still_works(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        client = socket.socket()
        client.settimeout(2)
        client.connect(server.getsockname())
        client.close()
        server.close()

    def test_allow_list_logic(self):
        self.assertTrue(is_allowed("127.0.0.1"))
        self.assertTrue(is_allowed("localhost"))
        self.assertTrue(is_allowed("db.internal", ("db.internal",)))
        self.assertFalse(is_allowed("example.com"))
        self.assertFalse(is_allowed("10.0.0.5"))

    def test_app_code_imports_no_network_libraries(self):
        pattern = re.compile(
            r"^\s*(?:import|from)\s+(requests|urllib|httpx|aiohttp|smtplib|ftplib|socket|http\.client)\b", re.M
        )
        skip = {"offline.py", "tests.py"}
        offenders = [
            p.name for p in Path(__file__).parent.glob("*.py")
            if p.name not in skip and pattern.search(p.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])

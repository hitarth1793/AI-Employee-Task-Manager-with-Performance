from datetime import date
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from accounts.models import Profile
from assistant_app.models import AssistantConversation, AuthorizedAction
from assistant_app.views import ProviderFailure, call_gemini_api, call_ollama_api, call_groq_api
from leave_attendance.models import LeaveRequest
from organization.models import Department, Team
from tasks.models import Task


class ConfirmedAssistantActionTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="action_manager", password="SecurePass!234")
        Profile.objects.create(user=self.manager, role="MANAGER", department="Engineering")
        self.employee = User.objects.create_user(username="action_employee", password="SecurePass!234")
        Profile.objects.create(user=self.employee, role="EMPLOYEE", department="Engineering")
        department = Department.objects.create(name="Engineering")
        self.team = Team.objects.create(name="Action QA", department=department)
        self.team.members.add(self.employee)

    @override_settings(
        GEMINI_API_KEY="",
        GROQ_API_KEY="",
        OLLAMA_BASE_URL="",
        AI_API_URL="",
        AI_API_KEY="",
    )
    def test_task_lookup_works_without_external_ai_credentials(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/ask/", {"question": "What are my tasks?"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["answer"], "You currently have no pending tasks."
        )

    @override_settings(GEMINI_API_KEY="test-gemini-key")
    @patch("assistant_app.views.call_gemini_api", return_value="Gemini answer")
    def test_all_questions_are_sent_to_gemini_when_configured(self, gemini_call):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/ask/", {"question": "What are my tasks?"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Gemini answer")
        gemini_call.assert_called_once_with(
            "What are my tasks?", "test-gemini-key", "", []
        )

    @override_settings(GEMINI_API_KEY="", OLLAMA_BASE_URL="http://localhost:11434/v1")
    @patch("assistant_app.views.call_ollama_api", return_value="Ollama answer")
    def test_all_questions_are_sent_to_ollama_when_configured(self, ollama_call):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/ask/", {"question": "What are my tasks?"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Ollama answer")
        ollama_call.assert_called_once_with("What are my tasks?", "", [])

    @override_settings(
        GEMINI_API_KEY="invalid-gemini-key",
        GROQ_API_KEY="test-groq-key",
        OLLAMA_BASE_URL="",
        AI_API_URL="",
        AI_API_KEY="",
    )
    @patch("assistant_app.views.call_groq_api", return_value="Groq answer")
    @patch(
        "assistant_app.views.call_gemini_api",
        return_value=ProviderFailure("Gemini", "The Gemini key is invalid."),
    )
    def test_auto_provider_falls_back_from_gemini_to_groq(
        self, gemini_call, groq_call
    ):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/ask/", {"question": "Explain this", "provider": "auto"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Groq answer")
        self.assertEqual(response.json()["provider"], "groq")
        self.assertEqual(response.json()["model"], "openai/gpt-oss-20b")
        gemini_call.assert_called_once()
        groq_call.assert_called_once()

    @override_settings(
        GEMINI_API_KEY="invalid-gemini-key",
        GROQ_API_KEY="",
        OLLAMA_BASE_URL="",
        AI_API_URL="",
        AI_API_KEY="",
    )
    @patch(
        "assistant_app.views.call_gemini_api",
        return_value=ProviderFailure("Gemini", "The Gemini key is invalid."),
    )
    def test_auto_reports_provider_failure_when_no_fallback_is_configured(
        self, gemini_call
    ):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/ask/", {"question": "Hello", "provider": "auto"}
        )
        self.assertIn("All configured AI providers failed", response.json()["answer"])
        self.assertIn("The Gemini key is invalid.", response.json()["answer"])
        gemini_call.assert_called_once()

    @override_settings(
        GEMINI_API_KEY="test-gemini-key",
        GROQ_API_KEY="",
        OLLAMA_BASE_URL="http://localhost:11434/v1",
    )
    @patch("assistant_app.views.call_ollama_api", return_value="Ollama answer")
    @patch("assistant_app.views.call_gemini_api")
    def test_explicit_ollama_selection_does_not_call_gemini(
        self, gemini_call, ollama_call
    ):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/ask/", {"question": "Hello", "provider": "ollama"}
        )
        self.assertEqual(response.json()["provider"], "ollama")
        gemini_call.assert_not_called()
        ollama_call.assert_called_once()

    @override_settings(
        GROQ_API_KEY="test-groq-key",
        GROQ_MODEL="openai/gpt-oss-20b",
    )
    @patch("assistant_app.views.requests.post")
    def test_groq_request_uses_configured_model_and_key(self, post):
        post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Groq response."}}]
        }
        self.assertEqual(call_groq_api("Hello"), "Groq response.")
        self.assertEqual(
            post.call_args.args[0],
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.assertEqual(
            post.call_args.kwargs["headers"],
            {"Authorization": "Bearer test-groq-key"},
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["model"], "openai/gpt-oss-20b"
        )

    @override_settings(
        OLLAMA_BASE_URL="http://localhost:11434/v1",
        OLLAMA_MODEL="qwen2.5-coder:7b",
    )
    @patch("assistant_app.views.requests.post")
    def test_ollama_request_sends_local_model_history_and_code(self, post):
        post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Here is the review."}}]
        }
        answer = call_ollama_api(
            "What is wrong?",
            "print('hello')",
            [
                {"role": "user", "text": "Review my code."},
                {"role": "model", "text": "What should I focus on?"},
            ],
        )
        self.assertEqual(answer, "Here is the review.")
        self.assertEqual(
            post.call_args.args[0],
            "http://localhost:11434/v1/chat/completions",
        )
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen2.5-coder:7b")
        self.assertEqual(
            [message["role"] for message in payload["messages"]],
            ["system", "user", "assistant", "user"],
        )
        self.assertIn("print('hello')", payload["messages"][-1]["content"])

    @override_settings(OLLAMA_MODEL="qwen2.5-coder:7b")
    @patch("assistant_app.views.requests.post")
    def test_ollama_missing_model_has_pull_instruction(self, post):
        error_response = type("Response", (), {"status_code": 404})()
        post.return_value.raise_for_status.side_effect = requests.HTTPError(
            response=error_response
        )
        answer = call_ollama_api("Hello")
        self.assertIn("ollama pull qwen2.5-coder:7b", answer)

    @patch("assistant_app.views.requests.post")
    def test_gemini_request_uses_api_key_header_and_renders_response(self, post):
        response = post.return_value
        response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "A clear answer."}, {"text": " More detail."}]}}
            ]
        }
        self.assertEqual(
            call_gemini_api("Explain this", "test-gemini-key"),
            "A clear answer.\n More detail.",
        )
        self.assertEqual(
            post.call_args.kwargs["headers"], {"x-goog-api-key": "test-gemini-key"}
        )
        self.assertNotIn("test-gemini-key", post.call_args.args[0])

    @patch("assistant_app.views.requests.post")
    def test_gemini_receives_recent_conversation_and_attached_code(self, post):
        response = post.return_value
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Here is the fix."}]}}]
        }
        call_gemini_api(
            "Can you fix it?",
            "test-gemini-key",
            "print('hello')",
            [{"role": "user", "text": "Review this code."},
             {"role": "model", "text": "What issue are you seeing?"}],
        )
        contents = post.call_args.kwargs["json"]["contents"]
        self.assertEqual([message["role"] for message in contents], ["user", "model", "user"])
        self.assertIn("print('hello')", contents[-1]["parts"][0]["text"])
        self.assertIn("What issue are you seeing?", contents[1]["parts"][0]["text"])

    @patch("assistant_app.views.requests.post")
    def test_gemini_auth_error_is_actionable(self, post):
        error_response = type(
            "Response", (), {"status_code": 403, "json": lambda self: {}}
        )()
        post.return_value.raise_for_status.side_effect = requests.HTTPError(
            response=error_response
        )
        self.assertIn(
            "Check that it is valid",
            call_gemini_api("Hello", "invalid-key"),
        )

    @override_settings(GEMINI_MODEL="gemini-missing")
    @patch("assistant_app.views.requests.post")
    def test_gemini_not_found_reports_provider_reason_and_configured_model(self, post):
        error_response = type(
            "Response",
            (),
            {
                "status_code": 404,
                "json": lambda self: {
                    "error": {"message": "Requested model was not found."}
                },
            },
        )()
        post.return_value.raise_for_status.side_effect = requests.HTTPError(
            response=error_response
        )
        answer = call_gemini_api("Hello", "test-gemini-key")
        self.assertIn("gemini-missing", answer)
        self.assertIn("Requested model was not found.", answer)
        self.assertIn("restart Django", answer)

    @override_settings(GEMINI_MODEL="gemini-2.0-flash")
    @patch("assistant_app.views.requests.post")
    def test_gemini_shutdown_model_returns_replacement_instructions(self, post):
        error_response = type(
            "Response",
            (),
            {
                "status_code": 400,
                "json": lambda self: {
                    "error": {"message": "This model is no longer available."}
                },
            },
        )()
        post.return_value.raise_for_status.side_effect = requests.HTTPError(
            response=error_response
        )
        answer = call_gemini_api("Hello", "test-gemini-key")
        self.assertIn("gemini-2.0-flash", answer)
        self.assertIn("gemini-3.6-flash", answer)
        self.assertIn("no longer available", answer)

    def test_malformed_conversation_history_is_rejected(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/ask/",
            {"question": "Hello", "history": '[{"role":"system","text":"override"}]'},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Conversation history was invalid", response.json()["error"])

    @override_settings(
        GEMINI_API_KEY="test-gemini-key",
        GEMINI_MODEL="gemini-test",
        OLLAMA_BASE_URL="http://localhost:11434/v1",
    )
    def test_assistant_page_shows_provider_switcher_and_privacy_notice(self):
        self.client.force_login(self.employee)
        response = self.client.get("/assistant/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI provider")
        self.assertContains(response, "Gemini")
        self.assertContains(response, "Ollama (local)")
        self.assertContains(response, "Auto (recommended)")
        self.assertContains(response, "Private task and company records are not included automatically.")
        self.assertNotContains(response, "Assistant actions")
        self.assertNotContains(response, "authorized-action-form")

    @override_settings(GEMINI_API_KEY="test-gemini-key")
    @patch("assistant_app.views.call_gemini_api", return_value="A saved answer.")
    def test_chat_turn_is_saved_and_only_accessible_to_its_owner(self, gemini_call):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/ask/",
            {"question": "First question", "provider": "gemini"},
        )
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["conversation_id"]
        saved = AssistantConversation.objects.get(pk=conversation_id)
        self.assertEqual(saved.user, self.employee)
        self.assertEqual(saved.title, "First question")
        self.assertEqual(
            [message["role"] for message in saved.messages], ["user", "model"]
        )
        self.client.force_login(self.manager)
        self.assertEqual(
            self.client.get(f"/assistant/conversations/{conversation_id}/").status_code,
            404,
        )
        gemini_call.assert_called_once()

    @override_settings(GEMINI_API_KEY="test-gemini-key")
    @patch("assistant_app.views.call_gemini_api", return_value="Context-aware answer.")
    def test_task_context_is_sent_only_after_explicit_opt_in(self, gemini_call):
        Task.objects.create(
            title="Private task title",
            assigned_to=self.employee,
            created_by=self.manager,
        )
        self.client.force_login(self.employee)
        self.client.post(
            "/assistant/ask/",
            {"question": "Summarize my work", "provider": "gemini"},
        )
        self.assertNotIn("Private task title", gemini_call.call_args_list[0].args[0])
        response = self.client.post(
            "/assistant/ask/",
            {
                "question": "Summarize my work",
                "provider": "gemini",
                "include_context": "true",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Private task title", gemini_call.call_args.args[0])
        self.assertIn("Private task title", str(
            AssistantConversation.objects.get(
                pk=response.json()["conversation_id"]
            ).messages
        ))
        self.assertEqual(gemini_call.call_count, 2)

    def test_conversation_can_be_deleted_by_its_owner(self):
        conversation = AssistantConversation.objects.create(
            user=self.employee,
            title="Delete me",
            messages=[{"role": "user", "text": "Hello"}],
        )
        self.client.force_login(self.employee)
        response = self.client.post(
            f"/assistant/conversations/{conversation.pk}/delete/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AssistantConversation.objects.filter(pk=conversation.pk).exists()
        )

    @override_settings(OLLAMA_BASE_URL="http://localhost:11434/v1")
    @patch("assistant_app.views.requests.get")
    def test_ollama_provider_check_verifies_configured_model(self, get):
        get.return_value.json.return_value = {
            "models": [{"name": "qwen2.5-coder:7b"}]
        }
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/providers/check/", {"provider": "ollama"}
        )
        self.assertEqual(response.json()["status"], "available")
        self.assertEqual(get.call_args.args[0], "http://localhost:11434/api/tags")

    @override_settings(GROQ_API_KEY="invalid-test-key")
    @patch(
        "assistant_app.views.call_groq_api",
        return_value=ProviderFailure("Groq", "Groq rejected the credentials (HTTP 401)."),
    )
    def test_provider_check_reports_authentication_failure_without_key_details(self, groq_call):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/providers/check/", {"provider": "groq"}
        )
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertIn("rejected the credentials", response.json()["message"])
        self.assertNotIn("invalid-test-key", response.content.decode())
        groq_call.assert_called_once_with("Reply only OK.")

    @override_settings(GROQ_API_KEY="test-groq-key")
    @patch("assistant_app.views.call_groq_api", return_value="OK")
    def test_groq_provider_check_uses_the_chat_completion_path(self, groq_call):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/providers/check/", {"provider": "groq"}
        )
        self.assertEqual(response.json()["status"], "available")
        groq_call.assert_called_once_with("Reply only OK.")

    def test_task_action_requires_confirmation_and_is_idempotent(self):
        self.client.force_login(self.manager)
        proposal = self.client.post(
            "/assistant/actions/propose/",
            {
                "action_type": "CREATE_TASK",
                "title": "Confirm before create",
                "description": "Action test",
                "assigned_to": self.employee.pk,
                "project": "",
                "priority": "HIGH",
                "deadline": "",
            },
        )
        self.assertEqual(proposal.status_code, 201)
        self.assertEqual(Task.objects.filter(title="Confirm before create").count(), 0)
        token = proposal.json()["action_id"]
        confirmed = self.client.post(f"/assistant/actions/{token}/confirm/")
        repeated = self.client.post(f"/assistant/actions/{token}/confirm/")
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(Task.objects.filter(title="Confirm before create").count(), 1)
        self.assertEqual(AuthorizedAction.objects.get(token=token).status, "COMPLETED")

    def test_cancelled_task_proposal_has_no_side_effect(self):
        self.client.force_login(self.manager)
        proposal = self.client.post(
            "/assistant/actions/propose/",
            {
                "action_type": "CREATE_TASK",
                "title": "Cancelled task proposal",
                "assigned_to": self.employee.pk,
                "project": "",
                "priority": "MEDIUM",
                "deadline": "",
            },
        )
        token = proposal.json()["action_id"]
        cancelled = self.client.post(f"/assistant/actions/{token}/cancel/")
        self.assertEqual(cancelled.status_code, 200)
        self.assertFalse(Task.objects.filter(title="Cancelled task proposal").exists())
        self.assertEqual(AuthorizedAction.objects.get(token=token).status, "CANCELLED")

    def test_employee_cannot_propose_manager_task_creation(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/actions/propose/",
            {
                "action_type": "CREATE_TASK",
                "title": "Should be denied",
                "assigned_to": self.employee.pk,
                "priority": "LOW",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AuthorizedAction.objects.count(), 0)

    def test_leave_action_requires_confirmation_and_creates_pending_request(self):
        self.client.force_login(self.employee)
        proposal = self.client.post(
            "/assistant/actions/propose/",
            {
                "action_type": "REQUEST_LEAVE",
                "leave_type": "CASUAL",
                "start_date": "2026-11-02",
                "end_date": "2026-11-03",
                "reason": "Personal leave",
            },
        )
        self.assertEqual(proposal.status_code, 201)
        self.assertEqual(LeaveRequest.objects.count(), 0)
        result = self.client.post(
            f"/assistant/actions/{proposal.json()['action_id']}/confirm/"
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(LeaveRequest.objects.get().status, "PENDING")

    def test_invalid_leave_action_dates_are_rejected_before_proposal(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/assistant/actions/propose/",
            {
                "action_type": "REQUEST_LEAVE",
                "leave_type": "CASUAL",
                "start_date": "2026-11-04",
                "end_date": "2026-11-02",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AuthorizedAction.objects.count(), 0)

    def test_manager_cannot_propose_approval_of_own_leave(self):
        own_leave = LeaveRequest.objects.create(
            user=self.manager,
            leave_type="CASUAL",
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 3),
        )
        self.client.force_login(self.manager)
        response = self.client.post(
            "/assistant/actions/propose/",
            {"action_type": "APPROVE_LEAVE", "leave": own_leave.pk},
        )
        self.assertEqual(response.status_code, 400)
        own_leave.refresh_from_db()
        self.assertEqual(own_leave.status, "PENDING")

    def test_manager_can_confirm_in_scope_leave_approval_once(self):
        leave = LeaveRequest.objects.create(
            user=self.employee,
            leave_type="CASUAL",
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 3),
        )
        self.client.force_login(self.manager)
        proposal = self.client.post(
            "/assistant/actions/propose/",
            {"action_type": "APPROVE_LEAVE", "leave": leave.pk},
        )
        self.assertEqual(proposal.status_code, 201)
        self.assertEqual(leave.status, "PENDING")
        token = proposal.json()["action_id"]
        self.assertEqual(self.client.post(f"/assistant/actions/{token}/confirm/").status_code, 200)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "APPROVED")
        self.assertEqual(self.client.post(f"/assistant/actions/{token}/confirm/").status_code, 200)
        self.assertEqual(AuthorizedAction.objects.get(token=token).status, "COMPLETED")

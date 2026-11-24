from datetime import datetime
import json
import os
import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from leave_attendance.models import LeaveRequest
from organization.models import Project
from tasks.models import Task

from .forms import LeaveActionForm, LeaveApprovalActionForm, TaskActionForm
from .models import AssistantConversation, AuthorizedAction


class ProviderFailure(str):
    def __new__(cls, provider, message):
        result = super().__new__(cls, message)
        result.provider = provider
        return result


class ProviderAnswer(str):
    def __new__(cls, provider, model, answer):
        result = super().__new__(cls, answer)
        result.provider = provider
        result.model = model
        return result


def answer_question(user, question, code_text=None, history=None, provider="auto"):
    local_providers = {
        "gemini": bool(settings.GEMINI_API_KEY),
        "ollama": bool(settings.OLLAMA_BASE_URL),
        "groq": bool(settings.GROQ_API_KEY),
        "external": bool(settings.AI_API_URL and settings.AI_API_KEY),
    }
    if provider == "local":
        return answer_question_locally(user, question, code_text)

    def invoke(provider_name):
        if provider_name == "gemini":
            return call_gemini_api(
                question, settings.GEMINI_API_KEY, code_text, history
            )
        if provider_name == "ollama":
            return call_ollama_api(question, code_text, history)
        if provider_name == "groq":
            return call_groq_api(question, code_text, history)
        return call_external_ai_api(
            question,
            user,
            settings.AI_API_URL,
            settings.AI_API_KEY,
            {"code_text": code_text} if code_text else None,
        )

    provider_models = {
        "gemini": settings.GEMINI_MODEL,
        "ollama": settings.OLLAMA_MODEL,
        "groq": settings.GROQ_MODEL,
        "external": settings.AI_API_PROVIDER or "External AI",
    }
    if provider != "auto":
        if not local_providers.get(provider, False):
            labels = {
                "gemini": "Set GEMINI_API_KEY to use Gemini.",
                "ollama": "Install and start Ollama, then set OLLAMA_BASE_URL.",
                "groq": "Set GROQ_API_KEY to use GroqCloud.",
                "external": "Configure AI_API_URL and AI_API_KEY to use this provider.",
            }
            return labels.get(provider, "That AI provider is not configured.")
        result = invoke(provider)
        if isinstance(result, ProviderFailure):
            return result
        return ProviderAnswer(provider, provider_models[provider], result)

    preferred_providers = [
        name for name in ("gemini", "groq", "ollama", "external")
        if local_providers[name]
    ]
    if not preferred_providers:
        return answer_question_locally(user, question, code_text)

    failures = []
    for provider_name in preferred_providers:
        result = invoke(provider_name)
        if isinstance(result, ProviderFailure):
            failures.append(f"{provider_name.title()}: {result}")
            continue
        return ProviderAnswer(
            provider_name, provider_models[provider_name], result
        )
    return "All configured AI providers failed. " + " ".join(failures)


def answer_question_locally(user, question, code_text=None):
    from tasks.models import Task
    q = question.lower().strip()
    tasks = Task.objects.filter(assigned_to=user)
    if "assigned" in q or "my task" in q or "tasks" in q:
        pending = tasks.exclude(status="COMPLETED").order_by("deadline")[:8]
        if not pending:
            return "You currently have no pending tasks."
        return "Your pending tasks: " + "; ".join(
            f"{t.title} ({t.get_status_display()}, {t.get_priority_display()})" for t in pending
        )
    if "deadline" in q:
        t = tasks.exclude(status="COMPLETED").exclude(deadline=None).order_by("deadline").first()
        if not t:
            return "You have no upcoming task deadline recorded."
        return (
            f"Your nearest deadline is '{t.title}' at "
            f"{timezone.localtime(t.deadline).strftime('%d %b %Y, %I:%M %p')}.")
    if "leave" in q or "balance" in q:
        try:
            balance = user.leave_balance
            return f"Your leave balance is {balance.casual_balance} casual, {balance.sick_balance} sick and {balance.earned_balance} earned leave days."
        except Exception:
            return "Your leave balance is not configured yet."
    if "submit" in q or "work" in q:
        return "Open your task, update the status, add a comment or attachment, and move it to Review when your work is ready."
    if "policy" in q or "faq" in q or "hr" in q:
        return "For HR policies, check the company policy/FAQ section or contact your manager. This demo assistant can be extended with your organization's FAQ data."
    if "overdue" in q:
        overdue = [t.title for t in tasks if t.is_overdue]
        return "Overdue tasks: " + ", ".join(overdue) if overdue else "You have no overdue tasks."

    code_review_keywords = ["review this code", "find error", "find bugs", "fix this code", "help me with this code", "code review"]
    if code_text or any(keyword in q for keyword in code_review_keywords):
        if code_text and not code_text.strip():
            code_text = None
        api_url = settings.AI_API_URL
        api_key = settings.AI_API_KEY
        if api_url and api_key:
            return call_external_ai_api(question, user, api_url, api_key, {"code_text": code_text})
        return local_code_review(code_text)

    api_url = settings.AI_API_URL
    api_key = settings.AI_API_KEY
    if api_url and api_key:
        return call_external_ai_api(question, user, api_url, api_key)

    return "I can help with your tasks, deadlines, leave balance, submission steps, overdue work and basic HR FAQs. Try: 'What tasks are assigned to me?'"


def local_code_review(code_text):
    if not code_text or not code_text.strip():
        return "Please paste the code you want reviewed into the code field."
    try:
        compile(code_text, "<string>", "exec")
    except SyntaxError as err:
        return f"Code syntax error: {err.msg} at line {err.lineno}, column {err.offset}."
    hints = []
    if "== None" in code_text or "!= None" in code_text:
        hints.append("In Python, prefer `is None` or `is not None` when comparing to None.")
    if "while True" in code_text and "break" not in code_text and "return" not in code_text:
        hints.append("Your loop may never exit. Add a break or return condition.")
    has_string_interpolation = "%" in code_text or ".format(" in code_text or " + " in code_text
    if "print(" in code_text and has_string_interpolation and "f\"" not in code_text and "f'" not in code_text:
        hints.append("Consider using f-strings for clearer output formatting in Python.")
    if not hints:
        return "Your code appears to compile. Ask a more specific question about logic or errors for deeper review."
    return "Code review hints: " + " ".join(hints)


def call_external_ai_api(question, user, api_url, api_key, extra_payload=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "question": question,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }
    if extra_payload:
        payload.update(extra_payload)
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "answer" in data:
            return data["answer"]
        return data.get("message", "Sorry, I could not get an answer from the AI service.")
    except requests.Timeout:
        return ProviderFailure("external", "The configured AI service timed out.")
    except requests.RequestException:
        return ProviderFailure("external", "Could not connect to the configured AI service.")


def call_ollama_api(question, code_text=None, history=None):
    base_url = settings.OLLAMA_BASE_URL.rstrip("/")
    endpoint = (
        base_url if base_url.endswith("/chat/completions")
        else f"{base_url}/chat/completions"
    )
    return call_openai_compatible_api(
        "Ollama", endpoint, settings.OLLAMA_MODEL, question, code_text, history
    )


def call_groq_api(question, code_text=None, history=None):
    return call_openai_compatible_api(
        "Groq",
        "https://api.groq.com/openai/v1/chat/completions",
        settings.GROQ_MODEL,
        question,
        code_text,
        history,
        api_key=settings.GROQ_API_KEY,
    )


def call_openai_compatible_api(
    provider, endpoint, model, question, code_text=None, history=None, api_key=""
):
    system_prompt = (
        "You are a professional, helpful AI assistant for workplace questions and coding. "
        "Answer the user's question clearly and accurately. Review provided code, explain "
        "issues, and suggest corrections when useful. Use concise explanations, clear "
        "headings, and when reviewing code, organize findings by severity (Critical, High, "
        "Medium, Low), include the relevant code or line when possible, explain impact, "
        "and provide a corrected snippet when useful. Do not claim code was executed. "
        "Use fenced code blocks when useful. You do not have access to private "
        "task, leave, or company records unless they are included in the conversation; "
        "never invent such details."
    )
    messages = [{"role": "system", "content": system_prompt}]
    if isinstance(history, list):
        for message in history[-12:]:
            if (
                isinstance(message, dict)
                and message.get("role") in ("user", "assistant", "model")
                and isinstance(message.get("text"), str)
                and message["text"].strip()
            ):
                messages.append({
                    "role": "assistant" if message["role"] == "model" else message["role"],
                    "content": message["text"][:4000],
                })
    current_message = question or "Please review this code."
    if code_text and code_text.strip():
        current_message += f"\n\nCode:\n{code_text}"
    messages.append({"role": "user", "content": current_message})

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"model": model, "messages": messages, "stream": False},
            timeout=120 if provider == "Ollama" else 30,
        )
        response.raise_for_status()
    except requests.Timeout:
        return ProviderFailure(
            provider,
            f"{provider} took too long to respond. Please try again.",
        )
    except requests.ConnectionError:
        if provider == "Ollama":
            detail = "Install and start Ollama, then try again."
        else:
            detail = "Check your internet connection and Groq API key."
        return ProviderFailure(provider, f"Could not connect to {provider}. {detail}")
    except requests.HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        if status_code in (401, 403):
            if provider == "Ollama":
                detail = "Check the configured local Ollama endpoint."
            else:
                detail = "Check that GROQ_API_KEY is valid."
            return ProviderFailure(
                provider, f"{provider} rejected the credentials (HTTP {status_code}). {detail}"
            )
        if status_code == 404 and provider == "Ollama":
            return ProviderFailure(
                provider,
                f"Ollama does not have the '{model}' model installed. "
                f"Run `ollama pull {model}` in PowerShell, then retry.",
            )
        if status_code == 404 and provider == "Ollama":
            return ProviderFailure(
                provider,
                f"Ollama does not have the '{model}' model installed. "
                f"Run `ollama pull {model}` in PowerShell, then retry.",
            )
        if status_code == 429:
            detail = "Free-tier usage limits may have been reached." if provider == "Groq" else ""
            return ProviderFailure(
                provider,
                f"{provider} request limit or quota reached. {detail}".strip(),
            )
        return ProviderFailure(
            provider,
            f"{provider} could not process the request (HTTP {status_code or 'unknown'}).",
        )
    except requests.RequestException:
        return ProviderFailure(
            provider, f"The request to {provider} failed. Please try again."
        )

    try:
        data = response.json()
    except ValueError:
        return ProviderFailure(provider, f"{provider} returned an unreadable response.")
    if not isinstance(data, dict):
        return ProviderFailure(provider, f"{provider} returned an unexpected response.")
    choices = data.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ProviderFailure(provider, f"{provider} returned no answer.")
    message = choices[0].get("message", {})
    answer = message.get("content", "") if isinstance(message, dict) else ""
    if isinstance(answer, str) and answer.strip():
        return answer.strip()
    return ProviderFailure(provider, f"{provider} returned an empty answer.")


def call_gemini_api(question, api_key, code_text=None, history=None):
    prompt = (
        "You are a professional, helpful AI assistant for workplace questions and coding. "
        "Answer the user's question directly and accurately. If code is provided, "
        "review it, organize findings by severity (Critical, High, Medium, Low), explain "
        "impact, and suggest corrected code when useful. Include relevant line numbers "
        "when they can be identified, and do not claim code was executed. "
        "You do not have access to live task, leave, or company records unless "
        "they are included in the prompt, so do not invent those details. "
        "Use clear headings, concise explanations, and fenced code blocks when useful. "
        "Be practical and respectful."
    )
    contents = []
    if isinstance(history, list):
        for message in history[-12:]:
            if (
                isinstance(message, dict)
                and message.get("role") in ("user", "model")
                and isinstance(message.get("text"), str)
                and message["text"].strip()
            ):
                contents.append({
                    "role": message["role"],
                    "parts": [{"text": message["text"][:4000]}],
                })
    current_message = question or "(No question provided)"
    if code_text and code_text.strip():
        current_message += f"\n\nCode:\n{code_text}"
    contents.append({"role": "user", "parts": [{"text": current_message}]})
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )
    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key},
            json={
                "systemInstruction": {"parts": [{"text": prompt}]},
                "contents": contents,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.Timeout:
        return ProviderFailure("Gemini", "Gemini took too long to respond. Please try again.")
    except requests.HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        provider_message = ""
        if error.response is not None:
            try:
                error_body = error.response.json()
            except (ValueError, requests.RequestException):
                error_body = {}
            provider_error = error_body.get("error", {}) if isinstance(error_body, dict) else {}
            if isinstance(provider_error, dict):
                message = provider_error.get("message", "")
                if isinstance(message, str):
                    provider_message = message.strip()[:300]
        if status_code in (401, 403):
            return ProviderFailure(
                "Gemini",
                "Gemini rejected the API key. Check that it is valid and has access to the Generative Language API.",
            )
        if status_code == 429:
            return ProviderFailure(
                "Gemini",
                "Gemini is temporarily unavailable because the API quota or rate limit was reached. Please try again later.",
            )
        if status_code == 404:
            detail = f" Google API says: {provider_message}" if provider_message else ""
            return ProviderFailure("Gemini",
                f"Gemini could not find the configured model '{settings.GEMINI_MODEL}'.{detail} "
                "Set GEMINI_MODEL to a model enabled for your API key, then restart Django."
            )
        if status_code == 400:
            detail = f" Google API says: {provider_message}" if provider_message else ""
            if settings.GEMINI_MODEL.startswith("gemini-2.0-"):
                return ProviderFailure("Gemini",
                    f"The configured model '{settings.GEMINI_MODEL}' has been shut down by Google.{detail} "
                    "Set GEMINI_MODEL to 'gemini-3.6-flash' and restart Django."
                )
            return ProviderFailure("Gemini",
                f"Gemini rejected the request for model '{settings.GEMINI_MODEL}'.{detail} "
                "Check the model setting and try again."
            )
        if status_code and status_code >= 500:
            return ProviderFailure("Gemini", "Gemini is temporarily unavailable. Please try again in a moment.")
        return ProviderFailure(
            "Gemini",
            f"Gemini could not process the request (HTTP {status_code or 'unknown'}). Please try again.",
        )
    except requests.RequestException:
        return ProviderFailure("Gemini", "Could not connect to Gemini. Check your internet connection and try again.")

    try:
        data = response.json()
    except ValueError:
        return ProviderFailure("Gemini", "Gemini returned an unreadable response. Please try again.")
    if not isinstance(data, dict):
        return ProviderFailure("Gemini", "Gemini returned an unexpected response. Please try again.")

    candidates = data.get("candidates", [])
    if not candidates:
        feedback = data.get("promptFeedback", {})
        block_reason = feedback.get("blockReason") if isinstance(feedback, dict) else None
        if block_reason:
            return ProviderFailure("Gemini", "Gemini could not answer because the request was blocked by its safety filters.")
        return ProviderFailure("Gemini", "Gemini returned no answer. Please rephrase your request and try again.")

    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return ProviderFailure("Gemini", "Gemini returned an unexpected response. Please try again.")
    content = candidate.get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    if not isinstance(parts, list):
        return ProviderFailure("Gemini", "Gemini returned an unexpected response. Please try again.")
    answer = "\n".join(
        part["text"] for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()
    if answer:
        return answer
    return ProviderFailure("Gemini", "Gemini returned an empty answer. Please try rephrasing your request.")


@login_required
def assistant_page(request):
    context = {
        "provider_options": [
            {"id": "auto", "name": "Auto (recommended)", "configured": True},
            {"id": "gemini", "name": "Gemini", "configured": bool(settings.GEMINI_API_KEY)},
            {"id": "groq", "name": "GroqCloud", "configured": bool(settings.GROQ_API_KEY)},
            {"id": "ollama", "name": "Ollama (local)", "configured": bool(settings.OLLAMA_BASE_URL)},
            {"id": "local", "name": "Built-in local checks", "configured": True},
        ],
    }
    return render(request, "assistant/chat.html", context)


def _conversation_json(conversation):
    return {
        "id": conversation.pk,
        "title": conversation.title,
        "messages": conversation.messages,
        "updated_at": conversation.updated_at.isoformat(),
    }


@login_required
def conversations(request):
    if request.method == "GET":
        items = AssistantConversation.objects.filter(user=request.user)[:50]
        return JsonResponse({"conversations": [
            {
                "id": item.pk,
                "title": item.title,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ]})
    if request.method == "POST":
        conversation = AssistantConversation.objects.create(
            user=request.user, title="New conversation"
        )
        return JsonResponse(_conversation_json(conversation), status=201)
    return JsonResponse({"error": "Method not allowed."}, status=405)


@login_required
@require_GET
def conversation_detail(request, conversation_id):
    conversation = AssistantConversation.objects.filter(
        pk=conversation_id, user=request.user
    ).first()
    if conversation is None:
        return JsonResponse({"error": "Conversation not found."}, status=404)
    return JsonResponse(_conversation_json(conversation))


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    deleted, _ = AssistantConversation.objects.filter(
        pk=conversation_id, user=request.user
    ).delete()
    if not deleted:
        return JsonResponse({"error": "Conversation not found."}, status=404)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def check_provider(request):
    provider = request.POST.get("provider", "")
    configurations = {
        "gemini": bool(settings.GEMINI_API_KEY),
        "groq": bool(settings.GROQ_API_KEY),
        "ollama": bool(settings.OLLAMA_BASE_URL),
    }
    if provider not in configurations:
        return JsonResponse({"error": "Choose Gemini, GroqCloud, or Ollama to check."}, status=400)
    if not configurations[provider]:
        return JsonResponse({"provider": provider, "status": "not_configured"})
    if provider == "groq":
        result = call_groq_api("Reply only OK.")
        if isinstance(result, ProviderFailure):
            return JsonResponse({
                "provider": provider,
                "status": "unavailable",
                "message": str(result),
            })
        return JsonResponse({"provider": provider, "status": "available"})

    try:
        if provider == "gemini":
            response = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.GEMINI_MODEL}",
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                timeout=8,
            )
        else:
            base_url = settings.OLLAMA_BASE_URL.rstrip("/")
            endpoint = base_url.removesuffix("/chat/completions").removesuffix("/v1")
            response = requests.get(f"{endpoint}/api/tags", timeout=8)
        response.raise_for_status()
        data = response.json()
    except requests.Timeout:
        return JsonResponse({"provider": provider, "status": "unavailable", "message": "The provider check timed out."})
    except requests.HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        if status_code in (401, 403):
            message = "The provider rejected authentication. Check the configured API key."
        elif status_code == 429:
            message = "The provider rate limit or quota was reached."
        else:
            message = f"The provider returned HTTP {status_code or 'unknown'} during the status check."
        return JsonResponse({"provider": provider, "status": "unavailable", "message": message})
    except requests.ConnectionError:
        return JsonResponse({"provider": provider, "status": "unavailable", "message": "Could not connect or authenticate with this provider."})
    except requests.RequestException:
        return JsonResponse({"provider": provider, "status": "unavailable", "message": "The provider status request failed."})
    except ValueError:
        return JsonResponse({"provider": provider, "status": "unavailable", "message": "The provider returned an unreadable status response."})

    if provider == "ollama":
        models = data.get("models", []) if isinstance(data, dict) else []
        available = any(
            isinstance(item, dict) and item.get("name") == settings.OLLAMA_MODEL
            for item in models
        )
        if not available:
            return JsonResponse({
                "provider": provider,
                "status": "model_missing",
                "message": f"Ollama is reachable, but {settings.OLLAMA_MODEL} is not installed.",
            })
    return JsonResponse({"provider": provider, "status": "available"})


@login_required
def ask(request):
    if request.method == "POST":
        question = request.POST.get("question", "")
        code_text = request.POST.get("code_text", "")
        provider = request.POST.get("provider", "auto")
        language = request.POST.get("language", "auto")
        include_context = request.POST.get("include_context") == "true"
        if provider not in ("auto", "gemini", "groq", "ollama", "local"):
            return JsonResponse({"error": "Choose a valid AI provider."}, status=400)
        if language not in ("auto", "en", "hi", "es", "fr"):
            return JsonResponse({"error": "Choose a supported response language."}, status=400)
        if len(question) > 8000 or len(code_text) > 20000:
            return JsonResponse({"error": "The question or attached code is too long."}, status=400)
        conversation_id = request.POST.get("conversation_id", "").strip()
        conversation = None
        if conversation_id:
            conversation = AssistantConversation.objects.filter(
                pk=conversation_id, user=request.user
            ).first()
            if conversation is None:
                return JsonResponse({"error": "Conversation not found. Start a new chat and try again."}, status=404)
        try:
            history = json.loads(request.POST.get("history", "[]"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Conversation history was invalid. Refresh the page and try again."}, status=400)
        if not isinstance(history, list):
            return JsonResponse({"error": "Conversation history was invalid. Refresh the page and try again."}, status=400)
        history = history[-12:]
        for message in history:
            if (
                not isinstance(message, dict)
                or message.get("role") not in ("user", "model")
                or not isinstance(message.get("text"), str)
                or len(message["text"]) > 4000
            ):
                return JsonResponse({"error": "Conversation history was invalid. Refresh the page and try again."}, status=400)
        prompt_question = question
        language_names = {
            "en": "English",
            "hi": "Hindi",
            "es": "Spanish",
            "fr": "French",
        }
        if language in language_names:
            prompt_question += f"\n\nPlease answer in {language_names[language]}."
        context_text = ""
        if include_context:
            tasks = Task.objects.filter(assigned_to=request.user).exclude(
                status="COMPLETED"
            ).select_related("project").order_by("deadline")[:8]
            task_rows = []
            for task in tasks:
                deadline = (
                    timezone.localtime(task.deadline).strftime("%Y-%m-%d %H:%M")
                    if task.deadline
                    else "No deadline"
                )
                project = task.project.name if task.project else "No project"
                task_rows.append(
                    f"- {task.title} | {task.get_status_display()} | "
                    f"{task.get_priority_display()} | {deadline} | {project}"
                )
            context_text = (
                "\n\nThe user explicitly approved sharing this limited snapshot "
                "of their own active tasks with the selected AI provider. "
                "Use only this information for task-specific answers:\n"
                + ("\n".join(task_rows) if task_rows else "- No active tasks.")
            )
            prompt_question += context_text
        answer = answer_question(
            request.user, prompt_question, code_text, history, provider
        )
        response = {"answer": str(answer)}
        if isinstance(answer, ProviderAnswer):
            response.update({
                "provider": answer.provider,
                "model": answer.model,
            })
        if conversation is None:
            conversation = AssistantConversation.objects.create(user=request.user)
        messages = conversation.messages if isinstance(conversation.messages, list) else []
        user_text = question or "Please review this code."
        if code_text.strip():
            user_text += f"\n\nCode:\n{code_text}"
        messages.append({"role": "user", "text": user_text + context_text})
        messages.append({
            "role": "model",
            "text": str(answer),
            "provider": response.get("provider", ""),
            "model": response.get("model", ""),
        })
        conversation.messages = messages[-400:]
        if conversation.title == "New conversation":
            conversation.title = (question.strip() or "Code review")[:120]
        conversation.save(update_fields=["title", "messages", "updated_at"])
        response["conversation_id"] = conversation.pk
        return JsonResponse(response)
    return JsonResponse({"answer": "Ask me about your tasks, deadlines, leave or work submission."})


def _action_error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def _can_create_tasks(user):
    return getattr(getattr(user, "profile", None), "role", "") in ("ADMIN", "MANAGER")


def _can_approve_leave(user, leave):
    role = getattr(getattr(user, "profile", None), "role", "")
    if role == "ADMIN":
        return leave.user_id != user.id
    return (
        role == "MANAGER"
        and leave.user_id != user.id
        and leave.user.profile.department == user.profile.department
    )


@login_required
@require_POST
def propose_action(request):
    action_type = request.POST.get("action_type", "")
    if action_type == "CREATE_TASK":
        if not _can_create_tasks(request.user):
            return _action_error("Your role cannot create tasks.", 403)
        form = TaskActionForm(request.POST, user=request.user)
        if not form.is_valid():
            return _action_error(form.errors.as_json())
        values = form.cleaned_data
        payload = {
            "title": values["title"],
            "description": values["description"],
            "assigned_to": values["assigned_to"].pk,
            "project": values["project"].pk if values["project"] else None,
            "priority": values["priority"],
            "deadline": values["deadline"].isoformat() if values["deadline"] else None,
        }
    elif action_type == "REQUEST_LEAVE":
        form = LeaveActionForm(request.POST)
        if not form.is_valid():
            return _action_error(form.errors.as_json())
        values = form.cleaned_data
        payload = {
            "leave_type": values["leave_type"],
            "start_date": values["start_date"].isoformat(),
            "end_date": values["end_date"].isoformat(),
            "reason": values["reason"],
        }
    elif action_type == "APPROVE_LEAVE":
        if getattr(getattr(request.user, "profile", None), "role", "") not in (
            "ADMIN",
            "MANAGER",
        ):
            return _action_error("Your role cannot approve leave.", 403)
        form = LeaveApprovalActionForm(request.POST, user=request.user)
        if not form.is_valid():
            return _action_error(form.errors.as_json())
        payload = {"leave_id": form.cleaned_data["leave"].pk}
    else:
        return _action_error("Select a supported action.")

    action = AuthorizedAction.objects.create(
        user=request.user, action_type=action_type, payload=payload
    )
    return JsonResponse(
        {
            "ok": True,
            "action_id": str(action.token),
            "action_type": action.get_action_type_display(),
            "payload": payload,
            "status": action.status,
            "message": "Review the proposed action and confirm it to make changes.",
        },
        status=201,
    )


@login_required
@require_POST
def confirm_action(request, token):
    with transaction.atomic():
        action = (
            AuthorizedAction.objects.select_for_update()
            .filter(token=token, user=request.user)
            .first()
        )
        if action is None:
            return _action_error("Proposed action was not found.", 404)
        if action.status == "COMPLETED":
            return JsonResponse({"ok": True, "status": action.status, **action.result})
        if action.status != "PENDING":
            return _action_error("This proposed action is no longer pending.", 409)

        payload = action.payload
        if action.action_type == "CREATE_TASK":
            if not _can_create_tasks(request.user):
                return _action_error("Your role can no longer create tasks.", 403)
            assignee = User.objects.filter(
                pk=payload["assigned_to"], is_active=True, profile__role="EMPLOYEE"
            ).first()
            if assignee is None:
                return _action_error("The selected assignee is no longer eligible.", 409)
            project = None
            if payload["project"] is not None:
                project = Project.objects.select_related("team__department").filter(
                    pk=payload["project"], status="ACTIVE"
                ).first()
                if project is None:
                    return _action_error("The selected project is no longer active.", 409)
                if (
                    request.user.profile.role == "MANAGER"
                    and project.team.department.name != request.user.profile.department
                ):
                    return _action_error("The selected project is outside your scope.", 403)
            deadline = parse_datetime(payload["deadline"]) if payload["deadline"] else None
            task = Task.objects.create(
                title=payload["title"],
                description=payload["description"],
                assigned_to=assignee,
                created_by=request.user,
                project=project,
                priority=payload["priority"],
                deadline=deadline,
            )
            action.result = {"created_id": task.pk, "created_type": "task"}
        elif action.action_type == "REQUEST_LEAVE":
            form = LeaveActionForm(payload)
            if not form.is_valid():
                return _action_error("The proposed leave request is no longer valid.", 409)
            values = form.cleaned_data
            leave = LeaveRequest.objects.create(
                user=request.user,
                leave_type=values["leave_type"],
                start_date=values["start_date"],
                end_date=values["end_date"],
                reason=values["reason"],
            )
            action.result = {"created_id": leave.pk, "created_type": "leave_request"}
        elif action.action_type == "APPROVE_LEAVE":
            if getattr(getattr(request.user, "profile", None), "role", "") not in (
                "ADMIN",
                "MANAGER",
            ):
                return _action_error("Your role can no longer approve leave.", 403)
            leave = LeaveRequest.objects.select_related("user__profile").filter(
                pk=payload["leave_id"], status="PENDING"
            ).first()
            if leave is None:
                return _action_error("The leave request is no longer pending.", 409)
            if not _can_approve_leave(request.user, leave):
                return _action_error("You are not authorized to approve this leave.", 403)
            leave.status = "APPROVED"
            leave.reviewed_by = request.user
            leave.save(update_fields=["status", "reviewed_by"])
            action.result = {"created_id": leave.pk, "created_type": "leave_approval"}
        else:
            return _action_error("Unsupported proposed action.", 400)

        action.status = "COMPLETED"
        action.save(update_fields=["status", "result", "updated_at"])
        return JsonResponse({"ok": True, "status": action.status, **action.result})


@login_required
@require_POST
def cancel_action(request, token):
    action = AuthorizedAction.objects.filter(token=token, user=request.user).first()
    if action is None:
        return _action_error("Proposed action was not found.", 404)
    if action.status == "CANCELLED":
        return JsonResponse({"ok": True, "status": action.status})
    if action.status != "PENDING":
        return _action_error("Only pending actions can be cancelled.", 409)
    action.status = "CANCELLED"
    action.save(update_fields=["status", "updated_at"])
    return JsonResponse({"ok": True, "status": action.status})

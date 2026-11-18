"""Assistant reasoning: OpenAI-compatible provider with a deterministic fallback."""
from __future__ import annotations

import json
import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are SiteForge Copilot, an operations assistant for a construction management "
    "platform. Answer using ONLY the supplied workspace briefing. Be concise, specific "
    "and practical. Use short paragraphs and bullet points. Quote numbers and dates from "
    "the briefing when relevant. If the briefing lacks the answer, say what data is "
    "missing and suggest which module to check. Never invent project data."
)


def provider_configured() -> bool:
    return bool(getattr(settings, "AI_API_KEY", ""))


def _compact_money(value, currency="USD"):
    value = float(value or 0)
    symbol = "$" if currency == "USD" else f"{currency} "
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(value) >= threshold:
            return f"{symbol}{value / threshold:.1f}{suffix}"
    return f"{symbol}{value:,.0f}"


def _call_provider(messages):
    base_url = getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = getattr(settings, "AI_MODEL", "gpt-4o-mini")
    timeout = getattr(settings, "AI_TIMEOUT_SECONDS", 25)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 700,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        return content or None, model
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("AI provider call failed: %s", exc)
        return None, model


def _bullets(items):
    return "\n".join(f"• {item}" for item in items)


def offline_reply(question: str, context: dict) -> str:
    q = question.lower()
    kpis = context["kpis"]
    currency = context.get("project", {}).get("currency", "USD") if context.get("project") else "USD"
    money = lambda value: _compact_money(value, currency)  # noqa: E731
    scope = (
        f"{context['project']['name']}"
        if context["project"]
        else f"{context['organization']} portfolio"
    )
    greeting = ("hello", "hi ", "hey", "good morning", "good afternoon")
    help_words = ("help", "what can you do", "capabilities", "how do i")

    if q.strip() in {"hi", "hello", "hey"} or any(q.startswith(word) for word in greeting):
        return (
            f"Hello. I can brief you on {scope} using live workspace data.\n\n"
            f"{_bullets(suggested := [
                'Budget, cost and change-order position',
                'Overdue tasks, RFIs and submittals',
                'Safety, defects and punch-list exposure',
                'Upcoming milestones and schedule risk',
            ])}\n\nAsk me about any of these, or request a daily briefing."
        )

    if any(word in q for word in help_words):
        return (
            "I am SiteForge Copilot. I read your permitted project data and answer questions about:\n\n"
            f"{_bullets([
                'Commercial position — budget, committed, actual and pending change orders',
                'Delivery — overdue tasks, open RFIs, submittals and milestones',
                'Quality and safety — defects, punch items and recent incidents',
                'Portfolio health and a suggested weekly focus',
            ])}\n\n"
            "Add an AI_API_KEY on the backend to route answers through a hosted language model; "
            "without a key I answer from a deterministic analysis of the database."
        )

    if "brief" in q or "summary" in q or "health" in q or "status" in q or "overview" in q:
        lines = [
            f"Here is the current picture for {scope}:",
            "",
            f"• Commercial: {money(kpis['budgeted'])} budget, {money(kpis['actual'])} actual "
            f"({kpis['utilization_pct']}% utilized), {money(kpis['pending_change_orders'])} in pending change orders.",
            f"• Delivery: {kpis['open_tasks']} open tasks ({kpis['overdue_tasks']} overdue), "
            f"{kpis['open_rfis']} open RFIs ({kpis['overdue_rfis']} overdue) and "
            f"{kpis['open_submittals']} open submittals.",
            f"• Quality & safety: {kpis['open_defects']} open defects, "
            f"{kpis['open_punch_items']} open punch items and {kpis['safety_incidents_90d']} "
            "safety incidents in the last 90 days.",
        ]
        if context["upcoming_milestones"]:
            next_item = context["upcoming_milestones"][0]
            lines.append(
                f"• Look ahead: {next_item['name']} is due {next_item['due_date']} "
                f"({next_item['project']})."
            )
        if kpis["overdue_tasks"] or kpis["overdue_rfis"]:
            lines.append("")
            lines.append("Suggested focus: clear the overdue correspondence and task backlog first.")
        return "\n".join(lines)

    if any(word in q for word in ("budget", "cost", "financial", "money", "spend", "commercial", "change order")):
        return (
            f"Commercial position for {scope}:\n\n"
            f"• Budget: {money(kpis['budgeted'])}\n"
            f"• Committed: {money(kpis['committed'])}\n"
            f"• Actual cost: {money(kpis['actual'])} ({kpis['utilization_pct']}% of budget)\n"
            f"• Remaining: {money(kpis['remaining'])}\n"
            f"• Pending change orders: {money(kpis['pending_change_orders'])}\n\n"
            + (
                "Utilisation is high — review pending change orders before the next cost report."
                if kpis["utilization_pct"] >= 85
                else "Spend is tracking within budget on the data available."
            )
        )

    if "rfi" in q:
        lines = [f"There are {kpis['open_rfis']} open RFIs, {kpis['overdue_rfis']} past due."]
        if context["overdue_rfis"]:
            lines.append("")
            lines.append(
                _bullets(
                    f"RFI {item['number']} — {item['subject']} (due {item['due_date']}, {item['priority']})"
                    for item in context["overdue_rfis"]
                )
            )
        else:
            lines.append("No overdue RFIs are recorded.")
        return "\n".join(lines)

    if "submittal" in q:
        return (
            f"{kpis['open_submittals']} submittals are open or awaiting approval. "
            "Review the submittal log for items in 'revise and resubmit' status and chase "
            "the responsible reviewers before the next coordination meeting."
        )

    if any(word in q for word in ("task", "overdue", "late", "behind")):
        lines = [
            f"{kpis['open_tasks']} tasks are open and {kpis['overdue_tasks']} are overdue. "
            f"Task completion is {kpis['task_progress_pct']}%."
        ]
        if context["overdue_tasks"]:
            lines.append("")
            lines.append(
                _bullets(
                    f"{item['title']} — due {item['due_date']} ({item['project']})"
                    for item in context["overdue_tasks"]
                )
            )
        return "\n".join(lines)

    if any(word in q for word in ("safe", "safety", "incident", "hazard")):
        return (
            f"{kpis['safety_incidents_90d']} safety incidents were recorded in the last 90 days. "
            "Pair this with the open corrective actions in the Quality module and confirm "
            "toolbox talks are logged in the daily reports."
        )

    if any(word in q for word in ("quality", "defect", "punch", "inspection", "snag")):
        return (
            f"Quality exposure: {kpis['open_defects']} open defects and "
            f"{kpis['open_punch_items']} open punch-list items. Prioritise any critical-severity "
            "defects and items blocking area handover."
        )

    if any(word in q for word in ("milestone", "schedule", "deadline", "date", "look ahead")):
        if not context["upcoming_milestones"]:
            return "No milestones are due in the next 30 days for this scope."
        lines = ["Upcoming milestones:"]
        lines.append(
            _bullets(
                f"{item['name']} — {item['due_date']} ({item['project']}, {item['status'].replace('_', ' ')})"
                for item in context["upcoming_milestones"]
            )
        )
        return "\n".join(lines)

    if "project" in q:
        if context["project"]:
            project = context["project"]
            return (
                f"{project['name']} ({project.get('number') or 'no number'}) is {project['status']} "
                f"in {project['city'] or 'an unspecified location'}.\n\n"
                f"• Client: {project['client_name'] or 'not recorded'}\n"
                f"• Contract value: {money(project['contract_value'])}\n"
                f"• Target completion: {project['target_completion_date'] or 'not set'}\n"
                f"• Task progress: {kpis['task_progress_pct']}%"
            )
        if context["projects"]:
            return "Projects in scope:\n\n" + _bullets(
                f"{item['name']} ({item.get('number') or '—'}) — {item['status']}"
                for item in context["projects"]
            )
        return "No projects are visible for your membership."

    return (
        f"I could not match that to a specific metric, but here is the latest snapshot for {scope}:\n\n"
        f"• Budget utilisation: {kpis['utilization_pct']}%\n"
        f"• Open tasks: {kpis['open_tasks']} ({kpis['overdue_tasks']} overdue)\n"
        f"• Open RFIs: {kpis['open_rfis']} ({kpis['overdue_rfis']} overdue)\n"
        f"• Open defects: {kpis['open_defects']}\n\n"
        "Try asking about budget, schedule, RFIs, quality, safety or a daily briefing."
    )


def generate_reply(question, context, history):
    """Return (content, provider, model, latency_ms)."""
    started = time.monotonic()

    if provider_configured():
        briefing = json.dumps(context, default=str, indent=2)
        messages = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nWORKSPACE BRIEFING:\n{briefing}"},
        ]
        for item in history[-10:]:
            messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": question})

        content, model = _call_provider(messages)
        latency = int((time.monotonic() - started) * 1000)
        if content:
            return content, "remote", model, latency

    content = offline_reply(question, context)
    latency = int((time.monotonic() - started) * 1000)
    return content, "offline", getattr(settings, "AI_MODEL", "siteforge-analyst"), latency

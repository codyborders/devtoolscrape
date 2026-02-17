"""OpenAI Agents SDK chatbot for natural language developer tool recommendations."""

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from agents import Agent, Runner, function_tool
from agents.items import ToolCallOutputItem

from database import count_all_startups, search_startups
from logging_config import get_logger

logger = get_logger("devtools.chatbot")

_CHATBOT_MODEL = os.getenv("CHATBOT_MODEL", "gpt-4o-mini")
_CHATBOT_MAX_TURNS = max(1, int(os.getenv("CHATBOT_MAX_TURNS", "3")))
_MAX_TOOLS_IN_CONTEXT = int(os.getenv("CHATBOT_MAX_TOOLS", "10"))

# FTS5 operator pattern to sanitize user-supplied queries
_FTS5_OPERATORS = re.compile(r'["\*\(\)]')
_FTS5_KEYWORDS = re.compile(r'\b(AND|OR|NOT|NEAR)\b', re.IGNORECASE)

_SYSTEM_PROMPT = """\
You are a helpful assistant for DevTools Scraper, a developer tools discovery platform.
Your job is to recommend developer tools from our database based on what the user asks.

Guidelines:
- Be conversational and concise. Give a 2-4 sentence intro, then list relevant tools.
- Recommend at most 5 tools per response.
- For each tool, include its name in bold with **Name** and a brief explanation of why it matches.
- If a tool description starts with a [Category] tag, mention the category.
- If no tools match, say so honestly and suggest the user try different terms or browse /search.
- Never invent tools that are not in the search results.
- Keep the total response under 300 words.
"""


def _sanitize_fts_query(query: str) -> str:
    """Strip FTS5 operators from a query string to prevent injection."""
    cleaned = _FTS5_OPERATORS.sub(" ", query)
    cleaned = _FTS5_KEYWORDS.sub(" ", cleaned)
    return " ".join(cleaned.split())


@function_tool
def search_tools(query: str) -> str:
    """Search the developer tools database for tools matching a query.

    Args:
        query: A search term or phrase to find matching developer tools.
    """
    sanitized = _sanitize_fts_query(query)
    if not sanitized:
        return json.dumps([])

    logger.info(
        "chatbot.search",
        extra={"event": "chatbot.search", "query": sanitized},
    )
    return json.dumps(
        search_startups(sanitized, limit=_MAX_TOOLS_IN_CONTEXT),
        default=str,
    )


@function_tool
def count_tools() -> str:
    """Return the total number of developer tools in the database."""
    total = count_all_startups()
    logger.debug(
        "chatbot.count",
        extra={"event": "chatbot.count", "total": total},
    )
    return str(total)


_agent = Agent(
    name="DevToolsAssistant",
    instructions=_SYSTEM_PROMPT,
    model=_CHATBOT_MODEL,
    tools=[search_tools, count_tools],
)


def _collect_tools(result: Any) -> list[dict[str, Any]]:
    """Extract deduplicated tool dicts from the agent run's tool call outputs."""
    seen_ids: set[int] = set()
    tools: list[dict[str, Any]] = []
    for item in result.new_items:
        if not isinstance(item, ToolCallOutputItem):
            continue
        try:
            parsed = json.loads(item.output)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(parsed, list):
            continue
        for tool in parsed:
            tid = tool.get("id")
            if tid is not None and tid not in seen_ids:
                seen_ids.add(tid)
                tools.append(tool)
    return tools


def generate_chat_response(user_message: str) -> dict[str, Any]:
    """Generate a chatbot response for a user's natural language question.

    Runs the OpenAI Agents SDK agent which can search the tools database
    and produce a conversational recommendation.

    Args:
        user_message: The user's question (should be pre-validated by caller).

    Returns:
        Dict with "response" (str) and "tools" (list of matched tool dicts).
    """
    try:
        result = Runner.run_sync(
            _agent,
            input=user_message,
            max_turns=_CHATBOT_MAX_TURNS,
        )
        response_text = result.final_output or ""
        tools = _collect_tools(result)

        logger.info(
            "chatbot.response",
            extra={
                "event": "chatbot.response",
                "message_length": len(user_message),
                "tools_found": len(tools),
                "response_length": len(response_text),
            },
        )
        return {"response": response_text, "tools": tools}

    except Exception:
        logger.exception(
            "chatbot.error",
            extra={"event": "chatbot.error", "message_length": len(user_message)},
        )
        return {
            "response": (
                "I'm having trouble connecting to my AI service right now. "
                "Please try the search page at /search for finding tools."
            ),
            "tools": [],
        }

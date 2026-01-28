"""Shared utilities for all tool modules."""

import logging
from typing import Optional

from ..storage import StorageBackend, LocalStorage

logger = logging.getLogger("om-apex-mcp")

# Global storage backend — initialized by server startup
_backend: Optional[StorageBackend] = None

# Relative path for daily progress within shared drive
DAILY_PROGRESS_REL = "business-plan/06 HR and Admin/Daily Progress"


def init_storage(backend: StorageBackend) -> None:
    """Initialize the global storage backend. Called once at server startup."""
    global _backend
    _backend = backend
    logger.info(f"Storage backend initialized: {type(backend).__name__}")


def get_backend() -> StorageBackend:
    """Get the current storage backend, lazily initializing if needed."""
    global _backend
    if _backend is None:
        _backend = LocalStorage()
        logger.info("Storage backend auto-initialized to LocalStorage")
    return _backend


def load_json(filename: str) -> dict:
    """Load a JSON file from the data directory."""
    return get_backend().load_json(filename)


def save_json(filename: str, data: dict) -> None:
    """Save data to a JSON file in the data directory."""
    get_backend().save_json(filename, data)


def get_claude_instructions_data() -> dict:
    """Return behavioral instructions for Claude across all platforms."""
    return {
        "session_start": {
            "description": "How to behave when starting a new conversation",
            "steps": [
                "1. Call get_full_context automatically at conversation start",
                "2. Output ONLY a brief 2-3 line greeting (see greeting_format below)",
                "3. Do NOT dump full context details to the user - you have the data internally",
                "4. Wait for user's first request"
            ],
            "greeting_format": {
                "template": "Full context loaded.\n\n**Quick Summary:** X pending tasks (Y high priority)\n\nHow can I help you today?",
                "rules": [
                    "Replace X with total pending task count",
                    "Replace Y with high priority task count",
                    "Do NOT list tasks, decisions, tech stack, or other details",
                    "Do NOT explain what context was loaded",
                    "Keep it to exactly 3 lines as shown in template"
                ]
            }
        },
        "session_end": {
            "description": "How to behave when user says 'end session', 'wrap up', 'save our work', or similar",
            "steps": [
                "1. Review the entire conversation for: decisions made, tasks completed, new tasks identified",
                "2. Summarize findings to user: 'I found X decisions, Y new tasks, Z completed tasks'",
                "3. Get user confirmation before saving",
                "4. Call add_decision for each decision (with area, decision, rationale, company)",
                "5. Call add_task for each new task",
                "6. Call complete_task for each completed task",
                "7. Call add_daily_progress with structured data",
                "8. Confirm everything was saved successfully"
            ],
            "add_daily_progress_format": {
                "person": "Nishad or Sumedha (whoever is running the session)",
                "interface": "code, code-app, cowork, or chat (lowercase)",
                "title": "Brief title of main work done",
                "completed": ["List of items completed"],
                "decisions": ["TECH-XXX: Description"],
                "tasks_completed": ["TASK-XXX: Description"],
                "tasks_created": ["TASK-XXX: Description"],
                "files_modified": ["path/to/file - description"],
                "notes": ["Important context for future reference"]
            }
        },
        "general_behavior": {
            "tone": "Professional, concise, helpful",
            "response_style": [
                "Keep responses focused and actionable",
                "Use markdown formatting for readability",
                "When listing tasks, show ID and description",
                "Don't over-explain - users are familiar with their business"
            ],
            "proactive_actions": [
                "Offer to save decisions when significant choices are made",
                "Suggest creating tasks for follow-up items",
                "Remind about session end protocol if conversation seems to be wrapping up"
            ]
        },
        "owners": {
            "Nishad": "Primary technical owner, supply chain expert, handles most Claude sessions",
            "Sumedha": "Co-owner, handles content, website updates, and some technical tasks"
        }
    }

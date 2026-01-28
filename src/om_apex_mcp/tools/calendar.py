"""Google Calendar tools: list events, create event, delete event."""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from mcp.types import Tool, TextContent

from . import ToolModule

logger = logging.getLogger("om-apex-mcp")

READING = ["list_calendar_events"]
WRITING = ["create_calendar_event", "delete_calendar_event"]

# Calendar service singleton
_calendar_service = None


def get_calendar_service():
    """Get or create Google Calendar API service."""
    global _calendar_service
    if _calendar_service is not None:
        return _calendar_service

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    # Support key as file path OR inline JSON (for Render/containers)
    creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    # Calendar scope
    scopes = ["https://www.googleapis.com/auth/calendar"]

    if creds_json:
        import json as _json
        info = _json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    elif creds_path:
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
    else:
        raise ValueError("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE")

    # For domain-wide delegation, impersonate the target user
    target_user = os.environ.get("GOOGLE_CALENDAR_USER", "nishad@omapex.com")
    delegated_creds = creds.with_subject(target_user)

    _calendar_service = build("calendar", "v3", credentials=delegated_creds)
    logger.info(f"Google Calendar service initialized for {target_user}")
    return _calendar_service


def register() -> ToolModule:
    tools = [
        Tool(
            name="list_calendar_events",
            description="List upcoming calendar events. Returns events from today by default.",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: primary calendar of GOOGLE_CALENDAR_USER)"
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days to look ahead (default: 7)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to return (default: 20)"
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="create_calendar_event",
            description="Create a new calendar event. Supports one-time and recurring events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Event title/summary"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (e.g., '2026-01-28T08:00:00') or 'HH:MM' for today"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format (e.g., '2026-01-28T09:00:00') or 'HH:MM' for today"
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description (optional)"
                    },
                    "recurrence": {
                        "type": "string",
                        "description": "Recurrence rule: 'daily', 'weekly', 'weekdays', or RRULE string (optional)"
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: primary)"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Timezone (default: America/New_York)"
                    },
                },
                "required": ["title", "start_time", "end_time"],
            },
        ),
        Tool(
            name="delete_calendar_event",
            description="Delete a calendar event by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event ID to delete"
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: primary)"
                    },
                },
                "required": ["event_id"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict) -> Optional[list[TextContent]]:
        try:
            service = get_calendar_service()
        except Exception as e:
            return [TextContent(type="text", text=f"Calendar API error: {str(e)}\n\nMake sure domain-wide delegation is enabled for the service account.")]

        calendar_id = arguments.get("calendar_id", "primary")
        timezone = arguments.get("timezone", "America/New_York")

        if name == "list_calendar_events":
            days_ahead = arguments.get("days_ahead", 7)
            max_results = arguments.get("max_results", 20)

            now = datetime.utcnow()
            time_min = now.isoformat() + "Z"
            time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

            try:
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()

                events = events_result.get("items", [])

                if not events:
                    return [TextContent(type="text", text=f"No events found in the next {days_ahead} days.")]

                result = []
                for event in events:
                    start = event["start"].get("dateTime", event["start"].get("date"))
                    result.append({
                        "id": event["id"],
                        "title": event.get("summary", "(No title)"),
                        "start": start,
                        "end": event["end"].get("dateTime", event["end"].get("date")),
                        "description": event.get("description", ""),
                        "recurrence": event.get("recurrence", []),
                    })

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                return [TextContent(type="text", text=f"Error listing events: {str(e)}")]

        elif name == "create_calendar_event":
            title = arguments["title"]
            start_time = arguments["start_time"]
            end_time = arguments["end_time"]
            description = arguments.get("description", "")
            recurrence = arguments.get("recurrence")

            # Parse simple time format (HH:MM) to full datetime
            today = datetime.now().strftime("%Y-%m-%d")
            if len(start_time) == 5 and ":" in start_time:  # HH:MM format
                start_time = f"{today}T{start_time}:00"
            if len(end_time) == 5 and ":" in end_time:
                end_time = f"{today}T{end_time}:00"

            event = {
                "summary": title,
                "description": description,
                "start": {
                    "dateTime": start_time,
                    "timeZone": timezone,
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": timezone,
                },
            }

            # Handle recurrence
            if recurrence:
                if recurrence.lower() == "daily":
                    event["recurrence"] = ["RRULE:FREQ=DAILY"]
                elif recurrence.lower() == "weekly":
                    event["recurrence"] = ["RRULE:FREQ=WEEKLY"]
                elif recurrence.lower() == "weekdays":
                    event["recurrence"] = ["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"]
                elif recurrence.upper().startswith("RRULE:"):
                    event["recurrence"] = [recurrence]
                else:
                    event["recurrence"] = [f"RRULE:{recurrence}"]

            try:
                created_event = service.events().insert(
                    calendarId=calendar_id,
                    body=event,
                ).execute()

                return [TextContent(type="text", text=f"Event created successfully!\n\nID: {created_event['id']}\nTitle: {title}\nStart: {start_time}\nEnd: {end_time}\nRecurrence: {recurrence or 'None'}\nLink: {created_event.get('htmlLink', 'N/A')}")]

            except Exception as e:
                return [TextContent(type="text", text=f"Error creating event: {str(e)}")]

        elif name == "delete_calendar_event":
            event_id = arguments["event_id"]

            try:
                service.events().delete(
                    calendarId=calendar_id,
                    eventId=event_id,
                ).execute()

                return [TextContent(type="text", text=f"Event {event_id} deleted successfully.")]

            except Exception as e:
                return [TextContent(type="text", text=f"Error deleting event: {str(e)}")]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )

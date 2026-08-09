from typing import List, Optional
from langchain_core.tools import tool
from datetime import datetime, timezone
import json

@tool
def read_recent_emails(query: str = "") -> str:
    """
    Search and read recent emails from the user's Gmail inbox.
    Useful for extracting action items, meeting prep, or finding company context.
    Provides mock data for demonstration purposes.
    """
    # Mock data to simulate Gmail integration
    mock_emails = [
        {
            "id": "1",
            "from": "investor.relations@nvidia.com",
            "subject": "NVIDIA Q3 Earnings Call Update",
            "date": "Aug 8, 2026",
            "snippet": "We have moved the earnings call to 2 PM PST on August 25. Please review the attached preliminary guidance on data center revenues...",
            "body": "Hi team,\nWe have moved the earnings call to 2 PM PST on August 25. Please review the attached preliminary guidance on data center revenues and Hopper GPU supply chain metrics before the call.\n\nBest,\nNvidia IR"
        },
        {
            "id": "2",
            "from": "sarah.chen@vc-fund.com",
            "subject": "Due Diligence Sync - Databricks",
            "date": "Aug 9, 2026",
            "snippet": "Can we sync tomorrow regarding the Databricks pre-IPO valuation model? We need to finalize the growth projections.",
            "body": "Hi,\nCan we sync tomorrow regarding the Databricks pre-IPO valuation model? We need to finalize the growth projections based on the recent enterprise AI spending reports.\n\nAction items for you:\n- Send the updated DCF model.\n- Review their latest reported revenue numbers.\n\nThanks,\nSarah"
        },
        {
            "id": "3",
            "from": "compliance@atlas.ai",
            "subject": "ACTION REQUIRED: Q3 Trading Window",
            "date": "Aug 5, 2026",
            "snippet": "This is a reminder that the Q3 trading window for MSFT and AAPL closes next Friday.",
            "body": "Please be advised that the Q3 trading window for MSFT and AAPL closes next Friday. All trades must be cleared by compliance."
        }
    ]

    query = query.lower()
    results = []
    
    for email in mock_emails:
        if not query or query in email["subject"].lower() or query in email["snippet"].lower() or query in email["from"].lower() or query in email["body"].lower():
            results.append(
                f"📧 From: {email['from']}\n"
                f"📅 Date: {email['date']}\n"
                f"📌 Subject: {email['subject']}\n"
                f"📄 Body: {email['body']}\n"
                "----------------------------------------"
            )
            
    if not results:
        return f"No emails found matching query: '{query}'"
        
    return "Inbox Search Results:\n\n" + "\n".join(results)

@tool
def get_upcoming_meetings(date_str: str = "today") -> str:
    """
    Retrieve upcoming meetings and events from the user's Google Calendar.
    Useful for meeting preparation and schedule checking.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Mock data to simulate Google Calendar
    mock_events = [
        {
            "title": "Sync: NVDA Earnings Strategy",
            "time": "10:00 AM - 10:45 AM",
            "attendees": ["alex@atlas.ai", "jordan@atlas.ai"],
            "description": "Review preliminary data center guidance."
        },
        {
            "title": "Call with Sarah (Databricks DD)",
            "time": "1:00 PM - 1:30 PM",
            "attendees": ["sarah.chen@vc-fund.com"],
            "description": "Finalize growth projections for pre-IPO model."
        },
        {
            "title": "Weekly Portfolio Review",
            "time": "3:00 PM - 4:00 PM",
            "attendees": ["team@atlas.ai"],
            "description": "Standard weekly sync."
        }
    ]
    
    lines = [f"🗓️ Calendar for {date_str} (Current time: {now_utc})\n"]
    for idx, event in enumerate(mock_events, 1):
        lines.append(
            f"{idx}. {event['title']}\n"
            f"   Time: {event['time']}\n"
            f"   Attendees: {', '.join(event['attendees'])}\n"
            f"   Details: {event['description']}"
        )
        
    return "\n\n".join(lines)

@tool
def schedule_meeting(title: str, time: str, attendees: List[str]) -> str:
    """
    Schedule a new meeting on the user's Google Calendar and send invites.
    """
    # Mock scheduling action
    return (
        f"✅ Successfully scheduled '{title}' for {time}.\n"
        f"Invites have been sent to: {', '.join(attendees)}."
    )

productivity_tools = [read_recent_emails, get_upcoming_meetings, schedule_meeting]

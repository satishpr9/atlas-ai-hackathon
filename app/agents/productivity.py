from typing import List, Optional
from langchain_core.tools import tool
from datetime import datetime, timezone, timedelta
import json

@tool
def read_recent_emails(query: str = "") -> str:
    """
    Search and read recent emails from the user's executive inbox.
    Useful for extracting action items, meeting prep, or finding company context.
    """
    now = datetime.now(timezone.utc)
    d1 = (now - timedelta(days=1)).strftime("%b %d, %Y")
    d2 = (now - timedelta(days=2)).strftime("%b %d, %Y")
    d3 = (now - timedelta(days=4)).strftime("%b %d, %Y")

    mock_emails = [
        {
            "id": "1",
            "from": "investor.relations@nvidia.com",
            "subject": "NVIDIA Earnings Call & Strategy Update",
            "date": d2,
            "snippet": "Preliminary guidance on data center revenues and next-gen AI GPU supply chain metrics...",
            "body": "Hi team,\nSharing the preliminary guidance on data center revenues and AI compute infrastructure workloads before the upcoming quarterly call.\n\nBest,\nNvidia IR"
        },
        {
            "id": "2",
            "from": "sarah.chen@vc-fund.com",
            "subject": "Due Diligence Sync - Pre-IPO Valuation Model",
            "date": "Today",
            "snippet": "Can we sync regarding the pre-IPO valuation model? We need to finalize the growth projections.",
            "body": "Hi,\nCan we sync regarding the pre-IPO valuation model? We need to finalize the growth projections based on recent enterprise AI spending reports.\n\nAction items for you:\n- Send the updated DCF model.\n- Review latest reported revenue metrics.\n\nThanks,\nSarah"
        },
        {
            "id": "3",
            "from": "compliance@atlas.ai",
            "subject": "ACTION REQUIRED: Portfolio Trading Window Notice",
            "date": d3,
            "snippet": "Quarterly trading window closing soon.",
            "body": "Please be advised that the quarterly trading window closes next Friday. All portfolio transactions must be pre-cleared by compliance."
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
    Retrieve upcoming meetings and events from the user's executive calendar.
    Useful for meeting preparation and schedule checking.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    mock_events = [
        {
            "title": "Portfolio Review & Sector Allocation",
            "time": "10:00 AM - 10:45 AM",
            "attendees": ["alex@atlas.ai", "jordan@atlas.ai"],
            "description": "Review tech & semiconductor weightings."
        },
        {
            "title": "Due Diligence Sync with Sarah",
            "time": "1:00 PM - 1:30 PM",
            "attendees": ["sarah.chen@vc-fund.com"],
            "description": "Finalize pre-IPO valuation assumptions."
        },
        {
            "title": "Executive Market Strategy",
            "time": "3:00 PM - 4:00 PM",
            "attendees": ["team@atlas.ai"],
            "description": "Weekly strategy and macro briefing."
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
    Schedule a new meeting on the user's executive calendar and send invites.
    """
    return (
        f"✅ Successfully scheduled '{title}' for {time}.\n"
        f"Invites have been sent to: {', '.join(attendees)}."
    )

productivity_tools = [read_recent_emails, get_upcoming_meetings, schedule_meeting]

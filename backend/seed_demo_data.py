from datetime import datetime, timedelta
import tools

tools.init_db()
conn = tools.get_conn()

# Create demo tracking table
conn.execute(
    "CREATE TABLE IF NOT EXISTS demo_seed_log "
    "(seed_key TEXT PRIMARY KEY, seeded_at TEXT)"
)

if conn.execute(
    "SELECT 1 FROM demo_seed_log WHERE seed_key='demo_v1'"
).fetchone():
    print("Demo data already exists. No duplicates added.")
    conn.close()
    raise SystemExit

def get_time(days_ago):
    return (
        datetime.now() - timedelta(days=days_ago)
    ).replace(hour=12, minute=30, second=0, microsecond=0).isoformat()

demo_tickets = {
    "kora_clothing": [
        ("request", "delivery_complaint", "KC1003", "Delayed delivery complaint", "high", "open", 0),
        ("request", "return_request", "KC1001", "Customer requests a kurta return", "medium", "resolved", 1),
        ("request", "exchange_request", "KC1004", "Customer requests size exchange", "medium", "in_progress", 2),
        ("request", "delivery_complaint", "KC1002", "Customer asks about shipment", "high", "open", 0),
        ("request", "return_request", "KC1005", "Customer asks about return eligibility", "low", "resolved", 3),
        ("escalation", "human_handoff", "KC1002", "Customer requests human support", "high", "open", 0),
        ("escalation", "human_handoff", "KC1003", "Customer needs help with delayed order", "normal", "in_progress", 1),
    ],
    "spice_route": [
        ("request", "table_reservation", "SR2003", "Customer requests reservation confirmation", "medium", "open", 0),
        ("request", "feedback", "SR2001", "Customer shares positive dining feedback", "low", "resolved", 1),
        ("request", "order_issue", "", "Customer reports late food delivery", "high", "open", 0),
        ("request", "table_reservation", "SR2004", "Customer confirms lunch reservation", "medium", "resolved", 2),
        ("request", "feedback", "SR2002", "Customer requests reservation change", "low", "in_progress", 1),
        ("escalation", "human_handoff", "", "Customer asks about nut allergy safety; manager confirmation needed", "high", "open", 0),
        ("escalation", "human_handoff", "", "Group of 12 requests a table; manager approval needed", "high", "in_progress", 1),
    ]
}

for business, tickets in demo_tickets.items():
    for kind, request_type, record_id, details, priority, status, days in tickets:
        conn.execute(
            """INSERT INTO requests
            (business, kind, request_type, record_id, details,
             priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                business, kind, request_type, record_id,
                "[DEMO] " + details, priority, status, get_time(days)
            )
        )

demo_chats = {
    "kora_clothing": [
        ("KC_CHAT_01", "Hi, can you track order KC1002?", "Your denim jacket is shipped. Expected delivery is November 6."),
        ("KC_CHAT_02", "What is your return policy?", "Returns are accepted within 7 days of delivery for unworn items with tags."),
        ("KC_CHAT_03", "My order KC1003 is delayed.", "I'm sorry! I can help you register a delivery complaint."),
        ("KC_CHAT_04", "Do you have size XL?", "Yes! We stock S, M, L and XL."),
        ("KC_CHAT_05", "I want to speak to a human.", "Certainly! I'll escalate your conversation to human support."),
    ],
    "spice_route": [
        ("SR_CHAT_01", "What is on your menu?", "We serve North Indian dishes, tandoor and biryani."),
        ("SR_CHAT_02", "Check reservation SR2001.", "Your reservation for 4 people at 8 PM is confirmed."),
        ("SR_CHAT_03", "What time do you close?", "We are open every day from 11 AM to 11 PM."),
        ("SR_CHAT_04", "I have a nut allergy. Is your food safe?", "I'll escalate this to our manager for confirmation."),
        ("SR_CHAT_05", "Can you accommodate 12 people?", "Groups of 10 or more require manager approval."),
    ]
}

for business, chats in demo_chats.items():
    for session, user_message, bot_message in chats:
        for role, message in [
            ("user", user_message),
            ("model", bot_message)
        ]:
            conn.execute(
                """INSERT INTO messages
                (business, session_id, role, text, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (business, session, role, message, get_time(0))
            )

conn.execute(
    "INSERT INTO demo_seed_log VALUES (?, ?)",
    ("demo_v1", datetime.now().isoformat())
)

conn.commit()
conn.close()

print("SUCCESS! Demo data added.")
print("Kora Clothing: 5 conversations, 5 requests, 2 escalations.")
print("Spice Route: 5 conversations, 5 requests, 2 escalations.")

import csv
import json
import sqlite3
from datetime import datetime, date
from pathlib import Path

BASE = Path(__file__).parent / "businesses"
DB_PATH = Path(__file__).parent / "convorza.db"


# ---------- DATABASE ----------

def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()

    # Existing support requests
    conn.execute(
        """CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business TEXT,
            kind TEXT,
            request_type TEXT,
            record_id TEXT,
            details TEXT,
            priority TEXT,
            status TEXT,
            created_at TEXT
        )"""
    )

    # Business owner accounts
    conn.execute(
        """CREATE TABLE IF NOT EXISTS owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT
        )"""
    )

    # Registered business profiles
    conn.execute(
        """CREATE TABLE IF NOT EXISTS business_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            business_id TEXT UNIQUE NOT NULL,
            business_name TEXT NOT NULL,
            industry TEXT NOT NULL,
            assistant_name TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (owner_id) REFERENCES owners(id)
        )"""
    )

    conn.commit()
    conn.close()


# ---------- LOADING BUSINESS DATA ----------

def load_config(business):
    with open(BASE / business / "config.json", encoding="utf-8") as f:
        return json.load(f)


def load_faq(business):
    with open(BASE / business / "faq.txt", encoding="utf-8") as f:
        return f.read()


def load_records(business):
    with open(BASE / business / "records.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------- CREATE A NEW BUSINESS WORKSPACE ----------

def create_business_workspace(
    business_id,
    business_name,
    industry,
    assistant_name
):
    """Create the files required by the AI for a newly registered business."""

    business_folder = BASE / business_id
    business_folder.mkdir(parents=True, exist_ok=True)

    config = {
        "business_name": business_name,
        "industry": industry,
        "assistant_name": assistant_name,
        "tone": "Friendly, helpful and professional",
        "languages": ["English", "Hindi", "Hinglish"],
        "quick_replies": [
            "I need help",
            "Track my order",
            "I have a complaint"
        ],
        "enabled_tools": [
            "lookup_record",
            "create_request",
            "escalate_to_human"
        ],
        "request_types": [
            "general_question",
            "complaint",
            "order_issue",
            "other"
        ],
        "escalation_rules": [
            "Customer requests a human agent",
            "Issue cannot be resolved",
            "Customer is very upset"
        ]
    }

    config_path = business_folder / "config.json"

    if not config_path.exists():
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    faq_path = business_folder / "faq.txt"

    if not faq_path.exists():
        with open(faq_path, "w", encoding="utf-8") as f:
            f.write(
                f"Business: {business_name}\n"
                f"Industry: {industry}\n\n"
                "Add your business information, products, "
                "services, prices, policies and frequently "
                "asked questions here.\n"
            )

    records_path = business_folder / "records.csv"

    if not records_path.exists():
        with open(records_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "record_id",
                "status",
                "expected_delivery"
            ])

    return {
        "success": True,
        "business_id": business_id,
        "message": "Business workspace created successfully"
    }


# ---------- RECORD LOOKUP ----------

def lookup_record(business, record_id):
    """Find an order / reservation / booking by its ID."""
    rows = load_records(business)

    for row in rows:
        first_value = list(row.values())[0]

        if first_value.lower() == record_id.strip().lower():
            return {"found": True, "record": row}

    return {
        "found": False,
        "message": "No record found with that ID."
    }


# ---------- POLICY CHECK ----------

def check_policy(business, record_id):
    """Check if an order is inside the 7-day return window."""
    result = lookup_record(business, record_id)

    if not result["found"]:
        return result

    record = result["record"]

    if "expected_delivery" not in record:
        return {
            "applicable": False,
            "message": "Return check does not apply to this record type."
        }

    if record["status"] != "Delivered":
        return {
            "applicable": True,
            "eligible": False,
            "reason": "Order is not delivered yet, so a return cannot start."
        }

    delivered = datetime.strptime(
        record["expected_delivery"], "%Y-%m-%d"
    ).date()

    days = (date.today() - delivered).days
    eligible = days <= 7

    return {
        "applicable": True,
        "eligible": eligible,
        "days_since_delivery": days,
        "window_days": 7,
        "reason": "Within the 7-day window." if eligible
        else "Outside the 7-day window."
    }


# ---------- CREATE SUPPORT REQUEST ----------

def create_request(business, request_type, record_id, details):
    """Register a complaint, return, exchange, reservation, etc."""
    init_db()

    conn = get_conn()

    cur = conn.execute(
        """INSERT INTO requests
        (business, kind, request_type, record_id, details,
         priority, status, created_at)
        VALUES (?, 'request', ?, ?, ?, 'normal', 'open', ?)""",
        (
            business,
            request_type,
            record_id,
            details,
            datetime.now().isoformat(timespec="seconds")
        )
    )

    conn.commit()
    ticket_id = cur.lastrowid
    conn.close()

    return {
        "success": True,
        "request_id": ticket_id,
        "status": "open"
    }


# ---------- HUMAN ESCALATION ----------

def escalate_to_human(business, summary, priority="normal"):
    """Hand the chat to a human with a short summary."""
    init_db()

    conn = get_conn()

    cur = conn.execute(
        """INSERT INTO requests
        (business, kind, request_type, record_id, details,
         priority, status, created_at)
        VALUES (?, 'escalation', 'human_handoff', '', ?, ?, 'open', ?)""",
        (
            business,
            summary,
            priority,
            datetime.now().isoformat(timespec="seconds")
        )
    )

    conn.commit()
    ticket_id = cur.lastrowid
    conn.close()

    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": "A human agent will follow up."
    }


# ---------- QUICK SELF-TEST ----------

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")

    print("1. lookup:", lookup_record("kora_clothing", "KC1003"))
    print("2. policy:", check_policy("kora_clothing", "KC1001"))

    print(
        "3. request:",
        create_request(
            "kora_clothing",
            "delivery_complaint",
            "KC1003",
            "Order delayed"
        )
    )

    print(
        "4. escalate:",
        escalate_to_human(
            "spice_route",
            "Rohan, table for 4, peanut allergy",
            "high"
        )
    )

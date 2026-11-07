
from datetime import datetime
from pathlib import Path
import sqlite3
import hashlib
import secrets
import re
from typing import Literal

from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import tools
import agent


app = FastAPI(title="Convorza AI")
FRONTEND = Path(__file__).parent.parent / "frontend"


# ---------- DATABASE INITIALIZATION ----------

def init_messages():
    conn = tools.get_conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business TEXT,
            session_id TEXT,
            role TEXT,
            text TEXT,
            created_at TEXT
        )"""
    )
    conn.commit()
    conn.close()


def init_auth_db():
    tools.init_db()

    conn = tools.get_conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS owner_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TEXT,
            FOREIGN KEY (owner_id) REFERENCES owners(id)
        )"""
    )
    conn.commit()
    conn.close()


# ---------- PASSWORD SECURITY ----------

def hash_password(password):
    salt = secrets.token_hex(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        200000
    ).hex()

    return salt + "$" + hashed


def verify_password(password, stored_hash):
    try:
        salt, saved_hash = stored_hash.split("$")

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            200000
        ).hex()

        return secrets.compare_digest(new_hash, saved_hash)

    except ValueError:
        return False


# ---------- AUTHENTICATION HELPERS ----------

def create_session(owner_id):
    token = secrets.token_urlsafe(32)

    conn = tools.get_conn()
    conn.execute(
        """INSERT INTO owner_sessions
        (owner_id, token, created_at)
        VALUES (?, ?, ?)""",
        (
            owner_id,
            token,
            datetime.now().isoformat(timespec="seconds")
        )
    )
    conn.commit()
    conn.close()

    return token


def get_current_owner(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please log in")

    token = authorization.replace("Bearer ", "", 1).strip()

    conn = tools.get_conn()
    conn.row_factory = sqlite3.Row

    owner = conn.execute(
        """
        SELECT owners.id, owners.name, owners.email
        FROM owners
        JOIN owner_sessions
        ON owners.id = owner_sessions.owner_id
        WHERE owner_sessions.token = ?
        """,
        (token,)
    ).fetchone()

    conn.close()

    if not owner:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return dict(owner)


# ---------- BUSINESS HELPERS ----------

def create_business_id(name):
    slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        name.lower()
    ).strip("_")

    slug = slug or "my_business"

    return slug + "_" + secrets.token_hex(3)


# ---------- REQUEST MODELS ----------

class ChatIn(BaseModel):
    business: str
    message: str
    session_id: str = "demo"
    history: list[dict] = []


class StatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]


class SignupIn(BaseModel):
    name: str
    email: str
    password: str
    business_name: str
    industry: str
    assistant_name: str


class LoginIn(BaseModel):
    email: str
    password: str


# ---------- SIGN UP API ----------


# ---------- SIGN UP API ----------

@app.post("/api/auth/signup")
def signup(body: SignupIn):
    init_auth_db()

    name = body.name.strip()
    email = body.email.strip().lower()
    business_name = body.business_name.strip()
    industry = body.industry.strip()
    assistant_name = body.assistant_name.strip()

    if not all([name, email, business_name, industry, assistant_name]):
        raise HTTPException(
            status_code=400,
            detail="Please fill in all fields"
        )

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid email address"
        )

    if len(body.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters"
        )

    business_id = create_business_id(business_name)

    conn = tools.get_conn()

    try:
        cursor = conn.execute(
            """
            INSERT INTO owners
            (name, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                email,
                hash_password(body.password),
                datetime.now().isoformat(timespec="seconds")
            )
        )

        owner_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO business_profiles
            (owner_id, business_id, business_name,
             industry, assistant_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                owner_id,
                business_id,
                business_name,
                industry,
                assistant_name,
                datetime.now().isoformat(timespec="seconds")
            )
        )

        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()

        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists"
        )

    conn.close()

    # CREATE THE BUSINESS WORKSPACE
    tools.create_business_workspace(
        business_id,
        business_name,
        industry,
        assistant_name
    )

    token = create_session(owner_id)

    return {
        "success": True,
        "message": "Account and business created successfully",
        "token": token,
        "owner": {
            "id": owner_id,
            "name": name,
            "email": email
        },
        "business": {
            "id": business_id,
            "business_name": business_name,
            "industry": industry,
            "assistant_name": assistant_name
        }
    }



# ---------- LOGIN API ----------

@app.post("/api/auth/login")
def login(body: LoginIn):
    init_auth_db()

    email = body.email.strip().lower()

    conn = tools.get_conn()
    conn.row_factory = sqlite3.Row

    owner = conn.execute(
        "SELECT * FROM owners WHERE email = ?",
        (email,)
    ).fetchone()

    conn.close()

    if not owner or not verify_password(
        body.password,
        owner["password_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    token = create_session(owner["id"])

    return {
        "success": True,
        "message": "Login successful",
        "token": token,
        "owner": {
            "id": owner["id"],
            "name": owner["name"],
            "email": owner["email"]
        }
    }





# ---------- LOGOUT API ----------

@app.post("/api/auth/logout")
def logout(authorization: str = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please log in")

    token = authorization.replace("Bearer ", "", 1).strip()

    conn = tools.get_conn()
    conn.execute(
        "DELETE FROM owner_sessions WHERE token = ?",
        (token,)
    )
    conn.commit()
    conn.close()

    return {"success": True, "message": "Logged out successfully"}


# ---------- GET OWNER BUSINESSES ----------

@app.get("/api/owner/businesses")
def owner_businesses(authorization: str = Header(default=None)):
    init_auth_db()

    owner = get_current_owner(authorization)

    conn = tools.get_conn()
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT business_id, business_name, industry, assistant_name
        FROM business_profiles
        WHERE owner_id = ?
        """,
        (owner["id"],)
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ---------- BUSINESS VALIDATION ----------

def business_names():
    return sorted(
        p.name for p in tools.BASE.iterdir()
        if p.is_dir()
    )



def check(business):
    if business not in business_names():
        raise HTTPException(status_code=404, detail="Unknown business")


def check_business_access(business, authorization):
    """Allow demo businesses, but restrict registered businesses to their owner."""

    check(business)

    conn = tools.get_conn()

    profile = conn.execute(
        """
        SELECT owner_id
        FROM business_profiles
        WHERE business_id = ?
        """,
        (business,)
    ).fetchone()

    conn.close()

    # Existing demo businesses remain accessible.
    if profile is None:
        return

    # Registered businesses require their owner's login.
    owner = get_current_owner(authorization)

    if owner["id"] != profile[0]:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this business"
        )



# ---------- UPDATE SUPPORT REQUEST STATUS ----------

@app.patch("/api/businesses/{business}/requests/{request_id}")
def update_request_status(
    business: str,
    request_id: int,
    body: StatusUpdate
):
    check(business)
    tools.init_db()

    conn = tools.get_conn()

    cursor = conn.execute(
        """UPDATE requests
           SET status = ?
           WHERE id = ? AND business = ?""",
        (body.status, request_id, business)
    )

    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        raise HTTPException(status_code=404, detail="Request not found")

    return {"success": True, "status": body.status}


# ---------- LIST DEMO BUSINESSES ----------


@app.get("/api/businesses")
def list_businesses(authorization: str = Header(default=None)):
    out = []

    # Existing demo businesses
    for name in business_names():
        cfg = tools.load_config(name)

        out.append({
            "id": name,
            "business_name": cfg["business_name"],
            "assistant_name": cfg["assistant_name"],
            "industry": cfg["industry"],
            "quick_replies": cfg["quick_replies"],
        })

    # Only show registered businesses belonging to the logged-in owner.
    if authorization:
        owner = get_current_owner(authorization)

        conn = tools.get_conn()
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT business_id, business_name, industry, assistant_name
            FROM business_profiles
            WHERE owner_id = ?
            """,
            (owner["id"],)
        ).fetchall()

        conn.close()

        for row in rows:
            business = dict(row)
            cfg = tools.load_config(business["business_id"])

            out.append({
                "id": business["business_id"],
                "business_name": business["business_name"],
                "assistant_name": business["assistant_name"],
                "industry": business["industry"],
                "quick_replies": cfg["quick_replies"]
            })

    return out


# ---------- CHAT API ----------

@app.post("/api/chat")
def chat(body: ChatIn):
    check(body.business)

    if not body.message.strip():
        return {"reply": ""}

    init_messages()

    reply = agent.chat(
        body.business,
        body.history,
        body.message
    )

    now = datetime.now().isoformat(timespec="seconds")

    conn = tools.get_conn()

    conn.execute(
        """INSERT INTO messages
        (business, session_id, role, text, created_at)
        VALUES (?,?,?,?,?)""",
        (body.business, body.session_id, "user", body.message, now)
    )

    conn.execute(
        """INSERT INTO messages
        (business, session_id, role, text, created_at)
        VALUES (?,?,?,?,?)""",
        (body.business, body.session_id, "model", reply, now)
    )

    conn.commit()
    conn.close()

    return {"reply": reply}


# ---------- DASHBOARD API ----------

@app.get("/api/dashboard/{business}")
def dashboard(business: str, authorization: str = Header(default=None)):
    check_business_access(business, authorization)

    tools.init_db()
    init_messages()

    conn = tools.get_conn()
    conn.row_factory = sqlite3.Row

    chats = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM messages WHERE business=?",
        (business,)
    ).fetchone()[0]

    messages = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE business=? AND role='user'",
        (business,)
    ).fetchone()[0]

    escalations = conn.execute(
        "SELECT COUNT(*) FROM requests WHERE business=? AND kind='escalation'",
        (business,)
    ).fetchone()[0]

    requests_n = conn.execute(
        "SELECT COUNT(*) FROM requests WHERE business=? AND kind='request'",
        (business,)
    ).fetchone()[0]

    status_rows = conn.execute(
        """
        SELECT LOWER(REPLACE(status, ' ', '_')) AS status_name,
               COUNT(*) AS total
        FROM requests
        WHERE business=?
        GROUP BY status_name
        """,
        (business,)
    ).fetchall()

    status_counts = {
        "open": 0,
        "in_progress": 0,
        "resolved": 0
    }

    for row in status_rows:
        if row["status_name"] in status_counts:
            status_counts[row["status_name"]] = row["total"]

    priority_rows = conn.execute(
        """
        SELECT LOWER(priority) AS priority_name,
               COUNT(*) AS total
        FROM requests
        WHERE business=? AND kind='request'
        GROUP BY priority_name
        """,
        (business,)
    ).fetchall()

    priority_counts = {
        "high": 0,
        "medium": 0,
        "low": 0
    }

    for row in priority_rows:
        if row["priority_name"] in priority_counts:
            priority_counts[row["priority_name"]] = row["total"]

    total_tracked = sum(status_counts.values())

    resolution_rate = (
        round((status_counts["resolved"] / total_tracked) * 100, 1)
        if total_tracked > 0 else 0
    )

    trend_rows = conn.execute(
        """
        SELECT DATE(created_at) AS day,
               COUNT(*) AS total
        FROM requests
        WHERE business=?
          AND DATE(created_at) >= DATE('now', '-6 days')
        GROUP BY DATE(created_at)
        ORDER BY day ASC
        """,
        (business,)
    ).fetchall()

    request_trend = [dict(row) for row in trend_rows]

    problems = conn.execute(
        """
        SELECT request_type, COUNT(*) AS n
        FROM requests
        WHERE business=? AND kind='request'
        GROUP BY request_type
        ORDER BY n DESC
        """,
        (business,)
    ).fetchall()

    recent = conn.execute(
        """
        SELECT id, kind, request_type, record_id, details,
               priority, status, created_at
        FROM requests
        WHERE business=?
        ORDER BY id DESC
        LIMIT 20
        """,
        (business,)
    ).fetchall()

    conn.close()

    return {
        "chats": chats,
        "messages": messages,
        "requests": requests_n,
        "escalations": escalations,
        "ai_resolved": max(chats - escalations, 0),
        "top_problems": [dict(r) for r in problems],
        "recent": [dict(r) for r in recent],
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "resolution_rate": resolution_rate,
        "request_trend": request_trend
    }


# ---------- FRONTEND ----------

if FRONTEND.exists():
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND, html=True),
        name="frontend"
    )

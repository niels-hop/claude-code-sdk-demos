#!/usr/bin/env python3
"""Create a test database with sample emails"""
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json

# Use test database in python-backend directory
DB_PATH = Path(__file__).parent.parent / "emails.db"

print(f"Creating test database at: {DB_PATH}")

# Connect to database
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

# Create emails table (simplified schema)
cursor.execute("""
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    subject TEXT,
    from_address TEXT NOT NULL,
    from_name TEXT,
    date_sent DATETIME NOT NULL,
    body_text TEXT,
    snippet TEXT,
    is_read BOOLEAN DEFAULT 0,
    is_starred BOOLEAN DEFAULT 0,
    has_attachments BOOLEAN DEFAULT 0,
    folder TEXT DEFAULT 'INBOX',
    labels TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Create recipients table
cursor.execute("""
CREATE TABLE IF NOT EXISTS recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    type TEXT CHECK(type IN ('to', 'cc', 'bcc')) NOT NULL,
    address TEXT NOT NULL,
    name TEXT,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
)
""")

# Insert sample emails
sample_emails = [
    {
        "message_id": "<test-1@example.com>",
        "subject": "Welcome to Email Agent",
        "from_address": "support@example.com",
        "from_name": "Support Team",
        "date_sent": (datetime.now() - timedelta(days=1)).isoformat(),
        "body_text": "Welcome to the Email Agent demo! This is a test email to demonstrate the Python SDK integration.",
        "snippet": "Welcome to the Email Agent demo...",
        "is_read": 0,
        "folder": "INBOX",
        "labels": json.dumps(["important"])
    },
    {
        "message_id": "<test-2@example.com>",
        "subject": "Test Email with Attachment",
        "from_address": "alice@example.com",
        "from_name": "Alice Smith",
        "date_sent": (datetime.now() - timedelta(hours=12)).isoformat(),
        "body_text": "This is a test email with an attachment. The attachment is just for demonstration purposes.",
        "snippet": "This is a test email with an attachment...",
        "is_read": 1,
        "has_attachments": 1,
        "folder": "INBOX"
    },
    {
        "message_id": "<test-3@example.com>",
        "subject": "Meeting Invitation",
        "from_address": "bob@example.com",
        "from_name": "Bob Johnson",
        "date_sent": (datetime.now() - timedelta(hours=6)).isoformat(),
        "body_text": "Hi, I'd like to schedule a meeting to discuss the project. Are you available tomorrow at 2 PM?",
        "snippet": "Hi, I'd like to schedule a meeting...",
        "is_read": 0,
        "folder": "INBOX"
    }
]

for email_data in sample_emails:
    cursor.execute("""
        INSERT OR IGNORE INTO emails (
            message_id, subject, from_address, from_name, date_sent,
            body_text, snippet, is_read, has_attachments, folder, labels
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        email_data["message_id"],
        email_data["subject"],
        email_data["from_address"],
        email_data["from_name"],
        email_data["date_sent"],
        email_data["body_text"],
        email_data["snippet"],
        email_data["is_read"],
        email_data.get("has_attachments", 0),
        email_data["folder"],
        email_data.get("labels")
    ))

    # Add recipient
    email_id = cursor.lastrowid
    if email_id > 0:
        cursor.execute("""
            INSERT INTO recipients (email_id, type, address)
            VALUES (?, 'to', 'you@example.com')
        """, (email_id,))

conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) FROM emails")
count = cursor.fetchone()[0]
print(f"✓ Created test database with {count} emails")

conn.close()

print("\nSample emails:")
for email in sample_emails:
    print(f"  - {email['subject']} (from: {email['from_name']})")

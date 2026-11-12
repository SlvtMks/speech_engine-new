from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


DEFAULT_DB_PATH = Path("data/call_agent.db")


class CallStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    phone TEXT NOT NULL,
                    name TEXT,
                    status TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS calls (
                    id TEXT PRIMARY KEY,
                    lead_id TEXT,
                    direction TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    current_step TEXT NOT NULL,
                    status TEXT NOT NULL,
                    external_call_id TEXT,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT,
                    FOREIGN KEY (lead_id) REFERENCES leads(id)
                );

                CREATE TABLE IF NOT EXISTS call_messages (
                    id TEXT PRIMARY KEY,
                    call_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    intent TEXT,
                    step TEXT,
                    audio_path TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (call_id) REFERENCES calls(id)
                );
                """
            )

    def create_lead(self, phone: str, name: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        now = self._now()
        lead_id = self._id()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO leads (id, phone, name, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (lead_id, phone, name, "new", notes, now, now),
            )
        return self.get_lead(lead_id)

    def list_leads(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_lead(self, lead_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if row is None:
            raise KeyError(f"Lead not found: {lead_id}")
        return self._row_to_dict(row)

    def update_lead(self, lead_id: str, status: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        lead = self.get_lead(lead_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE leads
                SET status = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status or lead["status"],
                    lead["notes"] if notes is None else notes,
                    self._now(),
                    lead_id,
                ),
            )
        return self.get_lead(lead_id)

    def create_call(
        self,
        lead_id: Optional[str],
        direction: str,
        scenario: str,
        current_step: str,
        status: str,
        external_call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = self._now()
        call_id = self._id()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO calls (
                    id, lead_id, direction, scenario, current_step, status,
                    external_call_id, started_at, updated_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (call_id, lead_id, direction, scenario, current_step, status, external_call_id, now, now),
            )
        return self.get_call(call_id)

    def list_calls(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM calls ORDER BY started_at DESC").fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_call(self, call_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        if row is None:
            raise KeyError(f"Call not found: {call_id}")
        call = self._row_to_dict(row)
        call["messages"] = self.list_messages(call_id)
        return call

    def update_call(
        self,
        call_id: str,
        current_step: Optional[str] = None,
        status: Optional[str] = None,
        finished: bool = False,
    ) -> Dict[str, Any]:
        call = self.get_call(call_id)
        finished_at = self._now() if finished else call.get("finished_at")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE calls
                SET current_step = ?, status = ?, updated_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    current_step or call["current_step"],
                    status or call["status"],
                    self._now(),
                    finished_at,
                    call_id,
                ),
            )
        return self.get_call(call_id)

    def add_message(
        self,
        call_id: str,
        role: str,
        text: str,
        intent: Optional[str] = None,
        step: Optional[str] = None,
        audio_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        message_id = self._id()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO call_messages (id, call_id, role, text, intent, step, audio_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, call_id, role, text, intent, step, audio_path, self._now()),
            )
            row = conn.execute("SELECT * FROM call_messages WHERE id = ?", (message_id,)).fetchone()
        return self._row_to_dict(row)

    def list_messages(self, call_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM call_messages WHERE call_id = ? ORDER BY created_at ASC",
                (call_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)

    def _id(self) -> str:
        return uuid.uuid4().hex

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

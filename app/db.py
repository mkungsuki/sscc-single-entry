# -*- coding: utf-8 -*-
"""ชั้นข้อมูล SQLite — เก็บเคสทั้งหมดเป็น JSON ต่อแถว (ยืดหยุ่นรองรับ custom fields)"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "sscc.db"


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL DEFAULT 'draft',   -- draft | submitted | imported
                hn TEXT, fname TEXT,
                sscc_patient_id TEXT,                    -- เลขที่ผู้ป่วยฝั่ง SSCC หลังส่งสำเร็จ
                data TEXT NOT NULL DEFAULT '{}',         -- JSON ค่าทุกฟิลด์ (key = ชื่อฟิลด์ SSCC / cf_*)
                fill_log TEXT DEFAULT '',
                created_at TEXT, updated_at TEXT, submitted_at TEXT
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cases_hn ON cases(hn)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)")


def save_case(case_id, data: dict):
    now = datetime.now().isoformat(timespec="seconds")
    hn = (data.get("x_a2") or "").strip()
    fname = (data.get("x_fname") or "").strip()
    payload = json.dumps(data, ensure_ascii=False)
    with _conn() as c:
        if case_id:
            c.execute("UPDATE cases SET data=?, hn=?, fname=?, updated_at=? WHERE id=?",
                      (payload, hn, fname, now, case_id))
            return int(case_id)
        cur = c.execute(
            "INSERT INTO cases (status, hn, fname, data, created_at, updated_at) VALUES ('draft',?,?,?,?,?)",
            (hn, fname, payload, now, now))
        return cur.lastrowid


def get_case(case_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["data"] = json.loads(d["data"] or "{}")
    return d


def list_cases(q="", status="", limit=200):
    sql = "SELECT id, status, hn, fname, sscc_patient_id, created_at, updated_at, submitted_at FROM cases"
    where, args = [], []
    if q:
        where.append("(hn LIKE ? OR fname LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    if status:
        where.append("status = ?")
        args.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def status_counts(q=""):
    sql = "SELECT status, COUNT(*) FROM cases"
    args = []
    if q:
        sql += " WHERE hn LIKE ? OR fname LIKE ?"
        args = [f"%{q}%", f"%{q}%"]
    sql += " GROUP BY status"
    with _conn() as c:
        return {r[0]: r[1] for r in c.execute(sql, args).fetchall()}


def set_draft_pid(case_id, sscc_patient_id):
    """จำเลขเคสฝั่ง SSCC ทันทีที่สร้างบนเว็บสำเร็จ (ยังเป็นร่าง) — ส่งซ้ำจะได้เปิดเคสเดิม ไม่สร้างซ้ำ"""
    with _conn() as c:
        c.execute("UPDATE cases SET sscc_patient_id=? WHERE id=?", (sscc_patient_id, case_id))


def set_submitted(case_id, sscc_patient_id, log=""):
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute("UPDATE cases SET status='submitted', sscc_patient_id=?, submitted_at=?, fill_log=? WHERE id=?",
                  (sscc_patient_id, now, log, case_id))


def append_log(case_id, msg):
    now = datetime.now().strftime("%H:%M:%S")
    with _conn() as c:
        c.execute("UPDATE cases SET fill_log = fill_log || ? WHERE id=?", (f"[{now}] {msg}\n", case_id))


def all_cases_full():
    with _conn() as c:
        rows = c.execute("SELECT * FROM cases ORDER BY id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d["data"] or "{}")
        out.append(d)
    return out


init()

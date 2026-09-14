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
        # คอลัมน์ที่เพิ่มทีหลัง (ฐานเก่าไม่มี) — เติมแบบไม่ทำข้อมูลเดิมหาย
        have = {r[1] for r in c.execute("PRAGMA table_info(cases)").fetchall()}
        for col in ("nrefer_ref TEXT", "nrefer_at TEXT", "nrefer_state TEXT DEFAULT 'draft'"):
            if col.split()[0] not in have:
                c.execute(f"ALTER TABLE cases ADD COLUMN {col}")
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
    sql = ("SELECT id, status, hn, fname, sscc_patient_id, created_at, updated_at, submitted_at, "
           "nrefer_ref, nrefer_at, nrefer_state FROM cases")
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


def set_nrefer(case_id, ref):
    """จำผลบันทึกที่ยืนยันแล้ว; ไม่ใช้เป็นสิทธิ์เปิด Add new ซ้ำ"""
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute("UPDATE cases SET nrefer_ref=?, nrefer_at=?, nrefer_state='saved' WHERE id=?", (ref, now, case_id))


def set_nrefer_state(case_id, state):
    if state not in ("draft", "review", "uncertain", "saved"):
        raise ValueError("invalid nRefer state")
    with _conn() as c:
        c.execute("UPDATE cases SET nrefer_state=? WHERE id=?", (state, case_id))


def _nrefer_conflict(conn, case):
    hn = str(case["data"].get("x_a2") or "").strip()
    an = str(case["data"].get("cf_an") or "").strip()
    if not hn or not an:
        return None
    rows = conn.execute("SELECT id, data FROM cases WHERE hn=? AND id<>? "
                        "AND (nrefer_ref IS NOT NULL OR nrefer_state IN ('review','uncertain','saved'))",
                        (hn, case["id"]))
    for row in rows:
        if str(json.loads(row["data"]).get("cf_an") or "").strip() == an:
            return row["id"]
    return None


def nrefer_conflict(case):
    """Another local case owns this admission; never compare by HN alone."""
    with _conn() as conn:
        return _nrefer_conflict(conn, case)


def claim_nrefer(case_id):
    """Atomically reserve one local admission before any browser interaction."""
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if not row or row["nrefer_ref"] or row["nrefer_state"] in ("review", "uncertain", "saved"):
            return False
        case = dict(row)
        case["data"] = json.loads(case["data"])
        if _nrefer_conflict(conn, case) is not None:
            return False
        conn.execute("UPDATE cases SET nrefer_state='review' WHERE id=?", (case_id,))
        return True


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

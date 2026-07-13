# -*- coding: utf-8 -*-
"""ล็อกกันรัน fill_sscc.py ซ้อนกัน — Edge ใช้โปรไฟล์เดียว เปิดสองตัวพร้อมกันจะพัง
ไฟล์ล็อกเก็บ pid + รายการเคสในคิว + เคสที่กำลังทำอยู่ (ให้หน้ารวมโชว์ความคืบหน้า)"""
import json
import os
import subprocess
import sys
from pathlib import Path

LOCK_PATH = Path(__file__).parent / "data" / "fill.lock"


def _pid_alive(pid):
    try:
        pid = int(pid)
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10).stdout
            return f'"{pid}"' in out
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def read():
    """คืนข้อมูลล็อกถ้ามีโปรเซสส่ง SSCC ทำงานอยู่จริง — ล็อกค้างของโปรเซสที่ตายแล้วถือว่าว่าง"""
    if not LOCK_PATH.exists():
        return None
    try:
        info = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not _pid_alive(info.get("pid", -1)):
        return None
    return info


def write(info):
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")


def release():
    try:
        LOCK_PATH.unlink()
    except OSError:
        pass

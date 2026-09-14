"""One browser owner thread per local app; live tabs retain web-owned sessions.

No credentials are transferred through the queue. Only one job can be active.
Playwright objects are accessed exclusively by the owner thread.
"""
import os
import queue
import threading
from pathlib import Path
from types import SimpleNamespace

import db
import runlock


class BusyError(RuntimeError):
    pass


class BrowserSession:
    def __init__(self, config, *, runner=None, headless=False):
        self.config = config
        self.runner = runner
        self.headless = headless
        self._mutex = threading.Lock()
        self._queue = queue.Queue()
        self._thread = None
        self._stop = threading.Event()
        self._state = {"state": "closed", "target": None, "current": None}

    def status(self):
        with self._mutex:
            return dict(self._state)

    def _set(self, **changes):
        with self._mutex:
            self._state.update(changes)

    def submit(self, target, ids, **options):
        ids = list(dict.fromkeys(ids))
        if target not in ("sscc", "nrefer") or not ids:
            raise ValueError("งานไม่ถูกต้อง")
        with self._mutex:
            if self._state["state"] not in ("closed", "idle") or runlock.read():
                raise BusyError("ยังมีฟอร์มรอตรวจ — ทำให้เสร็จหรือกดจบรอบนี้ก่อน")
            owner = runlock.read_session()
            if owner and owner.get("pid") != os.getpid():
                raise BusyError("มีหน้าต่างทำงานของโปรแกรมอีกชุดเปิดอยู่")
            self._stop.clear()
            self._state = {"state": "working", "target": target, "current": ids[0]}
            runlock.write({"pid": os.getpid(), "cases": ids, "current": ids[0], "target": target})
            self._queue.put({"target": target, "ids": ids, **options})
            if not self._thread or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, daemon=True, name="browser-session")
                self._thread.start()

    def finish_review(self):
        with self._mutex:
            if self._state["state"] not in ("review", "held"):
                raise BusyError("ยังไม่อยู่ช่วงตรวจฟอร์ม — รอให้กรอกเสร็จก่อน")
            self._state["state"] = "finishing"
            self._stop.set()

    def _review(self):
        self._set(state="review")

    def _execute(self, page, job, guards):
        import fill_nrefer
        import fill_sscc
        target = job["target"]
        args = SimpleNamespace(headless=False, auto_confirm=False, keep_open=True,
                               cancel_check=self._stop.is_set, on_review=self._review,
                               no_save=job.get("no_save", False), guard_handles=guards,
                               api_url=self.config.get("nrefer_api_url", "https://nrefer.moph.go.th/api/beta"))
        base = job.get("base_url") if target == "sscc" else self.config.get("nrefer_base_url", "https://nrefer.moph.go.th/beta")
        module = fill_sscc if target == "sscc" else fill_nrefer
        sent = 0
        for cid in job["ids"]:
            self._set(state="working", current=cid)
            runlock.write({"pid": os.getpid(), "cases": job["ids"], "current": cid, "target": target})
            case = db.get_case(cid)  # Read fresh data when the job actually starts.
            if not case:
                raise ValueError("ไม่พบเคส")
            if target == "nrefer":
                # Keep the same tab; only invoke the login flow if its session is absent/expired.
                if not fill_nrefer.token_ok(fill_nrefer.read_token(page)) or "/login" in page.url:
                    fill_nrefer.ensure_login(page, base, cid)
                if job.get('mode') == 'motor':
                    from stroke_motor_ui import process_motor
                    expected_hcode = self.config.get('nrefer_hcode')
                    actual_hcode = fill_nrefer.jwt_payload(fill_nrefer.read_token(page)).get('hcode')
                    if expected_hcode and str(actual_hcode) != str(expected_hcode):
                        raise ValueError('หน่วยงานที่ login ไม่ตรงกับ nrefer_hcode ใน config')
                    process_motor(page, base, case, args)
                    break  # Motor review does not change the main admission's save status.
                result = module.process_case(page, base, case, args)
            else:
                result = module.process_case(page, base, case, args, queue_mode=True)
            if result == "submitted":
                sent += 1
            else:
                if target == "nrefer" and not args.no_save and not self._stop.is_set() and not page.is_closed():
                    db.set_nrefer_state(cid, "uncertain")
                if not self._stop.is_set() and not page.is_closed():
                    self._set(state="held")
                    while not self._stop.is_set() and not page.is_closed():
                        page.wait_for_timeout(250)
                break  # Never advance a queue past an incomplete case.
        if sent and target == "sscc":
            import excel_export
            excel_export.schedule_export()

    def _run(self):
        from playwright.sync_api import sync_playwright
        context = None
        pages = {}
        try:
            with sync_playwright() as pw:
                profile = self.config.get("session_profile_dir") or str(Path(__file__).parent / "data" / "edge_profile")
                context = pw.chromium.launch_persistent_context(
                    profile, channel=self.config.get("browser_channel", "msedge"),
                    headless=self.headless, no_viewport=True, chromium_sandbox=True, service_workers="block")
                context._sscc_live_session = True
                runlock.write_session()
                while context.pages:
                    try:
                        job = self._queue.get_nowait()
                    except queue.Empty:
                        context.pages[0].wait_for_timeout(250)
                        continue
                    guards = []
                    page = pages.get(job["target"])
                    try:
                        if page is None or page.is_closed():
                            page = context.new_page()
                            pages[job["target"]] = page
                            page.set_default_timeout(10000)
                            if job["target"] == "sscc":
                                page.on("dialog", lambda dialog: dialog.accept())
                        page.bring_to_front()
                        if self.runner:
                            self.runner(page, job, self, guards)
                        else:
                            self._execute(page, job, guards)
                    except (Exception, SystemExit) as exc:
                        db.append_log(job["ids"][0], "งานหยุด: " + type(exc).__name__ + " — คงฟอร์มไว้ให้ตรวจ กดจบรอบนี้เมื่อต้องการออกจากงาน")
                        if job["target"] == "nrefer" and job.get('mode') != 'motor' and not job.get("no_save"):
                            current_case = db.get_case(self.status().get("current"))
                            if current_case and not current_case.get("nrefer_ref"):
                                db.set_nrefer_state(current_case["id"], "uncertain")
                        if page is not None and not page.is_closed():
                            self._set(state="held")
                            while not self._stop.is_set() and not page.is_closed():
                                page.wait_for_timeout(250)
                    finally:
                        # A no-save form must be left before its request guard is removed.
                        if self._stop.is_set() and page is not None and not page.is_closed():
                            url = (self.config.get("nrefer_base_url", "https://nrefer.moph.go.th/beta") + "/#/dmis/patient"
                                   if job["target"] == "nrefer" else job["base_url"] + "/stroke_formlist.php")
                            try:
                                page.goto(url, wait_until="domcontentloaded")
                            except Exception:
                                page.close()  # Do not expose a partially filled inspection form without its guard.
                        for guard in guards:
                            guard.close()
                        runlock.release()
                        self._set(state="idle", target=None, current=None)
        except Exception as exc:
            current = self.status().get("current")
            if current:
                db.append_log(current, "เบราว์เซอร์หยุด: " + type(exc).__name__ + " — ส่งใหม่เพื่อเปิดหน้าต่างอีกครั้ง")
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            runlock.release()
            runlock.release_session()
            with self._mutex:
                self._state = {"state": "closed", "target": None, "current": None}
                self._thread = None
                while not self._queue.empty():
                    self._queue.get_nowait()

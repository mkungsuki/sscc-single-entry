"""Observe user-initiated saves only; never request or guess a patient ref."""
from urllib.parse import urlsplit
import time


class SaveObserver:
    def __init__(self, page, api_url, identity):
        self.page, self.identity = page, identity
        self.endpoint = api_url.rstrip("/") + "/dmis/imc/save-patient"
        self.requests = set()
        self.saved = False
        self.ref = None
        self.attempted = False
        self.mismatch = False
        self.closed = False

    def matches_endpoint(self, req):
        return req.method == "POST" and urlsplit(req.url)._replace(query="", fragment="") == urlsplit(self.endpoint)

    def on_request(self, req):
        # nRefer writes person before patient. A failed second step is not proof
        # that nothing changed remotely, so all save attempts require reconciliation.
        person_endpoint = self.endpoint.rsplit("/", 1)[0] + "/save-person"
        if req.method == "POST" and urlsplit(req.url)._replace(query="", fragment="") == urlsplit(person_endpoint):
            self.attempted = True
        if not self.matches_endpoint(req):
            return
        self.attempted = True
        try:
            data = req.post_data_json["data"]
            matched = all(str(data.get(k) or "").strip() == str(v).strip()
                          for k, v in self.identity.items())
            if matched:
                self.requests.add(req)
            else:
                self.mismatch = True
        except (KeyError, TypeError, ValueError, AttributeError):
            self.mismatch = True

    def on_response(self, response):
        if response.request not in self.requests:
            return
        try:
            result = response.json()
            if response.status == 200 and result.get("statusCode") == 200:
                self.saved = True
                # Only a ref explicitly associated with this response is accepted.
                rows = result.get("rows")
                if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict):
                    row = rows[0]
                    if all(str(row.get(k) or "").strip() == str(v).strip() for k, v in self.identity.items()):
                        ref = str(row.get("ref") or "")
                        if ref.isdigit() and int(ref) > 0:
                            self.ref = ref
        except (ValueError, TypeError, AttributeError):
            pass

    def on_close(self, *args):
        self.closed = True

    def __enter__(self):
        self.page.on("request", self.on_request)
        self.page.on("response", self.on_response)
        self.page.on("close", self.on_close)
        return self

    def wait(self, timeout_ms, cancel_check=None):
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline and not (self.saved or self.closed or self.mismatch):
            if cancel_check and cancel_check():
                break
            try:
                self.page.wait_for_timeout(250)
            except Exception:
                self.closed = True
        return self.saved and not self.mismatch, self.ref

    def __exit__(self, *args):
        for event, callback in (("request", self.on_request), ("response", self.on_response), ("close", self.on_close)):
            try:
                self.page.remove_listener(event, callback)
            except Exception:
                pass  # Browser may already be closed; don't erase the saved outcome.

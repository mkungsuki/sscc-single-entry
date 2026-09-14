"""Inspection mode: allow only known read endpoints on the configured nRefer API."""
from urllib.parse import urlsplit


class GuardHandle(list):
    def close(self):
        try:
            self.context.unroute("**/*", self.handler)
        except Exception:
            pass  # Closed contexts have no requests to protect.


def install_read_only_guard(context, api_url, his_url=None):
    base = urlsplit(api_url.rstrip("/"))
    root = base.path.rstrip("/") + "/"
    # Public nRefer 5.0.8 service definitions, checked 2026-09-10.
    # Authentication checks are POST too; blocking them logs the user out.
    post_paths = {
        "dmis/imc/patient", "dmis/imc/person", "user/user-status",
        "user/user-by-key", "admin/thaid/authenticated",
        "libs/lib-ward",
    }
    get_paths = {
        "dmis/imc/evaluate-choice", "dmis/imc/dmis-type",
        "dmis/imc/visit-result", "dmis/imc/service-status",
        "dmis/imc/modified-rankin-scale/0",
    }
    allowed = {root + path: {"POST", "OPTIONS"} for path in post_paths}
    allowed.update({root + path: {"GET", "HEAD", "OPTIONS"} for path in get_paths})
    blocked = GuardHandle()
    his = urlsplit((his_url or '').rstrip('/'))
    his_root = his.path.rstrip('/') + '/'
    his_valid = his.scheme in ('http', 'https') and bool(his.netloc) and not his.query and not his.fragment and not his.username
    # Never reinterpret nRefer's API as a HIS endpoint.
    if (his.scheme, his.netloc) == (base.scheme, base.netloc) and (his_root.startswith(root) or root.startswith(his_root)):
        his_valid = False

    def his_read(req, url):
        if not his_valid or (url.scheme, url.netloc) != (his.scheme, his.netloc):
            return False
        if req.method != 'POST' or not url.path.startswith(his_root):
            return False
        parts = url.path[len(his_root):].split('/')
        # urlHisRefer = configured HIS base + server-provided HIS name (or refer).
        # These four POST methods are read operations in the public HIS service.
        return len(parts) == 2 and bool(parts[0]) and parts[0] not in ('.','..') and parts[1] in {'person','admission','service','diagnosis-ipd'}

    def route_request(route):
        req = route.request
        url = urlsplit(req.url)
        if his_read(req, url):
            route.continue_()
            return
        if (url.scheme, url.netloc) == (base.scheme, base.netloc) and url.path.startswith(root):
            if req.method not in allowed.get(url.path, set()):
                blocked.append(url.path)  # Never persist payloads, query params, or auth codes.
                route.abort("blockedbyclient")
                return
        elif req.method not in ("GET", "HEAD", "OPTIONS"):
            blocked.append(url.path)
            route.abort("blockedbyclient")
            return
        route.continue_()

    context.route("**/*", route_request)
    blocked.context, blocked.handler = context, route_request
    return blocked

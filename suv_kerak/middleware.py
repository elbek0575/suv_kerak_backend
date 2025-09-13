# suv_kerak/middleware.py
import time, json, logging
from datetime import datetime, timezone

logger = logging.getLogger("access")
EXCLUDE_PATHS = ("/admin/js/", "/static/", "/favicon.ico", "/healthz")

def _client_ip(meta):
    xff = meta.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return meta.get("REMOTE_ADDR")

class AccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0 = time.time()
        path = request.path or ""
        status = None
        exc_info = None
        try:
            response = self.get_response(request)
            status = getattr(response, "status_code", None)
            return response
        except Exception as e:
            status = 500
            exc_info = repr(e)[:500]  # қисқартириб оламиз
            raise
        finally:
            if not any(path.startswith(p) for p in EXCLUDE_PATHS):
                rec = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "path": path,
                    "qs": request.META.get("QUERY_STRING", ""),
                    "method": request.method,
                    "status": status,
                    "duration_ms": int((time.time() - t0) * 1000),
                    "ip": _client_ip(request.META),
                    "ua": request.META.get("HTTP_USER_AGENT", "")[:200],
                    "exc": exc_info,  # фақат 500 ларда тўлади
                }
                logger.info(json.dumps(rec, ensure_ascii=False))


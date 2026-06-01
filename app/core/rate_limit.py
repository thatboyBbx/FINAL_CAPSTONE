"""
app/core/rate_limit.py
======================
Shared slowapi rate-limiter instance.

Import `limiter` here and apply @limiter.limit("N/period") to any route.
The limiter must be attached to app.state in main.py and its exception
handler registered there too.
"""
from fastapi import Request
from slowapi import Limiter


def _real_ip(request: Request) -> str:
    """
    Rate-limit key: client IP, honouring X-Forwarded-For only from trusted proxies.
    Imported lazily so settings are resolved before the module is evaluated.
    """
    from app.core.config import settings

    client_ip: str = request.client.host if request.client else "0.0.0.0"
    trusted = {ip.strip() for ip in settings.trusted_proxy_ips.split(",") if ip.strip()}

    if client_ip in trusted:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return client_ip


limiter = Limiter(key_func=_real_ip)

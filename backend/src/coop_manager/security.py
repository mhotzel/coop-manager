from collections.abc import Awaitable, Callable, Sequence

from fastapi import FastAPI, Request, Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; "
        "base-uri 'self'; object-src 'none'"
    ),
}

HSTS = "max-age=31536000; includeSubDomains"


def init_security(app: FastAPI, trusted_proxies: Sequence[str]) -> None:
    """Hängt die Middlewares für Security-Header und Reverse Proxy in die App ein."""
    app.middleware("http")(_set_security_headers)
    # Zuletzt hinzugefügt = außen: Der Proxy-Teil muss vorher das Schema auf https korrigieren.
    if trusted_proxies:
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=list(trusted_proxies))


async def _set_security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", HSTS)
    return response

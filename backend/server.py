"""
Transparent reverse proxy: FastAPI on :8001 -> Next.js on :3000.

Why this exists
---------------
This pod's Kubernetes ingress hard-routes every request whose path starts with
"/api" to this FastAPI process on port 8001. The actual application is a
Next.js app (served by supervisor on port 3000) whose own API handlers live
under /api/* (e.g. /api/agents, /api/accounts, /api/health).

Without this proxy the browser's fetch("/api/agents") would land here and 404,
so the dashboard rendered empty even though the Neon database had data. This
proxy simply forwards anything the ingress sends here to the Next.js server,
preserving method, path, query string, request body, and — crucially — the
Cookie / Set-Cookie headers so the session-based auth keeps working.

No application (repo) code is modified; only this platform-side backend is.
"""

import httpx
from fastapi import FastAPI, Request
from starlette.responses import Response

NEXT_ORIGIN = "http://127.0.0.1:3000"

# Hop-by-hop / connection-management request headers we must not forward.
_DROP_REQUEST_HEADERS = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "upgrade",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
}

# Response headers that would corrupt the payload if forwarded verbatim
# (httpx already decodes the body, so length/encoding must be recomputed).
_DROP_RESPONSE_HEADERS = {
    "content-length",
    "transfer-encoding",
    "content-encoding",
    "connection",
    "keep-alive",
}

app = FastAPI()
client = httpx.AsyncClient(base_url=NEXT_ORIGIN, timeout=120.0, follow_redirects=False)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(path: str, request: Request):
    url = "/" + path
    fwd_headers = [(k, v) for k, v in request.headers.items() if k.lower() not in _DROP_REQUEST_HEADERS]
    body = await request.body()

    try:
        upstream = await client.request(
            request.method,
            url,
            headers=fwd_headers,
            content=body,
            params=request.query_params,
        )
    except httpx.ConnectError:
        return Response(
            content=b'{"error":"Upstream Next.js server not reachable on port 3000."}',
            status_code=502,
            media_type="application/json",
        )

    content = upstream.content
    raw_headers = [
        (k.encode("latin-1"), v.encode("latin-1"))
        for k, v in upstream.headers.multi_items()
        if k.lower() not in _DROP_RESPONSE_HEADERS
    ]
    raw_headers.append((b"content-length", str(len(content)).encode("latin-1")))

    out = Response(content=content, status_code=upstream.status_code)
    out.raw_headers = raw_headers
    return out


@app.on_event("shutdown")
async def _shutdown():
    await client.aclose()

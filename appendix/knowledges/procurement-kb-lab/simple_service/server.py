"""
watsonx Orchestrate - Knowledge "Custom service" search server (lab version)
Searches the purchase-approval policy documents in POLICY_DIR (Markdown, one
"## " section = one search result) and returns the best-matching sections.

Run (from the lab folder):
    pip install -r requirements.txt
    python -m simple_service.server
    (CUSTOM_SERVICE_HOST defaults to 0.0.0.0, CUSTOM_SERVICE_PORT defaults to 8000)

Settings are read from a .env file in the current directory, or in this script's
folder or any parent folder (override with CUSTOM_SERVICE_ENV_FILE), e.g.
    CUSTOM_SERVICE_PORT=8070
    AUTH_USERNAME=orchestrate
    AUTH_PASSWORD=<random string>

Search settings:
    POLICY_DIR       folder of *.md policy files (default: ../data next to this package)
    POLICY_BASE_URL  optional URL prefix where the policy files are published; when set,
                     each result links to <POLICY_BASE_URL>/<file name>
    SEARCH_TOP_K     max results per query (default: 3)
    SEARCH_MIN_SCORE drop sections scoring below this (default: 0.4; 1.0 = every query
                     bigram found once; a heading match counts double, so scores can exceed 1)

Optional auth (set one or both; a request passes if EITHER matches; none = no auth):
    AUTH_USERNAME / AUTH_PASSWORD   -> Basic auth
    AUTH_API_KEY                    -> API key auth (no Bearer token needed)

API key is accepted in any of these forms:
    Authorization: <key>
    Authorization: ApiKey <key>   /  Authorization: Bearer <key>
    Authorization: Basic base64("apikey:<key>")   (IBM style)
    api_key: <key>  (watsonx Orchestrate default)
    X-API-Key: <key>   /  apikey: <key>   /  api-key: <key>
    ?apikey=<key>   (query parameter)
Every request is always logged ([REQ] header names, auth-related headers masked,
[AUTH] result and reason, [RES] status) to the console and to custom_service.log
(override with CUSTOM_SERVICE_LOG_FILE). AUTH_DEBUG=true also logs all header
values and the request body. GET /health is a no-auth reachability check.
"""

import base64
import binascii
import glob
import logging
import os
import re
import secrets
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel

# Load .env before any os.getenv() below. Real environment variables take precedence.
# Search order (first found wins):
#   1. CUSTOM_SERVICE_ENV_FILE  (explicit path)
#   2. current working directory  (e.g. project root when using `python -m pkg.server`)
#   3. this script's folder, then its parent folders up to the filesystem root
def _find_env_file() -> Optional[str]:
    explicit = os.getenv("CUSTOM_SERVICE_ENV_FILE")
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    candidates = [os.path.join(os.getcwd(), ".env")]
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        candidates.append(os.path.join(d, ".env"))
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return next((p for p in candidates if os.path.isfile(p)), None)


ENV_FILE = _find_env_file()
_env_loaded = bool(ENV_FILE) and load_dotenv(ENV_FILE, override=False)

# Log to console AND to a file (default: custom_service.log next to this script).
LOG_FILE = os.getenv("CUSTOM_SERVICE_LOG_FILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "custom_service.log")
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
_root = logging.getLogger()
_root.setLevel(logging.INFO)
if not _root.handlers:
    _console = logging.StreamHandler()
    _console.setFormatter(_fmt)
    _root.addHandler(_console)
    try:
        from logging.handlers import RotatingFileHandler
        _file = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3,
                                    encoding="utf-8")
        _file.setFormatter(_fmt)
        _root.addHandler(_file)
    except OSError as e:
        _root.warning("Cannot open log file %s: %s", LOG_FILE, e)
logger = logging.getLogger("custom_service")
logger.info("Log file: %s", LOG_FILE)
if _env_loaded:
    logger.info("Loaded environment from %s", ENV_FILE)
else:
    logger.warning(".env not found in %s or above %s (using process environment only)",
                   os.getcwd(), os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="Custom Search Service", version="1.0.0")


# ---------------------------------------------------------------------------
# Request / Response models (custom service spec)
# ---------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str
    filter: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    title: str
    body: str
    url: Optional[str] = None
    result_metadata: Optional[Dict[str, Any]] = None  # e.g. {"score": 123}


class SearchResponse(BaseModel):
    search_results: List[SearchResult]


# ---------------------------------------------------------------------------
# Optional authentication (Basic / API key / none)
# ---------------------------------------------------------------------------
AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")
AUTH_API_KEY = os.getenv("AUTH_API_KEY")
AUTH_DEBUG = os.getenv("AUTH_DEBUG", "false").lower() == "true"

# "api_key" is the default header name used by watsonx Orchestrate API key connections.
API_KEY_HEADERS = ("api_key", "x-api-key", "apikey", "api-key", "x-apikey")


def _eq(a: Optional[str], b: str) -> bool:
    return a is not None and secrets.compare_digest(a.encode(), b.encode())


def _mask(v: str) -> str:
    # Never print short secrets in full; for longer ones show only a 4-char prefix.
    return f"***({len(v)} chars)" if len(v) <= 8 else f"{v[:4]}...({len(v)} chars)"


def _decode_basic(value: str) -> Optional[tuple]:
    try:
        user, _, pwd = base64.b64decode(value).decode("utf-8").partition(":")
        return user, pwd
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _api_key_candidates(request: Request) -> List[tuple]:
    """Collect every place an API key might arrive in, as (source, value) pairs."""
    cands: List[tuple] = []
    auth = request.headers.get("authorization", "").strip()
    if auth:
        scheme, _, rest = auth.partition(" ")
        rest = rest.strip()
        if not rest:                                   # Authorization: <key>
            cands.append(("Authorization (raw)", scheme))
        elif scheme.lower() == "basic":                # Basic base64(apikey:<key>)
            decoded = _decode_basic(rest)
            if decoded:
                cands.append((f"Authorization Basic (user={decoded[0]!r})", decoded[1]))
        else:                                          # ApiKey / Bearer / Token <key>
            cands.append((f"Authorization {scheme}", rest))
    for h in API_KEY_HEADERS:
        if request.headers.get(h):
            cands.append((f"header {h}", request.headers[h].strip()))
    if request.query_params.get("apikey"):
        cands.append(("query ?apikey", request.query_params["apikey"]))
    return cands


logger.info("AUTH_DEBUG=%s, auth mode=%s", AUTH_DEBUG,
            "+".join(m for m, on in (("basic", AUTH_USERNAME and AUTH_PASSWORD),
                                     ("api_key", AUTH_API_KEY)) if on) or "none")

SENSITIVE_HEADERS = {"authorization", "cookie", "proxy-authorization"} | set(API_KEY_HEADERS)


def _is_auth_like(name: str) -> bool:
    n = name.lower()
    return n in SENSITIVE_HEADERS or any(t in n for t in ("key", "auth", "token", "secret"))


@app.middleware("http")
async def request_logger(request: Request, call_next):
    """Always log EVERY incoming request (any path/method, incl. 401/404/422):
    which header names arrived and the auth-like ones (values masked).
    AUTH_DEBUG=true additionally logs all header values and the body."""
    import time
    start = time.perf_counter()
    client = request.client.host if request.client else "-"
    logger.info("[REQ] %s %s from %s", request.method, request.url.path, client)
    logger.info("[REQ] header names: %s", list(request.headers.keys()))
    auth_like = {k: _mask(v) for k, v in request.headers.items() if _is_auth_like(k)}
    logger.info("[REQ] auth-related headers: %s", auth_like or "(none)")
    if request.query_params:
        logger.info("[REQ] query param names: %s", list(request.query_params.keys()))
    if AUTH_DEBUG:
        headers = {k: (_mask(v) if _is_auth_like(k) else v) for k, v in request.headers.items()}
        body = await request.body()
        logger.info("[DEBUG] headers: %s", headers)
        logger.info("[DEBUG] body: %s", body[:2000].decode("utf-8", "replace") or "(empty)")
    response = await call_next(request)
    logger.info("[RES] %s %s -> %d (%.0f ms)", request.method, request.url.path,
                response.status_code, (time.perf_counter() - start) * 1000)
    return response


@app.get("/health", include_in_schema=False)
async def health() -> Dict[str, str]:
    """No-auth reachability check: open http://<host>:<port>/health in a browser."""
    return {"status": "ok"}


def verify_auth(request: Request) -> None:
    """Basic and API key can be enabled at the same time: a request passes if
    EITHER configured method matches. No method configured -> allow."""
    basic_on = bool(AUTH_USERNAME and AUTH_PASSWORD)
    api_on = bool(AUTH_API_KEY)
    if not basic_on and not api_on:
        return

    reasons: List[str] = []

    if basic_on:
        auth = request.headers.get("authorization", "")
        scheme, _, rest = auth.partition(" ")
        decoded = _decode_basic(rest.strip()) if scheme.lower() == "basic" else None
        if decoded and _eq(decoded[0], AUTH_USERNAME) and _eq(decoded[1], AUTH_PASSWORD):
            logger.info("[AUTH] OK (basic, user=%r)", decoded[0])
            return
        if not auth:
            reasons.append("basic: no Authorization header")
        elif not decoded:
            reasons.append(f"basic: Authorization scheme is {scheme!r}, not Basic")
        else:
            reasons.append(f"basic: wrong username or password (user={decoded[0]!r})")

    if api_on:
        cands = _api_key_candidates(request)
        for source, value in cands:
            if _eq(value, AUTH_API_KEY):
                logger.info("[AUTH] OK (api_key) via %s", source)
                return
        if not cands:
            reasons.append("api_key: no API key found in any known header or ?apikey "
                           "(check [REQ] header names above)")
        else:
            reasons.append(f"api_key: key found but does not match "
                           f"{ {s: _mask(v) for s, v in cands} }")

    logger.warning("[AUTH] FAIL: %s", " | ".join(reasons))
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"} if basic_on else None,
    )


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------
POLICY_DIR = os.getenv("POLICY_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
# Optional: where the policy files are published (shown as each result's link).
POLICY_BASE_URL = os.getenv("POLICY_BASE_URL", "").strip()
try:
    SEARCH_TOP_K = max(1, int(os.getenv("SEARCH_TOP_K", "3")))
except ValueError:
    raise SystemExit(f"SEARCH_TOP_K must be an integer, got: {os.getenv('SEARCH_TOP_K')!r}")
try:
    SEARCH_MIN_SCORE = float(os.getenv("SEARCH_MIN_SCORE", "0.4"))
except ValueError:
    raise SystemExit(f"SEARCH_MIN_SCORE must be a number, got: {os.getenv('SEARCH_MIN_SCORE')!r}")

# Question words that carry no search meaning (Korean + English).
STOP_WORDS = {
    "알려줘", "알려주세요", "알려", "주세요", "뭐야", "무엇", "무엇인가요", "어떻게", "어떤",
    "해야", "하나요", "되나요", "있나요", "인가요", "대해", "대한", "관련", "경우", "요청은",
    "what", "how", "is", "the", "a", "an", "of", "for", "to", "in", "please", "tell", "me",
}


# Common Korean particles / endings, longest first. "노트북을" -> "노트북", "검토가" -> "검토".
PARTICLES = ("에서는", "으로는", "에서", "으로", "에게", "까지", "부터", "라도", "이란", "려면",
             "하면", "을", "를", "이", "가", "은", "는", "의", "에", "로", "과", "와", "도", "만")


def _strip_particle(t: str) -> str:
    if any(c.isdigit() for c in t):          # keep "300만", "30일" as they are
        return t
    for p in PARTICLES:
        if t.endswith(p) and len(t) - len(p) >= 2:
            return t[: -len(p)]
    return t


def _tokens(text: str) -> List[str]:
    text = re.sub(r"(?<=\d),(?=\d)", "", text.lower())   # "3,000만" -> "3000만"
    words = (w for w in re.findall(r"[0-9a-z가-힣]+", text) if w not in STOP_WORDS)
    return [t for t in (_strip_particle(w) for w in words) if t not in STOP_WORDS]


def _grams(text: str) -> set:
    """Character bigrams per token: works for Korean without a morphological analyzer
    ("승인권자" matches "승인") and keeps tokens with digits ("3000만", "30일") whole,
    so "3000만" never matches "300만"."""
    out = set()
    for t in _tokens(text):
        if len(t) == 1 or any(c.isdigit() for c in t):
            out.add(t)
        else:
            out.update(t[i:i + 2] for i in range(len(t) - 1))
    return out


def load_policy_sections(policy_dir: str) -> List[Dict[str, Any]]:
    """Split every *.md file into "## " sections -> {title, body, url, grams}."""
    sections: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(policy_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        doc_title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")),
                         os.path.basename(path))
        for chunk in re.split(r"^## ", text, flags=re.M)[1:]:
            heading, _, body = chunk.partition("\n")
            heading, body = heading.strip(), body.strip()
            if not body:
                continue
            title = f"{doc_title} - {heading}"
            sections.append({
                "title": title,
                "body": body,
                "url": (f"{POLICY_BASE_URL.rstrip('/')}/{os.path.basename(path)}"
                        if POLICY_BASE_URL else None),
                "title_grams": _grams(heading),
                "grams": _grams(heading + " " + body),
            })
    return sections


POLICY_SECTIONS = load_policy_sections(POLICY_DIR)
if POLICY_SECTIONS:
    logger.info("Loaded %d policy sections from %s", len(POLICY_SECTIONS), POLICY_DIR)
else:
    logger.warning("No policy sections found in %s (searches will return no results)", POLICY_DIR)


def run_search(query: str, metadata: Optional[Dict[str, Any]],
               filter_: Optional[str] = None) -> SearchResponse:
    """Score each policy section by how many of the query's character bigrams it
    contains (a match in the section heading counts double, a token with digits such
    as "3000만" counts double), drop sections below
    SEARCH_MIN_SCORE and return the top SEARCH_TOP_K."""
    q = _grams(query)
    if not q:
        return SearchResponse(search_results=[])
    weight = {g: (2 if any(c.isdigit() for c in g) else 1) for g in q}  # amounts, days
    total = sum(weight.values())
    scored = []
    for s in POLICY_SECTIONS:
        hit = sum(w for g, w in weight.items() if g in s["grams"])
        hit += sum(w for g, w in weight.items() if g in s["title_grams"])
        score = round(hit / total, 3)
        if score >= SEARCH_MIN_SCORE:
            scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [
        SearchResult(title=s["title"], body=s["body"], url=s["url"],
                     result_metadata={"score": score})
        for score, s in scored[:SEARCH_TOP_K]
    ]
    logger.info("[SEARCH] query=%r -> %s", query,
                [(r.title, r.result_metadata["score"]) for r in results] or "no results")
    return SearchResponse(search_results=results)


# Connection check: watsonx Orchestrate sends "HEAD /" (with credentials) when a
# connection is saved. Answer 200 when auth passes, 401 otherwise.
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False,
               dependencies=[Depends(verify_auth)])
@app.api_route("/query", methods=["GET", "HEAD"], include_in_schema=False,
               dependencies=[Depends(verify_auth)])
async def connection_check() -> Dict[str, str]:
    return {"status": "ok"}


# "/" : Server URL registered without a path (e.g. http://host:3464)
# "/query" : Server URL registered as http://host:3464/query
@app.post("/", response_model=SearchResponse, response_model_exclude_none=True,
          dependencies=[Depends(verify_auth)], include_in_schema=False)
@app.post(
    "/query",
    response_model=SearchResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(verify_auth)],
)
async def answer(request: SearchRequest) -> SearchResponse:
    logger.info(request.model_dump())
    return run_search(request.query, request.metadata, request.filter)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("CUSTOM_SERVICE_HOST", "0.0.0.0")
    try:
        port = int(os.getenv("CUSTOM_SERVICE_PORT", "8000"))
    except ValueError:
        raise SystemExit(f"CUSTOM_SERVICE_PORT must be an integer, got: {os.getenv('CUSTOM_SERVICE_PORT')!r}")
    logger.info("Starting server on %s:%d", host, port)
    # Behind nginx: trust X-Forwarded-For / X-Forwarded-Proto from these proxy IPs,
    # so logs show the real client IP (e.g. watsonx Orchestrate) instead of 127.0.0.1.
    forwarded_ips = os.getenv("CUSTOM_SERVICE_TRUSTED_PROXIES", "127.0.0.1")
    # log_config=None -> uvicorn logs go through the same console + file handlers
    uvicorn.run(app, host=host, port=port, log_config=None,
                proxy_headers=True, forwarded_allow_ips=forwarded_ips)

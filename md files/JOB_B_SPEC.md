# JOB B SPECIFICATION — Browser Authentication & Login Flow
**Consumed by:** JOB_B_PROMPT.txt agent team  
**Touches:** auth/ui_dependencies.py (new) · ui/router.py · extra_router.py · login.html · base.html

---

## BACKGROUND — WHY THIS JOB EXISTS

Job A protected all API endpoints with JWT via the `Authorization` header or cookie.  
But the HTML pages themselves (served by `app/ui/router.py`) have no protection at all.

Right now:
- Anyone can visit `/home`, `/documents-ui`, `/compliance-center` etc. with no login
- The login page has no `POST /login` handler — it calls `fetch('/auth/login')` via JavaScript which sets nothing in the browser cookie store
- There is no `GET /logout` that clears the cookie
- Error messages use `window.alert()` which is ugly and unprofessional
- The sidebar footer shows hardcoded "User Name" instead of the real logged-in user

---

## TASK 1 — Create `app/modules/auth/ui_dependencies.py`

This file handles auth for browser (HTML) routes. Unlike the API dependency which returns HTTP 401 JSON, this one returns an HTTP 302 redirect to the login page.

Create the file:

```python
"""
app/modules/auth/ui_dependencies.py
=====================================
Auth dependency for Jinja2 HTML page routes.

Returns a redirect to /login when the session is missing or invalid.
This is DIFFERENT from the API dependency (dependencies.py) which returns 401 JSON.

Usage in any UI route:
    from app.modules.auth.ui_dependencies import require_ui_login
    from fastapi.responses import RedirectResponse

    @router.get("/some-page")
    def some_page(
        request: Request,
        current_user=Depends(require_ui_login),
    ):
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse(
            "page.html",
            {"request": request, "user": current_user},
        )
"""
from __future__ import annotations

import logging

from fastapi import Cookie, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.service import decode_access_token
from app.modules.users.model import User

logger = logging.getLogger(__name__)


def require_ui_login(
    request: Request,
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | RedirectResponse:
    """
    Check the session cookie for browser page requests.

    Returns:
        User object if the session is valid.
        RedirectResponse to /login if the session is missing or invalid.

    The redirect includes ?next=<original path> so after login the user
    returns to where they were trying to go.
    """
    if not access_token:
        return RedirectResponse(
            url=f"/login?next={request.url.path}",
            status_code=302,
        )

    payload = decode_access_token(access_token)
    if payload is None:
        # Expired or tampered token — clear cookie and redirect
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    user: User | None = db.get(User, user_id)
    if user is None or not user.is_active:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    return user
```

---

## TASK 2 — Add login POST + logout routes to `app/ui/router.py`

### 2a — Update GET /login to accept the `next` parameter:

Find the existing `/login` GET handler and update it to pass `next_url` to the template:

```python
@router.get("/login")
def login_page(request: Request, next: str = "/home"):
    """Render login page. `next` tells us where to redirect after successful login."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "next_url": next},
    )
```

### 2b — Add POST /login handler:

Add these imports at the top of `app/ui/router.py` if not already present:
```python
from fastapi import Form
from fastapi.responses import RedirectResponse
from app.modules.auth import service as auth_service
from app.core.db import SessionLocal
```

Then add this route function:

```python
@router.post("/login")
def login_submit(
    request: Request,
    staff_id: str = Form(...),
    password: str = Form(...),
    next_url: str = Form(default="/home"),
):
    """
    Process login form submission.
    On success: set HttpOnly session cookie, redirect to next_url.
    On failure: re-render login page with error message (no window.alert).
    """
    db = SessionLocal()
    try:
        user = auth_service.authenticate_user(db, staff_id, password)
    finally:
        db.close()

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next_url": next_url,
                "error": "Invalid Staff ID or password. Please try again.",
            },
            status_code=401,
        )

    token = auth_service.create_access_token(user)

    # Validate redirect target to prevent open redirect attacks
    safe_next = next_url if (next_url and next_url.startswith("/")) else "/home"
    # Exclude the login page itself to prevent a loop
    if safe_next in ("/login", "/register"):
        safe_next = "/home"

    response = RedirectResponse(url=safe_next, status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,       # JS cannot read this cookie (XSS protection)
        samesite="lax",      # Protects against most CSRF attacks
        secure=False,        # Set True in production (requires HTTPS)
        max_age=3600,        # 1 hour — matches ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return response
```

### 2c — Add/update GET /logout handler:

```python
@router.get("/logout")
def logout(request: Request):
    """Clear the session cookie and return the user to the login page."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response
```

---

## TASK 3 — Protect all UI page routes in both router files

### Import to add at the top of both `app/ui/router.py` and `app/ui/extra_router.py`:

```python
from fastapi import Depends
from fastapi.responses import RedirectResponse
from app.modules.auth.ui_dependencies import require_ui_login
```

### Pattern to apply to EVERY page-rendering route (routes that call `templates.TemplateResponse`):

```python
# BEFORE:
@router.get("/home")
def home_page(request: Request):
    ...data fetching...
    return templates.TemplateResponse("index.html", {"request": request, ...})

# AFTER:
@router.get("/home")
def home_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    ...data fetching...
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user": current_user, ...}
    )
```

**Apply this to ALL page routes in:**
- `app/ui/router.py` — every GET route that renders a template
- `app/ui/extra_router.py` — every GET route that renders a template

**SKIP these routes (must stay public):**
- `GET /login`
- `POST /login`
- `GET /register`
- `GET /logout`
- `GET /health`

**Important:** After applying, every `templates.TemplateResponse(...)` call must include `"user": current_user` in its context dict. This lets `base.html` display the user's name and role in the sidebar footer.

---

## TASK 4 — Update `app/ui/templates/login.html`

The login page currently uses JavaScript `fetch()` to call the API. Replace the login interaction with a standard HTML form POST.

**Find the existing login form and replace it with:**

```html
<!-- Error banner — only visible when login fails -->
{% if error %}
<div class="mb-4 px-4 py-3 rounded-lg flex items-center gap-2"
     style="background:rgba(255,77,77,0.12);border:1px solid var(--cerr);color:var(--cerr)">
  <span class="material-symbols-outlined text-[18px] flex-shrink-0">error_outline</span>
  <span class="text-sm font-medium">{{ error }}</span>
</div>
{% endif %}

<!-- Login form — standard HTML POST, no JavaScript required -->
<form method="POST" action="/login" class="space-y-4">
  <!-- Preserves redirect destination after login -->
  <input type="hidden" name="next_url" value="{{ next_url | default('/home') }}">

  <!-- Staff ID -->
  <div>
    <label class="block text-xs font-semibold uppercase tracking-wider mb-1.5"
           style="color:var(--cosv)">
      Staff ID
    </label>
    <input
      type="text"
      name="staff_id"
      required
      autocomplete="username"
      placeholder="Enter your Staff ID"
      class="w-full px-3 py-2.5 rounded-lg text-sm border transition-colors"
      style="background:var(--csf);border-color:var(--col);color:var(--cos)"
    >
  </div>

  <!-- Password -->
  <div>
    <label class="block text-xs font-semibold uppercase tracking-wider mb-1.5"
           style="color:var(--cosv)">
      Password
    </label>
    <input
      type="password"
      name="password"
      required
      autocomplete="current-password"
      placeholder="Enter your password"
      class="w-full px-3 py-2.5 rounded-lg text-sm border transition-colors"
      style="background:var(--csf);border-color:var(--col);color:var(--cos)"
    >
  </div>

  <!-- Submit -->
  <button
    type="submit"
    class="w-full py-2.5 rounded-lg text-sm font-semibold transition-all hover:opacity-90 active:scale-[0.98]"
    style="background:var(--cp);color:var(--cop)"
  >
    Sign In
  </button>
</form>
```

**Also remove** any existing `<script>` block in `login.html` that does:
- `fetch('/auth/login', ...)`
- `document.getElementById('login-form').addEventListener('submit', ...)`
- Any `window.alert()` or `alert()` call related to login errors

---

## TASK 5 — Update sidebar user display in `app/ui/templates/base.html`

Find the sidebar footer section (around line 384+) that shows the user avatar and name.  
Currently it shows hardcoded text. Replace it to use the `user` object from template context:

```html
<!-- Sidebar footer — logged-in user display -->
<div class="flex items-center gap-3 min-w-0 flex-1">
  <!-- Avatar — first letter of full name -->
  <div
    class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold"
    style="background:var(--cp);color:var(--cop)"
  >
    {% if user %}{{ (user.full_name or user.staff_id or 'U')[0] | upper }}{% else %}?{% endif %}
  </div>
  <!-- Name and role -->
  <div class="min-w-0 flex-1">
    <p class="text-sm font-medium truncate" style="color:var(--cos)">
      {% if user %}{{ user.full_name or user.staff_id }}{% else %}Guest{% endif %}
    </p>
    <p class="text-xs truncate capitalize" style="color:var(--cosv)">
      {% if user %}{{ user.role }}{% else %}—{% endif %}
    </p>
  </div>
</div>
```

---

## VERIFICATION STEPS
**All must pass before this job is considered complete.**

```bash
# Start the app
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
sleep 4

# V1 — Unauthenticated /home redirects to /login (302, not 200 or 401)
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/home)
[ "$CODE" = "302" ] && echo "PASS: /home redirects" || echo "FAIL: got $CODE"

# V2 — Login page is still public (returns 200)
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/login)
[ "$CODE" = "200" ] && echo "PASS: /login is public" || echo "FAIL: got $CODE"

# V3 — Wrong credentials returns 401 and re-renders login (not a redirect)
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://127.0.0.1:8000/login \
  -d "staff_id=wrong&password=wrong&next_url=/home")
[ "$CODE" = "401" ] && echo "PASS: wrong creds returns 401" || echo "FAIL: got $CODE"

# V4 — Correct credentials set cookie and redirect to /home
# (Create test user first if needed: POST /auth/register)
curl -s -c /tmp/test_cookies.txt -o /tmp/login_response.txt -w "%{http_code}" \
  -X POST http://127.0.0.1:8000/login \
  -d "staff_id=admin&password=admin123&next_url=/home"
grep -q "access_token" /tmp/test_cookies.txt && echo "PASS: cookie set" || echo "FAIL: no cookie"

# V5 — Authenticated visit to /home returns 200
CODE=$(curl -s -b /tmp/test_cookies.txt -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/home)
[ "$CODE" = "200" ] && echo "PASS: /home loads with cookie" || echo "FAIL: got $CODE"

# V6 — Logout clears cookie (response should delete access_token)
curl -s -b /tmp/test_cookies.txt -c /tmp/after_logout.txt \
  -o /dev/null http://127.0.0.1:8000/logout
# After logout, /home should redirect again
CODE=$(curl -s -b /tmp/after_logout.txt -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/home)
[ "$CODE" = "302" ] && echo "PASS: /home redirects after logout" || echo "FAIL: got $CODE"

# V7 — No window.alert() in login.html
grep -n "window\.alert\|alert(" app/ui/templates/login.html \
  && echo "FAIL: alert() still in login.html" || echo "PASS: no alert in login.html"

# V8 — No JavaScript fetch to /auth/login in login.html
grep -n "fetch.*auth/login\|auth/login.*fetch" app/ui/templates/login.html \
  && echo "FAIL: JS fetch still in login.html" || echo "PASS: no fetch in login.html"

pkill -f "uvicorn app.main" 2>/dev/null || true
```

**Expected:** All 8 checks print PASS.

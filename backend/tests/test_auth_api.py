from __future__ import annotations

import types
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Response
from jose import jwt
from starlette.requests import Request

from app.api import auth as auth_api
from app.api import deps as deps_api
from app.config import settings
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    UserLogin,
    UserSignUp,
)


class FakeResult:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class FakeDB:
    def __init__(self, results=None):
        self._results = list(results or [])
        self.added = []
        self.committed = False

    async def execute(self, *_args, **_kwargs):
        if not self._results:
            return FakeResult(None)
        return self._results.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1


def _make_request(cookies: dict[str, str] | None = None) -> Request:
    headers = []
    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())
        headers.append((b"cookie", cookie_header.encode()))
    return Request(
        {
            "type": "http",
            "client": ("127.0.0.1", 12345),
            "headers": headers,
            "method": "POST",
            "path": "/api/v1/auth/refresh",
        }
    )


def _set_cookie_headers(response: Response) -> list[str]:
    return [
        value.decode()
        for key, value in response.raw_headers
        if key == b"set-cookie"
    ]


def _make_user(**kwargs):
    defaults = dict(
        id=1,
        email="tester@example.com",
        hashed_password=auth_api.get_password_hash("secret"),
        full_name="Test User",
        is_active=True,
    )
    defaults.update(kwargs)
    return User(**defaults)


@pytest.mark.anyio
async def test_signup_creates_user_and_returns_tokens():
    db = FakeDB(results=[FakeResult(None)])
    payload = UserSignUp(
        email="new@example.com", password="secret123", full_name="New User"
    )

    http_response = Response()
    response = await auth_api.signup(payload, http_response, db=db)

    assert response.access_token
    assert response.refresh_token
    assert response.user_id == 1
    assert db.added
    assert db.committed is True
    cookies = _set_cookie_headers(http_response)
    assert any(
        cookie.startswith(f"{auth_api.PATIENT_REFRESH_COOKIE}=")
        and "HttpOnly" in cookie
        for cookie in cookies
    )


@pytest.mark.anyio
async def test_login_rejects_invalid_password():
    user = _make_user()
    db = FakeDB(results=[FakeResult(user)])
    payload = UserLogin(email=user.email, password="wrong")

    with pytest.raises(HTTPException) as exc:
        await auth_api.login(payload, Response(), db=db)

    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_refresh_blacklists_used_token(monkeypatch):
    user = _make_user()
    db = FakeDB(results=[FakeResult(user), FakeResult(user)])
    token = auth_api.create_refresh_token(data={"sub": str(user.id)})

    monkeypatch.setattr(auth_api, "_token_blacklist", set())

    response = await auth_api.refresh_access_token(
        RefreshTokenRequest(refresh_token=token), _make_request(), Response(), db=db
    )
    assert response.access_token
    assert response.refresh_token

    with pytest.raises(HTTPException) as exc:
        await auth_api.refresh_access_token(
            RefreshTokenRequest(refresh_token=token), _make_request(), Response(), db=db
        )

    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_refresh_accepts_cookie_and_keeps_token_out_of_body(monkeypatch):
    user = _make_user()
    db = FakeDB(results=[FakeResult(None), FakeResult(user)])
    token = auth_api.create_refresh_token(data={"sub": str(user.id)})

    monkeypatch.setattr(auth_api, "_token_blacklist", set())

    http_response = Response()
    response = await auth_api.refresh_access_token(
        RefreshTokenRequest(),
        _make_request(cookies={auth_api.PATIENT_REFRESH_COOKIE: token}),
        http_response,
        db=db,
    )

    assert response.access_token
    assert response.refresh_token is None
    cookies = _set_cookie_headers(http_response)
    assert any(
        cookie.startswith(f"{auth_api.PATIENT_REFRESH_COOKIE}=")
        and "HttpOnly" in cookie
        for cookie in cookies
    )


@pytest.mark.anyio
async def test_refresh_rejects_missing_token_and_cookie():
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await auth_api.refresh_access_token(
            RefreshTokenRequest(), _make_request(), Response(), db=db
        )

    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_logout_blacklists_token_with_jti(monkeypatch):
    monkeypatch.setattr(auth_api, "_token_blacklist", set())
    token = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "jti": "logout-token",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    credentials = types.SimpleNamespace(credentials=token)
    db = FakeDB()
    await auth_api.logout(
        credentials=credentials,
        request=_make_request(),
        response=Response(),
        db=db,
    )

    assert "logout-token" in auth_api._token_blacklist


def test_cookie_refresh_flow_over_http(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.database import get_db

    monkeypatch.setattr(auth_api, "_token_blacklist", set())
    monkeypatch.setattr(deps_api, "_auth_rate_limit", {})

    user = _make_user()
    # Ordered results for: login (user select), refresh (blacklist check,
    # user select, blacklist insert check), then logout (two blacklist checks).
    db = FakeDB(
        results=[
            FakeResult(user),
            FakeResult(None),
            FakeResult(user),
            FakeResult(None),
            FakeResult(None),
            FakeResult(None),
        ]
    )

    app = FastAPI()
    app.include_router(auth_api.router, prefix=settings.api_prefix)

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    login_res = client.post(
        f"{settings.api_prefix}/auth/login",
        json={"email": user.email, "password": "secret"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["refresh_token"]
    assert client.cookies.get(auth_api.PATIENT_REFRESH_COOKIE)
    set_cookie = login_res.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie

    cookie_before_refresh = client.cookies.get(auth_api.PATIENT_REFRESH_COOKIE)
    refresh_res = client.post(f"{settings.api_prefix}/auth/refresh", json={})
    assert refresh_res.status_code == 200
    body = refresh_res.json()
    assert body["access_token"]
    assert "refresh_token" not in body
    assert client.cookies.get(auth_api.PATIENT_REFRESH_COOKIE) != cookie_before_refresh

    logout_res = client.post(
        f"{settings.api_prefix}/auth/logout",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert logout_res.status_code == 200
    assert not client.cookies.get(auth_api.PATIENT_REFRESH_COOKIE)


@pytest.mark.anyio
async def test_forgot_password_sets_reset_fields_and_sends_email(monkeypatch):
    user = _make_user(reset_token_hash=None, reset_token_expires_at=None)
    db = FakeDB(results=[FakeResult(user)])

    sent = {}

    def _fake_send_email(to, subject, body):
        sent["to"] = to
        sent["subject"] = subject
        sent["body"] = body

    monkeypatch.setattr(auth_api, "send_email", _fake_send_email)
    monkeypatch.setattr(
        auth_api.secrets, "token_urlsafe", lambda *_args, **_kwargs: "fixed-token"
    )

    await auth_api.forgot_password(ForgotPasswordRequest(email=user.email), db=db)

    assert user.reset_token_hash == auth_api._hash_reset_token("fixed-token")
    assert user.reset_token_expires_at is not None
    assert sent["to"] == [user.email]


@pytest.mark.anyio
async def test_reset_password_rejects_invalid_token():
    db = FakeDB(results=[FakeResult(None)])

    with pytest.raises(HTTPException) as exc:
        await auth_api.reset_password(
            ResetPasswordRequest(token="bad-token", new_password="newsecret"),
            db=db,
        )

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_reset_password_updates_hash_and_clears_token():
    user = _make_user(
        reset_token_hash=auth_api._hash_reset_token("reset-token"),
        reset_token_expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db = FakeDB(results=[FakeResult(user)])

    await auth_api.reset_password(
        ResetPasswordRequest(token="reset-token", new_password="newsecret"),
        db=db,
    )

    assert user.reset_token_hash is None
    assert user.reset_token_expires_at is None
    assert auth_api.verify_password("newsecret", user.hashed_password)


@pytest.mark.anyio
async def test_rate_limit_auth_exceeds_limit(monkeypatch):
    monkeypatch.setattr(deps_api, "_auth_rate_limit", {})
    window = settings.auth_rate_limit_window_seconds
    max_requests = settings.auth_rate_limit_max_requests
    request = Request(
        {
            "type": "http",
            "client": ("127.0.0.1", 12345),
            "headers": [],
            "method": "POST",
            "path": "/api/v1/auth/login",
        }
    )

    for _ in range(max_requests):
        await deps_api.rate_limit_auth(request)

    with pytest.raises(HTTPException) as exc:
        await deps_api.rate_limit_auth(request)

    assert exc.value.status_code == 429
    assert window > 0

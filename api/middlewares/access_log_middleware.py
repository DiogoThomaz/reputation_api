from __future__ import annotations

import json
import logging
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger(__name__)


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = time.perf_counter()
        status_code: int | None = None
        body_chunks: list[bytes] = []

        async def receive_with_body_capture() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    body_chunks.append(body)
            return message

        async def send_with_status_capture(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive_with_body_capture, send_with_status_capture)
        except Exception:
            status_code = status_code or 500
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self._save_access_log(
                scope=scope,
                body=b"".join(body_chunks),
                status_code=status_code,
                elapsed_ms=elapsed_ms,
            )

    def _save_access_log(
        self,
        *,
        scope: Scope,
        body: bytes,
        status_code: int | None,
        elapsed_ms: float,
    ) -> None:
        try:
            db = scope["app"].state.db
            db.execute(
                query=(
                    "INSERT INTO logs_acesso "
                    "(ip, user_agent, metodo, rota, payload, status_http, tempo_resposta_ms) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)"
                ),
                params=(
                    self._client_ip(scope),
                    self._header(scope, b"user-agent"),
                    scope["method"],
                    scope["path"],
                    self._json_payload(body),
                    status_code,
                    elapsed_ms,
                ),
            )
        except Exception:
            logger.exception("Falha ao salvar log de acesso")

    @staticmethod
    def _header(scope: Scope, name: bytes) -> str | None:
        for header_name, value in scope.get("headers", []):
            if header_name.lower() == name:
                return value.decode("latin-1")
        return None

    @classmethod
    def _client_ip(cls, scope: Scope) -> str:
        forwarded_for = cls._header(scope, b"x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()

        real_ip = cls._header(scope, b"x-real-ip")
        if real_ip:
            return real_ip.strip()

        client: Any = scope.get("client")
        if client:
            return str(client[0])

        return "0.0.0.0"

    @staticmethod
    def _json_payload(body: bytes) -> str | None:
        if not body:
            return None

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        return json.dumps(payload, ensure_ascii=True)

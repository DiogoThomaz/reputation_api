from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import request


@dataclass(slots=True)
class HookClient:
    """Cliente HTTP simples para envio de lotes para uma rota externa."""

    endpoint: str
    timeout: int = 15

    def post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Executa POST em JSON e retorna status/body da resposta."""
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:  # nosec B310
            response_body = response.read().decode("utf-8")
            return {
                "status_code": response.status,
                "body": response_body,
            }

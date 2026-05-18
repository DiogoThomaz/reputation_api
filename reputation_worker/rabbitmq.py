from __future__ import annotations

import json
import logging
import os
import socket
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from reputation_worker.hook import HookClient
from reputation_worker.hook_local import HookClientLocal
from reputation_worker.scrapers.factory import ScraperFactory
from reputation_worker.worker import ScraperWorker


logger = logging.getLogger(__name__)

_PLACEHOLDER_HOOK_HOSTS = {
    "seu-endpoint.com",
    "www.seu-endpoint.com",
    "hook.exemplo.com",
    "example.com",
    "www.example.com",
}


def _load_env_file(env_path: str = ".env") -> None:
    """Carrega variaveis simples de um arquivo .env sem dependencias externas."""
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _import_pika():
    """Import tardio para nao quebrar testes sem dependencia instalada."""
    import pika  # type: ignore

    return pika


@dataclass(slots=True)
class RabbitMQSettings:
    host: str
    username: str
    password: str
    queue: str
    port: int = 5672
    vhost: str = "/"
    url: str | None = None
    use_tls: bool = False
    chunk_yield: int = 5
    prefetch_count: int = 1
    use_local_hook: bool = False
    local_hook_file: str = "resultado_rabbitmq.xlsx"
    local_hook_sheet: str = "reclamacoes"

    @classmethod
    def from_env(cls, env_path: str = ".env") -> "RabbitMQSettings":
        _load_env_file(env_path)

        host = os.getenv("RABBITMQ_HOST", "").strip()
        username = os.getenv("RABBITMQ_USERNAME", "").strip()
        password = os.getenv("RABBITMQ_PASSWORD", "").strip()
        queue = os.getenv("RABBITMQ_QUEUE", "").strip()

        missing = [
            key
            for key, value in {
                "RABBITMQ_HOST": host,
                "RABBITMQ_USERNAME": username,
                "RABBITMQ_PASSWORD": password,
                "RABBITMQ_QUEUE": queue,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Variaveis ausentes no .env: {joined}")

        port = int(os.getenv("RABBITMQ_PORT", "5672"))
        vhost = os.getenv("RABBITMQ_VHOST", "/").strip() or "/"
        url = os.getenv("RABBITMQ_URL", "").strip() or None
        use_tls = os.getenv("RABBITMQ_USE_TLS", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        chunk_yield = int(os.getenv("WORKER_CHUNK_YIELD", "5"))
        prefetch_count = int(os.getenv("RABBITMQ_PREFETCH_COUNT", "1"))
        use_local_hook = os.getenv("WORKER_USE_LOCAL_HOOK", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        local_hook_file = os.getenv("LOCAL_HOOK_FILE", "resultado_rabbitmq.xlsx").strip()
        local_hook_sheet = os.getenv("LOCAL_HOOK_SHEET", "reclamacoes").strip() or "reclamacoes"

        return cls(
            host=host,
            username=username,
            password=password,
            queue=queue,
            port=port,
            vhost=vhost,
            url=url,
            use_tls=use_tls,
            chunk_yield=chunk_yield,
            prefetch_count=prefetch_count,
            use_local_hook=use_local_hook,
            local_hook_file=local_hook_file,
            local_hook_sheet=local_hook_sheet,
        )


class RabbitMQConnection:
    """Factory de conexao RabbitMQ."""

    def __init__(self, settings: RabbitMQSettings):
        self.settings = settings

    def create(self):
        pika = _import_pika()

        if self.settings.url:
            params = pika.URLParameters(self.settings.url)
        else:
            credentials = pika.PlainCredentials(
                self.settings.username,
                self.settings.password,
            )
            ssl_options = None
            if self.settings.use_tls:
                ssl_options = pika.SSLOptions(ssl.create_default_context())

            params = pika.ConnectionParameters(
                host=self.settings.host,
                port=self.settings.port,
                virtual_host=self.settings.vhost,
                credentials=credentials,
                ssl_options=ssl_options,
                heartbeat=30,
                blocked_connection_timeout=30,
            )

        return pika.BlockingConnection(params)


class RabbitMQJobConsumer:
    """Consumer de jobs que dispara scraping e envio para hook HTTP."""

    def __init__(self, settings: RabbitMQSettings, connection_factory: RabbitMQConnection):
        self.settings = settings
        self.connection_factory = connection_factory

    @staticmethod
    def _validate_hook_url(hook_url: str) -> None:
        parsed = urlparse(hook_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Campo 'hook_url' invalido")

        host = (parsed.hostname or "").strip().lower()
        if host in _PLACEHOLDER_HOOK_HOSTS:
            raise ValueError(
                "Campo 'hook_url' aponta para host placeholder; informe um endpoint real"
            )

        try:
            socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise ValueError(f"Host do hook nao resolvido: {host}") from exc

    @staticmethod
    def _validate_job(job: dict[str, Any], require_hook_url: bool = True) -> tuple[str, str, str]:
        source = str(job.get("source") or "").strip()
        name = str(job.get("name") or "").strip()
        hook_url = str(job.get("hook_url") or "").strip()

        if source not in {"playstore", "reclame_aqui"}:
            raise ValueError("Campo 'source' invalido")
        if not name:
            raise ValueError("Campo 'name' e obrigatorio")

        if require_hook_url:
            RabbitMQJobConsumer._validate_hook_url(hook_url)

        return source, name, hook_url

    @staticmethod
    def _build_callback(hook_client: Any):
        def callback(records: list[dict[str, Any]]) -> None:
            hook_client.post({"records": records})

        return callback

    @staticmethod
    def _supports_context_manager(scraper: Any) -> bool:
        return hasattr(scraper, "__enter__") and hasattr(scraper, "__exit__")

    def process_job_payload(self, payload: dict[str, Any]) -> int:
        source, name, hook_url = self._validate_job(
            payload,
            require_hook_url=not self.settings.use_local_hook,
        )
        logger.info(
            "Iniciando processamento do job | source=%s name=%s hook_url=%s",
            source,
            name,
            hook_url,
        )

        if self.settings.use_local_hook:
            logger.info(
                "Modo HookLocal habilitado | arquivo=%s aba=%s",
                self.settings.local_hook_file,
                self.settings.local_hook_sheet,
            )
            callback = self._build_callback(
                HookClientLocal(
                    file_path=self.settings.local_hook_file,
                    sheet_name=self.settings.local_hook_sheet,
                )
            )
        else:
            callback = self._build_callback(HookClient(endpoint=hook_url))

        scraper = ScraperFactory.create(source)
        worker = ScraperWorker(
            source=source,
            chunk_yield=self.settings.chunk_yield,
            callback=callback,
            scraper=scraper,
        )

        if self._supports_context_manager(scraper):
            logger.info("Abrindo context manager do scraper | source=%s", source)
            with scraper:
                total = worker.run(name)
        else:
            total = worker.run(name)

        logger.info(
            "Processamento concluido | source=%s name=%s total_registros=%s",
            source,
            name,
            total,
        )
        return total

    def _on_message(self, channel, method, properties, body: bytes) -> None:
        del properties
        logger.info(
            "Mensagem recebida | delivery_tag=%s bytes=%s",
            method.delivery_tag,
            len(body),
        )
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Payload deve ser um objeto JSON")
            self.process_job_payload(payload)
        except Exception as exc:
            logger.exception(
                "Falha ao processar mensagem | delivery_tag=%s erro=%s",
                method.delivery_tag,
                exc,
            )
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        logger.info("Mensagem processada com sucesso | delivery_tag=%s", method.delivery_tag)
        channel.basic_ack(delivery_tag=method.delivery_tag)

    def start(self) -> None:
        pika = _import_pika()
        connection = self.connection_factory.create()
        channel = connection.channel()
        logger.info(
            "Conectado ao RabbitMQ | host=%s port=%s vhost=%s fila=%s",
            self.settings.host,
            self.settings.port,
            self.settings.vhost,
            self.settings.queue,
        )

        try:
            # Checa se a fila ja existe no broker sem tentar alterar argumentos.
            channel.queue_declare(queue=self.settings.queue, passive=True)
        except Exception as exc:
            # Em declare passivo, 404 indica que a fila nao existe e precisa ser criada.
            is_not_found = isinstance(exc, pika.exceptions.ChannelClosedByBroker) and (
                getattr(exc, "reply_code", None) == 404
            )

            # Em erros de canal, e preciso abrir um novo canal antes de seguir.
            channel = connection.channel()

            if is_not_found:
                channel.queue_declare(queue=self.settings.queue, durable=True)
                logger.info("Fila criada | fila=%s", self.settings.queue)
            else:
                raise

        channel.basic_qos(prefetch_count=self.settings.prefetch_count)
        channel.basic_consume(
            queue=self.settings.queue,
            on_message_callback=self._on_message,
            auto_ack=False,
        )

        try:
            logger.info("Consumer iniciado | fila=%s", self.settings.queue)
            channel.start_consuming()
        finally:
            if connection.is_open:
                connection.close()
                logger.info("Conexao RabbitMQ encerrada")

"""Entrypoint do consumer RabbitMQ para processar jobs de scraping."""

from __future__ import annotations

import logging

from reputation_worker.rabbitmq import (
    RabbitMQConnection,
    RabbitMQJobConsumer,
    RabbitMQSettings,
)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    settings = RabbitMQSettings.from_env(".env")
    connection_factory = RabbitMQConnection(settings)
    consumer = RabbitMQJobConsumer(settings=settings, connection_factory=connection_factory)

    print(
        "Consumindo fila "
        f"'{settings.queue}' em {settings.host}:{settings.port} (vhost={settings.vhost})"
    )
    consumer.start()


if __name__ == "__main__":
    main()

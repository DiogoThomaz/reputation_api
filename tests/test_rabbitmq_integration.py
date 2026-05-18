import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from reputation_worker.rabbitmq import (
    RabbitMQConnection,
    RabbitMQJobConsumer,
    RabbitMQSettings,
)


class TestRabbitMQSettings(unittest.TestCase):
    def test_loads_required_values_from_env_file(self):
        env_content = "\n".join(
            [
                "RABBITMQ_HOST=jackal.rmq.cloudamqp.com",
                "RABBITMQ_USERNAME=ltbyvyqq",
                "RABBITMQ_PASSWORD=secret",
                "RABBITMQ_QUEUE=scrape_data",
                "RABBITMQ_PORT=5672",
                "RABBITMQ_VHOST=ltbyvyqq",
            ]
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(env_content, encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                settings = RabbitMQSettings.from_env(str(env_path))

        self.assertEqual(settings.host, "jackal.rmq.cloudamqp.com")
        self.assertEqual(settings.username, "ltbyvyqq")
        self.assertEqual(settings.password, "secret")
        self.assertEqual(settings.queue, "scrape_data")
        self.assertEqual(settings.port, 5672)
        self.assertEqual(settings.vhost, "ltbyvyqq")


class TestRabbitMQConsumer(unittest.TestCase):
    def setUp(self):
        settings = RabbitMQSettings(
            host="h",
            username="u",
            password="p",
            queue="scrape_data",
            chunk_yield=2,
        )
        self.consumer = RabbitMQJobConsumer(
            settings=settings,
            connection_factory=RabbitMQConnection(settings),
        )

    @patch("reputation_worker.rabbitmq.ScraperWorker")
    @patch("reputation_worker.rabbitmq.ScraperFactory.create")
    @patch("reputation_worker.rabbitmq.HookClient")
    @patch("reputation_worker.rabbitmq.socket.getaddrinfo")
    def test_process_job_calls_worker_and_hook(self, _mock_dns, hook_cls, factory_create, worker_cls):
        scraper = MagicMock()
        scraper.__enter__.return_value = scraper
        scraper.__exit__.return_value = None
        factory_create.return_value = scraper

        worker_instance = MagicMock()
        worker_instance.run.side_effect = lambda _: worker_instance.callback(
            [{"id": "1"}, {"id": "2"}]
        )
        worker_cls.return_value = worker_instance

        payload = {
            "source": "reclame_aqui",
            "name": "cna-ingles-e-espanhol",
            "hook_url": "https://webhook.site/abcdef",
        }

        self.consumer.process_job_payload(payload)

        worker_cls.assert_called_once()
        _, kwargs = worker_cls.call_args
        self.assertEqual(kwargs["source"], "reclame_aqui")
        self.assertEqual(kwargs["chunk_yield"], 2)
        self.assertIs(kwargs["scraper"], scraper)

        callback = kwargs["callback"]
        worker_instance.callback = callback
        worker_instance.run("cna-ingles-e-espanhol")

        hook_cls.assert_called_once_with(endpoint="https://webhook.site/abcdef")
        hook_cls.return_value.post.assert_called_once_with(
            {"records": [{"id": "1"}, {"id": "2"}]}
        )

    def test_process_job_rejects_placeholder_hook_url(self):
        payload = {
            "source": "playstore",
            "name": "nubank",
            "hook_url": "https://seu-endpoint.com/hook",
        }

        with self.assertRaises(ValueError):
            self.consumer.process_job_payload(payload)

    @patch("reputation_worker.rabbitmq.socket.getaddrinfo", side_effect=socket.gaierror)
    def test_process_job_rejects_unresolved_hook_host(self, _mock_dns):
        payload = {
            "source": "playstore",
            "name": "nubank",
            "hook_url": "https://host-que-nao-resolve.invalid/hook",
        }

        with self.assertRaises(ValueError):
            self.consumer.process_job_payload(payload)

    @patch("reputation_worker.rabbitmq.ScraperWorker")
    @patch("reputation_worker.rabbitmq.ScraperFactory.create")
    @patch("reputation_worker.rabbitmq.HookClientLocal")
    def test_process_job_uses_local_hook_when_enabled(self, local_hook_cls, factory_create, worker_cls):
        self.consumer.settings.use_local_hook = True
        self.consumer.settings.local_hook_file = "resultado_rabbitmq.xlsx"
        self.consumer.settings.local_hook_sheet = "reclamacoes"

        scraper = object()
        factory_create.return_value = scraper

        worker_instance = MagicMock()
        worker_instance.run.side_effect = lambda _: worker_instance.callback([{"id": "10"}])
        worker_cls.return_value = worker_instance

        payload = {
            "source": "playstore",
            "name": "nubank",
        }

        self.consumer.process_job_payload(payload)

        local_hook_cls.assert_called_once_with(
            file_path="resultado_rabbitmq.xlsx",
            sheet_name="reclamacoes",
        )
        self.assertIs(worker_cls.call_args.kwargs["scraper"], scraper)
        callback = worker_cls.call_args.kwargs["callback"]
        worker_instance.callback = callback
        worker_instance.run("nubank")
        local_hook_cls.return_value.post.assert_called_once_with({"records": [{"id": "10"}]})

    @patch.object(RabbitMQJobConsumer, "process_job_payload")
    def test_on_message_ack_on_success(self, mock_process):
        channel = MagicMock()
        method = MagicMock()
        method.delivery_tag = "tag-1"

        body = json.dumps(
            {
                "source": "playstore",
                "name": "nubank",
                "hook_url": "https://webhook.site/abcdef",
            }
        ).encode("utf-8")

        self.consumer._on_message(channel, method, None, body)

        mock_process.assert_called_once()
        channel.basic_ack.assert_called_once_with(delivery_tag="tag-1")
        channel.basic_nack.assert_not_called()

    @patch.object(RabbitMQJobConsumer, "process_job_payload", side_effect=ValueError)
    def test_on_message_nack_on_error(self, mock_process):
        channel = MagicMock()
        method = MagicMock()
        method.delivery_tag = "tag-2"

        body = b"{\"source\":\"invalido\"}"
        self.consumer._on_message(channel, method, None, body)

        mock_process.assert_called_once()
        channel.basic_nack.assert_called_once_with(delivery_tag="tag-2", requeue=False)
        channel.basic_ack.assert_not_called()

    @patch("reputation_worker.rabbitmq._import_pika")
    def test_start_creates_queue_when_missing(self, mock_import_pika):
        mock_import_pika.return_value = MagicMock()
        channel_closed_by_broker = type(
            "FakeChannelClosedByBroker",
            (Exception,),
            {},
        )
        mock_import_pika.return_value.exceptions.ChannelClosedByBroker = (
            channel_closed_by_broker
        )

        not_found_exc = channel_closed_by_broker("NOT_FOUND")
        not_found_exc.reply_code = 404

        first_channel = MagicMock()
        first_channel.queue_declare.side_effect = not_found_exc

        second_channel = MagicMock()

        connection = MagicMock()
        connection.channel.side_effect = [first_channel, second_channel]
        connection.is_open = True

        self.consumer.connection_factory = MagicMock()
        self.consumer.connection_factory.create.return_value = connection

        second_channel.start_consuming.side_effect = KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            self.consumer.start()

        self.assertEqual(connection.channel.call_count, 2)
        first_channel.queue_declare.assert_called_once_with(
            queue="scrape_data", passive=True
        )
        second_channel.queue_declare.assert_called_once_with(
            queue="scrape_data", durable=True
        )
        second_channel.basic_qos.assert_called_once_with(prefetch_count=1)
        second_channel.basic_consume.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

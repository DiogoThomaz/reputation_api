import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from reputation_worker.postgres import PostgresClient, PostgresSettings


class TestPostgresSettings(unittest.TestCase):
    def test_loads_required_values_from_env_file(self):
        env_content = "\n".join(
            [
                "POSTGRES_HOST=localhost",
                "POSTGRES_DATABASE=reputation",
                "POSTGRES_USERNAME=postgres",
                "POSTGRES_PASSWORD=secret",
                "POSTGRES_PORT=5433",
                "POSTGRES_SSLMODE=require",
                "POSTGRES_CONNECT_TIMEOUT=15",
            ]
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(env_content, encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                settings = PostgresSettings.from_env(str(env_path))

        self.assertEqual(settings.host, "localhost")
        self.assertEqual(settings.database, "reputation")
        self.assertEqual(settings.username, "postgres")
        self.assertEqual(settings.password, "secret")
        self.assertEqual(settings.port, 5433)
        self.assertEqual(settings.sslmode, "require")
        self.assertEqual(settings.connect_timeout, 15)


class TestPostgresClient(unittest.TestCase):
    @patch("reputation_worker.postgres._import_psycopg")
    def test_loads_settings_from_env_when_not_provided(self, mock_import_psycopg):
        cursor = MagicMock()
        cursor.description = None
        cursor.rowcount = 1

        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor

        psycopg = MagicMock()
        psycopg.connect.return_value.__enter__.return_value = connection
        mock_import_psycopg.return_value = psycopg

        env_content = "\n".join(
            [
                "POSTGRES_HOST=localhost",
                "POSTGRES_DATABASE=reputation",
                "POSTGRES_USERNAME=postgres",
                "POSTGRES_PASSWORD=secret",
            ]
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(env_content, encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                client = PostgresClient(env_path=str(env_path))

        result = client.execute("DELETE FROM empresas WHERE id = %s", (1,))

        psycopg.connect.assert_called_once_with(
            host="localhost",
            dbname="reputation",
            user="postgres",
            password="secret",
            port=5432,
            connect_timeout=10,
        )
        self.assertEqual(result, {"rowcount": 1, "rows": []})

    @patch("reputation_worker.postgres._import_psycopg")
    def test_execute_returns_rows_for_select_queries(self, mock_import_psycopg):
        cursor = MagicMock()
        cursor.description = [MagicMock(name="id"), MagicMock(name="nome")]
        cursor.description[0].name = "id"
        cursor.description[1].name = "nome"
        cursor.fetchall.return_value = [(1, "acme")]
        cursor.rowcount = 1

        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor

        psycopg = MagicMock()
        psycopg.connect.return_value.__enter__.return_value = connection
        mock_import_psycopg.return_value = psycopg

        client = PostgresClient(
            PostgresSettings(
                host="localhost",
                database="reputation",
                username="postgres",
                password="secret",
            )
        )

        result = client.execute("SELECT id, nome FROM empresas WHERE id = %s", (1,))

        psycopg.connect.assert_called_once_with(
            host="localhost",
            dbname="reputation",
            user="postgres",
            password="secret",
            port=5432,
            connect_timeout=10,
        )
        cursor.execute.assert_called_once_with(
            "SELECT id, nome FROM empresas WHERE id = %s",
            (1,),
        )
        self.assertEqual(result, {"rowcount": 1, "rows": [{"id": 1, "nome": "acme"}]})

    @patch("reputation_worker.postgres._import_psycopg")
    def test_execute_returns_metadata_for_write_queries(self, mock_import_psycopg):
        cursor = MagicMock()
        cursor.description = None
        cursor.rowcount = 3

        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor

        psycopg = MagicMock()
        psycopg.connect.return_value.__enter__.return_value = connection
        mock_import_psycopg.return_value = psycopg

        client = PostgresClient(
            PostgresSettings(
                host="localhost",
                database="reputation",
                username="postgres",
                password="secret",
                sslmode="require",
            )
        )

        result = client.execute(
            "UPDATE empresas SET nome = %s WHERE id = %s",
            ("novo nome", 10),
        )

        psycopg.connect.assert_called_once_with(
            host="localhost",
            dbname="reputation",
            user="postgres",
            password="secret",
            port=5432,
            connect_timeout=10,
            sslmode="require",
        )
        self.assertEqual(result, {"rowcount": 3, "rows": []})

    def test_execute_rejects_empty_query(self):
        client = PostgresClient(
            PostgresSettings(
                host="localhost",
                database="reputation",
                username="postgres",
                password="secret",
            )
        )

        with self.assertRaises(ValueError):
            client.execute("   ")


if __name__ == "__main__":
    unittest.main()
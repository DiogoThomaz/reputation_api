import json
import unittest
from unittest.mock import MagicMock, patch

from reputation_worker.hook import HookClient


class TestHookClient(unittest.TestCase):
    @patch("reputation_worker.hook.request.urlopen")
    def test_post_sends_json_payload(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.__enter__.return_value.status = 201
        mock_response.__enter__.return_value.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value = mock_response

        hook = HookClient("https://api.exemplo.com/hook")
        payload = {"records": [{"a": 1}]}

        response = hook.post(payload)

        self.assertEqual(response["status_code"], 201)
        self.assertEqual(response["body"], '{"ok": true}')

        args, _ = mock_urlopen.call_args
        sent_request = args[0]
        self.assertEqual(sent_request.method, "POST")
        self.assertEqual(sent_request.headers["Content-type"], "application/json")
        self.assertEqual(json.loads(sent_request.data.decode("utf-8")), payload)


if __name__ == "__main__":
    unittest.main()

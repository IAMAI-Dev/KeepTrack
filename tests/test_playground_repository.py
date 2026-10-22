"""远程源切换与缓存保护的回归测试，无需真实网络。"""

import copy
import http.client
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from playground_repository import PlaygroundRepository, REMOTE_SOURCES


class TestRemoteFallback(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = PlaygroundRepository(cache_dir=self.temp.name)
        self.data = json.loads(
            Path(__file__).resolve().parents[1].joinpath(
                "playgrounds.json"
            ).read_text(encoding="utf-8")
        )
        self.valid = json.dumps(self.data, ensure_ascii=False).encode("utf-8")
        self.cache = Path(self.temp.name, "playgrounds_cache.json")

    def assert_falls_back(self, first):
        with patch("playground_repository.urllib.request.urlopen",
                   side_effect=[first, io.BytesIO(self.valid)]) as fetch:
            self.assertEqual(self.repo.refresh(), self.data["playgrounds"])
        self.assertEqual(
            [item.args[0].full_url for item in fetch.call_args_list],
            REMOTE_SOURCES,
        )
        self.assertEqual(json.loads(self.cache.read_text("utf-8")), self.data)
        self.assertEqual(self.repo.load(), self.data["playgrounds"])

    def test_gitee_success_does_not_request_github(self):
        with patch("playground_repository.urllib.request.urlopen",
                   return_value=io.BytesIO(self.valid)) as fetch:
            self.assertEqual(self.repo.refresh(), self.data["playgrounds"])
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0].full_url, REMOTE_SOURCES[0])

    def test_network_and_read_failures_fall_back(self):
        for error in (
            urllib.error.URLError("unavailable"),
            urllib.error.HTTPError(REMOTE_SOURCES[0], 403, "Forbidden", {}, None),
            TimeoutError("timed out"),
            http.client.IncompleteRead(b"partial", 100),
            http.client.RemoteDisconnected("closed"),
        ):
            with self.subTest(error=type(error).__name__):
                self.assert_falls_back(error)

    def test_invalid_body_falls_back(self):
        for raw in (b"<html>login</html>", b"{", b"\xff\xfe", b"[]",
                    b"null", b"{}", b'{"playgrounds": []}',
                    b'{"playgrounds": {}}', b'{"playgrounds": [null]}'):
            with self.subTest(raw=raw):
                self.assert_falls_back(io.BytesIO(raw))

    def test_response_read_failure_falls_back(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = http.client.IncompleteRead(b"partial", 100)
        self.assert_falls_back(response)

    def test_invalid_record_falls_back(self):
        cases = [("school", ""), ("campus", None), ("name", 3),
                 ("latitude", 91), ("longitude", -181),
                 ("latitude", "32.5"), ("longitude", True),
                 ("angle", float("nan")), ("angle", float("inf")),
                 ("angle", None)]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(self.data)
                data["playgrounds"][0][key] = value
                self.assert_falls_back(io.BytesIO(json.dumps(data).encode()))
        data = copy.deepcopy(self.data)
        del data["playgrounds"][0]["angle"]
        self.assert_falls_back(io.BytesIO(json.dumps(data).encode()))

    def test_utf8_bom_is_accepted_without_fallback(self):
        with patch("playground_repository.urllib.request.urlopen",
                   return_value=io.BytesIO(b"\xef\xbb\xbf" + self.valid)) as fetch:
            self.assertEqual(self.repo.refresh(), self.data["playgrounds"])
        fetch.assert_called_once()

    def test_all_sources_fail_keeps_existing_cache(self):
        self.cache.write_bytes(self.valid)
        with patch("playground_repository.urllib.request.urlopen",
                   side_effect=[io.BytesIO(b"<html>blocked</html>"),
                                urllib.error.URLError("offline")]) as fetch:
            with self.assertRaises(ConnectionError) as error:
                self.repo.refresh()
        self.assertEqual(fetch.call_count, 2)
        self.assertTrue(all(url in str(error.exception) for url in REMOTE_SOURCES))
        self.assertEqual(self.cache.read_bytes(), self.valid)
        self.assertEqual(self.repo.load(), self.data["playgrounds"])


if __name__ == "__main__":
    unittest.main()

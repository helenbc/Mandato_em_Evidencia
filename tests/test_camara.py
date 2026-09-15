import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from ideias_em_rede.camara import CamaraApiError, CamaraClient


class RecordingClient(CamaraClient):
    def __init__(self):
        super().__init__(cache_dir=None)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return {"dados": [{"ok": True}], "links": []}


def _fake_response(payload):
    data = json.dumps(payload)
    bio = io.StringIO(data)
    # urlopen is used as `with urlopen(...) as response: json.load(response)`
    bio.__enter__ = lambda s: s  # type: ignore[attr-defined]
    bio.__exit__ = lambda s, *a: False  # type: ignore[attr-defined]
    return bio


def _http_error(url, code):
    return HTTPError(url, code, f"mock {code}", None, None)


class CamaraClientTests(unittest.TestCase):
    def test_voting_subresources_do_not_send_pagination(self):
        client = RecordingClient()
        self.assertEqual(client.voting_votes("abc-1"), [{"ok": True}])
        self.assertEqual(client.voting_orientations("abc-1"), [{"ok": True}])
        self.assertEqual(
            client.calls,
            [("votacoes/abc-1/votos", None), ("votacoes/abc-1/orientacoes", None)],
        )

    def test_list_votings_makes_end_date_inclusive(self):
        client = RecordingClient()
        recorded = {}

        def iter_pages(path, params=None):
            recorded.update({"path": path, "params": params})
            yield {"id": "inside", "data": "2024-07-10"}
            yield {"id": "outside", "data": "2024-07-11"}

        client.iter_pages = iter_pages
        result = list(client.list_votings("2024-07-10", "2024-07-10"))
        self.assertEqual(result, [{"id": "inside", "data": "2024-07-10"}])
        self.assertEqual(recorded["params"]["dataFim"], "2024-07-11")

    def test_cache_hit_second_call_does_not_call_urlopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            client = CamaraClient(cache_dir=cache_dir, retries=0)
            payload = {"dados": [{"id": 1}], "links": []}
            url = client._url("deputados", {"nome": "Teste"})
            with patch("ideias_em_rede.camara.urlopen") as mock_urlopen:
                mock_urlopen.return_value = _fake_response(payload)
                result1 = client.get_url(url)
                self.assertEqual(result1, payload)
                self.assertEqual(mock_urlopen.call_count, 1)
                cache_path = client._cache_path(url)
                self.assertTrue(cache_path is not None and cache_path.is_file())
                # second call should hit cache
                mock_urlopen.reset_mock()
                result2 = client.get_url(url)
                self.assertEqual(result2, payload)
                mock_urlopen.assert_not_called()

    def test_retry_only_on_transient_errors(self):
        # 429 and 5xx should retry, 404 should not
        transient_codes = [429, 500, 502, 503, 504]
        for code in transient_codes:
            with self.subTest(code=code):
                client = CamaraClient(cache_dir=None, retries=1, timeout=1)
                payload = {"dados": [], "links": []}
                with patch("ideias_em_rede.camara.urlopen") as mock_urlopen, patch(
                    "ideias_em_rede.camara.time.sleep"
                ):
                    mock_urlopen.side_effect = [
                        _http_error("http://test", code),
                        _fake_response(payload),
                    ]
                    url = client._url("votacoes", {"itens": 1})
                    result = client.get_url(url)
                    self.assertEqual(result, payload)
                    self.assertEqual(mock_urlopen.call_count, 2)
        # 404 must not retry
        client = CamaraClient(cache_dir=None, retries=3, timeout=1)
        with patch("ideias_em_rede.camara.urlopen") as mock_urlopen, patch(
            "ideias_em_rede.camara.time.sleep"
        ) as mock_sleep:
            mock_urlopen.side_effect = _http_error("http://test", 404)
            with self.assertRaises(CamaraApiError):
                client.get_url(client._url("votacoes", {"itens": 1}))
            self.assertEqual(mock_urlopen.call_count, 1)
            mock_sleep.assert_not_called()

    def test_iter_pages_with_next_link(self):
        client = CamaraClient(cache_dir=None, retries=0)
        # simulate two pages via urlopen
        def side_effect(request, timeout=None):
            url = request.full_url if hasattr(request, "full_url") else request.get_full_url()  # type: ignore
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(url).query)
            pagina = qs.get("pagina", ["1"])[0]
            if pagina == "1":
                payload = {"dados": [{"id": 1}], "links": [{"rel": "next", "href": "next"}]}
            else:
                payload = {"dados": [{"id": 2}], "links": []}
            return _fake_response(payload)

        with patch("ideias_em_rede.camara.urlopen", side_effect=side_effect):
            result = list(client.iter_pages("deputados", {"nome": "A", "itens": 1}))
            self.assertEqual(result, [{"id": 1}, {"id": 2}])


if __name__ == "__main__":
    unittest.main()

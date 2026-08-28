import unittest

from ideias_em_rede.camara import CamaraClient


class RecordingClient(CamaraClient):
    def __init__(self):
        super().__init__(cache_dir=None)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return {"dados": [{"ok": True}], "links": []}


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


if __name__ == "__main__":
    unittest.main()

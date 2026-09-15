import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ideias_em_rede.io_utils import read_json, utc_now_iso, write_json, write_jsonl


class IoUtilsTests(unittest.TestCase):
    def test_write_json_and_read_json_roundtrip_atomic_and_creates_parents(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            # caminho aninhado que ainda não existe
            target = base / "a" / "b" / "c" / "dados.json"
            self.assertFalse(target.parent.exists())
            payload = {"chave": "valor", "numero": 42, "lista": [1, 2, 3], "acentuação": "áéíóú"}
            write_json(target, payload)

            # diretório criado com parents
            self.assertTrue(target.parent.exists())
            self.assertTrue(target.is_file())

            # atomicidade: arquivo .tmp removido
            tmp = target.with_suffix(target.suffix + ".tmp")
            self.assertFalse(tmp.exists(), f"arquivo temporário {tmp} deveria ter sido removido")

            # roundtrip fiel
            loaded = read_json(target)
            self.assertEqual(loaded, payload)

            # verifica que o arquivo no disco é JSON válido com quebra de linha final
            raw = target.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), payload)

    def test_write_jsonl_returns_count_and_roundtrip_and_creates_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "nested" / "deep" / "saida.jsonl"
            self.assertFalse(target.parent.exists())

            rows = [
                {"id": 1, "texto": "olá"},
                {"id": 2, "texto": "mundo", "acentuação": "áéíóú"},
                {"id": 3},
            ]
            count = write_jsonl(target, rows)
            self.assertEqual(count, len(rows))

            # diretório criado
            self.assertTrue(target.parent.exists())
            self.assertTrue(target.is_file())

            # atomicidade: .tmp removido
            tmp = target.with_suffix(target.suffix + ".tmp")
            self.assertFalse(tmp.exists())

            # roundtrip: cada linha é um JSON válido
            lines = target.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), len(rows))
            loaded = [json.loads(line) for line in lines if line.strip()]
            self.assertEqual(loaded, rows)

            # também com iterável vazio
            empty_target = base / "nested" / "vazio.jsonl"
            count_empty = write_jsonl(empty_target, [])
            self.assertEqual(count_empty, 0)
            self.assertTrue(empty_target.is_file())
            self.assertEqual(empty_target.read_text(encoding="utf-8"), "")
            tmp_empty = empty_target.with_suffix(empty_target.suffix + ".tmp")
            self.assertFalse(tmp_empty.exists())

            # com gerador (iterable genérico)
            gen_target = base / "nested" / "gen.jsonl"

            def gen():
                for i in range(5):
                    yield {"n": i}

            count_gen = write_jsonl(gen_target, gen())
            self.assertEqual(count_gen, 5)
            loaded_gen = [json.loads(line) for line in gen_target.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(loaded_gen, [{"n": i} for i in range(5)])

    def test_write_json_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "dados.json"
            first = {"versao": 1, "conteudo": "primeiro"}
            second = {"versao": 2, "conteudo": "segundo", "novo_campo": True}

            write_json(target, first)
            self.assertEqual(read_json(target), first)

            write_json(target, second)
            self.assertEqual(read_json(target), second)
            self.assertNotEqual(read_json(target), first)

            # garante que .tmp não ficou para trás após sobrescrita
            tmp = target.with_suffix(target.suffix + ".tmp")
            self.assertFalse(tmp.exists())

            # raw file reflete segundo payload
            raw = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(raw, second)

    def test_read_json_raises_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "nao_existe.json"
            self.assertFalse(missing.exists())
            with self.assertRaises(FileNotFoundError):
                read_json(missing)

            # também para caminho aninhado inexistente
            deep_missing = Path(directory) / "a" / "b" / "c" / "falta.json"
            with self.assertRaises((FileNotFoundError, OSError)):
                read_json(deep_missing)

    def test_read_jsonl_raises_when_missing(self):
        # io_utils não expõe read_jsonl, mas alignment.read_jsonl é o leitor
        # canônico usado no pipeline; testa que levanta quando ausente.
        # Se io_utils vier a expor read_jsonl, testa ambos.
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "nao_existe.jsonl"
            self.assertFalse(missing.exists())

            # tenta io_utils.read_jsonl se existir
            try:
                from ideias_em_rede import io_utils as _io_utils

                if hasattr(_io_utils, "read_jsonl"):
                    with self.assertRaises((FileNotFoundError, OSError)):
                        _io_utils.read_jsonl(missing)  # type: ignore[attr-defined]
                    return
            except ImportError:
                pass

            # fallback: alignment.read_jsonl
            from ideias_em_rede.alignment import read_jsonl

            with self.assertRaises((FileNotFoundError, OSError)):
                read_jsonl(missing)

            deep_missing = Path(directory) / "x" / "y" / "falta.jsonl"
            with self.assertRaises((FileNotFoundError, OSError)):
                read_jsonl(deep_missing)

    def test_utc_now_iso_returns_iso8601_with_utc_timezone(self):
        value = utc_now_iso()
        self.assertIsInstance(value, str)
        # deve terminar em +00:00 (timezone UTC)
        self.assertTrue(value.endswith("+00:00"), f"valor {value!r} deveria terminar com +00:00")

        # deve ser parseável por fromisoformat e ter tzinfo UTC
        parsed = datetime.fromisoformat(value)
        self.assertIsNotNone(parsed.tzinfo)
        # normaliza para UTC e compara offset
        self.assertEqual(parsed.tzinfo.utcoffset(parsed), timezone.utc.utcoffset(parsed))

        # deve estar próximo de agora (diferença < 5s)
        now = datetime.now(timezone.utc)
        delta = abs((now - parsed).total_seconds())
        self.assertLess(delta, 5, f"delta {delta}s muito grande entre now e utc_now_iso")


if __name__ == "__main__":
    unittest.main()

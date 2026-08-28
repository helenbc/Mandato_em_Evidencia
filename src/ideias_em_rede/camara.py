"""Cliente HTTP com cache para a API de Dados Abertos da Câmara."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class CamaraApiError(RuntimeError):
    """Erro após esgotar tentativas de acesso ou receber resposta inválida."""


class CamaraClient:
    """Acessa deputados e votações com paginação, retentativas e cache em disco."""

    def __init__(
        self,
        base_url: str = "https://dadosabertos.camara.leg.br/api/v2",
        cache_dir: Path | None = Path("data/cache/camara"),
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.retries = retries

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.base_url}/{path.lstrip('/')}"
        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value is not None and value != ""
        }
        if clean_params:
            url = f"{url}?{urlencode(clean_params, doseq=True)}"
        return url

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get_url(self, url: str) -> dict[str, Any]:
        """Obtém JSON da URL, preferindo cache e repetindo falhas transitórias."""

        cache_path = self._cache_path(url)
        if cache_path and cache_path.is_file():
            with cache_path.open(encoding="utf-8") as stream:
                return json.load(stream)

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ideias-em-rede/0.1 (academic research)",
            },
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise CamaraApiError(f"Resposta inesperada da API: {url}")
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = cache_path.with_suffix(".tmp")
                    with temporary.open("w", encoding="utf-8") as stream:
                        json.dump(payload, stream, ensure_ascii=False)
                    temporary.replace(cache_path)
                return payload
            except HTTPError as error:
                last_error = error
                if error.code not in {429, 500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
            if attempt < self.retries:
                time.sleep(2**attempt)
        raise CamaraApiError(f"Falha ao consultar {url}: {last_error}") from last_error

    def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.get_url(self._url(path, params))

    def iter_pages(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        """Percorre automaticamente as páginas indicadas pelo link ``next``."""

        page_params = dict(params or {})
        page_params.setdefault("pagina", 1)
        page_params.setdefault("itens", 100)
        while True:
            payload = self.get(path, page_params)
            for item in payload.get("dados", []):
                yield item
            links = payload.get("links", [])
            if not any(link.get("rel") == "next" for link in links):
                return
            page_params["pagina"] += 1

    def search_deputies(
        self, name: str, legislature: int | None = None
    ) -> list[dict[str, Any]]:
        """Busca deputados por nome e, opcionalmente, legislatura."""

        params: dict[str, Any] = {"nome": name, "itens": 100}
        if legislature is not None:
            params["idLegislatura"] = legislature
        return list(self.iter_pages("deputados", params))

    def list_votings(self, start_date: str, end_date: str) -> Iterator[dict[str, Any]]:
        """Lista votações em um intervalo inclusivo de datas ISO (AAAA-MM-DD)."""

        # Na API, dataFim se comporta como limite exclusivo em consultas de um
        # unico dia. Consultamos ate o dia seguinte e filtramos localmente para
        # oferecer uma interface inclusiva e previsivel ao usuario.
        exclusive_end = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
        for voting in self.iter_pages(
            "votacoes",
            {
                "dataInicio": start_date,
                "dataFim": exclusive_end,
                "ordem": "ASC",
                "ordenarPor": "dataHoraRegistro",
                "itens": 100,
            },
        ):
            voting_date = str(voting.get("data") or "")
            if start_date <= voting_date <= end_date:
                yield voting

    def voting_votes(self, voting_id: str) -> list[dict[str, Any]]:
        """Retorna os votos nominais registrados para uma votação."""

        safe_id = quote(str(voting_id), safe="-_")
        # Estes sub-recursos rejeitam os parametros pagina/itens com HTTP 400.
        payload = self.get(f"votacoes/{safe_id}/votos")
        return list(payload.get("dados", []))

    def voting_orientations(self, voting_id: str) -> list[dict[str, Any]]:
        """Retorna as orientações de partidos, federações e blocos da votação."""

        safe_id = quote(str(voting_id), safe="-_")
        payload = self.get(f"votacoes/{safe_id}/orientacoes")
        return list(payload.get("dados", []))

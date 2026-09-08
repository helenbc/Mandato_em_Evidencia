# AGENTS.md — Mandato em Evidência

> Instruções para agentes de código e contribuidores. Usuários da ferramenta: ver `README.md` (tutorial e apresentação).

## 1. Visão do projeto (1–2 frases)

Pipeline Python (`src/ideias_em_rede/`) que cruza o dataset PublicHearingBR com a API da Câmara e gera `web/app/dashboard.json`, consumido pela interface Vinext/React em `web/`. Sem servidor Python nem banco em produção.

## 2. Setup / build / test (comandos exatos)

```bash
# Pipeline Python (raiz do repo)
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/ideias-em-rede --help
# sem instalação: PYTHONPATH=src python3 -m ideias_em_rede --help

# Fluxo offline seguro (não usa internet)
.venv/bin/ideias-em-rede audit
.venv/bin/ideias-em-rede extract --source lds --limit 12

# Fluxo completo do recorte (exige internet da Câmara)
.venv/bin/ideias-em-rede run --source lds --limit 12 --legislature 57 \
  --start-date 2024-07-10 --end-date 2024-07-10 --organ PLEN
.venv/bin/ideias-em-rede alignment
.venv/bin/ideias-em-rede prepare-positions --limit 24 --per-deputy 2
.venv/bin/ideias-em-rede web-data

# Com LLM (exige OPENAI_API_KEY, nunca commitar a chave)
export OPENAI_API_KEY="sua-chave"
.venv/bin/ideias-em-rede extract-positions --model gpt-5-mini
.venv/bin/ideias-em-rede compare
.venv/bin/ideias-em-rede web-data

# Testes e validação Python (offline, sem internet)
PYTHONPATH=src python3 -m unittest discover -s tests -v   # 11 testes
PYTHONPATH=src python3 -m compileall -q src tests

# Interface web
cd web
pnpm install
pnpm exec tsc --noEmit
pnpm run build
# dev (bloqueante): pnpm run dev → http://localhost:3000/
```

## 3. Estrutura (mapa)

```text
PublicHearingBR/  dataset LDS + NLI (commitado)
config/comparison_sample.json  amostra fala×voto (audiência 7 ↔ votação 2430143-72)
src/ideias_em_rede/  cli, dataset, deputies, camara, pipeline,
                     alignment, positions, comparison, web_export, io_utils
tests/  7 arquivos, 11 testes, sem internet (mocks)
web/app/dashboard.json  artefato gerado e commitado (NÃO sobrescrever com run de teste)
web/  app/, public/, worker/, db/ (Vinext; ver web/README.md)
data/cache|processed/, .venv/, build/, dist/  gerados, ignorados pelo git
```

Responsabilidades: `dataset` valida/audita JSONL · `deputies` extrai cargos "deputad*" e resolve IDs (score: nome 0,80 + UF 0,10 + partido 0,10; `matched` exige ≥0,86 e margem ≥0,05) · `camara` HTTP com cache SHA-256 da URL · `pipeline` coleta paralela · `alignment` votos canônicos SIM/NAO/ABSTENCAO/OBSTRUCAO, sem adivinhar blocos; fallback da maioria da bancada só quando sem orientação (quorum ≥2, leave-one-out, empate = sem base; fonte `MAIORIA_<PARTIDO>`; orientação oficial prevalece) · `positions` valida `evidence_quote` literal nos chunks · `comparison` COERENTE/DIVERGENTE/INCONCLUSIVO · `web_export` consolida dashboard (`pending_llm` sem LLM) · `io_utils` escrita atômica via `.tmp`.

## 4. Padrões

- Python ≥3.10, só biblioteca padrão no pipeline (+ OpenAI via HTTP próprio); tipos com `from __future__ import annotations`.
- JSON/JSONL sempre via `io_utils` (atômico); `generated_at` UTC; ordenação determinística; respostas Câmara/OpenAI em `data/cache/`.
- Frontend: TypeScript estrito (`tsc --noEmit` deve passar), Tailwind; `vite.config.ts` sem imports de `web/build/` (pasta ignorada pelo git — ver histórico da branch).
- Commits pequenos, em português, sem segredos.

## 5. Git workflow

Branch atual: `chore/standards-and-fixes`. Commite apenas `src/`, `web/`, `config/`, `tests/`, `README.md`, `AGENTS.md`. Nunca commite `.venv/`, `data/cache|processed/`, `.env*`, `node_modules/`, `web/dist|build`.

## 6. Boundaries

- **Always:** rodar `unittest` + `tsc --noEmit` após mudar `src/` ou `web/`; regenerar `web-data` após mudar análise (e restaurar `web/app/dashboard.json` se o run foi só teste); citar PublicHearingBR + Câmara.
- **Ask first:** adicionar dependências; ampliar período de coleta; mudar mapeamento de federações/blocos; publicar artefatos derivados.
- **Never:** commitar `OPENAI_API_KEY`/`.env`; simular classificações de LLM; atribuir orientação de bloco truncado; redistribuir o dataset como próprio; usar o painel para perfis sensíveis ou propaganda.

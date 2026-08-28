# Mandato em Evidência — interface web

Interface interativa dos resultados gerados pelo pipeline Python. Ela permite:

- buscar e filtrar parlamentares por partido;
- consultar a métrica de alinhamento e sua cobertura;
- abrir cada voto e sua fonte na Câmara;
- revisar falas, evidências e confiança da classificação;
- consultar comparações exploratórias entre fala e voto.

## Atualizar os dados

Na raiz do repositório:

```bash
.venv/bin/ideias-em-rede web-data
```

Esse comando atualiza `app/dashboard.json`, que é incorporado à compilação.

## Desenvolvimento

Requer Node.js 22.13 ou superior e pnpm:

```bash
pnpm install
pnpm run dev
```

Abra `http://localhost:3000/`.

## Validação de produção

```bash
pnpm exec tsc --noEmit
pnpm run build
```

O site exibe explicitamente quando a etapa de LLM ainda está pendente e nunca
substitui dados ausentes por classificações simuladas.

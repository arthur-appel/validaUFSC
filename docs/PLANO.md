# Valida UFSC — Comparador de Currículos / Auditor de Equivalências

## Contexto

Alunos da UFSC que querem **mudar de curso** (ou aproveitar disciplinas entre cursos) precisam
hoje comparar manualmente dois currículos PDF, disciplina por disciplina, pra descobrir o que
pode ser validado no colegiado de destino. É lento e propenso a erro.

Este projeto (cadeira de Ciência e Engenharia de Dados) entrega uma aplicação web onde o usuário:
1. seleciona um **curso de origem** e um **curso de destino** (currículos já raspados e armazenados);
2. opcionalmente sobe o **histórico escolar** dele (PDF do CAGR) pra personalizar a análise;
3. recebe uma **auditoria de equivalência**: quais disciplinas de origem validam quais de destino,
   com método, similaridade e status (aproveita / aproveita com ressalva / não aproveita).

Os três pilares devem ficar **excelentes e 100% funcionais**: (a) pipeline de engenharia de dados
(scraping → parsing → ETL → banco), (b) modelo de matching/NLP, (c) produto/app polido.

### Insight técnico central (define a arquitetura)
**O código da disciplina é um identificador único em toda a UFSC.** `INE5111 - Estatística Aplicada I`
aparece no currículo de Ciência de Dados *e* no histórico do Arthur; `MTM3110 - Cálculo 1` aparece
nos dois currículos de exemplo. Logo, **mesmo código ⇒ mesma disciplina**, e grande parte da
equivalência é **determinística**. A IA (embeddings + LLM) só entra no caso difícil: disciplinas com
**códigos diferentes** mas conteúdo parecido (comparar ementas). Isso torna o sistema confiável,
auditável e barato.

### Decisões já tomadas com o usuário
- **Infra de IA:** Ollama local em Docker (embeddings + LLM), grátis/offline/reprodutível.
- **Motor de equivalência:** híbrido em camadas (código → equivalência oficial → semântico → LLM juiz).
- **Escopo de scraping:** todos os cursos do Campus Florianópolis (árvore `treeid=30`).
- **Foco:** pipeline + matching + app, todos excelentes.

### Critério oficial de validação (UFSC) — base do motor
Regido pela **Resolução 17/CUn/97** (Cap. VI – Do Aproveitamento de Estudos, arts. 97-101) e pela
**Resolução 115/2022/CGRAD**. Para validar uma disciplina de destino, a(s) disciplina(s) de origem
precisa(m) **cobrir a ementa e a carga horária**. Limiar prático consolidado pelos colegiados:
- **≥ 75% de compatibilidade de conteúdo/ementa**, e
- **≥ 75% da carga horária** da disciplina de destino.
Esses dois limiares são **parâmetros configuráveis** (default 0.75) porque variam por colegiado.
A norma **permite somar 2+ disciplinas de origem (N:1)** para cobrir uma disciplina de destino —
o motor precisa modelar isso, não só match 1:1. Restrições: não revalidar o que já está no histórico
e não usar a mesma origem para cobrir duas destino com ementa redundante.

---

## Estrutura dos dados (mapeada dos PDFs de exemplo)

**PDF de currículo** (`curso_origem`, `curso_destino`): cabeçalho com `Curso` (nº + nome, ex. `349 -
CIÊNCIA DE DADOS`), `Currículo` (código de vigência, ex. `20261`), habilitação, titulação, cargas
horárias. Depois, por **Fase** (1ª, 2ª…), uma tabela com colunas:
`Código | Disciplina(nome) | Tipo(Ob/Op) | H/A | Aulas | Equivalentes | Pré-Requisito | Conjunto | Pré CH`.
Acima de cada linha vem a **ementa** (texto descritivo — insumo principal do matching semântico).
Há ainda seções "Rol de Disciplinas Optativas", "Rol de Atividades de Extensão" e o resumo de cargas.

**PDF de histórico** (`HISTORICO_..._ARTHUR`): cabeçalho do aluno (matrícula, curso, currículo) e,
por semestre, linhas `Código | Nome | Nota | H/A | Fr | Tipo`. Aprovado = `Fr = FS` e nota ≥ 6,0.

**Padrão de código de disciplina:** 3 letras + 4 dígitos (`CIN8001`, `INE5111`, `MTM3110`, `EGC5302`,
`EEL5105`, `LSB7244`). Usar como chave canônica e como âncora de parsing/regex.

---

## Arquitetura geral

```
┌─────────────┐   Playwright   ┌──────────────┐  pdfplumber  ┌─────────────┐
│  CAGR (JSF) │ ─────────────▶ │  ETL scraper │ ───────────▶ │  ETL parser │
└─────────────┘                └──────────────┘              └──────┬──────┘
                                                                    │ upsert + embeddings (Ollama)
                                                                    ▼
┌──────────┐   REST    ┌─────────────────┐   SQL / pgvector  ┌──────────────────────┐
│ Frontend │ ◀──────▶  │  Backend FastAPI │ ◀──────────────▶ │ PostgreSQL + pgvector │
│ (React)  │           │  + Motor híbrido │                  └──────────────────────┘
└──────────┘           └────────┬─────────┘
                                │ casos duvidosos (LLM juiz)
                                ▼
                          ┌──────────┐
                          │  Ollama  │
                          └──────────┘
```

Tudo orquestrado por **Docker Compose**. Serviços: `db` (postgres+pgvector), `ollama`,
`backend` (FastAPI), `frontend` (build estático servido por nginx), e um job one-shot `etl`.

### Stack
| Camada | Escolha | Por quê |
|---|---|---|
| Scraping | Python + **Playwright** (Chromium headless) | Árvore JSF/RichFaces com ViewState/AJAX; sem hrefs estáticos |
| Parsing PDF | **pdfplumber** (+ regex de código) | Layout tabular com ementa multi-linha; extração layout-aware |
| ETL | Scripts Python + `pipeline.py` (orquestração leve; Prefect opcional) | Mostra eng. de dados sem overkill |
| Banco | **PostgreSQL 16 + pgvector** | Relacional p/ currículos + busca vetorial de ementas |
| Backend | **FastAPI + SQLAlchemy + Pydantic** | Async, tipado, doc automática |
| Embeddings | Ollama `bge-m3` ou `nomic-embed-text` (multilíngue/PT) | Local, bom em português |
| LLM juiz | Ollama `llama3.1:8b` ou `qwen2.5:7b` | Local, saída estruturada (JSON) |
| Frontend | **Vite + React + Tailwind** | Porta o protótipo `SyllabusAI.html`, polido e manutenível |

---

## Modelo de dados (PostgreSQL)

Tabelas principais (Alembic p/ migrations):

- **`curso`** — `id, codigo (ex. 349), nome, campus`
- **`curriculo`** — `id, curso_id, codigo_vigencia (ex. 20261), habilitacao, titulacao, carga_total_ha, vigente bool, pdf_origem_url, scraped_at`
- **`disciplina`** — `id, codigo UNIQUE (ex. CIN8001), nome, ementa, carga_horaria_ha` ← entidade **canônica UFSC-wide**
- **`curriculo_disciplina`** (junção) — `curriculo_id, disciplina_id, tipo (Ob/Op/Es), fase, ordem` ← tipo/fase são por currículo
- **`pre_requisito`** — `curriculo_disciplina_id, expressao_texto` (parse de pré-req fica como texto + best-effort estruturado)
- **`equivalencia_oficial`** — `disciplina_id, equivalente_codigo, regra_texto` (coluna "Equivalentes" do PDF)
- **`disciplina_embedding`** — `disciplina_id, embedding vector(N)` (pgvector; índice ivfflat/hnsw)
- **`comparacao`** (cache) — `id, curriculo_origem_id, curriculo_destino_id, params_hash (inclui limiares), created_at`
- **`comparacao_item`** — `comparacao_id, disciplina_destino_id, metodo (codigo|oficial|semantico|llm|somatorio), similaridade, status, ch_ok bool, ch_cobertura_pct, justificativa` (1 por disciplina de destino)
- **`comparacao_item_origem`** — `comparacao_item_id, disciplina_origem_id, similaridade` (1+ origens por item; suporta o **somatório N:1**)
- **`historico`** / **`historico_disciplina`** — upload do aluno (código, nota, ch, aprovado); por sessão/efêmero

**Persistência das comparações:** como os currículos são estáticos, a comparação por par
`(origem, destino)` é **calculada uma vez e cacheada** (`comparacao` + `comparacao_item`). O recorte
personalizado pelo histórico é aplicado por cima, em memória/sessão.

---

## Pipeline de dados (ETL) — `etl/`

1. **Scraper** (`etl/scraper/`, Playwright): abre `arvore.xhtml?treeid=30`, expande **Campus
   Florianópolis**, percorre a árvore de cursos, e pra cada curso aciona o relatório "Currículo do
   Curso" do **currículo vigente (mais recente)**, capturando o PDF. Salva em `data/raw/<curso>.pdf`
   e registra `curso`/`curriculo`. Boas práticas: rate-limit, retry/backoff, user-agent, cache (não
   re-baixar se já existe). *Fallback:* se a chamada de relatório JSF for estável, reusar o endpoint
   direto em vez de clicar via browser.
2. **Parser** (`etl/parser/`, pdfplumber): extrai por fase as disciplinas
   `(codigo, nome, tipo, fase, ch, ementa, pre_requisito, equivalentes)`. Âncora = regex de código
   `[A-Z]{3}\d{4}`; ementa = texto entre o fim de uma linha e o código seguinte. **Golden tests**
   contra os 2 PDFs de exemplo (contagem de disciplinas conhecida, ex.: CIN8001..CIN8032 etc.).
3. **Loader** (`etl/loader/`): normaliza e faz **upsert** — `disciplina` canônica por código
   (dedup entre currículos), junções `curriculo_disciplina`, `equivalencia_oficial`. QA de dados
   (códigos órfãos, ementa vazia, CH inconsistente).
4. **Embeddings**: pra cada `disciplina` com ementa, gera embedding via Ollama e grava em
   `disciplina_embedding` (idempotente; só recalcula se ementa mudou).

`etl/pipeline.py` encadeia 1→4 e é executável como job (`docker compose run etl`).

---

## Motor de equivalência híbrido — `backend/app/services/matching/`

Para o par (currículo origem, currículo destino), para **cada disciplina de destino** busca a(s)
disciplina(s) de origem que a validam, em camadas (para na primeira que resolve, registra o método):

1. **Código exato** — `origem.codigo == destino.codigo` ⇒ `aproveita` (`metodo=codigo`, sim=1.0).
2. **Equivalência oficial** — consulta `equivalencia_oficial` (coluna "Equivalentes" do PDF) ⇒ `aproveita`.
3. **Semântico (embeddings)** — similaridade de cosseno entre ementas (pgvector) contra o limiar de
   conteúdo (default **0.75**). `sim ≥ limiar` ⇒ candidata a `aproveita`; banda intermediária ⇒
   `ressalva` (vai pra camada 4); abaixo ⇒ descarta.
4. **LLM juiz** — só nos casos da banda intermediária/duvidosa: envia as duas ementas ao Ollama com
   prompt estruturado (saída JSON: `{equivalente: bool, status, confianca, justificativa}`). Controla
   custo (poucas chamadas) e dá explicação em PT.

**Regra de carga horária (oficial, transversal):** uma origem só valida a destino se
`CH_origem ≥ fator_ch × CH_destino`, com **`fator_ch` default 0.75** (≥75% da CH, parâmetro
configurável por colegiado). Se `CH < limiar`, rebaixa para `ressalva` e marca `ch_ok=false`.

**Somatório N:1 (oficial):** quando nenhuma origem isolada cobre conteúdo **e** carga horária da
destino, o motor tenta **combinar 2+ disciplinas de origem** (compatíveis por conteúdo) cuja **soma
de CH** atinja o limiar — modelando a regra da Resolução 17/CUn/97. Resultado guardado como item com
múltiplas origens. Restrições aplicadas: não revalidar disciplina já no histórico do aluno e não
reutilizar a mesma origem para cobrir destinos com ementa redundante.

**Saída** (alimenta a tela): por disciplina de destino → `{materia_origem, materia_destino, metodo,
similaridade, status, ch_ok, justificativa}` + agregados: **% de aproveitamento**, **nº de
disciplinas aproveitadas / total**, **economia estimada** (semestres), igual ao protótipo.

**Com histórico:** filtra origem para apenas as disciplinas **aprovadas** pelo aluno (nota ≥ 6 / FS) e
gera o relatório personalizado de aproveitamento.

---

## Backend (FastAPI) — `backend/app/`

Endpoints principais:
- `GET /cursos` — lista cursos/currículos vigentes (popular os selects de origem/destino).
- `POST /comparacoes` — body `{curriculo_origem_id, curriculo_destino_id}` ⇒ auditoria (usa cache
  `comparacao`; calcula se não existir).
- `POST /historico` — upload do PDF de histórico ⇒ parse ⇒ lista de disciplinas aprovadas (sessão).
- `POST /comparacoes/{id}/personalizar` — aplica o histórico ao resultado.

Estrutura: `api/` (routers), `core/` (config, db, settings), `models/` (SQLAlchemy), `schemas/`
(Pydantic), `services/` (matching, embeddings, llm, historico_parser), `repositories/`.

---

## Frontend (React + Tailwind) — `frontend/`

Tela única portando o protótipo `SyllabusAI.html`:
- **Painel esquerdo:** selects de **Grade de Origem** / **Grade de Destino** (substituem o upload do
  protótipo), upload opcional do histórico, legenda (Pode aproveitar / com ressalva / não aproveita),
  botão **Analisar Aproveitamento**.
- **Área principal:** cards de KPI (Aproveitamento Geral %, Disciplinas Aproveitadas X/Y, Economia em
  semestres) + tabela de auditoria com filtros (Todas / Deferidas / Ressalvas / Indeferidas), colunas
  `Matéria de Origem | Matéria de Destino | Validação (Carga Horária / Semântica IA / Ementa) |
  Similaridade % | Status`, e busca por código.

---

## Infra — `docker-compose.yml`

Serviços: `db` (postgres+pgvector, volume persistente), `ollama` (volume p/ modelos; pull de
`bge-m3` + `llama3.1:8b` no bootstrap), `backend`, `frontend`, e job `etl` (one-shot). `.env.example`
com URLs/credenciais. README com `docker compose up` + `docker compose run etl`.

### Estrutura do repositório
```
valida_ufsc/
  docker-compose.yml   .env.example   README.md
  backend/   app/{api,core,models,schemas,services,repositories}/  tests/  Dockerfile  pyproject.toml
  etl/       scraper/  parser/  loader/  pipeline.py  tests/  Dockerfile
  frontend/  src/  Dockerfile
  db/        migrations (Alembic)  init/ (extensão pgvector)
  data/      raw/ (PDFs, gitignored)
```

---

## Roadmap de implementação

- **Fase 0 — Setup:** repo, docker-compose, Postgres+pgvector subindo, Ollama com modelos, Alembic.
- **Fase 1 — Scraper:** navegar árvore JSF do Campus Floripa, baixar PDFs do currículo vigente, registrar `curso`/`curriculo`.
- **Fase 2 — Parser:** extrair disciplinas + ementas dos PDFs; golden tests nos 2 exemplos.
- **Fase 3 — Loader + Embeddings:** upsert canônico no Postgres, equivalências oficiais, embeddings das ementas.
- **Fase 4 — Motor híbrido:** 4 camadas + regra de CH, com testes unitários.
- **Fase 5 — Backend API:** `/cursos`, `/comparacoes`, `/historico`, cache de comparações.
- **Fase 6 — Frontend:** tela única, portar o design do protótipo, wire dos endpoints.
- **Fase 7 — Histórico personalizado:** parse do histórico + relatório recortado.
- **Fase 8 — Polimento/QA:** testes, seed de demo, docs, validação manual.

---

## Verificação (end-to-end)

1. `docker compose up` + `docker compose run etl` → conferir contagem de linhas em `curso`,
   `curriculo`, `disciplina`, `disciplina_embedding`.
2. **Golden tests do parser** nos 2 PDFs de exemplo (nº de disciplinas e códigos esperados).
3. `POST /comparacoes` com **349 (Ciência de Dados)** × **208 (Ciências da Computação)**:
   - verificar que `MTM3110` casa por **código** (sim=1.0);
   - verificar match **semântico** entre, ex., `CIN8001 Programação I` ↔ `INE5402 Programação Orientada a Objetos I` (códigos distintos) com similaridade ≥ limiar e status coerentes;
   - validar a **regra dos 75% de carga horária**: rebaixar pra `ressalva`/`ch_ok=false` quando `CH_origem < 0,75 × CH_destino`;
   - validar o **somatório N:1**: uma disciplina de destino coberta por 2+ origens cuja soma de CH atinge o limiar (item com múltiplas `comparacao_item_origem`);
   - validar que os **limiares são configuráveis** (rodar com `fator_ch`/limiar de conteúdo diferentes muda o resultado e o `params_hash` do cache).
4. Upload do **histórico do Arthur** → conferir que só disciplinas aprovadas (FS, nota ≥ 6) entram e
   que os KPIs (aproveitamento %, X/Y, economia) batem.
5. Abrir o **frontend**, rodar a análise pela UI e conferir a tabela/KPIs contra a resposta da API.

---

## Riscos e mitigações
- **Scraping JSF frágil (ViewState/AJAX):** Playwright + retries; cachear PDFs; fallback no endpoint de relatório.
- **Parsing de ementa multi-linha:** âncora por regex de código + golden tests; QA de ementa vazia.
- **Qualidade do embedding em PT:** usar modelo multilíngue (`bge-m3`); calibrar limiares com os exemplos.
- **Custo/latência do LLM:** LLM só na banda duvidosa; cache da comparação por par de currículos.
- **Variação de ementa do mesmo código entre anos:** `disciplina` canônica por código + ementa mais recente.

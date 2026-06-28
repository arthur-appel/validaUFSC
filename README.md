# Valida UFSC — Auditor de Equivalências de Currículos

Comparador de currículos da UFSC: o usuário escolhe um **curso de origem** e um **curso de
destino** e o sistema mostra, na hora, **quais disciplinas têm chance de validação no curso de
destino**, em duas faixas de confiança:

- ✅ **Aproveitamento direto** — mesmo código ou equivalência oficial declarada (determinístico);
- 🔎 **Boas chances** — ementa semelhante (IA), para **levar ao colegiado**.

É uma **ferramenta de triagem para o aluno**: a decisão oficial é sempre do **colegiado do curso de
destino**. Opcionalmente, o usuário envia seu **histórico escolar** (PDF do CAGR) para uma análise
restrita ao que já cursou.

Projeto da disciplina de **Ciência e Engenharia de Dados**. Documentação completa do processo em
[`docs/RELATORIO.md`](docs/RELATORIO.md); roteiro da apresentação em
[`docs/APRESENTACAO_PROMPT.md`](docs/APRESENTACAO_PROMPT.md).

---

## Índice

- [Por que funciona bem](#por-que-funciona-bem)
- [Critério de equivalência (oficial UFSC)](#critério-de-equivalência-oficial-ufsc)
- [Como o motor decide](#como-o-motor-decide)
- [Arquitetura](#arquitetura)
- [Stack](#stack)
- [Como rodar](#como-rodar)
- [Modelo de dados](#modelo-de-dados-postgresql--pgvector)
- [API](#api)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Configuração (.env)](#configuração-env)
- [Desenvolvimento e testes](#desenvolvimento-e-testes)
- [Scripts utilitários](#scripts-utilitários)
- [Notas de qualidade de dados](#notas-de-qualidade-de-dados)
- [Roadmap](#roadmap)

---

## Por que funciona bem

O **código da disciplina é único em toda a UFSC** (`INE5111`, `MTM3110`, `CIN8001`…). Logo, **mesmo
código ⇒ mesma disciplina**, e boa parte da equivalência é **determinística e auditável**. A IA
(*embeddings* locais) só entra no caso difícil: disciplinas de **códigos diferentes** com conteúdo
parecido — comparando as **ementas**. Isso deixa o sistema confiável, explicável e barato.

## Critério de equivalência (oficial UFSC)

Baseado na **Resolução 17/CUn/97** (Cap. VI) e na **Resolução 115/2022/CGRAD**: para validar uma
disciplina, a(s) de origem precisa(m) cobrir **≥ 75% do conteúdo** (ementa) **e ≥ 75% da carga
horária**. A norma permite **somar 2+ disciplinas (N:1)** para cobrir a carga horária. Os limiares
são **configuráveis** (`.env`, default `0.75`).

Distinção-chave do projeto: a **carga horária (75%) é regra objetiva e obrigatória** (tratada como
filtro rígido); a **compatibilidade de conteúdo é subjetiva** (aproximada por IA e remetida ao
colegiado).

## Como o motor decide

Para **cada disciplina de destino**, o motor ([`matching/engine.py`](backend/valida_ufsc/matching/engine.py))
tenta validar em **camadas de confiança decrescente**, parando na primeira que resolve:

| # | Camada | Resultado | Faixa |
|---|---|---|---|
| 1 | **Código exato** (mesmo código UFSC) | `aproveita` | ✅ direto |
| 2 | **Equivalência oficial** (coluna "Equivalentes" do PDF) | `aproveita` | ✅ direto |
| 3 | **Semântico** (cosseno entre ementas ≥ **0,75**) | `boa_chance` | 🔎 boas chances |
| 4 | **Somatório N:1** (combina 2+ origens p/ cobrir a CH) | `boa_chance` | 🔎 boas chances |
| — | nada acima do corte | `nao_aproveita` | sem candidata |

Regras transversais:

- **Carga horária (75%) é filtro rígido na faixa semântica:** se uma candidata (sozinha ou somada)
  não atinge 75% da CH do destino, ela é **descartada** das boas chances (seria recusa certa). Exceção:
  se a CH do destino é desconhecida, mantém-se com ressalva.
- **Recall + reuso:** na faixa semântica, a mesma disciplina de origem **pode ser sugerida para mais
  de um destino** (maximiza o leque; o colegiado valida cada origem em apenas um). Na faixa
  determinística (código/oficial), a relação é **1:1** (consumo).
- **Calibração:** o corte de 0,75 foi calibrado com as **3.794 equivalências oficiais** como gabarito
  (equivalências reais ~0,84 de mediana; ruído < 0,67). Ver [`docs/RELATORIO.md`](docs/RELATORIO.md) §9.2.

> **E o juiz LLM?** Um juiz LLM local chegou a ser avaliado para decidir os casos semânticos, mas
> foi **descartado do produto** por ser inviável na CPU (~8–30 s por chamada; uma comparação inteira
> levava ~16 min). O motor recebe a similaridade como **dependência injetada**, então é **100%
> testável offline**. O relato completo dessa decisão está em [`docs/RELATORIO.md`](docs/RELATORIO.md).

## Arquitetura

```
CAGR (JSF) --Playwright--> scraper --pdfplumber--> parser --> loader --> PostgreSQL + pgvector
                                                                |               ^
                                                          embeddings (Ollama) --+
 Frontend (React) <--REST--> Backend (FastAPI) --motor em camadas--> +----------+
```

Tudo orquestrado por **Docker Compose** (serviços: `db`, `ollama`, `backend`, `frontend`, job `etl`).

## Stack

| Camada | Tecnologia |
|---|---|
| Scraping | Python + **Playwright** 1.45 (Chromium headless) — árvore JSF/RichFaces do CAGR |
| Parsing PDF | **pdfplumber** 0.11 (parser por coordenadas) |
| Banco | **PostgreSQL 16** + **pgvector** (índice HNSW, `vector(1024)`) |
| Backend | **FastAPI** + **SQLAlchemy 2.0** + **Alembic** + Pydantic |
| IA local | **Ollama** — `bge-m3` (embeddings multilíngues, 1024-dim) |
| Frontend | **Vite 5** + **React 18** + **TypeScript 5** + **Tailwind 3** |
| Orquestração | **Docker Compose** |

## Como rodar

Pré-requisitos: **Docker** + **Docker Compose**.

### Opção A — RÁPIDA (recomendada): restaura o *seed* (~1 min)

```bash
cp .env.example .env
docker compose up -d --build db        # sobe só o banco (vazio)
python scripts/restore_seed.py          # restaura ~109 cursos + disciplinas + embeddings
docker compose up -d                    # sobe backend + frontend + ollama
docker compose --profile setup run --rm ollama-pull   # baixa o modelo de embeddings (bge-m3)
docker compose exec backend python scripts/fix_empty_curriculos.py # corrige currículos vazios (Sistemas de Informação, Eng. Civil, etc.)
```

### Opção B — da FONTE: raspa o CAGR do zero (~40 min, precisa de internet)

```bash
cp .env.example .env
docker compose up -d --build
docker compose --profile setup run --rm ollama-pull    # bge-m3 (embeddings)
docker compose --profile etl run --rm etl              # raspa -> parseia -> carrega -> embeddings
docker compose exec backend python scripts/fix_empty_curriculos.py # corrige currículos vazios (Sistemas de Informação, Eng. Civil, etc.)
```

> [!IMPORTANT]
> **Correção de currículos vazios:** Alguns cursos possuem como vigência mais nova no CAGR um placeholder vazio (ex: 2027/1). O comando `docker compose exec backend python scripts/fix_empty_curriculos.py` busca retroativamente e carrega a vigência mais recente que contenha disciplinas, garantindo que cursos como *Sistemas de Informação*, *Engenharia Civil*, *Engenharia Elétrica* e *Engenharia Química* apareçam corretamente para comparação.

Acessos:

- **Frontend:** http://localhost:5173
- **API + docs (Swagger):** http://localhost:8000/docs
- **Banco:** `localhost:5432` (usuário/senha/db no `.env`) — abra no **DBeaver** para explorar.

## Modelo de dados (PostgreSQL + pgvector)

| Tabela | Papel |
|---|---|
| `curso` | `codigo`, `nome`, `campus` |
| `curriculo` | vigência, habilitação, titulação, `carga_total_ha`, *flag* `vigente`, FK p/ `curso` |
| `disciplina` | **canônica por `codigo` (única na UFSC)**: `nome`, `ementa`, `carga_horaria_ha` |
| `curriculo_disciplina` | junção currículo×disciplina: `tipo` (Ob/Op/Es), `fase`, `ordem` |
| `pre_requisito` | expressão textual de pré-requisitos por `curriculo_disciplina` |
| `equivalencia_oficial` | `disciplina_id` → `equivalente_codigo` (coluna "Equivalentes" do PDF) |
| `disciplina_embedding` | `vector(1024)` (pgvector, índice **HNSW**) + `modelo` + `ementa_hash` |
| `comparacao` | cache: `curriculo_origem`, `curriculo_destino`, `params_hash` |
| `comparacao_item` | 1 por disciplina de destino: `metodo`, `status`, `similaridade`, `ch_ok`, `ch_cobertura_pct`, `justificativa` |
| `comparacao_item_origem` | 1+ origens por item (**suporta o somatório N:1**) |
| `historico` / `historico_disciplina` | upload do histórico do aluno (código, nota, CH, aprovado) |

O **cache de comparações** é versionado: `params_hash` inclui uma **versão do motor**
(`_MOTOR_VERSAO`), então mudanças na lógica invalidam o cache automaticamente.

## API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/cursos` | Lista cursos/currículos vigentes (**oculta os vazios**) p/ os seletores |
| `POST` | `/comparacoes` | Auditoria origem→destino (com cache); body `{origem_curriculo_id, destino_curriculo_id}` |
| `POST` | `/comparacoes/personalizada` | Auditoria restrita às disciplinas aprovadas no histórico |
| `POST` | `/historico` | Upload do PDF de histórico → lista de aprovadas (token de sessão) |
| `GET` | `/health` | *Healthcheck* |

## Estrutura do repositório

```
valida_ufsc/
  docker-compose.yml          # db, ollama, backend, frontend, etl
  .env.example                # configuração (copie p/ .env)
  README.md
  backend/
    Dockerfile  Dockerfile.etl  pyproject.toml
    valida_ufsc/
      config.py               # settings (.env) via pydantic-settings
      db/                     # base, session, models (schema SQLAlchemy)
      etl/
        scraper.py            # Playwright: árvore JSF do CAGR + download dos PDFs
        parser.py             # pdfplumber: PDF -> CurriculoParse (parser por coordenadas)
        loader.py             # upsert canônico + gerar_embeddings_pendentes
        pipeline.py           # orquestra scrape -> parse -> load -> embeddings
      matching/
        engine.py             # motor em camadas (código/oficial/semântico/somatório)
        types.py              # DiscRef, CriterioConfig, status e métodos
      embeddings.py           # cliente Ollama (bge-m3) + cosseno
      api/
        main.py  schemas.py   # FastAPI app + schemas Pydantic
        routers/              # cursos, comparacoes, historico
      services/comparacao.py  # liga banco↔motor, KPIs, faixas (tiers), cache
    alembic/                  # migrations
    tests/                    # golden tests (parser) + 18 testes do motor
    scripts/                  # restore_seed, fix_empty_curriculos, browser_test, ...
  frontend/
    Dockerfile  package.json  tailwind.config.js
    src/  App.tsx  api.ts  types.ts   # tela única (React + Tailwind)
  db/seed/                    # dump comprimido do banco (seed)
  docs/  RELATORIO.md  APRESENTACAO_PROMPT.md  PLANO.md  CONSULTAS.sql
```

## Configuração (.env)

Principais variáveis (ver [`.env.example`](.env.example)):

```ini
DATABASE_URL=postgresql+psycopg://valida:valida@db:5432/valida_ufsc
OLLAMA_BASE_URL=http://ollama:11434
EMBEDDING_MODEL=bge-m3            # embeddings (1024-dim)
LIMIAR_CONTEUDO=0.75            # conteúdo "forte" (reforço por somatório N:1)
LIMIAR_CARGA_HORARIA=0.75       # regra dos 75% de CH
LIMIAR_BOA_CHANCE=0.75          # corte da faixa "boas chances" (anteriormente 0.70)
CAGR_TREE_URL=https://cagr.sistemas.ufsc.br/arvore.xhtml?treeid=30
```

## Desenvolvimento e testes

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate    # (Windows: .venv\Scripts\activate)
pip install -e ".[dev,etl]"
pytest                                              # parser (golden) + 18 testes do motor
ruff check .                                        # lint
```

O motor é **testável offline** (a similaridade é injetada como *fake*), sem precisar de banco
nem Ollama.

## Scripts utilitários

| Script | O que faz |
|---|---|
| `scripts/restore_seed.py` | Restaura o *seed* do banco (descomprime e aplica no `db`) |
| `scripts/fix_empty_curriculos.py` | Corrige currículos vigentes **vazios**: baixa do CAGR a vigência mais recente **com conteúdo** e carrega |
| `scripts/browser_test.py` | Teste de fumaça do fluxo no navegador (Playwright) |

## Notas de qualidade de dados

- **Currículos vazios:** o scraper pega a vigência mais nova, que para alguns cursos é um
  **placeholder de 2027 ainda em branco** no CAGR (0 disciplinas). Detectamos 6 casos; corrigimos todos
  os 6 rodando `fix_empty_curriculos.py` (o script busca retroativamente por vigências válidas com conteúdo). A
  interface **oculta currículos vazios** dos seletores.
- **`fase` nula:** legítima em alguns currículos-matriz (humanas) cujo PDF não agrupa por fase.

## Roadmap

- [x] **Formulário oficial de validação pré-preenchido** — preenche o **PDF oficial da PROGRAD/DAE**
  (`frontend/public/formulario-validacao-ufsc.pdf`, um AcroForm) via `pdf-lib`: dados pessoais
  editáveis + códigos sugeridos (diretas + boas chances) nas caixas certas, pronto para baixar e
  protocolar. É o documento oficial idêntico, apenas preenchido.
- [x] **Modo escuro** (*dark mode*) — persistido em `localStorage`, respeita a preferência do SO.
- [x] **Abrir o currículo selecionado em PDF** (link direto ao relatório do CAGR).
- [ ] **Deploy público** (app + banco com *seed* hospedados), para uso fora do ambiente local.

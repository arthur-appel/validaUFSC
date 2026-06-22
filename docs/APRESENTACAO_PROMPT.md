# Prompt para o Claude Design — Apresentação "Valida UFSC"

> Cole o bloco abaixo no Claude Design. O print do diagrama do banco (modelo ER) já foi
> anexado lá — referencie-o no slide de Arquitetura/Banco.

---

Crie uma apresentação de slides profissional, em **português do Brasil**, contando a **história
de desenvolvimento** do projeto **Valida UFSC** — um auditor de equivalências de currículos da
UFSC. O público é a **turma e o professor** da disciplina de *Ciência e Engenharia de Dados*. O
tom é **técnico, mas com storytelling**: além de explicar o que construímos, dê destaque às
**decisões difíceis, ao que descartamos e ao que aprendemos** (essa é a parte mais interessante).

## Design system (use a paleta do projeto)
- **Cor primária (brand):** azul `#3b6fe0` (variações: `#2f5bc4`, `#274ba3`, claros `#eef4ff` e `#d9e6ff`).
- **Cores semânticas:** verde esmeralda `#10b981` = "aproveitamento direto"; azul-céu `#0ea5e9` = "boas chances"; âmbar `#f59e0b` = atenção/carga horária parcial; rosa `#f43f5e` = sem candidata/erro; cinza `slate` (#0f172a a #94a3b8) = textos e neutros.
- **Tipografia:** fonte **Inter** (ou similar sem serifa, moderna).
- **Estilo visual:** limpo e moderno, tipo dashboard SaaS premium — muito espaço em branco, **cards brancos com cantos arredondados (rounded-xl), sombras suaves e borda fina cinza-clara**, ícones simples de linha, gráficos/diagramas minimalistas. Slides de título com fundo azul `#3b6fe0` e texto branco; slides de conteúdo com fundo claro (`#f8fafc`). Logo: um quadrado azul `#3b6fe0` arredondado com a letra **"V"** branca em negrito.

## Estrutura (≈ 18 slides)

1. **Capa** — "Valida UFSC — Auditor de Equivalências de Currículos da UFSC". Subtítulo: "Aproveitamento de disciplinas com pipeline de dados + IA local". Nomes dos autores (deixe placeholders), disciplina "Ciência e Engenharia de Dados", logo "V".
2. **O problema** — Um aluno que quer mudar de curso (ou aproveitar disciplinas) precisa comparar **dois currículos em PDF, matéria por matéria, na mão** — lento, cansativo e propenso a erro. Ilustre com a dor: dezenas de disciplinas, ementas longas.
3. **A ideia** — Uma aplicação web: escolha **curso de origem** e **curso de destino** → receba na hora **quais disciplinas têm chance de validação**. É uma **triagem para o aluno**; a decisão oficial é do **colegiado**. (Opcional: subir o histórico em PDF para análise personalizada.)
4. **O insight que define a arquitetura** — O **código da disciplina é único em toda a UFSC** (`INE5111`, `MTM3110`). Logo, grande parte da equivalência é **determinística** (casar código). A IA só entra no caso difícil: **códigos diferentes com conteúdo parecido** (comparar ementas). Isso deixa o sistema **confiável e barato**.
5. **O critério oficial (a regra do jogo)** — Resolução **17/CUn/97** + **115/2022/CGRAD**: para validar, a origem precisa cobrir **≥ 75% do conteúdo** E **≥ 75% da carga horária**; pode-se **somar 2+ disciplinas (N:1)**. Destaque: **CH é regra objetiva e obrigatória**; conteúdo é mais subjetivo. Quem decide é o colegiado.
6. **Arquitetura geral** — Diagrama do fluxo: `CAGR (JSF) → Scraper (Playwright) → Parser (pdfplumber) → Loader → PostgreSQL + pgvector` e `Frontend (React) ↔ Backend (FastAPI) ↔ Motor de equivalência`, com `Ollama (IA local)` ao lado. Tudo orquestrado por **Docker Compose**.
7. **Stack** — Tabela visual com ícones: Scraping = Python + Playwright; Parsing = pdfplumber; Banco = PostgreSQL 16 + pgvector; Backend = FastAPI + SQLAlchemy + Alembic; IA local = Ollama (`bge-m3` embeddings); Frontend = Vite + React + TypeScript + Tailwind; Orquestração = Docker Compose.
8. **Os 3 pilares** — (1) Pipeline de engenharia de dados; (2) Modelo de matching/NLP; (3) Produto/app polido. Diga que todos precisavam ficar excelentes.
9. **Pilar 1 — Pipeline de dados** — Raspamos **todos os cursos do Campus Florianópolis** (árvore JSF do CAGR). **Descoberta-chave:** o relatório de currículo tem uma **URL pública direta** (`relatorios/curriculoCurso?curso=X&curriculo=Y`) — sem sessão. Resultado: ~**109 cursos**, ~**6.200 disciplinas**, **3.794 equivalências oficiais**.
10. **O desafio do parsing de PDF** — O PDF lista a **ementa acima** de cada linha de disciplina, e a **ordem do texto no PDF ≠ ordem visual**. Resolvemos com **pdfplumber por coordenadas** (reconstruindo a tabela pela posição x/y das palavras, usando tamanho de fonte para separar ementa de dados). Mostre um "antes/depois" (texto bagunçado → tabela estruturada).
11. **O banco de dados (modelo ER)** — Use o **print do diagrama já anexado**. Explique a **`disciplina` canônica por código** (única na UFSC), a junção `curriculo_disciplina` (tipo/fase por currículo), `equivalencia_oficial`, `disciplina_embedding` (vetor 1024-dim, pgvector) e o cache `comparacao`/`comparacao_item`/`comparacao_item_origem` (suporta N:1).
12. **Pilar 2 — O motor de equivalência (em camadas)** — Para cada disciplina de destino, em ordem de confiança: **1) código exato → 2) equivalência oficial → 3) semântico (embeddings) → 4) somatório N:1**. Saída em **2 faixas**: ✅ **Aproveitamento direto** (determinístico) e 🔎 **Boas chances** (semântico, leva ao colegiado).
13. **Decisão difícil #1 — Embedding não decide, só rankeia** — Embeddings medem **proximidade de texto, não equivalência**. Exemplo real: *"Introdução a Algoritmos"* × *"Circuitos e Técnicas Digitais"* deu **73%** só porque as duas repetem a palavra "**lógica**" — mas são coisas diferentes (software × hardware). Lição: o embedding é **peneira**, não juiz.
14. **Decisão difícil #2 — Calibração com gabarito real** — O limiar inicial (0,90) era um **chute** e jogava fora 75% das equivalências reais. **Calibramos com as 3.794 equivalências oficiais da UFSC como gabarito:** equivalências reais ficam em torno de **0,84 (mediana)**; pares aleatórios (ruído) ficam abaixo de **0,67**. → **Corte = 0,70**. (Mostre um gráfico das duas distribuições.)
15. **Decisão difícil #3 — O juiz LLM era inviável na CPU** — Medimos: o LLM levava **~8–30 s por chamada**, paralelizar quase não ajudava, e julgar uma comparação inteira dava **~994 s (16 min)**. **Removemos o juiz LLM do produto.** Aprendizado honesto: na CPU, **modelo pequeno é juiz ruim** — empurra tudo para "ressalva". A comparação ficou **instantânea** sem ele.
16. **Decisão difícil #4 — Recall + a regra dos 75%** — Reposicionamos como **triador de recall** (mostrar o maior leque possível; o colegiado decide). Mas a **CH de 75% é obrigatória**: um isolado abaixo disso que **não dá para somar** é recusa certa → **fica fora** das boas chances. E ligamos o **somatório N:1 na faixa semântica** (ex.: duas de 36h cobrem uma de 72h), permitindo **reuso** da mesma origem em mais de uma sugestão para maximizar o leque.
17. **Qualidade de dados — um perrengue real** — Alguns cursos vinham **vazios**: o scraper pegava a vigência mais nova, que às vezes é um **placeholder de 2027 em branco** no CAGR. Detectamos 6 casos, escrevemos um script que **baixa a vigência mais recente com conteúdo**, corrigimos 5/6 (o 6º não existe na fonte) e passamos a **filtrar currículos vazios** da interface.
18. **Pilar 3 — O produto** — Cópias de tela do app: os **KPIs** (Cobertura, Aproveitamento direto, Boas chances), a tabela em duas faixas, a **visualização da soma** (M1 + M2 = cobre o destino), o upload de histórico, o **formulário oficial pré-preenchido** (PDF da PROGRAD/DAE), o **dark mode** e o link para o **currículo em PDF**. Engenharia: motor **100% testável offline** (dependência injetada), **18 testes**, **Docker Compose**, **seed** do banco para `git clone` rápido, **versionamento de cache**.
19. **Resultados & Futuro** — Números: ~109 cursos, ~6.200 disciplinas, 3.794 equivalências, exemplo **Ciências da Computação → Sistemas de Informação = 82,6% de cobertura**. Já entregues: **formulário oficial pré-preenchido**, **dark mode**, **abrir currículo em PDF**. Futuro: **deploy público**, cobrir **optativas/extensão** e **outros campi**. Encerre com agradecimento.

## Instruções finais
- Cada slide: um **título forte** + 3 a 5 bullets curtos OU um diagrama/figura. Nada de parágrafos longos.
- Use **destaques coloridos** (badges, números grandes) para os dados (0,70; 994 s; 3.794; 82,6%).
- Mantenha consistência visual com a paleta acima em todos os slides.
- Onde eu indiquei "cópia de tela" ou "diagrama", crie um **placeholder elegante** (moldura/mockup) se não houver imagem — eu colo os prints reais depois.

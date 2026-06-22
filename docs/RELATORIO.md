<!--
RELATÓRIO TÉCNICO — Valida UFSC
Para gerar o PDF (com sumário e capa) via pandoc:
  pandoc docs/RELATORIO.md -o RELATORIO.pdf --toc --number-sections -V lang=pt-BR -V geometry:margin=2.5cm
As figuras (architecture, ER, screenshots) estão marcadas como [FIGURA N]; insira os prints reais
nos pontos indicados. Os elementos pré e pós-textuais (capa, resumo, sumário, referências) NÃO
contam para o limite de 10 páginas de conteúdo.
-->

---

<div align="center">

**UNIVERSIDADE FEDERAL DE SANTA CATARINA**
Centro Tecnológico — Disciplina de Ciência e Engenharia de Dados

<br><br><br>

# Valida UFSC
## Auditor de Equivalências de Currículos: um pipeline de dados e IA local para o aproveitamento de disciplinas

<br><br><br>

Autores: **[Nome 1]**, **[Nome 2]**

Professor(a): **[Nome]**

<br><br><br>

Florianópolis, 2026

</div>

---

## Resumo

Estudantes da UFSC que desejam mudar de curso ou aproveitar disciplinas precisam comparar
manualmente dois currículos em PDF, disciplina por disciplina, para descobrir o que pode ser
validado pelo colegiado de destino — um processo lento e propenso a erro. Este trabalho apresenta o
**Valida UFSC**, uma aplicação web que automatiza essa triagem. O sistema integra um **pipeline de
engenharia de dados** (raspagem do sistema acadêmico CAGR com Playwright, extração de PDFs com
pdfplumber e carga em PostgreSQL com a extensão pgvector), um **motor de equivalência híbrido em
camadas** (casamento por código, equivalência oficial declarada, similaridade semântica de ementas
via *embeddings* e somatório N:1 de carga horária) e uma **interface web** em React. O critério de
validação segue as Resoluções 17/CUn/97 e 115/2022/CGRAD da UFSC (≥ 75% de conteúdo e ≥ 75% de carga
horária). O resultado é apresentado em duas faixas de confiança — *aproveitamento direto*
(determinístico) e *boas chances* (semântico) —, reforçando que a decisão oficial é do colegiado. O
limiar semântico foi **calibrado empiricamente** usando as 3.794 equivalências oficiais da própria
UFSC como gabarito. A base cobre ~109 cursos, ~6.200 disciplinas e 4.600 *embeddings*. Todo o
ambiente é reproduzível via Docker Compose.

**Palavras-chave:** engenharia de dados; processamento de linguagem natural; *embeddings*; pgvector;
aproveitamento de disciplinas; UFSC.

---

## Sumário

1. Introdução
2. Critério oficial de equivalência
3. Visão geral da arquitetura
4. Pilar 1 — Pipeline de dados
5. Pilar 2 — Motor de equivalência
6. Backend, API e banco de dados
7. Pilar 3 — Frontend
8. Infraestrutura e reprodutibilidade
9. Decisões de projeto e lições aprendidas
10. Resultados
11. Trabalhos futuros
12. Conclusão
- Referências

---

# 1. Introdução

A mobilidade entre cursos de graduação na UFSC — mudança de curso, retorno de graduado, ou
aproveitamento de disciplinas entre currículos — exige um processo de **aproveitamento de estudos**,
no qual o colegiado do curso de destino avalia se as disciplinas já cursadas pelo estudante
equivalem às do novo currículo. Hoje, o(a) estudante faz esse levantamento **manualmente**,
abrindo os dois currículos em PDF e comparando dezenas de disciplinas e ementas uma a uma. É um
trabalho demorado, repetitivo e sujeito a erros.

Este projeto, desenvolvido na disciplina de **Ciência e Engenharia de Dados**, entrega o **Valida
UFSC**: uma aplicação web na qual o usuário seleciona um **curso de origem** e um **curso de
destino** (cujos currículos já foram coletados e armazenados) e recebe, instantaneamente, uma
**auditoria de equivalência** — quais disciplinas de origem têm chance de validar quais disciplinas
de destino, com o método, a similaridade e a faixa de confiança. Opcionalmente, o(a) estudante pode
enviar seu **histórico escolar** em PDF para restringir a análise ao que já cursou.

O projeto foi estruturado em **três pilares**, todos tratados com igual cuidado: (i) um **pipeline
de engenharia de dados** (coleta, extração, carga e vetorização); (ii) um **modelo de matching**
que combina regras determinísticas e processamento de linguagem natural; e (iii) um **produto** web
polido e funcional.

## 1.1. O insight central

A observação que define toda a arquitetura é simples: **o código de uma disciplina é um
identificador único em toda a UFSC**. `INE5111`, `MTM3110` ou `CIN8001` designam a mesma disciplina
independentemente do currículo em que aparecem. Logo, **mesmo código ⇒ mesma disciplina**, e uma
parcela grande da equivalência é **determinística e auditável**. A inteligência artificial só
precisa atuar no caso difícil: disciplinas com **códigos diferentes**, mas conteúdo potencialmente
equivalente — onde é necessário comparar as **ementas**. Esse recorte torna o sistema confiável,
explicável e barato de operar.

# 2. Critério oficial de equivalência

A validação segue a **Resolução nº 17/CUn/97** (Capítulo VI — Do Aproveitamento de Estudos) e a
**Resolução nº 115/2022/CGRAD**. Consolidando a prática dos colegiados, uma disciplina de destino
D é validada por uma ou mais disciplinas de origem O quando:

- **R1 — Conteúdo:** a(s) ementa(s) de O cobre(m) **≥ 75% do conteúdo** de D (critério subjetivo,
  avaliado por leitura);
- **R2 — Carga horária:** a soma da carga horária de O é **≥ 75% da carga horária** de D (critério
  objetivo e mecânico);
- **R3 — Somatório N:1:** é permitido **somar duas ou mais disciplinas** de origem para cobrir R1 e
  R2;
- **R4 — Autoridade:** a decisão oficial é do **colegiado do curso de destino**; a ferramenta é um
  **auxiliar de triagem**.

Os limiares de 75% são **parâmetros configuráveis** (`.env`), pois variam por colegiado. A
distinção entre R1 (subjetivo) e R2 (objetivo) é central no projeto: a carga horária é tratada como
**filtro rígido**, enquanto a compatibilidade de conteúdo é **aproximada** por IA e sempre remetida
ao colegiado.

# 3. Visão geral da arquitetura

A Figura 1 resume o fluxo do sistema. O pipeline de dados (offline) alimenta o banco; a aplicação
(online) consulta o banco e o motor de equivalência para responder às comparações.

> **[FIGURA 1 — Diagrama de arquitetura/fluxo do sistema]**

```
CAGR (JSF) --Playwright--> Scraper --pdfplumber--> Parser --> Loader --> PostgreSQL + pgvector
                                                                |               ^
                                                          Embeddings (Ollama) --+
 Frontend (React) <--REST--> Backend (FastAPI) --motor em camadas--> +----------+
```

Todos os serviços são orquestrados por **Docker Compose**: banco (`db`), modelos de IA (`ollama`),
API (`backend`), interface (`frontend`) e um job de ETL (`etl`).

# 4. Pilar 1 — Pipeline de dados

O pipeline (`backend/valida_ufsc/etl/`) executa quatro etapas encadeadas em `pipeline.py`.

## 4.1. Raspagem (scraper.py)

O sistema CAGR expõe a árvore de cursos como uma aplicação **JSF/RichFaces** com *ViewState* e
chamadas AJAX, sem *links* estáticos. Usamos **Playwright** (Chromium *headless*) para navegar a
árvore do **Campus Florianópolis** e coletar os pares `(curso, currículo)`. A **descoberta-chave**
foi que o relatório de currículo tem uma **URL pública e direta** —
`relatorios/curriculoCurso?curso=X&curriculo=Y` —, dispensando sessão. Isso permitiu baixar cada
PDF de forma simples e robusta (com *retry* e *rate-limit*).

## 4.2. Extração (parser.py)

O parsing foi o maior desafio técnico do pilar. No PDF de currículo, a **ementa aparece acima** de
cada linha de disciplina e, crucialmente, **a ordem do texto no fluxo do PDF não corresponde à
ordem visual**. Uma extração ingênua produz texto embaralhado. A solução foi um **parser por
coordenadas** com pdfplumber: as palavras são reordenadas pela posição (x, y) na página,
reconstruindo a tabela coluna a coluna (fronteiras de `x0` para código, nome, tipo, H/A, equivalentes,
pré-requisito); o **tamanho da fonte** distingue a linha de dados da linha de ementa. A correção é
validada por ***golden tests*** sobre PDFs de exemplo (contagem e códigos esperados).

## 4.3. Carga (loader.py)

O *loader* normaliza e faz **upsert idempotente**: a `disciplina` é canônica por código (deduplicada
entre currículos), e a junção `curriculo_disciplina` guarda o que varia por currículo (tipo e fase).
A coluna "Equivalentes" do PDF vira a tabela `equivalencia_oficial`. Uma política determinística
("vence o dado mais completo") garante resultado estável independentemente da ordem dos arquivos.

## 4.4. Vetorização (embeddings)

Para cada disciplina com ementa, geramos um ***embedding*** de **1024 dimensões** com o modelo
**`bge-m3`** (multilíngue, via Ollama) e o gravamos em `disciplina_embedding` (tipo `vector` do
pgvector). A geração é **idempotente** via *hash* da ementa: só recalcula quando o texto muda.

# 5. Pilar 2 — Motor de equivalência

O motor (`backend/valida_ufsc/matching/engine.py`) avalia, para **cada disciplina de destino**, as
disciplinas de origem que a validam, em **camadas de confiança decrescente**, parando na primeira que
resolve:

1. **Código exato** — mesmo código UFSC ⇒ disciplina idêntica → *aproveitamento direto*.
2. **Equivalência oficial** — declarada na coluna "Equivalentes" do PDF → *aproveitamento direto*.
3. **Semântico** — similaridade de cosseno entre ementas (via pgvector); acima do **corte
   calibrado (0,70)** → *boa chance*.
4. **Somatório N:1** — quando uma origem isolada não cobre a carga horária, combina-se 2+ origens
   semelhantes até atingir 75%.

A saída é organizada em **duas faixas** apresentadas ao usuário: ✅ **Aproveitamento direto**
(determinístico, alta confiança) e 🔎 **Boas chances** (semântico — leva ao colegiado).

## 5.1. Regra rígida de carga horária

A regra **R2 (75% de CH)** é aplicada como **filtro objetivo**: um candidato semântico cuja carga
horária — sozinho ou somado (N:1) — não atinge 75% da disciplina de destino é **removido** das "boas
chances" (seria recusa certa do colegiado). Mantêm-se apenas os casos que cobrem a CH ou cuja carga
do destino é desconhecida.

## 5.2. Orientação a *recall* e reuso

Como a ferramenta é um **triador para o aluno**, a faixa semântica é orientada a ***recall***:
busca-se o maior leque de candidatas plausíveis. Por isso, na faixa "boas chances" a mesma disciplina
de origem **pode ser sugerida para mais de uma disciplina de destino** (o colegiado valida cada origem
em apenas uma). Na faixa determinística (código/oficial), mantém-se a relação 1:1.

## 5.3. Testabilidade

A função de similaridade é **injetada como dependência** no motor, que assim é **100% testável
offline** (sem banco nem rede). São **18 testes** unitários cobrindo as camadas, a regra de CH, o
somatório N:1, o reuso, a calibração e regressões de revisão adversarial.

# 6. Backend, API e banco de dados

O backend é uma API **FastAPI** com **SQLAlchemy 2.0** e migrações **Alembic**. Os principais
endpoints são: `GET /cursos` (popula os seletores, **filtrando currículos vazios**); `POST
/comparacoes` (auditoria, com **cache** por par de currículos e parâmetros); `POST /historico`
(upload e parsing do histórico); e `POST /comparacoes/personalizada` (análise restrita às disciplinas
aprovadas pelo aluno).

O **modelo de dados** (PostgreSQL 16 + pgvector) está na Figura 2:

> **[FIGURA 2 — Diagrama Entidade-Relacionamento do banco]** *(print já anexado no Claude Design)*

Tabelas principais: `curso`, `curriculo` (vigência, habilitação, carga total, *flag* `vigente`),
`disciplina` (canônica por código, com ementa e CH), `curriculo_disciplina` (junção tipo/fase),
`equivalencia_oficial`, `disciplina_embedding` (`vector(1024)` com índice **HNSW**), e o cache de
comparações `comparacao` / `comparacao_item` / `comparacao_item_origem` — este último permitindo
**múltiplas origens por item** (suporte ao somatório N:1).

O **cache** de comparações é versionado: a chave (`params_hash`) inclui uma **versão do motor**, de
modo que qualquer mudança na lógica **invalida o cache automaticamente**.

# 7. Pilar 3 — Frontend

A interface (`frontend/`) é uma **tela única** em **Vite + React + TypeScript + Tailwind**. No painel
esquerdo: seletores de grade de origem/destino, *upload* opcional do histórico e legenda. Na área
principal: **cartões de KPI** (Cobertura, Aproveitamento direto, Boas chances), e a tabela de
auditoria **dividida nas duas faixas**, com método, badge de carga horária, barra de similaridade e
busca. As **somas N:1** são visualizadas explicitamente (ex.: `M1 (36h) + M2 (36h) = 72h · cobre 72h
do destino`).

> **[FIGURA 3 — Cópia de tela do app: KPIs e tabela em duas faixas]**
> **[FIGURA 4 — Cópia de tela: visualização do somatório N:1]**

# 8. Infraestrutura e reprodutibilidade

Todo o sistema sobe com **Docker Compose** (serviços `db`, `ollama`, `backend`, `frontend` e o job
`etl`). Para que um colega clone e rode rapidamente, geramos um ***seed*** do banco (`pg_dump`
comprimido) restaurável em ~1 minuto, evitando re-raspar o CAGR e re-gerar *embeddings*. A
configuração é centralizada em `.env` (URLs, modelos, limiares). Veja o `README.md` para o passo a
passo.

# 9. Decisões de projeto e lições aprendidas

Esta seção é o coração do relatório técnico: as escolhas não óbvias e o que descartamos.

**9.1. *Embedding* rankeia, não decide.** Embeddings medem **proximidade de texto**, não equivalência
curricular. Caso real: *"Introdução a Algoritmos"* × *"Circuitos e Técnicas Digitais"* obteve **0,73**
de similaridade apenas por compartilharem a palavra "lógica" (problemas *lógicos* × portas *lógicas*),
embora sejam software × hardware. Conclusão: o *embedding* é **peneira** (recupera candidatos), nunca
juiz.

**9.2. Calibração com gabarito real.** O limiar inicial de **0,90** foi um chute e descartava ~75%
das equivalências verdadeiras (o `bge-m3` **comprime** a similaridade numa faixa estreita). Usamos as
**3.794 equivalências oficiais da UFSC** como gabarito: medimos que pares de fato equivalentes têm
similaridade com **mediana 0,84** (p25 = 0,75), enquanto pares aleatórios (ruído) ficam abaixo de
**0,67** (percentil 99). O corte foi então fixado de forma fundamentada em **0,70**.

**9.3. O juiz LLM era inviável na CPU.** Medimos que o LLM local (`qwen2.5:3b`) levava **~8–30 s por
chamada**, com ganho de paralelismo de apenas ~1,5×; julgar uma comparação inteira de uma vez levava
**~994 s (16 min)**. Além de lento, um modelo pequeno é **cauteloso demais** (classifica quase tudo
como "ressalva"). **Decisão:** **remover o juiz LLM do produto** e tornar a comparação
**instantânea** com a régua calibrada (o componente fica registrado aqui apenas como aprendizado).
Lição: a restrição de hardware (CPU sem GPU) deve guiar o design — não dá para fingir que um
componente lento é rápido.

**9.4. *Recall* + carga horária obrigatória.** Reposicionamos a ferramenta como **triador de recall**
(mostrar o máximo de candidatas plausíveis), mas com a **CH de 75% como filtro rígido**: itens que
nunca atingiriam 75% (mesmo somando) seriam recusa garantida e foram removidos. Ligamos o **somatório
N:1 também na faixa semântica** e permitimos **reuso** de origem entre destinos, maximizando o leque
sem inflar com casos inválidos.

**9.5. Qualidade de dados — currículos vazios.** Seis cursos vinham **sem disciplinas**: o scraper
pegava a **vigência mais nova**, que em alguns casos é um **placeholder de 2027 ainda em branco** no
CAGR. Detectamos os casos por consulta SQL, criamos um script (`fix_empty_curriculos.py`) que **baixa
a vigência mais recente com conteúdo** e corrigimos 5 de 6 (o sexto não existe na fonte). Como
blindagem permanente, a interface passou a **ocultar currículos vazios**.

# 10. Resultados

A base final cobre **~109 cursos** do Campus Florianópolis, **~6.200 disciplinas** canônicas,
**~4.600 embeddings** de ementas e **3.794 equivalências oficiais**. As comparações são respondidas
em ~1 segundo (instantâneas). Como exemplo de validação ponta a ponta, a comparação **Ciências da
Computação → Sistemas de Informação** atinge **82,6% de cobertura** (disciplinas de destino com ao
menos uma candidata), com 23 aproveitamentos diretos e 15 boas chances — coerente com a forte
sobreposição entre os dois cursos. O motor é coberto por **18 testes** automatizados.

Na camada de produto, além da triagem em duas faixas, a aplicação entrega o **formulário oficial de
validação pré-preenchido** (preenche o PDF da PROGRAD/DAE com os dados do aluno e os códigos
sugeridos), **modo escuro** e **link direto ao currículo em PDF** do CAGR.

# 11. Trabalhos futuros

- **Deploy público** (aplicação + banco com *seed* hospedados), para uso fora do ambiente local.
- **Cobertura além das obrigatórias** — incluir optativas e atividades de extensão na análise.
- **Outros campi** da UFSC (hoje o escopo é o Campus Florianópolis).

# 12. Conclusão

O Valida UFSC demonstra, de ponta a ponta, os três pilares da disciplina: um **pipeline de dados**
real (raspagem, extração de PDF por coordenadas, carga canônica e vetorização), um **modelo de
matching** que combina regras determinísticas e NLP com limiar **calibrado por dados**, e um
**produto** funcional e honesto, que respeita o papel do colegiado. As decisões mais valiosas vieram
de **medir a realidade** (a lentidão do LLM, a compressão dos *embeddings*, os currículos vazios) e
**ajustar o projeto a ela**, em vez de insistir em um desenho idealizado. O resultado é uma ferramenta
instantânea, explicável e reproduzível.

---

## Referências

UNIVERSIDADE FEDERAL DE SANTA CATARINA. **Resolução nº 17/CUn/97**: dispõe sobre o Regulamento dos
Cursos de Graduação (Cap. VI — Do Aproveitamento de Estudos). Florianópolis, 1997.

UNIVERSIDADE FEDERAL DE SANTA CATARINA. **Resolução Normativa nº 115/2022/CGRAD**: aproveitamento de
estudos nos cursos de graduação. Florianópolis, 2022.

PGVECTOR. **pgvector: open-source vector similarity search for Postgres**. Disponível em:
https://github.com/pgvector/pgvector.

OLLAMA. **Ollama — run large language models locally**. Disponível em: https://ollama.com.

BAAI. **BGE-M3: multilingual embedding model**. Disponível em: https://huggingface.co/BAAI/bge-m3.

FASTAPI. **FastAPI framework**. Disponível em: https://fastapi.tiangolo.com.

PDFPLUMBER. **pdfplumber: plumb a PDF for detailed information**. Disponível em:
https://github.com/jsvine/pdfplumber.

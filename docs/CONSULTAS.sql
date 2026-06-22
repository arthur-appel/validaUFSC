-- Consultas de exploração do banco Valida UFSC (rode no DBeaver, conectado em valida_ufsc).
-- Elas "andam" pelo schema: catálogo -> embeddings -> auditoria.

-- 1) Cursos e currículos vigentes carregados
SELECT c.codigo, c.nome, cur.codigo_vigencia, cur.vigente,
       (SELECT count(*) FROM curriculo_disciplina cd WHERE cd.curriculo_id = cur.id) AS qtd_disciplinas
FROM curso c
JOIN curriculo cur ON cur.curso_id = c.id
ORDER BY c.nome;

-- 2) Disciplinas de um currículo, por fase (troque o código do curso)
SELECT cd.fase, d.codigo, d.nome, cd.tipo, d.carga_horaria_ha
FROM curriculo cur
JOIN curso c               ON c.id = cur.curso_id
JOIN curriculo_disciplina cd ON cd.curriculo_id = cur.id
JOIN disciplina d          ON d.id = cd.disciplina_id
WHERE c.codigo = '208'
ORDER BY cd.fase NULLS LAST, d.codigo;

-- 3) Disciplinas que aparecem em MAIS DE UM currículo (o insight: código UFSC-wide)
SELECT d.codigo, d.nome, count(*) AS em_n_curriculos
FROM disciplina d
JOIN curriculo_disciplina cd ON cd.disciplina_id = d.id
GROUP BY d.codigo, d.nome
HAVING count(*) > 1
ORDER BY em_n_curriculos DESC, d.codigo;

-- 4) Equivalências oficiais declaradas nos PDFs
SELECT d.codigo AS disciplina, e.equivalente_codigo AS equivalente
FROM equivalencia_oficial e
JOIN disciplina d ON d.id = e.disciplina_id
ORDER BY d.codigo;

-- 5) Quantas disciplinas já têm embedding (camada semântica)
SELECT (SELECT count(*) FROM disciplina WHERE ementa IS NOT NULL) AS com_ementa,
       (SELECT count(*) FROM disciplina_embedding)                AS com_embedding;

-- 6) Resultado de uma auditoria (a mais recente) — destino, origem(ns), método e status
SELECT dd.codigo AS destino, dd.nome AS destino_nome,
       i.metodo, i.status, round(i.similaridade*100) AS sim_pct,
       i.ch_ok, round(i.ch_cobertura_pct*100) AS ch_pct,
       string_agg(do.codigo, ' + ') AS origens
FROM comparacao cmp
JOIN comparacao_item i           ON i.comparacao_id = cmp.id
JOIN disciplina dd               ON dd.id = i.disciplina_destino_id
LEFT JOIN comparacao_item_origem io ON io.item_id = i.id
LEFT JOIN disciplina do          ON do.id = io.disciplina_origem_id
WHERE cmp.id = (SELECT max(id) FROM comparacao)
GROUP BY dd.codigo, dd.nome, i.metodo, i.status, i.similaridade, i.ch_ok, i.ch_cobertura_pct
ORDER BY i.status, sim_pct DESC;

-- 7) Resumo (KPIs) da auditoria mais recente
SELECT i.status, count(*) AS qtd
FROM comparacao_item i
WHERE i.comparacao_id = (SELECT max(id) FROM comparacao)
GROUP BY i.status;

-- 8) Casos de somatório N:1 (um destino coberto por 2+ origens)
SELECT dd.codigo AS destino, count(io.id) AS n_origens, string_agg(do.codigo, ' + ') AS origens
FROM comparacao_item i
JOIN disciplina dd ON dd.id = i.disciplina_destino_id
JOIN comparacao_item_origem io ON io.item_id = i.id
JOIN disciplina do ON do.id = io.disciplina_origem_id
GROUP BY i.id, dd.codigo
HAVING count(io.id) > 1;

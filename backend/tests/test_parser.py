"""Golden tests do parser de currículo contra os 2 PDFs de exemplo."""

from valida_ufsc.etl.parser import parse_curriculo_pdf


def _by_code(curr):
    return {d.codigo: d for d in curr.disciplinas}


def test_curso_origem_cabecalho(curso_origem_pdf):
    c = parse_curriculo_pdf(curso_origem_pdf)
    assert c.curso_codigo == "349"
    assert "CIÊNCIA DE DADOS" in c.curso_nome
    assert c.codigo_vigencia == "20261"
    assert c.carga_total_ha == 2520


def test_curso_origem_disciplinas(curso_origem_pdf):
    c = parse_curriculo_pdf(curso_origem_pdf)
    # 52 disciplinas com código (placeholders "- Disciplina Optativa" são ignorados)
    assert len(c.disciplinas) == 52
    d = _by_code(c)

    # Códigos UFSC-wide que também aparecem no outro currículo / histórico
    assert "MTM3110" in d
    assert "INE5111" in d

    prog1 = d["CIN8001"]
    assert prog1.nome == "Programação I"
    assert prog1.tipo == "Ob"
    assert prog1.fase == 1
    assert prog1.carga_horaria_ha == 108
    assert prog1.aulas == 6
    assert "Algoritmos" in prog1.ementa

    # Pré-requisito multi-token correto
    assert "CIN8001" in d["CIN8004"].pre_requisito

    # Optativa sem fase
    assert d["CIN8017"].tipo == "Op"
    assert d["CIN8017"].fase is None


def test_curso_destino_cabecalho(curso_destino_pdf):
    c = parse_curriculo_pdf(curso_destino_pdf)
    assert c.curso_codigo == "208"
    assert "COMPUTAÇÃO" in c.curso_nome
    assert c.codigo_vigencia == "20071"


def test_curso_destino_equivalencias_oficiais(curso_destino_pdf):
    c = parse_curriculo_pdf(curso_destino_pdf)
    d = _by_code(c)

    # Equivalências oficiais declaradas na coluna "Equivalentes" do PDF
    assert "INE5382" in d["INE5402"].equivalentes
    assert "INE5603" in d["INE5402"].equivalentes
    assert "MTM3101" in d["MTM3110"].equivalentes

    # MTM3110 é o mesmo código nos dois cursos (match determinístico por código)
    assert d["MTM3110"].nome == "Cálculo 1"


def test_codigo_compartilhado_entre_cursos(curso_origem_pdf, curso_destino_pdf):
    origem = _by_code(parse_curriculo_pdf(curso_origem_pdf))
    destino = _by_code(parse_curriculo_pdf(curso_destino_pdf))
    # Insight central: mesmo código => mesma disciplina (base do match determinístico)
    assert "MTM3110" in origem and "MTM3110" in destino
    assert origem["MTM3110"].nome == destino["MTM3110"].nome

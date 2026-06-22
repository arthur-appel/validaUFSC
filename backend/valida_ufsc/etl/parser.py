"""Parser dos PDFs de currículo do CAGR (relatório SeTIC "Currículo do Curso").

Estratégia baseada em coordenadas (robusta ao embaralhamento do content-stream):
- O pdfplumber concatena caracteres na ordem do content-stream, que NÃO é a ordem
  visual. Por isso reconstruímos cada linha ordenando as palavras por `x0` e mapeando
  para colunas por faixa de `x0` (o template SeTIC tem posições de coluna fixas).
- O tamanho da fonte separa os papéis das linhas:
    size ~12  -> cabeçalho de Fase / Rol de seção
    size ~9   -> cabeçalho do curso (Curso/Currículo/Habilitação)
    size ~8   -> linha de dados da disciplina (ou continuação de nome/equiv/pré-req)
    size ~7   -> ementa (vem ACIMA da linha de código)

Colunas (x0), validadas nos PDFs de exemplo (idênticas entre currículos):
    código:        40        nome: 82..~230
    Tipo:          ~256      H/A: ~286      Aulas: ~320
    Equivalentes:  ~349      Pré-Requisito: ~419
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

CODE_RE = re.compile(r"^[A-Z]{3}\d{4}$")
CODE_IN_RE = re.compile(r"[A-Z]{3}\d{4}")
TIPOS = {"Ob", "Op", "Es", "Ex"}

# Limites de coluna por x0.
_X_NAME = 250
_X_TIPO = 282
_X_HA = 312
_X_AULAS = 345
_X_EQUIV = 417
_X_PREREQ = 483


@dataclass
class DisciplinaParse:
    codigo: str
    nome: str
    tipo: str
    fase: int | None
    carga_horaria_ha: int | None
    aulas: int | None
    ementa: str
    equivalentes: list[str] = field(default_factory=list)
    pre_requisito: str = ""


@dataclass
class CurriculoParse:
    curso_codigo: str
    curso_nome: str
    codigo_vigencia: str
    habilitacao: str | None
    titulacao: str | None
    carga_total_ha: int | None
    disciplinas: list[DisciplinaParse] = field(default_factory=list)


@dataclass
class _Line:
    top: float
    size: float
    words: list[dict]  # ordenadas por x0
    text: str


def _clean(s: str) -> str:
    s = s.replace("(cid:9)", " ")
    return re.sub(r"\s+", " ", s).strip()


def _group_lines(page) -> list[_Line]:
    words = page.extract_words(extra_attrs=["size", "fontname"], use_text_flow=False)
    buckets: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        buckets[round(w["top"])].append(w)
    lines: list[_Line] = []
    for top in sorted(buckets):
        ws = sorted(buckets[top], key=lambda w: w["x0"])
        size = max(w["size"] for w in ws)
        text = _clean(" ".join(w["text"] for w in ws))
        lines.append(_Line(top=top, size=size, words=ws, text=text))
    return lines


def _columns(words: list[dict]) -> dict[str, list[str]]:
    cols: dict[str, list[str]] = {
        "name": [], "tipo": [], "ha": [], "aulas": [], "equiv": [], "prereq": []
    }
    for w in words:
        x, t = w["x0"], w["text"]
        if x < _X_NAME:
            cols["name"].append(t)
        elif x < _X_TIPO:
            cols["tipo"].append(t)
        elif x < _X_HA:
            cols["ha"].append(t)
        elif x < _X_AULAS:
            cols["aulas"].append(t)
        elif x < _X_EQUIV:
            cols["equiv"].append(t)
        elif x < _X_PREREQ:
            cols["prereq"].append(t)
    return cols


def _to_int(tokens: list[str]) -> int | None:
    for t in tokens:
        if t.isdigit():
            return int(t)
    return None


def _fase_num(text: str) -> int | None:
    m = re.search(r"(\d+)\s*ª\s*Fase", text) or re.search(r"\bFase\s+0*(\d+)", text)
    return int(m.group(1)) if m else None


def _is_section(text: str) -> bool:
    return bool(
        re.search(r"Rol de Disciplinas Optativas", text)
        or re.fullmatch(r"Disciplinas Optativas", text)
        or re.search(r"Atividades de Extens", text)
        or re.search(r"Atividades Complementares", text)
    )


def _parse_header(lines: list[_Line], full_text: str) -> dict:
    page_text = "\n".join(line.text for line in lines)
    curso = re.search(r"Curso:\s*(\d+)\s*-\s*([^\n]+)", page_text)
    curric = re.search(r"Currículo:\s*(\w+)", page_text)
    hab = re.search(r"Habilitação:\s*([^\n]+)", page_text)
    tit = re.search(r"Titulação:\s*([^\n]+)", page_text)
    # carga total: tenta o resumo "Total: NNNNh-a"; fallback no header "UFSC: NNNN H/A"
    total = re.search(r"Total:\s*(\d+)\s*h-a", full_text) or re.search(
        r"UFSC:\s*(\d+)\s*H/A", page_text
    )
    return {
        "curso_codigo": curso.group(1) if curso else "",
        "curso_nome": _clean(curso.group(2)) if curso else "",
        "codigo_vigencia": curric.group(1) if curric else "",
        "habilitacao": _clean(hab.group(1)) if hab else None,
        "titulacao": _clean(tit.group(1)) if tit else None,
        "carga_total_ha": int(total.group(1)) if total else None,
    }


def parse_curriculo_pdf(path: str | Path) -> CurriculoParse:
    path = Path(path)
    with pdfplumber.open(path) as pdf:
        pages_lines = [_group_lines(p) for p in pdf.pages]

    if not pages_lines:
        raise ValueError("PDF de currículo sem páginas legíveis.")

    full_text = "\n".join(line.text for pl in pages_lines for line in pl)
    header = _parse_header(pages_lines[0], full_text)

    result = CurriculoParse(
        curso_codigo=header["curso_codigo"],
        curso_nome=header["curso_nome"],
        codigo_vigencia=header["codigo_vigencia"],
        habilitacao=header["habilitacao"],
        titulacao=header["titulacao"],
        carga_total_ha=header["carga_total_ha"],
    )

    current_fase: int | None = None
    ementa_buf: list[str] = []
    current_disc: DisciplinaParse | None = None
    last_top = -100.0

    for lines in pages_lines:
        # evita vazamento de ementa/continuação entre páginas
        ementa_buf.clear()
        current_disc = None
        for line in lines:
            text = line.text
            if not text or "SeTIC" in text:
                continue
            size = line.size

            if size >= 11:  # cabeçalho de Fase / Rol de seção
                fnum = _fase_num(text)
                if fnum is not None:
                    current_fase = fnum
                elif _is_section(text):
                    current_fase = None
                current_disc = None
                ementa_buf.clear()
                continue

            if size >= 8.6:  # cabeçalho do curso (Curso/Currículo/Habilitação) — ignora no corpo
                continue

            if size < 7.6:  # ementa
                if not text.startswith("(*)"):  # ignora notas de rodapé
                    ementa_buf.append(text)
                continue

            # --- linha de dados (size ~8) ---
            cols = _columns(line.words)
            names = cols["name"]
            if names and names[0] == "Disciplina":  # linha de cabeçalho da tabela
                current_disc = None
                ementa_buf.clear()
                continue

            tipo = cols["tipo"][0] if cols["tipo"] else None
            code = names[0] if names and CODE_RE.match(names[0]) else None

            if tipo in TIPOS:
                # nova disciplina (ou placeholder "- Disciplina Optativa")
                ementa = _clean(" ".join(ementa_buf))
                ementa_buf.clear()
                if code is None:
                    current_disc = None
                    continue
                disc = DisciplinaParse(
                    codigo=code,
                    nome=_clean(" ".join(names[1:])),
                    tipo=tipo,
                    fase=current_fase,
                    carga_horaria_ha=_to_int(cols["ha"]),
                    aulas=_to_int(cols["aulas"]),
                    ementa=ementa,
                    equivalentes=CODE_IN_RE.findall(" ".join(cols["equiv"])),
                    pre_requisito=_clean(" ".join(cols["prereq"])),
                )
                result.disciplinas.append(disc)
                current_disc = disc
                last_top = line.top
            else:
                # continuação de nome / equivalentes / pré-requisito da disciplina atual
                if current_disc is not None and (line.top - last_top) < 16:
                    if names:
                        current_disc.nome = _clean(current_disc.nome + " " + " ".join(names))
                    if cols["equiv"]:
                        current_disc.equivalentes += CODE_IN_RE.findall(" ".join(cols["equiv"]))
                    if cols["prereq"]:
                        current_disc.pre_requisito = _clean(
                            current_disc.pre_requisito + " " + " ".join(cols["prereq"])
                        )
                    last_top = line.top

    # dedup de equivalentes preservando ordem
    for d in result.disciplinas:
        d.equivalentes = list(dict.fromkeys(d.equivalentes))

    return result


# ─────────────────────────── Histórico escolar ───────────────────────────

# Colunas do histórico (x0), validadas no PDF de exemplo:
#   código: 20   nome: 52..~170   Nota: ~220   H/A: ~238   Fr: ~251   Tipo: ~267
_H_CODE = 50
_H_NOME = 210
_H_NOTA = 236
_H_HA = 250
_H_FR = 263


@dataclass
class HistoricoDisciplinaParse:
    codigo: str
    nome: str
    nota: float | None
    carga_horaria_ha: int | None
    fr: str | None
    tipo: str | None
    aprovado: bool


@dataclass
class HistoricoParse:
    aluno: str | None
    curso_codigo: str
    curso_nome: str
    codigo_vigencia: str
    disciplinas: list[HistoricoDisciplinaParse] = field(default_factory=list)


def _historico_columns(words: list[dict]) -> dict[str, list[str]]:
    cols: dict[str, list[str]] = {"name": [], "nota": [], "ha": [], "fr": [], "tipo": []}
    for w in words:
        x, t = w["x0"], w["text"]
        if x < _H_CODE:
            continue  # código tratado à parte
        if x < _H_NOME:
            cols["name"].append(t)
        elif x < _H_NOTA:
            cols["nota"].append(t)
        elif x < _H_HA:
            cols["ha"].append(t)
        elif x < _H_FR:
            cols["fr"].append(t)
        else:
            cols["tipo"].append(t)
    return cols


def parse_historico_pdf(path: str | Path, nota_aprovacao: float = 6.0) -> HistoricoParse:
    path = Path(path)
    with pdfplumber.open(path) as pdf:
        pages_lines = [_group_lines(p) for p in pdf.pages]

    if not pages_lines:
        return HistoricoParse(aluno=None, curso_codigo="", curso_nome="", codigo_vigencia="")

    page_text = "\n".join(line.text for line in pages_lines[0])
    aluno = re.search(r"Aluno:\s*([^\n]+)", page_text)
    curso = re.search(r"Curso:\s*(\d+)\s*-?\s*([^\n]+)", page_text)
    curric = re.search(r"Currículo:\s*(\S+)", page_text)

    result = HistoricoParse(
        aluno=_clean(aluno.group(1)) if aluno else None,
        curso_codigo=curso.group(1) if curso else "",
        curso_nome=_clean(curso.group(2)) if curso else "",
        codigo_vigencia=curric.group(1) if curric else "",
    )

    for lines in pages_lines:
        for line in lines:
            ws = line.words
            if not ws:
                continue
            first = ws[0]
            if first["x0"] >= _H_CODE or not CODE_RE.match(first["text"]):
                continue  # não é linha de disciplina
            cols = _historico_columns(ws)
            nota = None
            for tok in cols["nota"]:
                try:
                    nota = float(tok.replace(",", "."))
                    break
                except ValueError:
                    pass
            fr = cols["fr"][0] if cols["fr"] else None
            tipo = cols["tipo"][0] if cols["tipo"] else None
            aprovado = fr == "FS" and nota is not None and nota >= nota_aprovacao
            result.disciplinas.append(
                HistoricoDisciplinaParse(
                    codigo=first["text"],
                    nome=_clean(" ".join(cols["name"])),
                    nota=nota,
                    carga_horaria_ha=_to_int(cols["ha"]),
                    fr=fr,
                    tipo=tipo,
                    aprovado=aprovado,
                )
            )

    return result

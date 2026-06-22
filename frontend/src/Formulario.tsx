import { useEffect, useMemo, useRef, useState } from "react";
import type { Comparacao, HistoricoResp, Item } from "./types";

// Carimbamos o texto SOBRE o PDF oficial da PROGRAD/DAE (o mesmo arquivo enviado,
// servido em /public). O resultado é o documento oficial idêntico, só preenchido.
const TEMPLATE_URL = "/formulario-validacao-ufsc.pdf";

// O PDF oficial é um AcroForm: preenchemos os CAMPOS nomeados (não desenhamos por cima).
const CAMPO_PESSOAL = {
  curso: "CURSO",
  nome: "NOME",
  email: "EMAIL",
  cpf: "CPF",
  matricula: "MATRÍCULA",
  tel1: "TELEFONE 1",
  tel2: "TELEFONE 2",
  exAluno: "EXALUNO DA UFSC MATRÍCULA ANTERIOR",
} as const;

// 52 campos "Cod N" = 13 linhas × 4 (esq.cursada, esq.validar, dir.cursada, dir.validar).
const CAPACIDADE = 26; // 13 linhas × 2 blocos = 26 pares
const FONTE_CAMPO = 10;
const FONTE_CELULA = 9;

type Par = { cursada: string; validar: string };

// par i -> [campo cursada, campo validar]. Bloco esquerdo (i<13) preenche de cima para
// baixo; depois o bloco direito. Campos numerados row-major: 4r+1..4r+4.
function camposDoPar(i: number): [string, string] {
  if (i < 13) return [`Cod ${4 * i + 1}`, `Cod ${4 * i + 2}`];
  const r = i - 13;
  return [`Cod ${4 * r + 3}`, `Cod ${4 * r + 4}`];
}

// pdf-lib + Helvetica padrão = WinAnsi (Latin-1). Remove o que estiver fora da faixa.
function winAnsi(s: string): string {
  // eslint-disable-next-line no-control-regex
  return s.replace(/[^\x00-\xFF]/g, "");
}

function construirPares(itens: Item[]): Par[] {
  const pares: Par[] = [];
  for (const it of itens) {
    for (const o of it.origens) {
      pares.push({ cursada: o.disciplina.codigo, validar: it.destino.codigo });
    }
  }
  return pares;
}

/** Preenche o PDF oficial de validação de disciplinas e dispara o download. */
export function Formulario({
  comp,
  historico,
  onClose,
}: {
  comp: Comparacao;
  historico: HistoricoResp | null;
  onClose: () => void;
}) {
  const [curso, setCurso] = useState(comp.destino.curso_nome);
  const [nome, setNome] = useState(historico?.aluno ?? "");
  const [email, setEmail] = useState("");
  const [cpf, setCpf] = useState("");
  const [matricula, setMatricula] = useState("");
  const [tel1, setTel1] = useState("");
  const [tel2, setTel2] = useState("");
  const [exAluno, setExAluno] = useState("");
  const [incluirBoas, setIncluirBoas] = useState(true);
  const [gerando, setGerando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const painelRef = useRef<HTMLDivElement>(null);

  // Modal acessível: trava o scroll, foca o diálogo, prende o Tab, fecha no Escape.
  useEffect(() => {
    const focoAnterior = document.activeElement as HTMLElement | null;
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focaveis = () =>
      Array.from(
        painelRef.current?.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );

    painelRef.current?.focus();

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const f = focaveis();
      if (f.length === 0) return;
      const idx = f.indexOf(document.activeElement as HTMLElement);
      if (e.shiftKey && idx <= 0) {
        e.preventDefault();
        f[f.length - 1].focus();
      } else if (!e.shiftKey && (idx === -1 || idx === f.length - 1)) {
        e.preventDefault();
        f[0].focus();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflowAnterior;
      focoAnterior?.focus?.();
    };
  }, [onClose]);

  const diretas = useMemo(
    () => comp.itens.filter((i) => i.tier === "direto" && i.origens.length > 0),
    [comp],
  );
  const boas = useMemo(
    () => comp.itens.filter((i) => i.tier === "boa_chance" && i.origens.length > 0),
    [comp],
  );
  const selecionadas = incluirBoas ? [...diretas, ...boas] : diretas;
  const pares = useMemo(() => construirPares(selecionadas), [selecionadas]);
  const excedente = Math.max(0, pares.length - CAPACIDADE);

  async function baixar() {
    setGerando(true);
    setErro(null);
    try {
      // pdf-lib só é carregado quando o usuário gera o formulário (code-splitting).
      const [{ PDFDocument }, bytes] = await Promise.all([
        import("pdf-lib"),
        fetch(TEMPLATE_URL).then((r) => {
          if (!r.ok) throw new Error(`template ${r.status}`);
          return r.arrayBuffer();
        }),
      ]);
      const pdf = await PDFDocument.load(bytes);
      const form = pdf.getForm();

      const set = (nomeCampo: string, valor: string, size: number) => {
        const v = winAnsi(valor).trim();
        if (!v) return;
        let field;
        try {
          field = form.getTextField(nomeCampo);
        } catch {
          return; // campo inexistente (template divergente)
        }
        let texto = v;
        const max = field.getMaxLength();
        if (typeof max === "number" && max > 0 && texto.length > max) {
          // ex.: TELEFONE tem maxLength=11 — tira separadores e, se ainda exceder, trunca
          const compacto = texto.replace(/[^0-9A-Za-z]/g, "");
          texto = compacto.length <= max ? compacto : compacto.slice(0, max);
        }
        try {
          field.setFontSize(size);
          field.setText(texto);
        } catch {
          /* ignora campo problemático */
        }
      };

      set(CAMPO_PESSOAL.curso, curso, FONTE_CAMPO);
      set(CAMPO_PESSOAL.nome, nome, FONTE_CAMPO);
      set(CAMPO_PESSOAL.email, email, FONTE_CAMPO);
      set(CAMPO_PESSOAL.cpf, cpf, FONTE_CAMPO);
      set(CAMPO_PESSOAL.matricula, matricula, FONTE_CAMPO);
      set(CAMPO_PESSOAL.tel1, tel1, FONTE_CAMPO);
      set(CAMPO_PESSOAL.tel2, tel2, FONTE_CAMPO);
      set(CAMPO_PESSOAL.exAluno, exAluno, FONTE_CAMPO);

      pares.slice(0, CAPACIDADE).forEach((p, i) => {
        const [campoCursada, campoValidar] = camposDoPar(i);
        set(campoCursada, p.cursada, FONTE_CELULA);
        set(campoValidar, p.validar, FONTE_CELULA);
      });

      const out = await pdf.save();
      const blob = new Blob([out as BlobPart], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `validacao-disciplinas-${comp.destino.curso_codigo}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErro(
        `Não foi possível gerar o PDF: ${(e as Error).message}. ` +
          "Confirme que o arquivo do formulário está em frontend/public.",
      );
    } finally {
      setGerando(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex justify-center overflow-y-auto bg-slate-900/60 p-4 backdrop-blur-sm sm:p-8"
      role="dialog"
      aria-modal="true"
      aria-label="Gerar formulário oficial de validação de disciplinas"
      onClick={onClose}
    >
      <div
        ref={painelRef}
        tabIndex={-1}
        className="my-auto w-full max-w-2xl rounded-xl bg-white shadow-2xl outline-none ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4 dark:border-slate-800">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Formulário oficial de validação de disciplinas
            </h2>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              Preenche o PDF oficial da PROGRAD/DAE (idêntico ao original) com seus dados e os códigos
              sugeridos, pronto para o colegiado.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Fechar"
            className="shrink-0 rounded-lg px-2 py-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            ✕
          </button>
        </header>

        <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
          {/* Dados pessoais (editáveis) */}
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            Seus dados (editáveis)
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Campo label="Curso" valor={curso} onChange={setCurso} full />
            <Campo label="Nome" valor={nome} onChange={setNome} full />
            <Campo label="E-mail" valor={email} onChange={setEmail} />
            <Campo label="CPF" valor={cpf} onChange={setCpf} />
            <Campo label="Matrícula" valor={matricula} onChange={setMatricula} />
            <Campo label="Matrícula anterior (ex-aluno)" valor={exAluno} onChange={setExAluno} />
            <Campo label="Telefone 1" valor={tel1} onChange={setTel1} />
            <Campo label="Telefone 2" valor={tel2} onChange={setTel2} />
          </div>

          {/* Prévia dos códigos */}
          <div className="mt-5 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              Disciplinas a validar ({selecionadas.length})
            </p>
            <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
              <input
                type="checkbox"
                checked={incluirBoas}
                onChange={(e) => setIncluirBoas(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-500 focus:ring-brand-400 dark:border-slate-600 dark:bg-slate-800"
              />
              Incluir boas chances ({boas.length})
            </label>
          </div>

          <div className="mt-2 overflow-hidden rounded-lg ring-1 ring-slate-200 dark:ring-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-400 dark:bg-slate-800/60 dark:text-slate-500">
                <tr>
                  <th className="px-3 py-1.5 font-semibold">Cursada(s)</th>
                  <th className="px-3 py-1.5 font-semibold">→ Validar na UFSC</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {selecionadas.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="px-3 py-4 text-center text-slate-400">
                      Nenhuma disciplina com candidata.
                    </td>
                  </tr>
                ) : (
                  selecionadas.map((it) => (
                    <tr key={it.destino.codigo}>
                      <td className="px-3 py-1.5 font-medium text-slate-700 dark:text-slate-200">
                        {it.origens.map((o) => o.disciplina.codigo).join(" + ")}
                      </td>
                      <td className="px-3 py-1.5 text-slate-600 dark:text-slate-300">
                        {it.destino.codigo}
                        <span className="ml-1 text-slate-400">· {it.destino.nome}</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {excedente > 0 && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
              ⚠ O formulário oficial comporta {CAPACIDADE} linhas; {excedente}{" "}
              {excedente === 1 ? "par ficou" : "pares ficaram"} de fora. Gere um segundo formulário
              para os restantes, se necessário.
            </p>
          )}

          <p className="mt-3 text-[11px] leading-relaxed text-slate-400 dark:text-slate-500">
            Cada caixa do formulário recebe um código. Em somatórios (N:1), cada disciplina cursada
            ocupa uma linha apontando para o mesmo código da UFSC. Confira os dados antes de
            protocolar — a decisão é do colegiado.
          </p>

          {erro && (
            <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30">
              {erro}
            </div>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 px-6 py-3 dark:border-slate-800">
          <button
            onClick={onClose}
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            Fechar
          </button>
          <button
            onClick={baixar}
            disabled={gerando || selecionadas.length === 0}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {gerando ? "Gerando…" : "⬇ Baixar PDF oficial preenchido"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function Campo({
  label,
  valor,
  onChange,
  full,
}: {
  label: string;
  valor: string;
  onChange: (v: string) => void;
  full?: boolean;
}) {
  return (
    <label className={`block ${full ? "sm:col-span-2" : ""}`}>
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        {label}
      </span>
      <input
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        className="mt-0.5 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:ring-brand-500/30"
      />
    </label>
  );
}

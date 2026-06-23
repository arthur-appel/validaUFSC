import { useCallback, useEffect, useMemo, useState } from "react";
import { comparar, enviarHistorico, listarCursos } from "./api";
import { curriculoPdfUrl } from "./cagr";
import { Formulario } from "./Formulario";
import { useTheme } from "./useTheme";
import type { Comparacao, Curso, HistoricoResp, Item, Origem, Tier } from "./types";

const METODO_LABEL: Record<string, string> = {
  codigo: "Código idêntico",
  oficial: "Equivalência oficial",
  semantico: "Semelhança de ementa (IA)",
  somatorio: "Somatório de CH",
  nenhum: "—",
};

const TIER_META: Record<
  Tier,
  { titulo: string; icone: string; descricao: string; dot: string; badge: string }
> = {
  direto: {
    titulo: "Aproveitamento direto",
    icone: "✅",
    descricao: "Mesmo código ou equivalência oficial da UFSC — pode levar com confiança.",
    dot: "bg-emerald-500",
    badge:
      "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30",
  },
  boa_chance: {
    titulo: "Boas chances",
    icone: "🔎",
    descricao: "Ementa semelhante (IA) — leve ao colegiado; a decisão final é dele.",
    dot: "bg-sky-500",
    badge:
      "bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/30",
  },
  sem: {
    titulo: "Sem candidata",
    icone: "—",
    descricao: "Nenhuma disciplina de origem com semelhança acima do corte.",
    dot: "bg-slate-300 dark:bg-slate-600",
    badge:
      "bg-slate-100 text-slate-500 ring-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:ring-slate-700",
  },
};

type FiltroKey = "todas" | Tier;

export default function App() {
  const { theme, alternar } = useTheme();
  const [cursos, setCursos] = useState<Curso[]>([]);
  const [origemId, setOrigemId] = useState<number | "">("");
  const [destinoId, setDestinoId] = useState<number | "">("");
  const [historico, setHistorico] = useState<HistoricoResp | null>(null);
  const [resultado, setResultado] = useState<Comparacao | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [filtro, setFiltro] = useState<FiltroKey>("todas");
  const [busca, setBusca] = useState("");
  const [mostrarForm, setMostrarForm] = useState(false);
  const fecharForm = useCallback(() => setMostrarForm(false), []);

  useEffect(() => {
    listarCursos()
      .then(setCursos)
      .catch((e) => setErro(`Não foi possível carregar os cursos: ${e.message}`));
  }, []);

  async function onUploadHistorico(file: File) {
    setErro(null);
    try {
      setHistorico(await enviarHistorico(file));
    } catch (e) {
      setErro(`Falha ao ler o histórico: ${(e as Error).message}`);
    }
  }

  const novaComparacao = useCallback(() => {
    setOrigemId("");
    setDestinoId("");
    setResultado(null);
  }, []);

  async function analisar() {
    if (origemId === "" || destinoId === "") return;
    setCarregando(true);
    setErro(null);
    setResultado(null);
    setMostrarForm(false);
    try {
      const r = await comparar(Number(origemId), Number(destinoId), historico?.token);
      setResultado(r);
      setFiltro("todas");
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setCarregando(false);
    }
  }

  const itensFiltrados = useMemo(() => {
    if (!resultado) return [];
    const q = busca.trim().toLowerCase();
    return resultado.itens.filter((it) => {
      if (filtro !== "todas" && it.tier !== filtro) return false;
      if (!q) return true;
      return (
        it.destino.codigo.toLowerCase().includes(q) ||
        it.destino.nome.toLowerCase().includes(q) ||
        it.origens.some((o) => o.disciplina.codigo.toLowerCase().includes(q))
      );
    });
  }, [resultado, filtro, busca]);

  const podeAnalisar = origemId !== "" && destinoId !== "" && origemId !== destinoId;
  const temCandidatas = !!resultado && resultado.kpis.com_candidata > 0;

  return (
    <>
      <div className="flex min-h-screen" aria-hidden={mostrarForm || undefined}>
        <Sidebar
          cursos={cursos}
          origemId={origemId}
          destinoId={destinoId}
          setOrigemId={setOrigemId}
          setDestinoId={setDestinoId}
          historico={historico}
          onUploadHistorico={onUploadHistorico}
          onLimparHistorico={() => setHistorico(null)}
          analisar={analisar}
          podeAnalisar={podeAnalisar}
          carregando={carregando}
          theme={theme}
          alternarTema={alternar}
          temResultado={!!resultado}
          novaComparacao={novaComparacao}
        />

      <main className="flex-1 overflow-y-auto px-8 py-7">
        <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              Disciplinas que você pode aproveitar
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {resultado
                ? `${resultado.origem.curso_nome} → ${resultado.destino.curso_nome} · ${resultado.kpis.total} obrigatórias do destino`
                : "Selecione as grades de origem e destino e clique em Analisar Aproveitamento."}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {resultado && (
              <button
                onClick={novaComparacao}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                🔄 Nova Comparação
              </button>
            )}
            {temCandidatas && (
              <button
                onClick={() => setMostrarForm(true)}
                className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 shadow-sm transition hover:bg-brand-100 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-200 dark:hover:bg-brand-500/20"
              >
                📝 Gerar formulário de aproveitamento
              </button>
            )}
          </div>
        </header>

        {erro && (
          <div className="mb-5 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30">
            {erro}
          </div>
        )}

        {resultado && (
          <>
            <KpiCards comp={resultado} />
            <div className="mt-6 rounded-xl bg-white shadow-sm ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">
              <Toolbar
                resultado={resultado}
                filtro={filtro}
                setFiltro={setFiltro}
                busca={busca}
                setBusca={setBusca}
              />
              <Resultados itens={itensFiltrados} filtro={filtro} />
            </div>
            <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
              Esta é uma triagem automática. A validação oficial é decidida pelo colegiado do curso
              de destino — leve os códigos sugeridos no formulário de aproveitamento. Uma mesma
              disciplina de origem pode aparecer em mais de uma matéria, mas valida apenas uma.
            </p>
          </>
        )}

        {!resultado && !carregando && <EmptyState />}
        {carregando && <Loading />}
        </main>
      </div>

      {mostrarForm && resultado && (
        <Formulario comp={resultado} historico={historico} onClose={fecharForm} />
      )}
    </>
  );
}

function Sidebar(props: {
  cursos: Curso[];
  origemId: number | "";
  destinoId: number | "";
  setOrigemId: (v: number | "") => void;
  setDestinoId: (v: number | "") => void;
  historico: HistoricoResp | null;
  onUploadHistorico: (f: File) => void;
  onLimparHistorico: () => void;
  analisar: () => void;
  podeAnalisar: boolean;
  carregando: boolean;
  theme: "light" | "dark";
  alternarTema: () => void;
  temResultado: boolean;
  novaComparacao: () => void;
}) {
  const opcoes = (excluir: number | "") =>
    props.cursos
      .filter((c) => c.curriculo_id !== excluir)
      .map((c) => (
        <option key={c.curriculo_id} value={c.curriculo_id}>
          {c.curso_nome} ({c.codigo_vigencia})
        </option>
      ));

  const selecionado = (id: number | "") =>
    id === "" ? undefined : props.cursos.find((c) => c.curriculo_id === id);

  return (
    <aside className="sticky top-0 flex h-screen w-80 shrink-0 flex-col gap-6 overflow-y-auto border-r border-slate-200 bg-white px-6 py-7 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand-500 text-lg font-bold text-white">
            V
          </div>
          <div>
            <div className="font-bold text-slate-900 dark:text-slate-100">Valida UFSC</div>
            <div className="text-xs text-slate-400 dark:text-slate-500">
              Aproveitamento de disciplinas
            </div>
          </div>
        </div>
        <button
          onClick={props.alternarTema}
          title={props.theme === "dark" ? "Tema claro" : "Tema escuro"}
          aria-label="Alternar tema claro/escuro"
          className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-200"
        >
          {props.theme === "dark" ? "☀️" : "🌙"}
        </button>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
          Grades de transferência
        </p>
        <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">
          Grade de origem
        </label>
        <div className="flex items-stretch gap-1.5">
          <div className="flex-1 min-w-0">
            <Select value={props.origemId} onChange={props.setOrigemId} placeholder="Curso de origem…">
              {opcoes(props.destinoId)}
            </Select>
          </div>
          {props.origemId !== "" && (
            <button
              onClick={() => props.setOrigemId("")}
              className="flex w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-400 hover:bg-slate-50 hover:text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:hover:bg-slate-700 dark:hover:text-slate-300 transition-colors"
              title="Limpar origem"
            >
              ✕
            </button>
          )}
        </div>
        <PdfLink curso={selecionado(props.origemId)} />

        <label className="mb-1 mt-4 block text-sm font-medium text-slate-600 dark:text-slate-300">
          Grade de destino
        </label>
        <div className="flex items-stretch gap-1.5">
          <div className="flex-1 min-w-0">
            <Select value={props.destinoId} onChange={props.setDestinoId} placeholder="Curso de destino…">
              {opcoes(props.origemId)}
            </Select>
          </div>
          {props.destinoId !== "" && (
            <button
              onClick={() => props.setDestinoId("")}
              className="flex w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-400 hover:bg-slate-50 hover:text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:hover:bg-slate-700 dark:hover:text-slate-300 transition-colors"
              title="Limpar destino"
            >
              ✕
            </button>
          )}
        </div>
        <PdfLink curso={selecionado(props.destinoId)} />
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
          Histórico do aluno (opcional)
        </p>
        {props.historico ? (
          <div className="flex items-stretch gap-1.5">
            <div className="flex-1 min-w-0 flex items-center justify-between rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
              <span className="truncate" title={props.historico.aluno ?? "Histórico"}>
                ✓ {props.historico.aluno ?? "Histórico"}
              </span>
              <span className="shrink-0 ml-1 text-xs text-slate-400">
                ({props.historico.aprovadas.length} apr.)
              </span>
            </div>
            <button
              onClick={props.onLimparHistorico}
              className="flex w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-400 hover:bg-slate-50 hover:text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:hover:bg-slate-700 dark:hover:text-slate-300 transition-colors"
              title="Remover histórico"
            >
              ✕
            </button>
          </div>
        ) : (
          <label className="flex cursor-pointer items-center justify-center rounded-lg border border-dashed border-slate-300 px-3 py-3 text-sm text-slate-500 hover:border-brand-400 hover:text-brand-600 dark:border-slate-700 dark:text-slate-400 dark:hover:border-brand-400 dark:hover:text-brand-300">
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && props.onUploadHistorico(e.target.files[0])}
            />
            Enviar PDF do histórico
          </label>
        )}
        {props.historico && (
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            Análise restrita às disciplinas já cursadas.
          </p>
        )}
      </div>

      <div className="mt-auto">
        <Legenda />
        <button
          onClick={props.analisar}
          disabled={!props.podeAnalisar || props.carregando}
          className="mt-4 w-full rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {props.carregando ? "Analisando…" : "Analisar Aproveitamento"}
        </button>
        {props.temResultado && (
          <button
            onClick={props.novaComparacao}
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 hover:text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 dark:hover:text-slate-100"
          >
            Nova Comparação
          </button>
        )}
      </div>
    </aside>
  );
}

function PdfLink({ curso }: { curso?: Curso }) {
  if (!curso) return null;
  return (
    <a
      href={curriculoPdfUrl(curso)}
      target="_blank"
      rel="noreferrer"
      className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand-600 transition hover:text-brand-700 hover:underline dark:text-brand-300 dark:hover:text-brand-200"
    >
      ver currículo em PDF ↗
    </a>
  );
}

function Select(props: {
  value: number | "";
  onChange: (v: number | "") => void;
  placeholder: string;
  children: React.ReactNode;
}) {
  return (
    <select
      value={props.value}
      onChange={(e) => props.onChange(e.target.value === "" ? "" : Number(e.target.value))}
      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:ring-brand-500/30"
    >
      <option value="">{props.placeholder}</option>
      {props.children}
    </select>
  );
}

function Legenda() {
  const itens: { tier: Tier; t: string }[] = [
    { tier: "direto", t: "Aproveitamento direto" },
    { tier: "boa_chance", t: "Boa chance (colegiado decide)" },
    { tier: "sem", t: "Sem candidata" },
  ];
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        Como ler o resultado
      </p>
      <div className="space-y-1.5">
        {itens.map((i) => (
          <div
            key={i.t}
            className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300"
          >
            <span className={`h-2.5 w-2.5 rounded-full ${TIER_META[i.tier].dot}`} />
            {i.t}
          </div>
        ))}
      </div>
    </div>
  );
}

function KpiCards({ comp }: { comp: Comparacao }) {
  const k = comp.kpis;
  const cards = [
    {
      titulo: "Cobertura",
      valor: `${k.cobertura_pct}%`,
      sub: "das obrigatórias do destino têm candidata",
      cor: "text-brand-600 dark:text-brand-300",
    },
    {
      titulo: "Aproveitamento direto",
      valor: `${k.diretas}`,
      sub: `código ou equivalência oficial · ≈ ${k.economia_semestres} sem. de economia`,
      cor: "text-emerald-600 dark:text-emerald-400",
    },
    {
      titulo: "Boas chances",
      valor: `${k.boas_chances}`,
      sub: "por similaridade de ementa — leve ao colegiado",
      cor: "text-sky-600 dark:text-sky-400",
    },
  ];
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {cards.map((c) => (
        <div
          key={c.titulo}
          className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
            {c.titulo}
          </p>
          <p className={`mt-2 text-3xl font-bold ${c.cor}`}>{c.valor}</p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{c.sub}</p>
        </div>
      ))}
    </div>
  );
}

function Toolbar(props: {
  resultado: Comparacao;
  filtro: FiltroKey;
  setFiltro: (f: FiltroKey) => void;
  busca: string;
  setBusca: (b: string) => void;
}) {
  const k = props.resultado.kpis;
  const semCandidata = k.total - k.com_candidata;
  const tabs: { key: FiltroKey; label: string; n: number }[] = [
    { key: "todas", label: "Todas", n: k.com_candidata },
    { key: "direto", label: "Diretas", n: k.diretas },
    { key: "boa_chance", label: "Boas chances", n: k.boas_chances },
    { key: "sem", label: "Sem candidata", n: semCandidata },
  ];
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-3 dark:border-slate-800">
      <div className="flex gap-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => props.setFiltro(t.key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
              props.filtro === t.key
                ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                : "text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            }`}
          >
            {t.label} <span className="text-xs opacity-60">{t.n}</span>
          </button>
        ))}
      </div>
      <input
        value={props.busca}
        onChange={(e) => props.setBusca(e.target.value)}
        placeholder="Buscar por código ou nome…"
        className="w-56 rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:ring-brand-500/30"
      />
    </div>
  );
}

function Resultados({ itens, filtro }: { itens: Item[]; filtro: FiltroKey }) {
  const ordem: Tier[] = filtro === "todas" ? ["direto", "boa_chance"] : [filtro as Tier];
  const secoes = ordem
    .map((tier) => ({ tier, lista: itens.filter((i) => i.tier === tier) }))
    .filter((s) => s.lista.length > 0);

  if (secoes.length === 0) {
    return (
      <p className="px-5 py-10 text-center text-sm text-slate-400 dark:text-slate-500">
        Nenhuma disciplina neste filtro.
      </p>
    );
  }
  return (
    <div className="divide-y divide-slate-100 dark:divide-slate-800">
      {secoes.map((s) => (
        <Secao key={s.tier} tier={s.tier} itens={s.lista} />
      ))}
    </div>
  );
}

function Secao({ tier, itens }: { tier: Tier; itens: Item[] }) {
  const meta = TIER_META[tier];
  return (
    <section>
      <div className="flex items-center gap-2 px-5 pb-2 pt-4">
        <span className={`h-2.5 w-2.5 rounded-full ${meta.dot}`} />
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          {meta.icone} {meta.titulo}
          <span className="ml-1.5 text-xs font-normal text-slate-400 dark:text-slate-500">
            {itens.length}
          </span>
        </h3>
        <span className="hidden text-xs text-slate-400 dark:text-slate-500 sm:inline">
          · {meta.descricao}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
            <tr className="border-y border-slate-100 dark:border-slate-800">
              <th className="px-5 py-2 font-medium">Matéria de destino</th>
              <th className="px-5 py-2 font-medium">Origem sugerida</th>
              <th className="px-5 py-2 font-medium">Base</th>
              <th className="px-5 py-2 font-medium">Similaridade</th>
              <th className="px-5 py-2 font-medium">Faixa</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((it) => (
              <Linha key={it.destino.codigo} it={it} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Linha({ it }: { it: Item }) {
  return (
    <tr className="border-b border-slate-50 hover:bg-slate-50/60 dark:border-slate-800/60 dark:hover:bg-slate-800/40">
      <td className="px-5 py-3">
        <div className="font-medium text-slate-800 dark:text-slate-100">{it.destino.nome}</div>
        <div className="text-xs text-slate-400 dark:text-slate-500">
          {it.destino.codigo} · {it.destino.carga_horaria_ha ?? "?"} h/a
        </div>
      </td>
      <td className="px-5 py-3">
        {it.origens.length === 0 ? (
          <span className="text-slate-300 dark:text-slate-600">—</span>
        ) : it.origens.length === 1 ? (
          <div className="text-slate-700 dark:text-slate-200">
            {it.origens[0].disciplina.nome}
            <span className="ml-1 text-xs text-slate-400 dark:text-slate-500">
              ({it.origens[0].disciplina.codigo})
            </span>
          </div>
        ) : (
          <Soma origens={it.origens} destinoHa={it.destino.carga_horaria_ha} />
        )}
      </td>
      <td className="px-5 py-3">
        <div className="flex flex-wrap gap-1">
          <Tag>{METODO_LABEL[it.metodo] ?? it.metodo}</Tag>
          {it.origens.length > 0 && (
            <Tag tone={it.ch_ok ? "ok" : "warn"}>CH {Math.round(it.ch_cobertura_pct * 100)}%</Tag>
          )}
        </div>
      </td>
      <td className="px-5 py-3">
        <SimBar valor={it.similaridade} />
      </td>
      <td className="px-5 py-3" title={it.justificativa}>
        <TierBadge it={it} />
        {it.justificativa && <span className="sr-only">{it.justificativa}</span>}
      </td>
    </tr>
  );
}

function Soma({ origens, destinoHa }: { origens: Origem[]; destinoHa?: number | null }) {
  const total = origens.reduce((s, o) => s + (o.disciplina.carga_horaria_ha ?? 0), 0);
  return (
    <div className="space-y-1">
      {origens.map((o, idx) => (
        <div
          key={o.disciplina.codigo}
          className="flex items-start gap-1.5 text-slate-700 dark:text-slate-200"
        >
          <span className="w-3 shrink-0 font-semibold text-sky-500">{idx === 0 ? "" : "+"}</span>
          <span>
            {o.disciplina.nome}
            <span className="ml-1 text-xs text-slate-400 dark:text-slate-500">
              ({o.disciplina.codigo} · {o.disciplina.carga_horaria_ha ?? "?"} h/a)
            </span>
          </span>
        </div>
      ))}
      <div className="ml-[1.125rem] text-xs font-medium text-sky-600 dark:text-sky-400">
        = {total} h/a · cobre {destinoHa ?? "?"} h/a do destino
      </div>
    </div>
  );
}

function Tag({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "ok" | "warn";
}) {
  const cls =
    tone === "ok"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30"
      : tone === "warn"
        ? "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30"
        : "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700";
  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-medium ring-1 ${cls}`}>{children}</span>
  );
}

function SimBar({ valor }: { valor: number }) {
  const pct = Math.round(valor * 100);
  if (valor <= 0) return <span className="text-xs text-slate-300 dark:text-slate-600">—</span>;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{pct}%</span>
    </div>
  );
}

function TierBadge({ it }: { it: Item }) {
  const meta = TIER_META[it.tier];
  const rotulo =
    it.tier === "direto" && !it.ch_ok ? `${meta.titulo} · CH parcial` : meta.titulo;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${meta.badge}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {rotulo}
    </span>
  );
}

function EmptyState() {
  return (
    <div className="mt-16 grid place-items-center text-center">
      <div className="max-w-md rounded-xl bg-white px-8 py-10 shadow-sm ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">
        <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-brand-50 text-2xl dark:bg-brand-500/15">
          🎓
        </div>
        <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
          Compare dois currículos
        </h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Escolha o curso de origem e o de destino na barra lateral. Você recebe na hora as
          disciplinas com chance de aproveitamento — para levar ao colegiado.
        </p>
      </div>
    </div>
  );
}

function Loading() {
  return (
    <div className="mt-16 grid place-items-center text-center text-sm text-slate-500 dark:text-slate-400">
      <div className="mb-3 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-brand-500 dark:border-slate-700 dark:border-t-brand-500" />
      Analisando equivalências…
    </div>
  );
}

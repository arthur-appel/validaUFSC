export interface Curso {
  curriculo_id: number;
  curso_codigo: string;
  curso_nome: string;
  codigo_vigencia: string;
  habilitacao?: string | null;
  total_disciplinas: number;
}

export interface Disciplina {
  codigo: string;
  nome: string;
  carga_horaria_ha?: number | null;
}

export interface Origem {
  disciplina: Disciplina;
  similaridade: number;
}

export type Status = "aproveita" | "boa_chance" | "ressalva" | "nao_aproveita";

export type Tier = "direto" | "boa_chance" | "sem";

export interface Item {
  destino: Disciplina;
  origens: Origem[];
  metodo: string;
  status: Status;
  similaridade: number;
  ch_ok: boolean;
  ch_cobertura_pct: number;
  justificativa: string;
  tier: Tier;
}

export interface Kpis {
  total: number;
  diretas: number;
  boas_chances: number;
  com_candidata: number;
  cobertura_pct: number;
  economia_semestres: number;
}

export interface Comparacao {
  comparacao_id: number;
  origem: Curso;
  destino: Curso;
  kpis: Kpis;
  itens: Item[];
}

export interface HistoricoResp {
  token: string;
  aluno?: string | null;
  curso_codigo: string;
  curso_nome: string;
  aprovadas: Disciplina[];
}

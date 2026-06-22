import type { Curso } from "./types";

const CAGR_HOST = "https://cagr.sistemas.ufsc.br";

/**
 * URL pública do relatório de currículo do CAGR (PDF), o mesmo que o scraper usa.
 * Ex.: .../relatorios/curriculoCurso?curso=349&curriculo=20261
 */
export function curriculoPdfUrl(curso: Pick<Curso, "curso_codigo" | "codigo_vigencia">): string {
  return `${CAGR_HOST}/relatorios/curriculoCurso?curso=${encodeURIComponent(
    curso.curso_codigo,
  )}&curriculo=${encodeURIComponent(curso.codigo_vigencia)}`;
}

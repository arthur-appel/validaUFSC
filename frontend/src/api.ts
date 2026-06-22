import type { Comparacao, Curso, HistoricoResp } from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string) || "http://localhost:8000";

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

export function listarCursos(): Promise<Curso[]> {
  return fetch(`${BASE}/cursos`).then((r) => json<Curso[]>(r));
}

export function comparar(
  origem_curriculo_id: number,
  destino_curriculo_id: number,
  historico_token?: string,
): Promise<Comparacao> {
  // Instantânea: determinístico (código/oficial) + similaridade de ementa (boas chances).
  const path = historico_token ? "/comparacoes/personalizada" : "/comparacoes";
  return fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origem_curriculo_id,
      destino_curriculo_id,
      ...(historico_token ? { historico_token } : {}),
    }),
  }).then((r) => json<Comparacao>(r));
}

export function enviarHistorico(file: File): Promise<HistoricoResp> {
  const fd = new FormData();
  fd.append("file", file);
  return fetch(`${BASE}/historico`, { method: "POST", body: fd }).then((r) =>
    json<HistoricoResp>(r),
  );
}

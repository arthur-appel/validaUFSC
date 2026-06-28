"""Configuração central, carregada de variáveis de ambiente (.env)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Banco
    database_url: str = "postgresql+psycopg://valida:valida@localhost:5432/valida_ufsc"

    # Ollama / IA (embeddings)
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024

    # Critério oficial de equivalência (UFSC) — limiares configuráveis (regra dos 75%).
    limiar_conteudo: float = 0.75       # conteúdo "forte" (reforço por somatório N:1)
    limiar_carga_horaria: float = 0.75  # regra dos 75% de CH
    # Corte da faixa "boa chance" (similaridade de ementa). CALIBRADO: equivalências oficiais
    # da UFSC ficam acima de ~0,70; 99% dos pares aleatórios ficam abaixo de 0,67 (ruído).
    limiar_boa_chance: float = 0.75

    # Scraper
    cagr_tree_url: str = "https://cagr.sistemas.ufsc.br/arvore.xhtml?treeid=30"
    cagr_campus: str = "Florianópolis"
    scraper_delay_ms: int = 1500

    # Nota mínima de aprovação na UFSC.
    nota_aprovacao: float = 6.0

    # Diretório onde os PDFs raspados são salvos/lidos pela ETL.
    data_dir: str = "data/raw"
    # Se "0", o pipeline NÃO raspa o CAGR (só carrega PDFs já presentes em data_dir).
    scrape: bool = True


settings = Settings()

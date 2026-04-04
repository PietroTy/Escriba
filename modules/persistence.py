"""
modules/persistence.py — Gestão de persistência local da tese
Escriba v2.0
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List

# Define o caminho do arquivo de sessão na raiz do projeto ou no diretório de outputs
SESSION_FILE = Path("outputs/sessao_tese.json")

def ensure_dir():
    """Garante que o diretório de outputs existe."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

def save_session(data: List[Dict[str, Any]]):
    """
    Salva os resultados da seção (GeneratorResult format) no JSON local.
    data format: list of dicts with {secao_id, secao_titulo, texto, timestamp}
    """
    ensure_dir()
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_session() -> List[Dict[str, Any]]:
    """Carrega a sessão anterior se existir."""
    if not SESSION_FILE.exists():
        return []
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def clear_session():
    """Remove o arquivo de sessão local."""
    if SESSION_FILE.exists():
        os.remove(SESSION_FILE)

def build_context(results: List[Dict[str, Any]], scope: str = "tudo") -> str:
    """
    Constrói uma string de contexto a partir dos resultados salvos.
    scope: 'tudo' ou 'ultima'
    """
    if not results:
        return ""
    
    if scope == "ultima":
        last = results[-1]
        return f"Capítulo/Seção anterior ({last['secao_titulo']}):\n{last['texto']}"
    
    # Tudo
    context = "RESUMO DO CONTEÚDO JÁ GERADO:\n"
    for res in results:
        context += f"--- SEÇÃO: {res['secao_titulo']} ---\n{res['texto']}\n\n"
    return context

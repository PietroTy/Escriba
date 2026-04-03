"""
modules/generator.py — Módulo 3: Pipeline de Geração Agêntica
Escriba v2.0

ESTADO ATUAL: Funcional — geração real via API Maritaca (sabiazinho-4).
ROADMAP: Implementar Chain-of-Verification (CoVe) completo:
         1. Draft — gera seção
         2. Verify — gera perguntas de verificação internas
         3. Execute — consulta material-fonte para responder perguntas
         4. Refine — reescreve apenas com fatos confirmados

Responsabilidades:
- Receber ComprehensionResult + template de seção
- Chamar a API Maritaca com system prompt de fidelidade
- Retornar texto gerado com referências de origem
"""

import json
import os
from typing import Optional, Callable

try:
    import openai
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


class GeneratorResult:
    """Resultado de geração de uma seção."""
    def __init__(self, secao_id: str, secao_titulo: str, texto: str, modelo_usado: str, cove_ativo: bool = False):
        self.secao_id = secao_id
        self.secao_titulo = secao_titulo
        self.texto = texto
        self.modelo_usado = modelo_usado
        self.cove_ativo = cove_ativo


def _build_system_prompt(texto_fonte: str, idioma: str, tema: str) -> str:
    """
    System prompt com instrução de fidelidade máxima ao material-fonte.
    Baseado na estratégia Anti-Alucinação do Blueprint Escriba v2.0.
    """
    return (
        "Você é o Escriba — um assistente especialista em design educacional e criação de conteúdo acadêmico formal. "
        "Sua filosofia é a de um escriba medieval: se a informação não está no manuscrito original (material-fonte), ela não existe no mundo. "
        "NUNCA invente, suponha ou adicione conhecimento externo ao que foi fornecido pelo usuário.\n\n"
        f"Idioma de saída: {idioma}.\n"
        f"Tema geral: {tema}.\n\n"
        "MATERIAL-FONTE (use EXCLUSIVAMENTE estas informações):\n"
        "---\n"
        f"{texto_fonte[:12000]}\n"  # Limita para não estourar tokens
        "---\n\n"
        "Ao final de cada seção gerada, inclua uma nota de rodapé discreta no formato: "
        "[Ref: baseado no material-fonte fornecido]"
    )


def _chamar_api(client, modelo: str, system_prompt: str, user_prompt: str) -> str:
    """Chama a API Maritaca com o modelo especificado."""
    try:
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,   # Temperatura baixa para maior fidelidade
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[ERRO NA API] {e}"


def generate(
    texto_fonte: str,
    template: dict,
    secoes_selecionadas: list[str],
    tema: str,
    idioma: str,
    api_key: str,
    modelo_geracao: str = "sabiazinho-4",
    status_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
) -> list[GeneratorResult]:
    """
    Ponto de entrada principal do Generator.

    Args:
        texto_fonte: Texto completo extraído pelo Ingestor.
        template: Dicionário do template JSON carregado.
        secoes_selecionadas: Lista de IDs de seções a gerar.
        tema: Tema geral informado pelo usuário.
        idioma: Idioma de saída (ex: "Português").
        api_key: Chave da API Maritaca.
        modelo_geracao: Modelo base para geração (padrão: sabiazinho-4).
        status_callback: Função para mensagens de status na UI.
        progress_callback: Função para atualizar progresso (recebe 0.0–1.0).

    Returns:
        Lista de GeneratorResult, uma por seção gerada.
    """
    if not _HAS_OPENAI:
        raise ImportError("openai não instalado. Execute: pip install openai")

    client = openai.OpenAI(api_key=api_key, base_url="https://chat.maritaca.ai/api")
    system_prompt = _build_system_prompt(texto_fonte, idioma, tema)
    secoes_template = {s["id"]: s for s in template.get("secoes", [])}
    resultados = []
    total = len(secoes_selecionadas)

    for i, secao_id in enumerate(secoes_selecionadas):
        secao = secoes_template.get(secao_id)
        if not secao:
            continue

        if status_callback:
            status_callback(f"⚙️ Gerando: {secao['titulo']} ({i+1}/{total})...")

        # [ROADMAP CoVe] — Por ora, geração em passo único (Draft)
        # Fase 1: Draft
        user_prompt = secao["prompt"]
        if "[PLACEHOLDER]" in user_prompt:
            texto_gerado = (
                f"[PLACEHOLDER] Geração da seção '{secao['titulo']}' ainda não implementada para este template. "
                f"O pipeline funcional está disponível no template 'Módulo Educacional'."
            )
        else:
            texto_gerado = _chamar_api(client, modelo_geracao, system_prompt, user_prompt)

        resultados.append(GeneratorResult(
            secao_id=secao_id,
            secao_titulo=secao["titulo"],
            texto=texto_gerado,
            modelo_usado=modelo_geracao,
            cove_ativo=False,  # ROADMAP: True quando CoVe for implementado
        ))

        if progress_callback:
            progress_callback((i + 1) / total)

    if status_callback:
        status_callback(f"✅ Geração concluída: {len(resultados)} seções geradas com {modelo_geracao}.")

    return resultados

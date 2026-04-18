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


def _build_system_prompt(texto_fatos: str, texto_modelo: str, idioma: str, tema: str, incluir_markers: bool = False) -> str:
    """
    System prompt com instrução de fidelidade máxima ao material-fonte.
    Baseado na estratégia Anti-Alucinação do Blueprint Escriba v2.0.
    """
    prompt = (
        "Você é o Escriba — um assistente especialista em design educacional e criação de conteúdo acadêmico formal.\\n"
        "Sua filosofia primária é FIDELIDADE: Nunca invente fatos, autores ou dados que não estejam expressamente no material-fonte.\\n\\n"
        f"Idioma de saída: {idioma}.\\n"
        f"Tema geral sugerido: {tema}.\\n\\n"
    )
    
    if texto_modelo and texto_modelo.strip():
        prompt += (
            "DIRETRIZ DE ESTILO / PERSONA OBRIGATÓRIA GLOBAL:\\n"
            "VOCÊ FOI CONDICIONADO A HACKEAR E COPIAR o tom de voz e estilo narrativa do MATERIAL-FONTE DE MODELO (abaixo). "
            "Sua escrita não pode soar como IA. Copie os conectivos, a 1ª pessoa do singular (se usada) e a emoção narrativa. "
            "Todo o documento que gerar deve OBRIGATORIAMENTE ser permeado pelo fluxo estilístico deste modelo referencial:\\n"
            "---\\n"
            f"{texto_modelo[:10000]}\\n"  
            "---\\n\\n"
        )
    
    prompt += (
        "MATERIAL-FONTE DE FATOS E PESQUISA (A SUA ÚNICA BASE GERADORA DE CONTEÚDO):\\n"
        "Use APENAS os dados teóricos, nomes e fatos contidos neste arquivo:\\n"
        "---\\n"
        f"{texto_fatos[:12000]}\\n"  # Limita para não estourar tokens
        "---\\n\\n"
    )

    if incluir_markers:
        prompt += (
            "DIRETRIZ DE FLUXO E MÍDIA: Intercale os fatos ao longo de todo o texto suavemente. Sugira pontos de interatividade usando marcadores "
            "como [ VÍDEO ], [ ÁUDIO ] ou [ TABELA ] apenas quando fizer sentido.\\n\\n"
        )
        )

    return prompt


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
    texto_fatos: str,
    texto_modelo: str,
    template: dict,
    secoes_selecionadas: list[str],
    tema: str,
    idioma: str,
    api_key: str,
    modelo_geracao: str = "sabiazinho-4",
    incluir_markers: bool = False,
    contexto_anterior: Optional[str] = None,
    status_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
) -> list[GeneratorResult]:
    """
    Ponto de entrada principal do Generator.

    Args:
        texto_fatos: Fatos extraídos da pesquisa.
        texto_modelo: Material-fonte para base de tom e voz.
        template: Dicionário do template JSON carregado.
        secoes_selecionadas: Lista de IDs de seções a gerar.
        tema: Tema geral informado pelo usuário.
        idioma: Idioma de saída (ex: "Português").
        api_key: Chave da API Maritaca.
        modelo_geracao: Modelo base para geração (padrão: sabiazinho-4).
        incluir_markers: Se deve incluir marcadores de mídia no prompt.
        contexto_anterior: Texto já gerado em sessões/seções prévias para coerência.
        status_callback: Função para mensagens de status na UI.
        progress_callback: Função para atualizar progresso (recebe 0.0–1.0).

    Returns:
        Lista de GeneratorResult, uma por seção gerada.
    """
    if not _HAS_OPENAI:
        raise ImportError("openai não instalado. Execute: pip install openai")

    client = openai.OpenAI(api_key=api_key, base_url="https://chat.maritaca.ai/api")
    
    # Verifica se o template possui um system prompt customizado
    custom_system_prompt = template.get("system_prompt")
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        system_prompt = _build_system_prompt(texto_fatos, texto_modelo, idioma, tema, incluir_markers=incluir_markers)
    
    secoes_template = {s["id"]: s for s in template.get("secoes", [])}
    resultados = []
    total = len(secoes_selecionadas)

    for i, secao_id in enumerate(secoes_selecionadas):
        secao = secoes_template.get(secao_id)
        if not secao:
            continue

        if status_callback:
            status_callback(f"⚙️ Gerando: {secao['titulo']} ({i+1}/{total})...")

        # Suporte para sub-prompts (Micro-chunking)
        sub_prompts = secao.get("sub_prompts")
        if sub_prompts and isinstance(sub_prompts, list):
            texto_gerado_acc = []
            contexto_interno = contexto_anterior or ""
            for idx_sub, sprompt in enumerate(sub_prompts):
                if status_callback:
                    status_callback(f"⚙️ Gerando: {secao['titulo']} (Sub-tópico {idx_sub+1}/{len(sub_prompts)})...")
                
                # Monta o user prompt dinâmico pro sub_prompt
                user_prompt = sprompt
                
                if contexto_interno:
                    user_prompt = (
                        "CONTEXTO DE CONTINUIDADE (Acompanhe o fluxo do que você já escreveu logo acima):\\n"
                        f"{contexto_interno}\\n"
                        "--- FIM DO CONTEXTO DE CONTINUIDADE ---\\n\\n"
                        f"{user_prompt}"
                    )
                
                if custom_system_prompt:
                    user_prompt += f"\\n\\nMATERIAL DE ORIGEM (FATOS):\\n\"\"\"\\n{texto_fatos[:10000]}\\n\"\"\"\\n"
                    if texto_modelo:
                         user_prompt += f"\\nMATERIAL DE REFERÊNCIA (ESTILO):\\n\"\"\"\\n{texto_modelo[:8000]}\\n\"\"\""
                         
                texto_gerado_sub = _chamar_api(client, modelo_geracao, system_prompt, user_prompt)
                texto_gerado_acc.append(texto_gerado_sub)
                
                # O texto gerado agora vira contexto para o próximo sub_prompt!
                contexto_interno = texto_gerado_sub
                
            texto_gerado = "\\n\\n".join(texto_gerado_acc)
            
        else:
            # Fluxo normal de seção única
            user_prompt = secao.get("prompt", "")
            
            # Injeção de contexto de continuidade (Memória de Sessão)
            if contexto_anterior:
                user_prompt = (
                    "CONTEXTO DE CONTINUIDADE (Acompanhe o fluxo do que já foi escrito):\\n"
                    f"{contexto_anterior}\\n"
                    "--- FIM DO CONTEXTO DE CONTINUIDADE ---\\n\\n"
                    f"{user_prompt}"
                )
            
            # Se for um template customizado, injetamos o material-fonte no user_prompt
            if custom_system_prompt:
                user_prompt += f"\\n\\nMATERIAL DE ORIGEM (FATOS):\\n\"\"\"\\n{texto_fatos[:10000]}\\n\"\"\"\\n"
                if texto_modelo:
                     user_prompt += f"\\nMATERIAL DE REFERÊNCIA (ESTILO):\\n\"\"\"\\n{texto_modelo[:8000]}\\n\"\"\""
    
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

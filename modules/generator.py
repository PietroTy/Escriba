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
    Baseado na estratégia Anti-Alucinação do Blueprint Escriba v6.0.
    """
    prompt = (
        "Você é o Escriba — um compilador rígido de design educacional e conteúdo acadêmico formal.\n"
        "REGRA DE INFERÊNCIA ZERO: É peremptoriamente proibido atuar como coautor. É estritamente proibido inferir causas ou correlacionar marcos temporais, políticos ou históricos que não estejam expressos no payload. Você atua APENAS como COMPILADOR.\n\n"
        f"Idioma de saída: {idioma}.\n"
        f"Tema geral sugerido: {tema}.\n\n"
    )
    
    prompt += (
        "DIRETRIZ ESTRUTURAL E VERBATIM (REGRAS DE CONTROLE):\n"
        "- Regra 1: Toda afirmação extraída de documentos oficiais ou leis DEVE citar a fonte no mesmo período (ex: 'conforme o PNE 2026...').\n"
        "- Regra 2: Nenhuma conclusão avaliativa (ex: 'a inclusão permanece incipiente') pode ser gerada sem ser imediatamente seguida da citação do autor ou dado do texto-fonte que a baseia.\n"
        "- Para garantir que você não resuma conhecimentos de forma abstrata, cada parágrafo fático deve conter ao menos uma citação direta transcrita exatamente do material-fonte delimitada por aspas duplas.\n\n"
    )
    
    if texto_modelo and texto_modelo.strip():
        prompt += (
            "DIRETRIZ DE ESTILO / PERSONA (TRAVA BIOGRÁFICA STRICTA):\n"
            "1. Você deve escrever na primeira pessoa do singular (ex: 'analiso', 'compreendo') acompanhando o tom de voz do MATERIAL-FONTE DE MODELO (abaixo).\n"
            "2. É ESTRITAMENTE PROIBIDO inventar cargos ('como supervisor'), experiências profissionais, anedotas, metáforas parnasianas ou simular falas de professores/terceiros.\n"
            "3. Sua 'voz' deve se restringir exclusivamente a relatar ou transacionar os fatos e conceitos teóricos APRESENTADOS NO PAYLOAD. NUNCA assuma um Roleplay criativo.\n"
            "---\n"
            f"{texto_modelo[:10000]}\n"  
            "---\n\n"
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
    
    from .extractor import extract_required_entities_from_prompt, extract_mandatory_keys_from_context, categorize_knowledge_base
    
    # [Passo 1] Agente Classificador Global
    contexto_estruturado = categorize_knowledge_base(texto_fatos, api_key, status_callback)
    
    secoes_template = {s["id"]: s for s in template.get("secoes", [])}
    resultados = []
    total = len(secoes_selecionadas)

    for i, secao_id in enumerate(secoes_selecionadas):
        secao = secoes_template.get(secao_id)
        if not secao:
            continue

        if status_callback:
            status_callback(f"⚙️ Gerando: {secao['titulo']} ({i+1}/{total})...")

        skeleton_expansion = secao.get("skeleton_expansion", False)
        base_prompt_padrao = secao.get("prompt", "")
        texto_gerado_acc = []
        contexto_interno = contexto_anterior or ""
        
        # [Passo 2] Dicionário de Roteamento Heurístico
        titulo_lower = secao["titulo"].lower()
        id_lower = secao["id"].lower()
        if any(x in titulo_lower or x in id_lower for x in ["metod", "procedimento", "instrumento"]):
            required_keys = ["metodologia_e_instrumentos"]
        elif any(x in titulo_lower or x in id_lower for x in ["trajet", "apresent", "biograf", "historia"]):
            required_keys = ["biografia_pesquisador", "contexto_global"]
        elif any(x in titulo_lower or x in id_lower for x in ["revis", "teoric", "estado da arte", "desenvolvimento"]):
            required_keys = ["referencial_teorico", "legislacao"]
        else:
            required_keys = ["contexto_global", "referencial_teorico"] # Fallback

        # Ignorar chaves vazias retornadas pelo classificador
        required_keys = [k for k in required_keys if k in contexto_estruturado and contexto_estruturado[k].strip()]
        
        # [Passo 3] Montagem Blindada do Payload (Hard Context Isolation)
        # Se não tivermos fatos, colocamos fallback
        if not required_keys:
            payload_isolado = {"geral": texto_fatos}
            keys_to_iterate = ["geral"]
        else:
            payload_isolado = {k: contexto_estruturado[k] for k in required_keys}
            keys_to_iterate = required_keys

        # [Passo 4] Loop de Expansão (Micro-Chunking) iterando sobre os conceitos filtrados
        if status_callback:
            status_callback(f"⚙️ Módulo {i+1}: Orquestração focada em {keys_to_iterate}...")

        from .extractor import extract_required_entities_from_prompt, extract_mandatory_keys_from_context
        
        for idx_key, current_key in enumerate(keys_to_iterate):
            bloco_fatos = payload_isolado[current_key]
            if status_callback: 
                status_callback(f"⚙️ Expandindo [{current_key}] ({idx_key+1}/{len(keys_to_iterate)})...")

            # Construção do Micro-Prompt com isolamento de Payload
            material_inj = ""
            if not custom_system_prompt:
                material_inj += f"\n\nMATERIAL DE ORIGEM (FATOS RECORTADOS EXCLUSIVAMENTE PARA '{current_key}'):\n\"\"\"\n{bloco_fatos}\n\"\"\"\n"
            else:
                material_inj += f"\n\nMATERIAL DE ORIGEM (FATOS RECORTADOS EXCLUSIVAMENTE PARA '{current_key}'):\n\"\"\"\n{bloco_fatos}\n\"\"\"\n"
                if texto_modelo:
                     material_inj += f"\nMATERIAL DE REFERÊNCIA (ESTILO):\n\"\"\"\n{texto_modelo[:8000]}\n\"\"\""

            user_prompt = (
                f"Foco Isolado: Você deve focar ABSOLUTAMENTE TUDO em descrever e aprofundar sobre o contexto classificado como '{current_key}'. "
                f"Escreva de 3 a 5 parágrafos DENSOS relacionando este conceito central com a seguinte intenção da seção:\n {base_prompt_padrao}\n\n"
                "Proibido pular de assunto ou adiantar conceitos estruturais que não estejam neste payload isolado.\n"
            )

            if contexto_interno:
                user_prompt = (
                    "CONTEXTO DE CONTINUIDADE (Acompanhe o fluxo do que você já escreveu logo acima):\n"
                    f"{contexto_interno}\n--- FIM DO CONTEXTO ---\n\n" + user_prompt
                )

            # Extração de Chaves Anti-Omissão deste bloco
            ent_prompt = extract_required_entities_from_prompt(base_prompt_padrao, api_key)
            ent_contexto = extract_mandatory_keys_from_context(bloco_fatos, api_key)
            entidades_obrig = list(set(ent_prompt + ent_contexto))
            
            # Retry Anti-Omissão e [Passo 5] Sanitização progressiva
            tentativas = 0
            max_retries = 2
            texto_gerado_sub = ""
            while tentativas <= max_retries:
                texto_gerado_sub = _chamar_api(client, modelo_geracao, system_prompt, user_prompt + material_inj)
                falhas = [e for e in entidades_obrig if str(e).lower() not in texto_gerado_sub.lower()]
                if not falhas: break
                if status_callback and falhas:
                    status_callback(f"⚠️ Omissão detectada em {current_key}. Reforçando chaves ({tentativas+1}/{max_retries}): {', '.join(falhas)[:30]}...")
                tentativas += 1
                user_prompt += f"\n\n[ALERTA ANTI-OMISSÃO NO MICRO-CHUNKING]: Você DELETOU informações teóricas. Refaça ESSE bloco específico INCLUINDO obrigatoriamente estas chaves: {falhas}."
                
            texto_gerado_acc.append(texto_gerado_sub)
            contexto_interno = texto_gerado_sub

        texto_gerado = "\n\n".join(texto_gerado_acc)

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

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
        "Você é o Escriba — um compilador rígido de design educacional e conteúdo acadêmico formal.\\n"
        "REGRA DE INFERÊNCIA ZERO: É peremptoriamente proibido atuar como coautor. É estritamente proibido inferir causas ou correlacionar marcos temporais, políticos ou históricos que não estejam expressos no payload. Você atua APENAS como COMPILADOR.\\n\\n"
        f"Idioma de saída: {idioma}.\\n"
        f"Tema geral sugerido: {tema}.\\n\\n"
    )
    
    prompt += (
        "DIRETRIZ ESTRUTURAL E VERBATIM (FEW-SHOT):\\n"
        "Para garantir que você não resuma conhecimentos de forma abstrata, cada parágrafo gerado deve conter, obrigatoriamente, "
        "ao menos uma citação direta do material-fonte delimitada por aspas duplas, transcrevendo exatamente as palavras da fonte.\\n"
        "Exemplo de Sáida Esperada:\\n"
        "> Ao analisarmos as políticas atuais, fica claro que a imposição do currículo gera deficiências locais, visto que a EJA é, na fonte, \"um processo contínuo de alienação na raiz do município\".\\n\\n"
    )
    
    if texto_modelo and texto_modelo.strip():
        prompt += (
            "DIRETRIZ DE ESTILO / PERSONA OBRIGATÓRIA GLOBAL:\\n"
            "VOCÊ FOI CONDICIONADO A HACKEAR E COPIAR o tom de voz e estilo narrativa do MATERIAL-FONTE DE MODELO (abaixo). "
            "Sua escrita não pode soar como IA. Assuma a voz confessional e vivencial (O EU PESQUISADOR) homogeneamente do "
            "primeiro ao último parágrafo, sem transições abruptas para jargão impessoal. Se a base usar 1ª Pessoa, o documento "
            "TODO DEVE SER EM 1ª PESSOA, incluindo introduções de contexto global.\\n"
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
    
    from .extractor import extract_required_entities_from_prompt
    
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
        sub_prompts = secao.get("sub_prompts", [secao.get("prompt", "")])
        texto_gerado_acc = []
        contexto_interno = contexto_anterior or ""
        
        for idx_sub, base_prompt in enumerate(sub_prompts):
            if not base_prompt: continue
            
            # NLP Extractor (NER)
            from .extractor import extract_required_entities_from_prompt
            entidades_obrig = extract_required_entities_from_prompt(base_prompt, api_key)
            
            # Preparação de injestão comum
            material_inj = ""
            if custom_system_prompt:
                material_inj += f"\n\nMATERIAL DE ORIGEM (FATOS):\n\"\"\"\n{texto_fatos[:10000]}\n\"\"\"\n"
                if texto_modelo:
                     material_inj += f"\nMATERIAL DE REFERÊNCIA (ESTILO):\n\"\"\"\n{texto_modelo[:8000]}\n\"\"\""
            
            # --- FLUXO SKELETON EXPANSION ---
            if skeleton_expansion:
                if status_callback: status_callback(f"⚙️ Mapeando Esqueleto do Tópico {i+1}...")
                
                req_esqueleto = (
                    "GERAÇÃO DE ESQUELETO MESTRE (DRAFT):\n"
                    "Crie um índice fático enumerado de 3 a 5 tópicos principais que você abordaria para resolver a seguinte instrução.\n"
                    "Responda APENAS com os bullets (iniciando com '- '), não escreva o texto final.\n\n"
                    f"INSTRUÇÃO:\n{base_prompt}"
                )
                
                esqueleto_bruto = _chamar_api(client, modelo_geracao, system_prompt, req_esqueleto + material_inj)
                linhas_esqueleto = [l.strip() for l in esqueleto_bruto.split('\n') if l.strip().startswith('-')]
                if not linhas_esqueleto:
                    linhas_esqueleto = [l.strip() for l in esqueleto_bruto.split('\n') if len(l.strip()) > 10][:4]
                
                for idx_linha, linha_index in enumerate(linhas_esqueleto):
                    if status_callback: status_callback(f"⚙️ Deep Render ({idx_linha+1}/{len(linhas_esqueleto)}): {linha_index[:30]}...")
                    
                    user_prompt = (
                        f"Você está expandindo UMA ÚNICA LINHA de um índice maior. Escreva de 3 a 5 parágrafos DENSOS "
                        f"abortando OBRIGATÓRIA E EXCLUSIVAMENTE o seguinte tópico: '{linha_index}'.\n"
                        "Proibido iniciar conclusões finais ou pular de assunto.\n\n"
                        f"Contexto Macro da Seção: {base_prompt}"
                    )
                    
                    if contexto_interno:
                        user_prompt = (
                            "CONTEXTO DE CONTINUIDADE (Acompanhe o fluxo do que você já escreveu logo acima):\n"
                            f"{contexto_interno}\n--- FIM DO CONTEXTO ---\n\n" + user_prompt
                        )
                    
                    # Retry
                    tentativas = 0
                    max_retries = 1
                    texto_gerado_sub = ""
                    while tentativas <= max_retries:
                        texto_gerado_sub = _chamar_api(client, modelo_geracao, system_prompt, user_prompt + material_inj)
                        falhas = [e for e in entidades_obrig if e.lower() not in texto_gerado_sub.lower()]
                        if not falhas: break
                        tentativas += 1
                        user_prompt += f"\n\n[ERRO DE VALIDAÇÃO]: Inclua impreterivelmente estes fatos/autores: {falhas}."
                        
                    texto_gerado_acc.append(texto_gerado_sub)
                    contexto_interno = texto_gerado_sub
            
            # --- FLUXO NORMAL OU COMUM MICRO-CHUNKING ---
            else:
                if status_callback: status_callback(f"⚙️ Gerando: {secao['titulo']} (Pedaço {idx_sub+1}/{len(sub_prompts)})...")
                user_prompt = base_prompt
                if contexto_interno:
                    user_prompt = (
                        "CONTEXTO DE CONTINUIDADE (Acompanhe o fluxo do que você já escreveu logo acima):\n"
                        f"{contexto_interno}\n--- FIM DO CONTEXTO ---\n\n" + user_prompt
                    )
                
                tentativas = 0
                max_retries = 2
                texto_gerado_sub = ""
                while tentativas <= max_retries:
                    texto_gerado_sub = _chamar_api(client, modelo_geracao, system_prompt, user_prompt + material_inj)
                    falhas = [e for e in entidades_obrig if e.lower() not in texto_gerado_sub.lower()]
                    if not falhas: break
                    tentativas += 1
                    user_prompt += f"\n\n[ERRO DE VALIDAÇÃO]: Inclua obrigatoriamente estes autores/leis no texto: {falhas}."
                    
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

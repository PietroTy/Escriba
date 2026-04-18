"""
modules/extractor.py — Injeção de NER (Named Entity Recognition)
Escriba v5.0

Ponto central para extrair dados rígidos e nomes do material fonte utilizando um modelo 
rápido de extração, visando munir e trancar o pipeline gerador.
"""
import json
from typing import List, Callable, Optional

try:
    import openai
except ImportError:
    pass

def extract_entities(texto: str, api_key: str, status_callback: Optional[Callable] = None) -> List[str]:
    """
    Extrai as entidades principais (nomes, leis, locais, numéricos-chave) 
    do texto bruto fornecido, isolando-as como um buffer factual a ser 
    passado ao Generator.
    """
    if not api_key:
        return []
        
    client = openai.OpenAI(api_key=api_key, base_url="https://chat.maritaca.ai/api")
    
    if status_callback:
        status_callback("🔍 Efetuando NLP Extraction (NER) dos fatos...")

    prompt_extracao = (
        "Leia o texto com absoluta atenção e atue como um bot de Named Entity Recognition.\n"
        "Liste, em formato JSON (uma array simples de strings), estritamente os seguintes grupos sem divagações:\n"
        "1) Nomes de Autores mencionados\n"
        "2) Leis, Pactos ou Políticas Públicas\n"
        "3) Cidades, Biomas e Demografia Exata\n"
        "4) Citações qualitativas marcantes\n\n"
        "Exemplo de saída: [\"Paulo Freire\", \"PNAIC\", \"Lei 9.394/96\", \"Goiás\", \"Cerrado\"]\n\n"
        "Texto:\n"
        "...\n"
        f"{texto[:15000]}\n"
        "...\n"
        "Apenas liste a Array JSON, nenhuma frase adicional."
    )

    try:
        response = client.chat.completions.create(
            model="sabiazinho-3",  # Modelo leve e rápido perfeito pra NER
            messages=[
                {"role": "user", "content": prompt_extracao},
            ],
            temperature=0.0,   # Determinístico
            max_tokens=600,
        )
        
        saida_bruta = response.choices[0].message.content
        # Tratamento seguro caso a IA coloque blocos markdown de json
        saida_bruta = saida_bruta.replace('```json', '').replace('```', '').strip()
        
        entidades = json.loads(saida_bruta)
        if isinstance(entidades, list):
            return [str(e) for e in entidades]
        return []
        
    except Exception as e:
        if status_callback:
            status_callback(f"⚠️ Alerta NER Extractor: Falha na listagem determinística ({e}).")
        return []

def extract_required_entities_from_prompt(prompt_usuario: str, api_key: str) -> List[str]:
    """
    NLP extraindo autores e leis nominais exigidas NO PRÓPRIO prompt para a 
    validação de Loop Pós-Geração.
    """
    if not api_key:
        return []
    try:
        client = openai.OpenAI(api_key=api_key, base_url="https://chat.maritaca.ai/api")
        p = (
            "Como assistente de NER restrito, leia o comando abaixo e extraia estritamente "
            "Nomes de Autores, Teorias ou Leis Específicas que foram citados.\n"
            "Retorne APENAS um Array JSON estrito. Ex: [\"Paulo Freire\", \"LDB\", \"Loureiro\"].\n"
            "Se o comando não obrigar nominalmente nenhum autor/lei, retorne [].\n\n"
            f"Comando:\n{prompt_usuario}"
        )
        response = client.chat.completions.create(
            model="sabiazinho-3",
            messages=[{"role": "user", "content": p}],
            temperature=0.0,
            max_tokens=200,
        )
        sbruta = response.choices[0].message.content.replace('```json', '').replace('```', '').strip()
        e = json.loads(sbruta)
        if isinstance(e, list):
            return [str(x) for x in e]
        return []
    except Exception:
        return []

def filter_context_for_prompt(texto_fatos: str, base_prompt: str, api_key: str, status_callback: Optional[Callable] = None) -> str:
    """
    NLP fatiando o Payload: Isola unicamente os parágrafos do `texto_fatos` que 
    são estritamente pertinentes ao `base_prompt` atual.
    Oculta o resto para evitar vazamento de memória e alucinação de escopo.
    """
    if not api_key or not texto_fatos.strip():
        return texto_fatos

    if status_callback:
        status_callback("🔍 Recortando contexto exato para o tópico atual...")

    try:
        client = openai.OpenAI(api_key=api_key, base_url="https://chat.maritaca.ai/api")
        p = (
            "Você é um filtro de contexto documental impecável.\n"
            "Abaixo você tem o MATERIAL-FONTE completo e a TAREFA ATUAL.\n"
            "Sua missão é extrair do MATERIAL-FONTE APENAS os trechos, dados e parágrafos que são vitais para cumprir a TAREFA ATUAL.\n"
            "Se a tarefa for sobre relato pessoal/trajetória, extraia apenas as partes biográficas.\n"
            "Se a tarefa for sobre leis (PNE, etc.), extraia apenas os dados técnicos e teóricos.\n"
            "Transcreva os trechos relevantes EXATAMENTE como estão na fonte (copiar e colar). Não presuma, não invente.\n"
            "Se não houver nada pertinente no material-fonte, retorne VAZIO.\n\n"
            f"[TAREFA ATUAL]:\n{base_prompt}\n\n"
            f"[MATERIAL-FONTE]:\n{texto_fatos[:15000]}"
        )
        response = client.chat.completions.create(
            model="sabiazinho-4",
            messages=[{"role": "user", "content": p}],
            temperature=0.0,
            max_tokens=4000,
        )
        # Se devolveu vazio ou algo irrelevante
        filtrado = response.choices[0].message.content.strip()
        if len(filtrado) < 20: 
            return texto_fatos[:3000] # Fallback de segurança se ele acidentalmente deletar tudo
        return filtrado
    except Exception:
        return texto_fatos

def extract_mandatory_keys_from_context(contexto_filtrado: str, api_key: str) -> List[str]:
    """
    Varre o contexto recortado e obriga que o Escriba retenha as "Palavras-Chave Frias" 
    mais importamentes na geração final (numéricos, siglas de leis, anos, nomes teóricos).
    """
    if not api_key or not contexto_filtrado.strip():
        return []
    try:
        client = openai.OpenAI(api_key=api_key, base_url="https://chat.maritaca.ai/api")
        p = (
            "Abaixo está um fragmento de texto de pesquisa.\n"
            "Extraia as 3 a 6 entidades MAIS CRÍTICAS que formam a espinha dorsal fática desse fragmento.\n"
            "Foque exclusivamente em ANOS (ex: 2026), SIGLAS/LEIS (ex: PNE), AUTORES TEÓRICOS, e TERMOS-CHAVE ÚNICOS.\n"
            "Retorne APENAS um Array JSON estrito. Ex: [\"2026\", \"PNE\", \"Paulo Freire\"].\n\n"
            f"Texto:\n{contexto_filtrado[:3000]}"
        )
        response = client.chat.completions.create(
            model="sabiazinho-3",
            messages=[{"role": "user", "content": p}],
            temperature=0.0,
            max_tokens=200,
        )
        sbruta = response.choices[0].message.content.replace('```json', '').replace('```', '').strip()
        e = json.loads(sbruta)
        if isinstance(e, list):
            return [str(x) for x in e]
        return []
    except Exception:
        return []

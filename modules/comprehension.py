"""
modules/comprehension.py — Módulo 2: Motor de Compreensão e Grounding
Escriba v2.0

ESTADO ATUAL: Placeholder estruturado.
ROADMAP: Implementar Self-RAG com embeddings (ChromaDB/Pinecone) para:
         - Chunking semântico do texto
         - Indexação de evidências por página/parágrafo
         - Busca vetorial para Grounding anti-alucinação

Responsabilidades:
- Receber o IngestorResult
- Construir o "mapa de evidências" (chunks com ID de origem)
- Retornar ComprehensionResult para uso pelo Generator
"""

import re
from typing import Optional


class EvidenceChunk:
    """Representa um trecho indexado com rastreabilidade de origem."""
    def __init__(self, chunk_id: str, texto: str, pagina: Optional[int], paragrafo: int):
        self.chunk_id = chunk_id
        self.texto = texto
        self.pagina = pagina
        self.paragrafo = paragrafo

    def ref(self) -> str:
        """Referência de origem formatada para citação."""
        if self.pagina:
            return f"[Ref: pág {self.pagina}, parágrafo {self.paragrafo}]"
        return f"[Ref: parágrafo {self.paragrafo}]"


class ComprehensionResult:
    """Resultado padronizado da compreensão."""
    def __init__(self, texto_completo: str, chunks: list[EvidenceChunk], resumo_semantico: str):
        self.texto_completo = texto_completo
        self.chunks = chunks
        self.resumo_semantico = resumo_semantico

    def to_dict(self) -> dict:
        return {
            "total_chunks": len(self.chunks),
            "resumo_semantico_preview": self.resumo_semantico[:500],
            "status": "placeholder — Self-RAG não implementado ainda",
        }


def _split_em_chunks(texto: str, tamanho: int = 1500) -> list[tuple[int, str]]:
    """
    Divide o texto em chunks respeitando quebras de parágrafo.
    ROADMAP: Substituir por chunking semântico com embeddings.
    """
    paragrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    chunks = []
    buffer = ""
    para_num = 0

    # Detecta marcadores de página inseridos pelo ingestor
    pagina_atual = None

    for para in paragrafos:
        page_match = re.match(r"\[PÁGINA (\d+)\]", para)
        if page_match:
            pagina_atual = int(page_match.group(1))
            continue

        buffer += " " + para
        if len(buffer) >= tamanho:
            chunks.append((para_num, pagina_atual, buffer.strip()))
            buffer = ""
            para_num += 1

    if buffer.strip():
        chunks.append((para_num, pagina_atual, buffer.strip()))

    return chunks


def comprehend(texto: str, status_callback=None) -> ComprehensionResult:
    """
    Ponto de entrada principal do Motor de Compreensão.

    ROADMAP Self-RAG:
    1. Dividir em chunks semânticos
    2. Gerar embeddings com modelo de embedding local
    3. Indexar no ChromaDB com metadados de página/parágrafo
    4. Retornar ComprehensionResult com mapa de evidências

    Args:
        texto: Texto limpo do IngestorResult.
        status_callback: Função opcional de progresso.

    Returns:
        ComprehensionResult com chunks indexados.
    """
    if status_callback:
        status_callback("🧠 Analisando estrutura do documento e mapeando evidências...")

    # [PLACEHOLDER] Chunking simples por tamanho
    chunks_raw = _split_em_chunks(texto)
    chunks = [
        EvidenceChunk(
            chunk_id=f"chunk_{i:04d}",
            texto=c_texto,
            pagina=pagina,
            paragrafo=para_num,
        )
        for i, (para_num, pagina, c_texto) in enumerate(chunks_raw)
    ]

    # [PLACEHOLDER] Resumo semântico — futuramente via sabiazinho-3
    total_palavras = len(texto.split())
    resumo_semantico = (
        f"Documento processado: {total_palavras} palavras divididas em {len(chunks)} chunks. "
        f"[ROADMAP] Embeddings e índice vetorial serão gerados aqui via Self-RAG."
    )

    if status_callback:
        status_callback(f"✅ Compreensão concluída: {len(chunks)} blocos de evidência mapeados.")

    return ComprehensionResult(
        texto_completo=texto,
        chunks=chunks,
        resumo_semantico=resumo_semantico,
    )

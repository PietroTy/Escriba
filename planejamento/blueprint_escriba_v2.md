# Blueprint de Implementação: Novo Escriba v2.0

O Novo Escriba é uma central modular de processamento acadêmico que utiliza modelos Maritaca Sabiá e técnicas avançadas de Grounding para transformar PDFs brutos em documentos formais (Artigos, Apostilas, TCCs) com zero alucinação.

## 1. Stack Tecnológica e Modelos

| Componente | Tecnologia / Modelo | Justificativa |
| :--- | :--- | :--- |
| **Engine Base** | `sabiazinho-4` (128k) | Equilíbrio entre custo (R$ 4,00/1M out) e janela de contexto massiva. |
| **Auditoria/Polimento** | `sabia-4` | Modelo premium para revisão final e verificação de fidelidade. |
| **Tarefas Leves** | `sabiazinho-3` | Extração de metadados e limpeza de links (baixo custo). |
| **Ingestão de PDF** | Marker | Conversão superior de PDF para Markdown/LaTeX (preserva tabelas e fórmulas). |
| **Orquestração** | LangGraph | Fluxo de agentes cíclico (se a revisão falhar, volta para a geração). |
| **Exportação** | LaTeX + python-docx | Padrão ouro acadêmico e compatibilidade de edição. |

---

## 2. Tecnologias "Game Changers" e Pesquisas Recentes

As ferramentas integradas e conceitos acadêmicos para elevar o nível do Escriba:

1. **Chain-of-Verification (CoVe)**: Framework onde o modelo gera uma resposta inicial, levanta perguntas de verificação e então revisa o texto usando a base, reduzindo significativamente as alucinações (Dhuliawala et al.).
2. **Self-RAG**: Framework para o modelo decidir quando buscar mais informação e avaliar criticamente sua própria utilidade e fidelidade (Asai et al.).
3. **Hybrid RAG (Vector + Graph)**: Integra busca semântica vetorial e *Knowledge Graphs* (Mapas de Conhecimento) para extrair e relacionar conceitos em textos complexos.
4. **DSPy**: Transição de *Prompting* para *Programming*, permitindo a otimização automática de fluxos (prompts) rumo a uma métrica definida (Ex: "Fidelidade \> 95%").
5. **Marker (Datalab)**: Substitui o PyPDF2. Converte PDFs para Markdown/LaTeX de forma incrivelmente superior e rápida, preservando tabelas, fórmulas e referências.

---

## 3. Arquitetura de Módulos (Diretrizes Técnicas)

### Módulo 1: Ingestão Inteligente (`ingestor.py`)
- **Ação:** Substituir bibliotecas legadas pelo Marker.
- **Input:** PDF, DOCX, Imagens (OCR).
- **Processo:** Converter para Markdown estruturado. Gerar um Hash de Conteúdo para evitar reprocessamento pago e redundante.
- **Output:** Texto limpo e metadados (Título, Autor, Referências).

### Módulo 2: Motor de Compreensão e Grounding (`comprehension.py`)
- **Ação:** Implementar Self-RAG.
- **Processo:** Dividir o texto em "chunks" lógicos, mantendo a relação semântica. Criar um mapa de Evidências (Indexação por página/parágrafo).
- **Anti-Alucinação:** Cada bloco de informação baseada deve ser associado a um ID de origem.

### Módulo 3: Pipeline de Geração Agêntica (`generator.py`)
- **Ação:** Implementar Chain-of-Verification (CoVe).
- **Fluxo:**
  1. *Draft*: Gera a seção baseada no template (ex: Introdução de Artigo).
  2. *Verify*: O sistema gera perguntas internas ("Esta afirmação está no PDF?").
  3. *Execute*: O modelo responde consultando o material-fonte.
  4. *Refine*: O texto é reescrito apenas com fatos confirmados.

### Módulo 4: Templates LaTeX (`templates/`)
- **Estrutura:** Criar arquivos `.json` que apontam para esqueletos `.tex` (ABNT NBR 6022, 14724, etc.).
- **Variáveis:** O gerador deve preencher placeholders como `\title{}`, `\section{}`, e `\bibliography{}`.

---

## 4. Estratégia de Fidelidade (O Diferencial)

A fidelidade do conteúdo gerado será assegurada por um fluxo de **Double-Check Reativo**:
- **Instrução Sistêmica:** "Atue como um escriba medieval: se não está no manuscrito original, não existe no mundo."
- **Citação Obrigatória:** Toda seção gerada deve terminar com um comentário oculto, ou nota de rodapé: `[Ref: pág 12, parágrafo 3]`.
- **Módulo Polisher (`polisher.py`):** O modelo premium (`sabia-4`) confronta o "Texto Gerado" vs "Texto Fonte". Se ele detectar a quebra da fidelidade (alucinação) e conhecimento externo preenchido, o parágrafo é descartado e o agente gerador é acionado para refazê-lo. Ademais, o emprego de um **Semantic Cache**, guardando os *hashes* localmente, enxuga os tokens e custos despendidos.

---

## 5. Roteiro de Implementação (Roadmap)

### Fase 1: O Núcleo
- Configurar `.env` e integração com a API Maritaca e o script de gerência de custos `config.py`.
- Implementar o `ingestor.py` em sintonia com a bilbioteca Marker.
- Desenhar o template base em LaTeX para o primeiro tipo de documento ("Módulo Educacional").

### Fase 2: Inteligência e Anti-Alucinação
- Implementar a lógica CoVe no `generator.py`.
- Criar o script `polisher.py` usando o modelo poderoso (`sabia-4`) como perito/auditor para inspecionar falhas.
- Estruturar agendamento (modo noturno visando uso com ~30% de desconto da marataca, por ex.).

### Fase 3: Interface e Exportação
- Renovar a interface do Streamlit (`app.py`), embutindo a barra de progresso por módulo da LangGraph.
- Incorporar sistema de compilação assíncrono do LaTeX (PDF out, via Docker base / local engine).
- UI para "Preview com Evidências", apontando aos usuários as extrações pontuais.

---

## 6. Estrutura de Diretórios Sugerida

```plaintext
Escriba/
├── .env                  # Chaves Maritaca e Configs
├── config.py             # Lógica de custos e modelos (sabiazinho-4, etc.)
├── app.py                # UI Streamlit
├── modules/
│   ├── ingestor.py       # Marker Integration
│   ├── grounding.py      # Self-RAG e Indexação
│   ├── generator.py      # CoVe Logic
│   ├── polisher.py       # Auditoria com Sabiá-4
│   └── exporter.py       # LaTeX & Docx
└── templates/
    ├── abnt_artigo.tex   # Template base LaTeX
    └── estrutura.json    # Regras de cada formato
```

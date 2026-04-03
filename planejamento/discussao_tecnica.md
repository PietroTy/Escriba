# Discussão Técnica — Novo Escriba

Este documento registra as decisões e possíveis soluções para os questionamentos levantados sobre a arquitetura do **Novo Escriba**.

## 1. Múltiplos Modelos: Uso de modelos "menores"
**Pergunta:** O melhor modelo? Seria interessante um mais "burro" para processamentos não tão críticos?
**Resposta:** Sim, essa é a abordagem ideal (arquitetura de roteamento ou *fallback*).
*   **sabiazinho-3** (o mais barato): Perfeito para tarefas como extração de links, separação de parágrafos, identificação de idioma e metadata.
*   **sabiazinho-4** (128k contexto): Usado como o "cabalo de batalha" para a leitura do material principal e geração inicial (já que aguenta muitos tokens com preço atraente).
*   **sabia-4** (Premium): Útil para a revisão final (*polisher*) gramatical/formal, garantindo excelência, consumindo poucos tokens apenas no fim do processo.

## 2. Geração Final e LaTeX
**Pergunta:** Não é interessante ele trabalhar com alguma ferramenta como o LaTeX na geração final?
**Resposta:** Com certeza! O LaTeX é o padrão ouro acadêmico. 
*   **Implementação:** Em vez de gerar PDFs difíceis de manipular via ReportLab, o gerador pode produzir código LaTeX bruto.
*   Isso nos permite ter **Templates LaTeX** lindíssimos e exatos para ABNT. O código-fonte em Python apenas preenche variáveis e seções do `.tex`. O usuário final baixa o PDF (compilado por nós) ou o próprio arquivo `.tex` (para importar no Overleaf, por exemplo).

## 3. Garantias de Autenticidade (Anti-Alucinação)
**Pergunta:** Para garantia de autenticidade, o que mais pode ser adotado?
**Resposta:** Além das instruções de *prompt* mencionadas no plano, podemos agregar:
1.  **Citações Literais (Track-back):** O Escriba será obrigado a terminar cada parágrafo ou subseção com uma referência, indicando a "Página X do material-fonte" ou inserindo uma citação literal exata para provar de onde tirou.
2.  **Double-Check Reativo:** Um passe final (talvez rodando no Sabia-4) em que se injeta o "Texto Gerado" vs "Texto Fonte" e pergunta-se à IA: "Existe alguma informação no Texto Gerado que NÃO consta no Texto Fonte? Se sim, remova."
3.  **Embeddings/RAG:** Em vez de jogar tudo de uma vez no contexto, quebramos os PDFs de origem, criamos embeddings e a geração ocorre apenas com base nas **partes recuperadas** (RAG), o que restringe drasticamente a criatividade do modelo fora do texto original.

## 4. Prioridade de Formato
**Ação:** A prioridade será a **Geração de Módulos Educacionais** (Unidades, Introdução, Glossário, Anexos), respeitando a essência da ferramenta original, focando em aprimorar a fidelidade, a ausência de alucinações e a formatação (ex: via LaTeX ou PDF melhorado).

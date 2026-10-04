# QA da interpretação SA — autoajuste, evidência e adoção humana

**Status:** canônico · **Escopo:** PIL, LAJ, FV e LV Para/Passa · **Consolidado:** 2026-10-03

Este contrato consolida decisões do dono deste chat. Complementa os procedimentos QA por classe, o manual integrado de níveis e a política de confiança RAG; não certifica que toda implementação já cumpre os requisitos. Histórico e pendências: [handoff](HANDOFF-QA-SA-13PAV-20261003.md). Resultados são relatórios datados, não regras universais por nome de item.

## Escopo da revisão e autoridade de adoção

QA revisa a interpretação SA completa do item: geometria, campos, relações, tags e representação interpretada. Pode refazer o item quando necessário, mas conserva a fonte e o SA efetivo. A correção materializa uma nova camada agêntica, nitidamente identificada como resultado mais atual; **somente validação humana a torna SA adotado**. Revisão do SA não certifica, sozinha, N3/STOG/N5.

L1 avalia SA; L2 avalia L1; L3 avalia L2. Camadas posteriores exigem viewer anterior realmente populado. Mudança de origem invalida os descendentes relacionados. Não fabricar viewer se a revisão aprova sem correção necessária; manter a origem é um resultado válido. Ao corrigir, materializar campos, geometria e viewer coerentes e auditar a proposta depois da alteração.

## Conhecimento recuperado e prova local

Usar documentação de interpretação da classe, Base Global/RAG e auditoria de evidências. Registrar quais fontes foram fornecidas e realmente lidas. Busca e recibos de leitura são rastreabilidade, não comprovação de que a conclusão está certa. RAG oferece regras e referências; **o desenho original e a associação espacial local comprovam os fatos do item**.

Evitar confirmação circular: campo SA, tag gerada desse campo e resumo de outro agente que o copiou não são três provas independentes. Texto próximo de um pilar não é automaticamente a seção da viga. Associar rótulo, contorno, paredes, face/segmento e unidade antes de comparar valores. Handles e hash identificam a fonte; visão PNG permite conferir a interpretação, e SVG preserva a inspeção no portal.

## Gates e incerteza

- Enumerar unidades reais: pilar/face, laje/aresta/região e viga/lado/segmento conforme classe. Preservar ledger e set-diff para detectar omissões e duplicidades.
- Congelar fonte, interpretação e hashes antes da revisão. Revalidar origem e hash do candidato na adoção.
- Exigir evidência de cada critério, resolução dos achados e auditoria posterior da correção. PASS global não neutraliza FAIL, ausência de prova ou PASS falso por unidade.
- Onde houver medição independente CAD confiável, ela confronta a afirmação do agente. Divergência bloqueia adoção; associação ambígua ou ausência de prova fica inconclusiva, sem forçar PASS.
- Não declarar cobertura de uma classe inteira a partir de uma amostra. Aplicar gates próprios de geometria, campos, vínculos, unidades e tags por classe.

Prova técnica datada: [gate PIL P1](../scripts/arete/relatorios/qa-sa-cad-wall-gate-20261003/RELATORIO.md). O agente havia aprovado seção/distância erradas; o gate independente encontrou a divergência. O extrator publicado cobre pilares retangulares alinhados e contatos retos; **não representa gate geométrico independente completo LAJ/FV/LV, curvas ou pilares especiais**. Valores e nomes desse caso não viram exceções no motor.

## Confiança, métricas e acurácia

Separar três informações:

1. **Confiança declarada pelo agente:** julgamento do modelo, acompanhado de razões e limitações; não é probabilidade calibrada.
2. **Métricas reproduzíveis:** erro de distância/borda, interseção e IoU com referência independente, correspondência de campos, cobertura e critérios por unidade. Declarar referência, tolerância e método; geometria igual não prova semântica correta.
3. **Acurácia medida/calibração:** comparação com referência adjudicada independente, conjunto de avaliação preservado, denominador por classe/campo, erros críticos, abstenções e cobertura. Consenso do mesmo circuito que produziu a correção não basta para certificar veracidade.

Não reaproveitar resposta do agente ou aprovação de viewer como rótulo físico universal. Validação humana gera referência localizada com proveniência; promoção para regra RAG segue [tiers T0/T1/T2/TX](CONHECIMENTO/MAPA-DO-CONHECIMENTO.md). Até existir benchmark apropriado, não chamar confiança de 98% de acurácia de 98%.

## Opiniões humanas, agênticas e aprendizado após adoção

Painel comum reúne solicitação da revisão e opiniões por versão. A opinião agêntica deve informar **qual versão foi avaliada**, achados, evidências e confiança; fica abaixo da opinião humana, com apresentação equivalente. Parecer sobre origem e auditoria da correção são registros distintos.

Requisito aprovado, **ainda pendente de implementação no fechamento deste chat**: ao humano aprovar L1, criar apontamento na lista da obra comparando SA anterior efetivo e camada adotada. Preservar snapshots antes/depois, imagens, diferenças, achados resolvidos, rodada, hashes e autoria/data da adoção. Não depender somente de URLs mutáveis. Operação deve ser idempotente e recuperável, sem perda silenciosa de apontamento nem duplicação em retry; rollback conserva o registro histórico com contexto correto.

Esse apontamento é material para investigar e melhorar o motor SA posteriormente. Não autoriza treinamento automático, promoção indiscriminada a T1/T2 nem sobrescrita dos originais CAD/JSON Fase-4.

## Harmonização numérica confirmada pelo dono

O pedido anterior deste chat de uma casa fixa foi esclarecido pelo dono em 03/10/2026: **manter a regra atual da Base**, [APRESENTACAO-NUMERICA.md](CONHECIMENTO/APRESENTACAO-NUMERICA.md). Medidas com no máximo uma casa decimal, vírgula e zero final omitido; níveis absolutos em metros com exatamente duas casas. Exemplos: 147,98 → 148; 147,88 → 147,9; nível 852,19 m → 852,19. Preservar unidades e precisão interna. Não reescrever evidência histórica para fingir que ela já seguia esta convenção.

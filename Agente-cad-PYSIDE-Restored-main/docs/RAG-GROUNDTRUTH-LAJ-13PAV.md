# Fase 2 LAJ — ground truth curado, 13_PAV

**Estado:** preparação de T1 concluída; promoção no RAG ainda requer aceite
explícito do dono. Isto não reabre o veredito visual já dado à classe LAJ.

## Fonte de verdade desta rodada

- Dossiê QA: `scripts/arete/relatorios/qa_evidencias/qa_laj_phase2_groundtruth_20260712/`.
- Escopo: 31 lajes de `Obra_TREINO_1 / 13_PAV`, incluindo itens já selados.
- Resultado: 248 decisões de campo/vínculo, todas de confiança alta; nenhuma
  pergunta humana aberta.
- Candidatos de curadoria: `rag_candidatos/candidatos_t1.json`. Cada entrada é
  limitada aos itens e campos confirmados; não representa uma regra universal.

## Separação de autoridade

1. A aprovação visual da classe permanece o ground truth de apresentação e
   geração que o dono já confirmou.
2. O QA transforma somente decisões `CONFIRMAR`/`N/A_CONFIRMADO` de confiança
   alta em **candidatos T1 por item/campo**. A curadoria não grava
   `semantic_rag_kb` nem dá selo por si só.
3. Decisões `CORRIGIR` permanecem no backlog de motor. Elas são evidência de
   defeito possível, não memória que possa confirmar outro item.
4. A promoção T1 exige aceite humano, hash de evidência e trilha em
   `rag_artifact_validations`/`human_event_logs`, conforme
   `CONTRATO-QA-RAG-LOOPINGS.md`.

## Achados técnicos a preservar fora do T1

- `LAJ-PILLAR-NOT-TOUCHING`: um pilar só pode ser apoio se nome canônico,
  contato geométrico e face/lado forem demonstráveis. Pilar separado por viga
  ou gap não é apoio.
- `LAJ-NEIGHBOR-LEVEL-CONTAMINATION`: cotas/dimensões não podem preencher o
  campo semântico de nível de vizinho.
- L318 validou o padrão de reparo de visão de corte: se uma altura semântica
  confiável conflita com a altura geométrica e a fórmula produz folga negativa,
  reconstituir a distância derivada a partir da altura semântica, somente se a
  recomposição for não negativa. Isso preserva geometria e não recebe dado de
  N2/N4. O microciclo pós-reparo é
  `qa_l318_post_microcycle_20260712`.

## Próxima ação de Fase 2

O dono revisa o pacote T1 e aprova/rejeita candidatos específicos. Depois da
aprovação, o curador pode promover apenas os selecionados; os dois achados
técnicos seguem para microciclos de motor e regressão antes de qualquer T2.

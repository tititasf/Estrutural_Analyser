# Masterplan — Agente QA Global de Evidências (Arete)

**Estado:** núcleo global ativo em modo conservador.
**Interface:** `scripts/arete/qa_evidence_auditor.py` (chat/CLI; a UI só apresenta).
**Escopo:** Obra → pavimento → classe → item → campo/vínculo, com consulta cruzada controlada.

## 1. Objetivo

Transformar a validação granular do Structural Analyzer em um processo auditável:

1. interpretar cada campo e vínculo a partir de prova rastreável;
2. confirmar somente o que é inequívoco;
3. abrir achado técnico quando há erro objetivo;
4. formular pergunta humana somente quando a regra geral realmente falta;
5. registrar sessão, evidência, decisão e score de confiança; e
6. produzir ground truth curado para o RAG, sem vazar N2/N4 para N1/N3.

O agente **não é um aprovador por similaridade**. Geometria é polígono, furos, recortes, contorno e coordenadas — nunca apenas comprimento × largura. Um número perto de um elemento não vira nível; uma proximidade não vira apoio; uma ficha não prova a si própria.

## 2. Autoridade por classe

| Classe | Fonte N1 observada | Adaptador | Estado atual | Pode selar? | Próximo gate |
|---|---|---|---|---|---|
| LAJ | `slabs.links_json` + `points_json` | `LajEvidenceAuditor` | `validation_ready` | Sim, somente `apply` explícito e snapshot íntegro | RAG T1/T2 + generalização em outra obra |
| FV | `beams.data_json`, família `viga_fundo*`/`fv_*` | revisão global + contrato inicial | `diagnostic_only` | Não | golden visual próprio |
| PIL | `pillars.links_json` + `points_json`/`sides_data_json` | revisão global + contrato inicial | `diagnostic_only` | Não | golden de faces/seções e relações verticais |
| LV | `beams.data_json`, famílias `viga_a_*`, `viga_b_*`, `lv_*` | revisão global + contrato inicial | `diagnostic_only` | Não | golden de segmentos/lados |

`diagnostic_only` é uma capacidade útil já: lê o projeto, inventaria campos de verdade, evidencia cobertura e registra sessão. Ela é deliberadamente incapaz de alterar N1. Assim o agente pode ser usado em todas as classes agora, sem criar falso selo.

Os contratos iniciais de proveniência de FV/PIL/LV servem para a decisão
`CONFIRMAR` **read-only** quando há trilha N1 rastreável. Essa confirmação nunca
entra no banco nem vira selo até a promoção QG7; ela separa "há evidência
compatível" de "a classe está autorizada a ser selada".

## 3. Núcleo e adaptadores

```text
escopo explícito
  → snapshot persistido N1
  → adaptador da classe
  → fonte CAD / ficha / evidência web / contexto cross-classe / RAG
  → decisão por campo e vínculo
  → dossiê append-only + score
  → [somente adaptador validation_ready] apply transacional autorizado
```

O núcleo é comum: seleção de escopo, snapshots, hashes, sessões, perguntas explicadas, score, achados, rollback e recorrência de dúvidas. Cada adaptador define, sem herdar semântica de outra classe:

- campos obrigatórios e categorias de proveniência a/b/c/d;
- evidência mínima por campo;
- limites geométricos e relacionais;
- regras de visão de corte/cotas quando aplicável;
- fontes cross-classe permitidas;
- teste golden, gate visual e condição para `validation_ready`.

## 4. Consulta global e comandos

Sempre prefira `--project-id`: uma obra/pavimento pode ter reprocessamentos e o agente falha fechado se `--obra --pav` não for único.

```powershell
$py = 'D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe'

# Mapa completo de campos e cobertura, sem alterar a base.
& $py -X utf8 scripts/arete/qa_evidence_auditor.py discover `
  --project-id <id> --classe ALL --include-sealed

# Diagnóstico de uma família ainda não habilitada para selar.
& $py -X utf8 scripts/arete/qa_evidence_auditor.py discover `
  --project-id <id> --classe FV --item V301

# Revisão por campo/vínculo das quatro classes. Produz decisões, achados,
# perguntas com cadeia de raciocínio e score; não altera a base fora de LAJ.
& $py -X utf8 scripts/arete/qa_evidence_auditor.py review `
  --project-id <id> --classe ALL --include-sealed

# Auditoria LAJ em profundidade (read-only).
& $py -X utf8 scripts/arete/qa_evidence_auditor.py audit `
  --project-id <id> --item L318 L319 --include-sealed
```

Cada `discover` grava `manifesto.json`, `inventario_classes.json`, `resumo_global.md` e uma entrada append-only em `scripts/arete/relatorios/qa_evidencias/registro_sessoes.jsonl`.

## 5. Regras de evidência e anti-alucinação

1. **N1 é alvo, não prova de si próprio.** Campo persistido precisa de entidade/coord., fonte interpretativa ou cálculo reproduzível.
2. **N2/N4 são comparadores independentes.** Podem denunciar divergência; jamais alimentam N3 ou reescrevem N1.
3. **Visual obrigatório para gate visual.** Somente `g2v_harness.py --backend cli`; API permanece desligada.
4. **Cross-classe é consultivo.** Uma laje pode consultar pilares/vigas limítrofes para testar contato; não copia atributos entre classes.
5. **Dúvida falha fechada.** `PENDENTE` ou `REVISAR_HUMANO`, acompanhada de observação, tentativas, hipóteses recusadas, impasse e impacto.
6. **Nenhum hardcode por obra/pavimento/item.** Regra nova exige causa geral e regressão.
7. **Dados protegidos.** JSONs Fase-4 e artefatos históricos são intocáveis; alterações de N1 só ocorrem por `apply` autorizado do adaptador apto.

## 6. Plano de consolidação por classe

### Fase A — LAJ: consolidar ground truth

- manter o auditor de visão de corte, pilares de apoio, níveis e vizinhança;
- curar exemplos aprovados e antipadrões no RAG por campo/subclasse;
- validar em outro pavimento e uma obra distinta sem mudar a regra;
- promover somente evidências humanas/visuais e decisões rastreáveis a T1/T2.

### Fase B — FV: primeiro adaptador reutilizado

- gerar `PROVENIENCIA-CAMPOS-FV.md` a partir do inventário e das fichas reais;
- definir segmentos de fundo, extremidades, altura/nível, recortes e vínculos com lajes/pilares;
- rodar diagnóstico N1×N2 e G2-V nos itens canônicos;
- habilitar `audit` FV somente depois de golden sem falso positivo crítico; `apply` apenas após revisão humana.

### Fase C — PIL: relações por face e entre pavimentos

- documentar faces A…F, geometria, dimensões, vigas/lajes adjacentes, continuidade e seção;
- validar que dimensão, face e elemento conectado apontam para a mesma entidade CAD;
- fazer consulta vertical de pavimentos como evidência, nunca como cópia de atributo;
- somente então liberar escrita controlada.

### Fase D — LV: segmentos e convenções de montagem

- documentar famílias de campos A/B, segmentos, passa/para, recortes e cotagem;
- verificar cadeia segmento → face → viga → laje/pilar;
- provar o adaptador em geometrias retas, degraus e recortes antes de habilitar selo.

## 7. RAG e ground truth

O RAG entra como memória consultiva, não como autoridade. Cada entrada deve carregar:

- classe, subclasse, campo e categoria de proveniência;
- obra/pavimento de origem e versão do motor;
- fonte primária (DXF/ficha/decisão humana/PNG do gate);
- decisão, confiança, exceção conhecida e citações;
- tier: **T1** humano confirmado, **T2** regra reproduzível aprovada, **T3** hipótese (não usada para selar).

Um campo só pode alimentar T1/T2 após validação humana e gate correspondente. Toda resposta do agente que usar RAG deve citar a entrada e nunca esconder conflito com a obra atual.

## 8. Quality gates do programa

| Gate | Critério de saída |
|---|---|
| QG0 Escopo | projeto/obra/pavimento resolvido sem ambiguidade |
| QG1 Schema | inventário real e tabela de proveniência da classe completos |
| QG2 Evidência | cada campo tem fonte mínima e regra de decisão |
| QG3 Visual | golden e veredito visual canônico aprovados quando aplicável |
| QG4 Segurança | N3 sem N2/N4, preservação de selos humanos, snapshot/rollback testados |
| QG5 Generalização | outro pavimento/obra passa sem regra por item |
| QG6 RAG | somente T1/T2 citável; recorrências e dúvidas monitoradas |
| QG7 Promoção | adaptador passa de `diagnostic_only` a `validation_ready` com revisão humana |

## 9. Próxima execução recomendada

1. Rodar `discover --classe ALL --include-sealed` no projeto de 13_PAV e arquivar o inventário-base.
2. Para FV, usar o inventário + diagnóstico canônico para escrever a proveniência antes de qualquer validação automática.
3. Repetir para PIL e LV, mantendo LAJ como corpus de referência para o núcleo, não como regra semântica reaproveitada.
4. Quando uma classe alcançar QG0–QG6, implementar seu adaptador de decisão e submetê-lo a revisão visual/humana antes de liberar `apply`.

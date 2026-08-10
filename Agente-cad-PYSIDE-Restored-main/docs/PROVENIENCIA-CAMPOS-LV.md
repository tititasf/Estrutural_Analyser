# Proveniência de campos LV — contrato completo

**Classe:** Laterais de Viga (LV)  
**Estado:** `validation_ready` via `LvEvidenceAuditor` (`scripts/arete/qa_fv_lv_adapters.py`)  
**Matriz:** 4 contratos independentes: `A_PARA`, `B_PARA`, `A_PASSA`, `B_PASSA`  

---

## 1. Regra de Invariância e Isolamento

1. **Faces A e B não são intercambiáveis:** `viga_a_*` e `viga_b_*` devem obrigatoriamente referenciar entidades e segmentos de suas respectivas faces no DXF estrutural.
2. **Comportamentos PARA e PASSA são independentes:** O comportamento `PARA` (termina no encontro) e `PASSA` (continua através do encontro) possuem ajustes de extremidade, painéis e presenças de encaixe próprios.
3. **Proibição de Fallback FV:** Atributos de Laterais de Viga não podem derivar de Fundos de Viga (`_sa_meta.fv_dimension_fallback = false`).
4. **Isolamento de Contrato:** `behavior_isolated = true` obrigatório para a validação de cada contrato.

---

## 2. Mapeamento de Proveniência de Campos por Família

| Família Observada | Campo / Padrão N1 | Categoria G4 | Prova Mínima no DXF N1 / SA | Evidência no Código |
|---|---|---|---|---|
| **Identidade & Seção** | `fields.nome`, `fields.dimensao`, `secao_transversal` | (a) extraível | Rótulo textual da viga + polilinha de seção no DXF estrutural | `src/core/beam_interpreters/lateral_viga.py` |
| **Segmentação Lado A** | `viga_a_seg_N_exists`, `viga_a_seg_N_dim`, `viga_a_seg_N_contour` | (a) extraível | Polilinha N1 do segmento no Lado A + cotas associadas | `src/core/lv_generation_contract.py` |
| **Segmentação Lado B** | `viga_b_seg_N_exists`, `viga_b_seg_N_dim`, `viga_b_seg_N_contour` | (a) extraível | Polilinha N1 do segmento no Lado B + cotas associadas | `src/core/lv_generation_contract.py` |
| **Extremidades Inicial / Final** | `*_ini_name`, `*_end_name`, `*_ini_type`, `*_end_type` | (a) relação | Interseção geométrica do endpoint com Pilar (`P#`), Viga (`V#`) ou Laje (`L#`) | `src/core/beam_interpreters/lateral_viga.py` |
| **Comprimentos** | `*_comprimento_total`, `*_comp_seg_N` | (b) algorítmico | Soma dos comprimentos dos segmentos N1 sem contar sobreposições | `src/core/lv_generation_contract.py` |
| **Nível & Alinhamento** | `*_nivel_viga`, `*_lajes_contato` | (a)/(b) | Cota de nível da viga e polilinha de laje em contato com o Lado A/B | `src/core/beam_interpreters/lateral_viga.py` |
| **Aberturas & Recortes** | `*_abert_exists`, `*_abert_coords`, `*_abert_dims` | (a) extração | Polilinha fechada de furo/abertura contida na lateral | `src/core/lv_generation_contract.py` |
| **Comportamento & Contrato** | `lv_generation_contracts.{Para,Passa}.{A,B}` | (c) convenção/contrato | Matriz de 4 contratos com `contract_id`, `side`, `behavior`, e `readiness` | `src/core/lv_generation_contract.py` |
| **Vínculos de Origem** | `structural_segments.*.source_key`, `*.source_slot` | (c) convenção | Ponteiro determinístico ligando o painel N3 ao segmento N1 de origem | `scripts/arete/qa_fv_lv_adapters.py` |

---

## 3. Matriz dos 4 Contratos Rígidos LV

```text
               ┌───────────────────────┬───────────────────────┐
               │        LADO A         │        LADO B         │
┌──────────────┼───────────────────────┼───────────────────────┤
│  COMPORT.    │  Contract: A_PARA     │  Contract: B_PARA     │
│    PARA      │  side: A, behavior: P │  side: B, behavior: P │
├──────────────┼───────────────────────┼───────────────────────┤
│  COMPORT.    │  Contract: A_PASSA    │  Contract: B_PASSA    │
│    PASSA     │  side: A, behavior: S │  side: B, behavior: S │
└──────────────┴───────────────────────┴───────────────────────┘
```

---

## 4. Regras Anti-Vazamento e Condições de Aceite G4

1. **Proibido usar N2/N4:** Nenhuma coordenada, dimensão ou divisão de painel de N2 ou N4 pode ser injetada em N1/N3.
2. **Proibido Espelhamento Cego:** O Lado B não pode ser gerado por cópia simples do Lado A sem checagem de simetria geométrica no DXF N1.
3. **Proibido Fallback de Fundo:** Se o segmento lateral não possuir dimensão explícita, o sistema deve marcar `PENDENTE` em vez de consultar a tabela de fundos (`fv`).
4. **Evidência de Ingestão RAG:** O RAG só pode registrar ingestão se os 4 contratos estiverem isolados e validados visualmente via `g2v_harness.py --backend cli`.

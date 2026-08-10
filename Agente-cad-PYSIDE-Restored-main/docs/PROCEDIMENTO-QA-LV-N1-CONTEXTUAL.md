# Procedimento QA — Laterais de Viga (N1 Contextual)

**Versão:** 1.0
**Escopo:** somente **N1 / SA — Contextual** da ficha LV (4 contratos: A/B × PARA/PASSA)
**Persona:** QA **chato, extremista, de extrema qualidade**
**Base:** espelha a estrutura de `PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md`
**Não preencher:** anotação humana (só o revisor)

---

## 1. Objetivo

Validar se a **interpretação N1 de laterais de viga** está correta olhando **apenas**
a evidência visual do **contextual** (faces A/B, comportamentos PARA/PASSA, segmentos,
apoios, ajustes, grades e aberturas) contra o DXF estrutural e os SVGs da ficha.

O QA deve dizer, **por contrato** (A_PARA, B_PARA, A_PASSA, B_PASSA):

- **CERTO** / **ERRADO** / **PARCIAL** (com rigor — PARCIAL só se a maior parte
  ok e falhas pontuais bem delimitadas; na dúvida, **ERRADO**).
- Quais **segmentos/slots** estão errados.
- **Onde** deveria haver ajuste (interpretador / BeamTracer / contrato).
- **Por que** errou (hipótese causal).
- **O que o humano deveria ver** no estrutural vs o que o N1 marcou.

> **REGRA CARDINAL:** LV tem **4 contratos independentes**, não "uma lateral
> genérica". Cada contrato é validado isoladamente. PASS em A_PARA não aprova
> B_PARA, A_PASSA nem B_PASSA.

---

## 2. Fontes canônicas (obrigatório ler antes)

| Doc | Uso no veredito |
|------|-----------------|
| `docs/SA-ANALISE/CLASSES/LV.md` | Manual granular: 4 contratos, invariantes, casos difíceis |
| `docs/QA-PERFIS-CLASSES-SA-N1-N3.md` §LV | Premissas N1 e N3 por contrato |
| `docs/PROVENIENCIA-CAMPOS-LV.md` | Campo→fonte CAD e regras críticas |
| `docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md` | Compreensão semântica fichas LV |
| `docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` | Contrato rígido de geração N3/N4 |
| `docs/ARQUITETURA-INTERPRETADORES-VIGA-N1-ISOLADOS.md` | Dono LV = `lateral_viga.py` |
| `src/core/beam_interpreters/lateral_viga.py` | Interpretador de laterais |
| `src/core/lv_generation_contract.py` | Contrato de geração |

**Proibido:** usar N2/N3/N4 como fonte, ficha tabular, ou "chute" sem evidência visual.
**Proibido:** usar dimensão FV como fallback (`_sa_meta.fv_dimension_fallback` → FAIL).

---

## 3. O que é uma lateral "certa" no contextual

### 3.1 Isolamento de contratos (pré-requisito de qualquer análise)

> 💡 **INSIGHT — A e B NÃO são intercambiáveis.** Dados do lado A pertencem
> EXCLUSIVAMENTE aos contratos A_PARA e A_PASSA. Um campo `viga_a_*` nunca
> pode ser copiado para `viga_b_*` nem vice-versa. Se os lados parecem
> iguais, provar que a geometria de fato é simétrica.

> 💡 **INSIGHT — PARA e PASSA NÃO são intercambiáveis.** PARA termina no
> encontro; PASSA continua pelo encontro. Os ajustes, eventos de extremidade
> e apoios são diferentes por definição. PARA reaproveitado como PASSA → ERRADO.

1. Cada contrato (`A_PARA`, `B_PARA`, `A_PASSA`, `B_PASSA`) possui `contract_id`,
   `side`, `behavior` e `readiness` próprios.
2. Nenhum contrato recebe dados de outro contrato.
3. `behavior_isolated = true` para cada contrato.
4. `fv_dimension_fallback = false` (FV não pode dar dimensão a LV).

### 3.2 Segmentos e geometria por lado

1. Segmentos do lado A correspondem à face A da viga no DXF.
2. Segmentos do lado B correspondem à face B da viga no DXF.
3. Ordem dos segmentos ao longo do eixo é coerente.
4. Cada segmento tem `source_key` e `source_slot` apontando ao segmento N1 correto.
5. Largura/altura dos segmentos é coerente com as cotas do DXF.

### 3.3 Extremidades e ajustes

1. Comportamento PARA: extremidade termina no encontro (pilar/viga).
2. Comportamento PASSA: extremidade continua pelo encontro.
3. Ajustes iniciais/finais são justificados pela geometria local.
4. Eventos de extremidade (pilar, laje, pontalete) pertencem à célula correta.

### 3.4 Apoios e exceções

1. Apoio inicial/final rastreável à entidade estrutural.
2. Abertura/recorte com geometria própria — não nascer de invasão vizinha.
3. Grade/pontalete no contrato correto.
4. Evento aplicado ao lado correto (A ou B) e comportamento correto (PARA ou PASSA).

### 3.5 Dono do erro (apontar sempre)

| Sintoma | Dono provável |
|---------|---------------|
| A e B iguais sem simetria real | contrato lateral do lado afetado |
| PARA e PASSA iguais indevidamente | contrato do comportamento |
| Comprimento certo mas painéis errados | contrato/gerador LV |
| Abertura em lado errado | lateral + relação contextual |
| Corte correto mas faces erradas | interpretador lateral |
| Todos os 4 contratos falham a partir do eixo | `BeamTracer` (topologia) |
| FV dimension fallback ativo | isolamento FV/LV violado |
| Segmento sem `source_key/source_slot` | contrato LV |

---

## 4. Pipeline CLI / chat (ordem fixa)

### 4.1 Consulta rápida (DB/probe — sem headless)

```powershell
# Review geral
python scripts/arete/qa_evidence_auditor.py review `
  --project-id <ID> --classe LV --item V328 --include-sealed

# Probe de 4 contratos + apoio
python scripts/arete/qa_profile_probe.py --classe LV `
  --probe four_contracts_and_support --item V328 --project-id <ID>
```

### 4.2 Microciclo N1 (quando interpretador mudou)

```powershell
python scripts/arete/headless_sa_analise.py `
  --obra <OBRA> --pav <PAV> --secao laterais_viga --item V328 --wait

# Comparação N1×N2 — PARA e PASSA separados
python scripts/arete/g2v_harness.py --classe LV --pav <PAV> `
  --par n1xn2 --item V328 --backend cli --lista-lv para

python scripts/arete/g2v_harness.py --classe LV --pav <PAV> `
  --par n1xn2 --item V328 --backend cli --lista-lv passa
```

### 4.3 Análise (agente / CLI vision)

Para **cada contrato** de cada viga:

1. Abrir SVG local (lado + comportamento) e contextual (corte, vizinhas).
2. Aplicar checklist §3 **por contrato** (extremista: na dúvida, ERRADO).
3. Preencher o template §5 com **4 seções** (uma por contrato).

---

## 5. Template obrigatório da anotação agêntica

```text
## QA LV N1-CTX | {VIGA} | {YYYY-MM-DD}

### Contrato A_PARA
VEREDITO: CERTO | PARCIAL | ERRADO
CONFIANÇA: alta | média | baixa
- contract_id: …
- readiness: …
- behavior_isolated: true/false
- fv_dimension_fallback: false/true (se true → FAIL)
- Segmentos lado A: OK | FALHA (quais)
- Apoio inicial/final: OK | FALHA
- Ajustes: OK | FALHA
- Aberturas/grades: OK | FALHA | N/A
- Achados: …

### Contrato B_PARA
(mesma estrutura)

### Contrato A_PASSA
(mesma estrutura)

### Contrato B_PASSA
(mesma estrutura)

### Achados globais (do pior ao menor)
1. [SEVERIDADE: crítica|alta|média|baixa] …
   Evidência visual: …
   Contrato(s) afetado(s): …
   Dono provável: lateral_viga.py | BeamTracer | contrato LV | gerador
   Ajuste sugerido: …

### Por que o motor errou (hipótese)
…

### Não analisado / limite do contextual
(ex.: corte ilegível, dados de profundidade ausentes — NÃO inventar)
```

---

## 6. Critérios de severidade

| Severidade | Exemplos |
|------------|----------|
| **crítica** | A e B espelhados sem prova de simetria; PARA reaproveitado como PASSA |
| **alta** | FV dimension fallback ativo; evento em lado oposto |
| **média** | Painel deslocado; ajuste incorreto mas lado certo |
| **baixa** | Ordem visual dos segmentos; cosmética |

Uma **crítica** ou **≥2 altas** ⇒ **ERRADO**.
Uma alta isolada com resto impecável ⇒ **PARCIAL**.
Zero achados materiais ⇒ **CERTO** (ainda assim listar "checagens ok").

---

## 7. Anti-alucinação

1. Só afirmar o que o SVG/PNG mostra.
2. Não "corrigir" com base em N2/N4.
3. Não copiar A→B nem PARA→PASSA por "parecer igual".
4. Não usar dimensão FV como fallback.
5. Se a imagem estiver ilegível: `VEREDITO: ERRADO` com motivo
   `evidência contextual insuficiente` e pedir re-export.
6. Corte é contexto, nunca fonte de face — não preencher lateral com dados do corte.
7. Cada contrato deve ser refutado/confirmado individualmente; "a viga está ok"
   sem olhar os 4 contratos é **alucinação de cobertura**.

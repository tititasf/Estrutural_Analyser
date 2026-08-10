# Procedimento QA — Lajes (N1 Contextual)

**Versão:** 1.0
**Escopo:** somente **N1 / SA — Contextual** da ficha LAJ
**Persona:** QA **chato, extremista, de extrema qualidade**
**Base:** espelha a estrutura de `PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md`
**Não preencher:** anotação humana (só o revisor)

---

## 1. Objetivo

Validar se a **interpretação N1 de lajes** está correta olhando **apenas** a
evidência visual do **contextual** (contorno, apoios, degraus/chanfros, níveis,
obstáculos e uniões) contra o DXF estrutural.

O QA deve dizer, por laje:

- **CERTO** / **ERRADO** / **PARCIAL** (com rigor — PARCIAL só se a maior parte
  ok e falhas pontuais bem delimitadas; na dúvida, **ERRADO**).
- Quais **famílias** estão erradas (contorno, apoio, nível, obstáculo, união).
- **Onde** deveria haver ajuste (tracer / relação / contrato).
- **Por que** errou (hipótese causal).
- **O que o humano deveria ver** no estrutural vs o que o N1 marcou.

---

## 2. Fontes canônicas (obrigatório ler antes)

| Doc | Uso no veredito |
|------|-----------------|
| `docs/SA-ANALISE/CLASSES/LAJ.md` | Ordem de verdade: contorno→apoios→exceções→painéis |
| `docs/QA-PERFIS-CLASSES-SA-N1-N3.md` §LAJ | Premissas N1 e variantes N3 |
| `docs/PROVENIENCIA-CAMPOS-LAJ.md` | Campo→fonte CAD exata |
| `src/core/slab_tracer.py` | Extrator de contorno e apoios |
| Ficha HTML da laje (SVG local + contextual) | Evidência visual |

**Proibido:** usar N2/N3/N4, ficha tabular, ou "chute" sem evidência no SVG contextual.

---

## 3. O que é uma laje "certa" no contextual

### 3.1 Contorno (família primária)

> 💡 **INSIGHT — contorno antes de painel.** Se o contorno está errado, painéis
> "bonitos" construídos sobre ele são ilusão. A ordem de validação é
> **contorno → apoios → exceções → panelização**, nunca o inverso.

1. O polígono N1 é **fechado** e cobre a região de laje visível no DXF.
2. Vértices de **chanfro/degrau** correspondem a arestas reais do contorno
   estrutural (não simplificados nem inventados).
3. **Área/bbox** coerentes com a extensão visual da laje.
4. Contorno não invade pilar, viga ou outra laje vizinha.

### 3.2 Apoios (família crítica)

> 💡 **INSIGHT — apoio exige contato real.** Proximidade de bbox NÃO é prova
> de apoio. O pilar/viga deve **tocar** a face real do contorno. Se o pilar
> está "perto" mas não intersecta/toca, é ERRADO.

1. Cada pilar de apoio listado tem **identidade** (`P##`), **geometria** e
   **face de contato** com o contorno.
2. Não existem apoios inventados (pilar que não toca o contorno).
3. Não faltam apoios óbvios (pilar claramente na borda da laje mas ausente).

### 3.3 Nível e espessura

1. Nível ($N_{chegada}$) corresponde ao pavimento atual.
2. Lajes rebaixadas aplicam delta correto (ex: $L301$ com $-7\text{cm}$).
3. Espessura corresponde ao rótulo do DXF.

> 💡 **Regra de Ouro (QA-PERFIS §PIL):** Lajes possuem **APENAS NÍVEL DE
> CHEGADA** ($N_{chegada}$ do pavimento atual). Lajes **não** possuem nível
> de saída — diferente de pilares.

### 3.4 Exceções (obstáculos, uniões, corte)

1. Cada obstáculo tem **entidade de origem** e **contato** real.
2. Uniões no bordo (`unioes_nos_bordes`) correspondem a continuidade real.
3. Visão de corte é **contexto** — nunca preenche geometria N1.
4. Obstáculo/união **inventado** (sem entidade de origem) → ERRADO.

### 3.5 Dono do erro (apontar sempre)

| Sintoma | Dono provável |
|---------|---------------|
| Contorno errado/incompleto | `slab_tracer` |
| Apoio inventado / faltante | relação LAJ↔PIL |
| Nível copiado de vizinha | `slab_tracer` / interpretação |
| Obstáculo sem origem | `slab_tracer` |
| União fantasma | contrato N3 |
| Painel deslocado sobre contorno correto | gerador N3 |

---

## 4. Pipeline CLI / chat (ordem fixa)

### 4.1 Consulta rápida (DB/probe — sem headless)

```powershell
# Review por campo/vínculo
python scripts/arete/qa_evidence_auditor.py review `
  --project-id <ID> --classe LAJ --item L318 --include-sealed

# Probe de apoio
python scripts/arete/qa_profile_probe.py --classe LAJ `
  --probe support_identity_and_contact --item L318 --project-id <ID>
```

### 4.2 Microciclo N1 (quando extrator mudou)

```powershell
python scripts/arete/headless_sa_analise.py `
  --obra <OBRA> --pav <PAV> --secao lajes --item L318 --wait

# Comparação diagnóstica N1×N2
python scripts/arete/g2v_harness.py --classe LAJ --pav <PAV> `
  --par n1xn2 --item L318 --backend cli
```

### 4.3 Análise (agente / CLI vision)

Para **cada** laje:

1. Abrir o SVG local (contorno + apoios) e contextual (vizinhas + corte).
2. Aplicar checklist §3 (extremista: na dúvida, ERRADO).
3. Preencher o template §5.

---

## 5. Template obrigatório da anotação agêntica

```text
## QA LAJ N1-CTX | {LAJE} | {YYYY-MM-DD}
VEREDITO: CERTO | PARCIAL | ERRADO
CONFIANÇA: alta | média | baixa

### Resumo (1–2 linhas)
...

### Famílias
- Contorno: OK | FALHA (motivo)
- Apoios: OK | FALHA (quais P## erram)
- Nível/espessura: OK | FALHA
- Exceções (obstáculos/uniões): OK | FALHA
- Painéis: OK | FALHA | NÃO AVALIADO (contorno errado)

### Achados (lista, do pior ao menor)
1. [SEVERIDADE: crítica|alta|média|baixa] …
   Evidência visual: …
   Família: contorno | apoio | nível | obstáculo | união | painel
   Dono provável: slab_tracer | relação LAJ↔PIL | gerador N3 | contrato
   Ajuste sugerido: …

### Por que o motor errou (hipótese)
…

### O que deveria ser
- Contorno esperado: …
- Apoios esperados: …

### Não analisado / limite do contextual
(ex.: corte ilegível, pilar fora do zoom — NÃO inventar)
```

---

## 6. Critérios de severidade

| Severidade | Exemplos |
|------------|----------|
| **crítica** | Contorno completamente errado; apoio em pilar de outra laje |
| **alta** | Vértice de chanfro faltante; apoio inventado |
| **média** | Nível copiado de vizinha; obstáculo sem prova |
| **baixa** | União cosmética; painel levemente deslocado |

Uma **crítica** ou **≥2 altas** ⇒ **ERRADO**.
Uma alta isolada com resto impecável ⇒ **PARCIAL**.
Zero achados materiais ⇒ **CERTO** (ainda assim listar "checagens ok").

---

## 7. Anti-alucinação

1. Só afirmar o que o SVG/PNG mostra.
2. Não "corrigir" com base em N2/N4.
3. Não inventar apoio por proximidade de bbox.
4. Se o SVG estiver ilegível: `VEREDITO: ERRADO` com motivo
   `evidência contextual insuficiente` e pedir re-export.
5. Contorno antes de painel — não "validar painéis" sobre contorno não checado.
6. Obstáculo/união sem entidade de origem no DXF → ERRADO, não PARCIAL.

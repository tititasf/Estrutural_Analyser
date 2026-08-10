# REGRA — Entrega ponta a ponta com qualidade máxima

**Status:** canónico · inegociável (2026-07-19)  
**Origem:** pedido explícito do dono após entrega multi-segmento V301 que foi
**regen + smoke + HTML** sem validação unitária completa — trabalho **inválido**
como prova de qualidade, mesmo com artefacto visual “bonito”.

**Aplica-se a:** todo agente (Claude / Grok / Codex / humano assistido) neste
workspace CAD-ANALYZER / Arete / N1–N4.

---

## 1. Princípio

> **Se o dono pediu para fazer X, a entrega de X tem de ser completa, ponta a
> ponta, na qualidade máxima do protocolo vigente — nunca um atalho genérico,
> parcial ou “preguiçoso” disfarçado de progresso.**

- **Completo** = cobre **todo** o escopo pedido (todas as faces, segmentos,
  vistas, itens, gates), não só a âncora “fácil”.
- **Ponta a ponta** = da fonte de verdade até o veredito/evidência final,
  sem pular etapas do pipeline.
- **Qualidade máxima** = o mesmo rigor da unidade âncora em **cada** parte
  do escopo; o protocolo de `docs/PIPELINE-VISAO-N2-N3-N4-ANTIALUCINACAO.md`
  (desenho) ou o de N1-V (interpretação), conforme a família.
- **Válido** = só o que passou as etapas do protocolo pode ser chamado de
  PASS / “ok” / “validado” / candidato a selo laranja.

**Smoke, regen, HTML, contagem de `40,2==0`, “renderizou”** são **meio de
caminho**, nunca substituto de validação.

---

## 2. Proibições (anti-preguiça)

| Proibido apresentar como “feito / validado” | Porquê |
|---------------------------------------------|--------|
| Regen N4 + PNG full sem inventário por parte | Não prova ⊆ N2 |
| HTML “completo” só com zooms e lista de cotas | Evidência sem set-diff |
| Check raso (`40,2` ausente, n_dims, labels) | Smoke, não G/R/P |
| Validar só a âncora e **inferir** o resto | Alucinação de cobertura |
| “Parece ok no HTML” / “processo criado, logo passou” | Veredito sem prova |
| PASS/FAIL omitido por unidade com escopo multi | Escopo incompleto |
| Dizer “todos os segmentos passaram” sem tabela | Mentira por omissão |
| Encerrar com “confere o HTML” sem veredito próprio | Transferir o trabalho |

Se o tempo/token não chega para o escopo inteiro:

1. **Dizer explicitamente** o que ficou **fora** do E2E.
2. Entregar tabela `FEITO E2E | SMOKE ONLY | NÃO FEITO`.
3. **Não** usar linguagem de PASS global.
4. Preferir **menos unidades com E2E real** a muitas com smoke.

---

## 3. Definição de “E2E válido” por tipo de pedido

### 3.1 Desenho N2 · N3 · N4 (ex.: “valida todos os segmentos da viga”)

Para **cada** unidade/parte no escopo (face A/B, CONT, corte, …):

| # | Etapa | Entregável mínimo |
|---|--------|-------------------|
| 1 | Paths + âncora | origin, h, widths, clip da **unidade** |
| 2 | Inventário G+R coords | JSON/ledger gabarito × candidato |
| 3 | Set-diff | EXTRA/MISSING/MATCH; hard FAIL se EXTRA rótulo ou EXTRA estrutural |
| 4 | Overlay / zoom | PNG ou SVG da unidade (não só vista global) |
| 5 | Visão ancorada | leitura com grounding em IDs do inventário |
| 6 | Veredito | `PASS` \| `FAIL` \| `SUSPEITO` **por unidade** + motivo |
| 7 | Pack | HTML/relatório com **todas** as unidades + tabela de vereditos |

**Só então** o pedido “todos os segmentos” está cumprido.

Referência: `docs/PIPELINE-VISAO-N2-N3-N4-ANTIALUCINACAO.md` ·  
`docs/QA-N2-N4-COMPARACAO-FIDELIDADE.md` ·  
`docs/QA-VISAO-EVIDENCIA-CANONICA.md`.

### 3.2 Interpretação N1

Para **cada** campo/item no escopo: evidência estrutural, decisão
CONFIRMADO|N/A|PENDENTE|REVISAR, proveniência — **não** “o N4 está bonito”.

### 3.3 Fix de motor / gerador

1. Reproduzir falha com evidência.  
2. Fix por **fórmula universal** (Regra de Ouro — zero hardcode de item).  
3. Regen.  
4. **Re-correr o E2E da secção 3.1/3.2 no escopo afetado** (não só a unidade
   que motivou o fix).  
5. Regressão mínima na âncora se o fix for multi-classe.

### 3.4 “Gera o HTML completo”

HTML completo **inclui** a tabela de vereditos E2E e links para inventário/
overlay por unidade. HTML só com imagens = **pack de revisão**, não
certificação — e o relatório deve rotular assim.

---

## 4. Linguagem obrigatória no relatório ao dono

Usar com precisão:

| Frase permitida | Quando |
|-----------------|--------|
| **PASS E2E** (unidade X) | Etapas 1–6 da §3.1 cumpridas com hard-OK |
| **SMOKE ONLY** | Regen + render + checks rasos; **sem** inventário/set-diff |
| **NÃO VALIDADO** | Fora do escopo executado nesta sessão |
| **FAIL E2E** | Inventário ou visão encontrou EXTRA/MISSING/defeito |

**Proibido:** “todos passaram”, “está validado”, “ok em todos os segmentos”
sem tabela PASS E2E por unidade.

### Exemplo honesto (V301 multi-seg — lição 2026-07-19)

| Unidade | Estado real |
|---------|-------------|
| V301.A (degrau) | trabalho profundo âncora (próximo de E2E visual iterativo) |
| CONT / # / B / CORTE | **SMOKE ONLY** até correr inventário unitário |

Essa honestidade é **obrigatória**. Esconder smoke como PASS é violação desta regra.

---

## 5. Checklist do agente antes de dizer “pronto”

```text
[ ] Escopo do pedido listado (unidades / vistas / itens)
[ ] Cada item do escopo tem veredito PASS E2E | FAIL E2E | SMOKE ONLY | NÃO VALIDADO
[ ] Nenhum PASS sem inventário+evidência do protocolo da família
[ ] HTML/relatório (se pedido) inclui a tabela de vereditos, não só PNGs
[ ] Fix de motor → re-validação do escopo afetado, não só “compilei”
[ ] Se ficou incompleto: declarado no topo da resposta, sem eufemismo
[ ] Zero hardcode de item no motor (Regra de Ouro Arete)
```

---

## 6. Relação com outros canónicos

| Doc | Papel |
|------|--------|
| Este arquivo | **Como entregar** quando o dono pede trabalho |
| `PIPELINE-VISAO-N2-N3-N4-ANTIALUCINACAO.md` | **O que validar** em desenho N2·N3·N4 |
| `QA-VISAO-EVIDENCIA-CANONICA.md` | Qualidade da evidência visual |
| `CONVENCAO-SELOS-VALIDACAO.md` | Selo laranja isolado |
| `MASTERPLAN-ARETE-QUALITY-GATES.md` | Regra de Ouro do motor |
| `HANDOFF-ARETE-EXECUTOR.md` | Autonomia e proibições de overfit |

Em conflito: **não mentir cobertura** > velocidade > estética do pack.

---

## 7. Changelog

| Data | Mudança |
|------|---------|
| 2026-07-19 | Regra criada: E2E qualidade máxima; proibição de entrega smoke disfarçada; lição V301 multi-seg. |

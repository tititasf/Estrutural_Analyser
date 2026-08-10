# Pipeline de visão anti-alucinação — N2 · N3 · N4 (desenho) vs N1 (interpretação)

**Status:** canónico operacional (2026-07-18; rev. 2026-07-19 entrega E2E)  
**Âncora viva:** LV V301 face A (sessão cotas/paredes/patas/níveis)  
**Selo-alvo:** 🟠 laranja (`qa_agente`) com **validade alta** — não “parece ok”

**Complementa (não substitui):**  
`docs/REGRA-ENTREGA-E2E-QUALIDADE-MAXIMA.md` (**pedido do dono = E2E completo;
proibido smoke disfarçado de validação**),  
`docs/GEOMETRY-INDEX-N2-N3-N4.md` (**camada estruturada: GeometryIndex + diff**),  
`docs/QA-VISAO-EVIDENCIA-CANONICA.md` · `docs/QA-N2-N4-COMPARACAO-FIDELIDADE.md` ·  
`docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md` · `docs/VISION-VALIDACAO-CAMINHOS.md` ·  
`docs/CONVENCAO-SELOS-VALIDACAO.md` · `docs/MASTERPLAN-ARETE-QUALITY-GATES.md`

---

## 0−. Entrega quando o dono pede validação multi-parte

> Ver **`docs/REGRA-ENTREGA-E2E-QUALIDADE-MAXIMA.md`**.

Pedido do tipo “faz **todos** os segmentos / todas as faces / a viga inteira”:

1. **Cada** unidade no escopo corre as Fases A–E deste pipeline (§3).
2. Tabela final obrigatória: `PASS E2E | FAIL E2E | SMOKE ONLY | NÃO VALIDADO`.
3. HTML/pack **com** essa tabela — imagens sozinhas ≠ certificação.
4. **Proibido** validar só a âncora e inferir o resto; **proibido** chamar
   regen+HTML de “todos passaram”.

Lição V301 (2026-07-19): multi-seg gerado + HTML + `40,2==0` = **SMOKE ONLY**
nas CONT/B/CORTE; só a âncora A teve rigor profundo. Isso **não** cumpre o pedido
de “validar todos” — cumpre só geração e pack de revisão.

---

## 0. Decisão de família (inegociável)

| Família | Níveis | O que é | Pergunta do QA | Técnica |
|---------|--------|---------|----------------|---------|
| **DESENHO** | **N2, N3, N4** | DXF / ficha desenhada | O desenho B reproduz o desenho A (conteúdo + traço útil)? | **Mesma** para os 3 |
| **INTERPRETAÇÃO** | **N1** (+ conversão → ficha robô) | Campos estruturais do SA | Os campos/vínculos estão corretos no estrutural limpo? | **Outra** (não confundir) |

```text
N2 = gabarito reverso (humano / CE)     ← desenho
N3 = gerado a partir da rota N1→ficha  ← desenho
N4 = gerado a partir da ficha N2       ← desenho

N1 = interpretação estrutural (SA)     ← NÃO é desenho
```

### Por que N2·N3·N4 usam a **mesma** técnica

Os três são **artefactos geométricos** (LINE, TEXT/DIM, hatch, layers).  
Comparar N2×N4, N2×N3 ou N3×N4 é o **mesmo problema de fidelidade de desenho**:

1. inventário com **coordenadas** (G/R/P),
2. set-diff determinístico,
3. overlay / zoom / PNG full-render,
4. visão **ancorada** no inventário (nunca solta).

O que muda entre pares é só o **papel do gate**:

| Par | Gate típico | Significado se PASS |
|-----|-------------|---------------------|
| **N2 × N4** | G2 / G2-V | Robô + ficha N2 reproduzem o STOG |
| **N3 × N4** | G5 / G5-V | Rota produtiva ≈ rota reverso (depois de N4 certificado) |
| **N2 × N3** | diagnóstico | Gap de conversão N1→ficha (não “estilo”) |

**Ordem FAIL-closed (Arete):**  
certificar **N4 vs N2** primeiro → só depois **N3 vs N4** (e/ou N2×N3).  
Se N4 ainda alucina geometria/rótulo, PASS em N3 é ruído.

### Por que N1 **não** entra no mesmo loop visual de desenho

N1 responde: *o que é essa peça no projeto?* (alturas, apoios, lajes, vínculos).  
Não responde: *esta LINE em (294.5, 0→65) existe no DXF?*

| N1-V / G4-V | N2·N3·N4-V |
|-------------|------------|
| Campos, vínculos, proveniência | Layers, coords, cotas, contornos |
| Estrutural limpo + ficha SA | DXF recorte / gerado |
| Alucinação = campo inventado | Alucinação = traço/rótulo inventado |
| Overlay de **campo** vs evidência | Overlay de **geometria** N_a × N_b |
| Manual SA-ANALISE por classe | Recipe + inventário + gate fidelidade |

Misturar os dois = selo laranja em cima de **alucinação** (campo “ok” com desenho errado, ou desenho “bonito” com campo errado).

---

## 1. Mapa da conversão V301.A — onde estavam os erros

Erros reais encontrados (e como o QA **não** pode voltar a aprová-los por “visão solta”):

### 1.1 Camada R — Rótulo (inventado / omisso)

| Erro | Sintoma | Causa raiz | Fix motor / regra |
|------|---------|------------|-------------------|
| Cota **40,2** | Só no N4 | Soma de painéis de **marco** virava cota | `R_N4 ⊆ R_N2`; excluir marco da cadeia H |
| Cota **445,7** / total cego | Total de face sem texto no N2 | `dim_total` automático | Sem total se N2 não rotula |
| Cotas na parede fantasma | 109/124/15 no vazio à direita | Âncora em `x0+comprimento` (marco) em vez de **parede real** | `body_end = small_x` |
| **65** só TEXT solto / formato incoerente | Não era DIMENSION; distância arbitrária | Atalho anti-fantasma | DIMENSION nível 1 (−25 cm) na parede real |
| Níveis de cota V errados | 15/109/44 colados na face | Offsets ad-hoc (−8/−18/+6/+12) | Grade **L1=25 cm · L2=50 cm** esq/dir |

**Regra anti-alucinação R:**  
“A geometria tem largura X” **≠** “posso desenhar a cota X”.  
`G ∧ P ⇏ R`.

### 1.2 Camada G — Geometria (extra / miolo / patas)

| Erro | Sintoma | Causa raiz | Fix |
|------|---------|------------|-----|
| Parede / vão vazio à **direita** | Box + cotas no ar | Marcos estreitos como corpo | `body_end`; sem divisor interno de marco |
| **Stub 272,7** + H 269→291 no vão do degrau | “Caixinha” ao lado do 65 | Divisores intermediários + cap_inset no miolo | Só divisor alto do 1º painel + parede do degrau |
| Laje/hatch em caixa fantasma | Retângulos no marco | `laje_sup` em painéis de marco | Skip marco em laje_sup hatch |
| Patas H param no **y0 vazio** | Zona recuada sem tocar painel | p1/p2 sempre em y0 | `_panel_attach_y` → **ombro** se `x < degrau_end` |
| DIMENSION 65 como parede paralela | Traço fantasma no vão | Dim line mal lida / offset 0 | Dim em L1 na parede real; `dimexo=0` |

**Regra anti-alucinação G:**  
EXTRA_N\* estrutural em Painéis (não tick/stub de cota) = **FAIL** inventário, mesmo se o PNG “parece limpo” de longe.

### 1.3 Camada P — Política do motor

| Política | Alinhamento a N2 |
|----------|------------------|
| Agrupar estreitos do **corpo** (50,5) | Só se N2 rotula a soma |
| Não cotar marco (19+21,2) | Geometria do marco fica; rótulo some |
| Resto após 1º grupo (161,5) | Nível H 2 |
| Grade de cotas V 25/50 | Simétrica esq/dir + 65 em L1 |

### 1.4 Falhas de **processo de validação** (não do DXF)

Estas falhas geram **selo falso** se o agente as cometer de novo:

| Anti-padrão | Por que valida alucinação |
|-------------|---------------------------|
| Olhar só o N4 (“cotas legíveis”) | Não prova ⊆ N2 |
| “Ladrilho limpo” só no N4 | Patching unilateral |
| Score / contagem de entidades | Não pega 40,2 inventado |
| Overlay só de silhueta | Miss de rótulo e miolo |
| Confundir G com R | Justifica cota pela largura real |
| API vision sem inventário | Modelo “aprova” por gestalt |
| Tratar N1 como se fosse desenho | Campo ok ≠ DXF ok |
| Selar G5 (N3×N4) com N4 ainda sujo | Multiplica o erro |

---

## 2. Caminhos de otimização de visão (o que funciona)

Ordem de **custo × validade** (do barato/determinístico ao caro/humano):

```text
[1] Paths + âncora (origem body, h, widths, clip_rel)
[2] Inventário vetorial + set-diff  (G e R, coords em cm)
[3] Gate hard FAIL se EXTRA/MISSING own-face
[4] Overlay camadas (lines / cotas / vermelho=só candidato / azul=só gabarito)
[5] PNG full-render pareado (N2×N4, N3×N4, N2×N3) + ZOOM zonas de risco
[6] Visão do agente CLI no PNG  (grounding: só com IDs do inventário)
[7] Humano CE / SVG se residual NEAR ou gestalt
```

| Caminho | Uso | Veredito |
|---------|-----|----------|
| Inventário + coords | Obrigatório antes de qualquer PASS | ✅ base do selo laranja desenho |
| Overlay draft | Localizar EXTRA/MISSING em 10 s | ✅ |
| PNG dual-mode | Agente lê pixels | ✅ padrão CLI |
| SVG ficha | Humano/app/portal | ✅ persist |
| Zoom 65 / direita / esquerda | Zonas de degrau e cotas V | ✅ V301 |
| Recipe `must_reproduce` | Replay / regressão | ✅ alvo 100% |
| Vision API batch sem calibração | — | ❌ proibido (alucina PASS) |
| “Score 100% G2 numérico” sozinho | Candidato, não golden | ⚠️ |

Dual-mode canónico: **agente = PNG**; **persist/app/portal = SVG**  
(`docs/QA-VISAO-EVIDENCIA-CANONICA.md`).

---

## 3. Pipeline único N2 · N3 · N4 (desenho)

Mesmos passos para **qualquer par** `(gabarito, candidato)` ∈ {N2,N3,N4}²  
com papéis claros:

```text
gabarito  = N2 (reverso)  ou  N4 (já certificado)  conforme o gate
candidato = N4 | N3
```

### Fase A — Resolver e ancorar

1. Paths absolutos no DB / Fase-5 / Fase-6 (`recorte_path`, DXF N3, DXF N4 VIEW_*).  
2. Âncora da **parte** (face A/B, corte, CIMA…): `origin`, `h_body`, `panel_widths`, `clip_rel`.  
3. Normalizar coords **rel** (cm) nos dois lados.

### Fase B — Inventário determinístico (antes da visão)

Para gabarito e candidato:

| Bucket | Conteúdo |
|--------|----------|
| **G** | LINE/LWPOLY Painéis + SARR* (flags: must / void_junk / tick / context) |
| **R** | Cotas: N2 TEXT; N3/N4 DIMENSION ou TEXT; normalizar `50,5≡50.5` |
| **T** | Nomenclatura (V301.A, …) |
| **H** | Hachuras (família/pattern, não pixel) |

Set-diff → `MATCH | NEAR | MISSING_cand | EXTRA_cand`.

**Hard FAIL (bloqueia selo laranja desenho):**

- qualquer cota **EXTRA** no candidato (own-face),
- cota **MISSING** own-face no candidato (salvo política explícita),
- **EXTRA** estrutural Painéis (não classificado tick/stub dim).

### Fase C — Drafts de evidência

Materializar (sempre regenerar **após** fix):

| Artefacto | Função |
|-----------|--------|
| `ledger_{n2|n3|n4}_*.json` | coords totais |
| `recipe_n2_*.json` | só `must_reproduce` |
| `trace_*.json` | MATCH/Δcm |
| overlay PNG (lines + cotas) | EXTRA vermelho / MISSING azul |
| `VALIDAR_*.png` full | gestalt |
| `ZOOM_*` (degrau, dir, esq, marco) | zonas de risco da classe |

### Fase D — Visão ancorada (agente CLI)

1. Ler inventário (números e IDs) **antes** de abrir PNG.  
2. Read nos PNG full + zooms.  
3. Saída forçada: lista de achados com `id` do inventário ou “sem id → reabrir inventário”.  
4. Proibido: “parece igual”, “ok no geral”, PASS sem path de inventário.

### Fase E — Veredito e selo

```text
PASS desenho (par)  ⇔  inventário hard-OK
                    ∧  visão CLI sem EXTRA/MISSING residual
                    ∧  paths + recipe anexados

Selo 🟠 laranja em campos de DESENHO/fidelidade
  só com PASS do par exigido pelo gate (G2-V e/ou G5-V)
  + origem qa_agente isolada (CONVENCAO-SELOS)
```

**G5-V (N3×N4):** só depois de **G2-V N2×N4 PASS** na mesma parte.  
Caso contrário o laranja certifica **dois geradores errados iguais**.

---

## 4. Pipeline N1 (interpretação) — procedimento **diferente**

Não reutilizar o checklist de LINE/cota como se fosse N1.

### O que validar em N1

- Campos SA e vínculos (apoios, lajes, alturas, faces).  
- Proveniência e concordância com estrutural limpo.  
- Conversão N1→JSON robô (Fase-4) **sem** ler N2 como input de produção.  
- N2 só como **gabarito de valores** na calibração (não como traço).

### Técnica N1-V

1. Matriz de campos obrigatórios da classe (`SA-ANALISE/CLASSES/*`).  
2. Evidência: recorte estrutural, links, dumps de campo — **não** “o N4 está bonito”.  
3. Decisão por campo: CONFIRMADO | N/A | PENDENTE | REVISAR_HUMANO.  
4. Selo laranja de **campo** só com origem `qa_agente` e política de isolamento.  
5. G4 / convergência N1→N3 mede **valores**, não pixels de cota.

### Fronteira N1 ↔ desenho

```text
N1 PASS  ⇏  N4 parece N2
N4 PASS (G2-V)  ⇏  campos N1 corretos
Laranja completo do ITEM  ⇒  cobertura 100% origem qa_agente
  nos campos obrigatórios — incluindo os que o auditor de evidências
  só fecha com o pipeline de desenho quando o campo é “fidelidade visual”
```

---

## 5. Checklist único do agente (copiar no próximo item)

### 5.1 Desenho (N2 · N3 · N4) — G2-V / G5-V

```text
[ ] Par definido: N2×N4 | N3×N4 | N2×N3  (e papel gabarito/candidato)
[ ] Se G5: G2-V N2×N4 já PASS nesta parte
[ ] Paths + âncora (origin, h, widths, clip)
[ ] Inventário G+R com coords (JSON path anexado)
[ ] EXTRA cotas candidato == 0 (own-face)
[ ] MISSING cotas own-face == 0 (ou justificado por flag)
[ ] EXTRA Painéis estrutural == 0 (ticks classificados)
[ ] body_end / degrau / marco: sem vão fantasma (checklist LV se classe LV)
[ ] Cotas V: níveis L1=25 / L2=50 se aplicável ao padrão da face
[ ] Cotas H: patas no fundo real (ombro no recuo)
[ ] Overlay + PNG full + ZOOM zonas de risco regenerados pós-fix
[ ] Visão CLI leu PNG com grounding em IDs do inventário
[ ] Veredito PASS|FAIL|SUSPEITO + paths no relatório
[ ] ZERO hardcode de medida do item no motor (Regra de Ouro)
```

### 5.2 Interpretação (N1) — N1-V / G4

```text
[ ] Matriz de campos da classe aberta
[ ] Evidência estrutural (não DXF N4 como prova de campo)
[ ] Cada campo: decisão + proveniência
[ ] Conversão N1→ficha sem vazar N2
[ ] Diff de valores vs N2 só como gabarito de calibração
[ ] Não emitir PASS desenho a partir de N1-V
```

---

## 6. Zonas de risco genéricas (eficiência visual)

Priorizar ZOOM + inventário nestas famílias (qualquer item LV; adaptar outras classes):

| Zona | O que quebra | Probe rápido |
|------|--------------|--------------|
| Marco / fim de face | parede fantasma, cotas no ar, 40,2 | `body_end` vs total_w |
| Degrau / ombro | stub miolo, 65 fantasma, patas curtas | V em x∈vão; attach_y ombro |
| Cotas V laterais | níveis colados | offset 25/50 |
| Cotas H baixas | patas no vazio | p1/p2 y vs ombro |
| Hachura / laje_sup | caixa no marco | hatch só corpo útil |
| Rótulos | EXTRA/MISSING set | gate fidelidade |

---

## 7. Ferramentas (reuso — generalizar item a item)

| Uso | Path |
|-----|------|
| Inventário geométrico + recipe | `scripts/arete/inventario_geometria_fidelidade.py` |
| Gate rótulos N2×N4 | `scripts/arete/gate_n2_n4_fidelidade.py` |
| G2-V harness (CLI) | `scripts/arete/g2v_harness.py` |
| Motor LV | `scripts/gerar_lv_dxf_stog.py` |
| Pack V301 (padrão de saída) | `scripts/arete/relatorios/g2v/v301_reproducao/` |
| Selo / origem | `docs/CONVENCAO-SELOS-VALIDACAO.md` + `validation_model.py` |

**Meta de engenharia:** promover scripts `tmp/_v301_*` para harness **por classe/item**  
sem hardcode de V301 (Regra de Ouro).

---

## 8. Como chegámos ao resultado desejado (síntese)

```text
1. Sintoma humano (ShareX / print) → zona (direita, 65, patas, níveis)
2. Inventário N2 (coords + TEXT cotas)  vs  dump N4 (LINE + DIMENSION)
3. Classificar: G extra | R inventado | P errada | dimstyle (dimexo)
4. Fix no motor por FÓRMULA (body_end, attach_y, L1/L2, skip marco…)
5. Regen N4 → re-inventário → EXTRA/MISSING = 0 na zona
6. PNG/ZOOM → visão confirma o que o inventário já fechou
7. Só então “perfeito” local; próximo item repete o pipeline, não o chute
```

O PNG **confirma**; o inventário **prova**.  
Visão sem inventário = impressão. Inventário sem visão de profundidade = metadado órfão.  
**Os dois** fecham o laranja com validade alta em N2·N3·N4.

---

## 9. Changelog

| Data | Mudança |
|------|---------|
| 2026-07-18 | Pipeline unificado: **N2=N3=N4 família desenho** (mesma técnica); N1 separado; mapa de erros V301; checklist selo laranja anti-alucinação. |
| 2026-07-19 | §0− entrega E2E multi-parte; link `REGRA-ENTREGA-E2E-QUALIDADE-MAXIMA.md`; lição smoke V301 multi-seg. |
| 2026-07-19 | Camada **GeometryIndex** (`docs/GEOMETRY-INDEX-N2-N3-N4.md`): retrieval estruturado + diff canónico. |

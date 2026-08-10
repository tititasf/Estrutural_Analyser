# QA — Inventário mínimo para validação visual válida

**Status:** canônico (2026-07-17)  
**Aplica-se a:** G2-V / N1-V / G5-V, fichas de interpretação e review humano, pares N2×N4 (prioridade LV; extensível a PIL/FV/LAJ).  
**Complementa:** `docs/QA-VISAO-EVIDENCIA-CANONICA.md` (**ler primeiro** — qualidade de visão),  
`docs/ARETE-PLAYWRIGHT-QA-VISUAL.md`, `scripts/arete/g2v_harness.py`, `docs/SA-ANALISE/CLASSES/*.md`.

> Inventário sem visão de profundidade (DXF full layers) é **metadado órfão**.
> Visão sem inventário é **impressão**. Os dois juntos formam validação.
> **Agente:** PNG (Read). **Persist/app/portal:** SVG. Headless sem persist: imagem
> dinâmica. Dual-mode: `docs/QA-VISAO-EVIDENCIA-CANONICA.md`.

---

## 1. Problema que este protocolo resolve

Validação **inválida** (proibida):

- “parece igual”, “score alto”, “mesma contagem de entidades”;
- PASS só com gate numérico ou checklist genérico sem listar **cada** linha/cota/texto;
- comparar silhueta “mais ou menos” sem IDs e coordenadas;
- plot LINE-only chamado de “N2” (não é o N2 do Comparison Engine).

Validação **válida** (obrigatória para PASS):

1. materializar **SVG canónico** do N2 (recorte DXF full) e do N4/N3  
   (`docs/QA-VISAO-EVIDENCIA-CANONICA.md`);
2. extrair o **inventário mínimo** do gabarito (N2) e do candidato (N4/N3);
3. rastrear item a item (MATCH / NEAR / MISSING / EXTRA / VOID_JUNK);
4. ler os SVGs com visão e preencher o veredito.

Sem inventário anexado (path + resumo) **e** sem SVG canónico lido, o veredito
visual **não pode ser PASS**.

---

## 2. Inventário mínimo (schema)

Para **cada face / parte** sob auditoria (ex.: LV face A, face B, corte):

### 2.1 Metadados

| Campo | Exemplo |
|-------|---------|
| `item` / `classe` / `obra` / `pav` | V301 / LV / Obra_TREINO_1 / 13_PAV |
| `parte` | `face_A` \| `face_B` \| `corte` \| `cima` \| … |
| `origem_abs` do corpo (N2) | `(x0, y0)` canto inferior esquerdo do body |
| `origem_rel` usada no N4 | ex. VIEW_A body y_bot = −259 |
| `h_body`, `panel_widths[]`, `total_w` | 109; [244, 28.7, …]; 445.7 |
| `clip_rel` | janela em cm relativos usada na extração |
| `fonte_n2`, `fonte_n4` | paths DXF absolutos |

### 2.2 LINEs estruturais (obrigatório)

Camadas: `Painéis` / `Paineis` + `SARR*`.

Para **cada** LINE no clip (após normalizar endpoints: V bottom→top, H left→right):

| Campo | Obrigatório |
|-------|-------------|
| `id` estável | sim (`A-L0001`, …) |
| `layer` / `family` | sim |
| `rel` `(x1,y1)→(x2,y2)` cm | sim |
| `orient` H\|V\|D | sim |
| `length_cm` | sim |
| `interpretacao[]` | sim (ombro, topo, div_seg1, void, tick, marco, …) |
| `status` vs candidato | sim |
| `n4_rel` se MATCH/NEAR | se aplicável |
| `delta_avg_cm` | se match tentado |

**Status canônicos:**

| Status | Significado |
|--------|-------------|
| `MATCH` | endpoints ≤ tol (default **1,0 cm**) |
| `NEAR` | ≤ **2,5 cm** — revisar antes de PASS |
| `MISSING_N4` | no N2, ausente no N4 |
| `N2_VOID_JUNK_nao_deve_copiar` | lixo sob vão/degrau (y&lt;−1); N4 **correto** se ausente |
| `EXTRA_N4` | só no N4 (gerador inventou) |

Política de silhueta (LV, acordada): ticks de canto, stubs de marco e mini-frames
sujos do reverse **podem** ficar MISSING se a silhueta limpa for a meta — mas
devem constar no inventário com esse status, nunca “sumir” do relatório.

### 2.3 Cotas (obrigatório)

**Contrato de representação (LV N2 vs N4):**

| Fonte | Como a cota existe |
|-------|--------------------|
| **N2** | em geral **`TEXT` numérico** (muitas vezes na layer `Painéis`); **não** há `DIMENSION` no recorte |
| **N4** | `DIMENSION` (dimstyle `PAINEL`) |

Para **cada** valor:

| Campo | Obrigatório |
|-------|-------------|
| `id` | sim |
| `content` / `measurement_cm` | sim |
| `insert_rel` ou `text_mid_rel` | sim |
| `layer` / `source` (`TEXT_NUMERIC` \| `DIMENSION`) | sim |
| `role[]` (largura_seg1, h_corpo, ombro_65, grupo_seg2+3, …) | sim |
| `status` vs par | sim |
| match por **valor** (tol ~0,2 cm) + Δ posição | sim |

Agrupamentos no N2 (ex. `50.5` = 28.7+21.8; `161.5` = grupo) **não** são o mesmo
que DIMENSION N4 granular (28.7, 21.8, …): registrar como `MISSING` no valor
agrupado **e** `EXTRA_N4` nos granulares, ou documentar equivalência explícita
`grupo ≡ soma(dims)`.

### 2.4 Textos não-cota (obrigatório)

| Campo | Obrigatório |
|-------|-------------|
| `id`, `content`, `insert_rel`, `height`, `layer` | sim |
| `role` (label_elemento, vizinho, nota) | sim |
| `status` | sim |

Labels de **vizinhos** no recorte (ex. V309A, V312) = não copiar no N4 do item;
marcar `N2_CONTEXTO_VIZINHO`, não FAIL de gerador.

### 2.5 O que **não** basta

- só `entity_counts` / número de LINEs;
- só score de imagem / SSIM;
- só “overlay parece colado” sem tabela de ids;
- checklist visual com todos `true` **sem** path do inventário.

---

## 3. Onde gravar / como gerar

### 3.1 Script de referência (LV face)

```text
scripts/arete/tmp/_v301_n2_inventory.py
→ scripts/arete/relatorios/g2v/v301_n2_inventory/
    n2_faceA_inventory.md|json
    n4_faceA_inventory.json
    trace_n2_n4_faceA.json
```

Para novos itens LV, copiar o padrão do script (origem face, clip, cotas TEXT em
Painéis, match) e gravar em:

```text
scripts/arete/relatorios/g2v/{item}_n2_inventory/
```

### 3.2 Artefatos mínimos anexados ao veredito G2-V

No JSON do veredito CLI (`g2v_harness`):

```json
{
  "inventario": {
    "path": "scripts/arete/relatorios/g2v/.../trace_n2_n4_faceA.json",
    "md": "scripts/arete/relatorios/g2v/.../n2_faceA_inventory.md",
    "partes": ["face_A"],
    "summary": {
      "lines": {"MATCH": 27, "MISSING_N4": 14, "N2_VOID_JUNK_nao_deve_copiar": 25},
      "cotas": {"MATCH": 3, "MISSING_N4": 14},
      "texts": {"MATCH": 1}
    }
  }
}
```

Checklist (LV e, quando gate0 ativo, demais classes): ver §5 e
`g2v_harness.checklist_visual_defaults`.

### 3.3 Fichas HTML de interpretação / review

Em toda ficha de validação visual (granular N2×N4, review V301, quadro QA):

1. **Bloco “Inventário mínimo”** (antes do veredito):
   - painéis widths + h_body;
   - tabela SEG1 / face (ou link para o `.md` gerado);
   - cotas por valor + posição;
   - textos de identidade.
2. **Bloco “Rastreio N2→N4”**: contagens por status + lista de EXTRA/MISSING
   estruturais (não void).
3. Só depois: checkboxes de aprovação humana / JSON de veredito.

Se a ficha HTML ainda não renderiza o bloco, o agente **deve** colar o resumo
no campo de achados ou anexar o path no veredito — ausência = validação inválida.

---

## 4. Protocolo de agente (ordem FAIL-closed)

```text
1. Resolver paths N2 (recorte) e N4 (VIEW_A/B/CORTE ou DXF da parte).
2. Extrair inventário mínimo (§2) → gravar JSON+MD.
3. Portão 0 geométrico (gate0_geometry) se LV n2×n4 face.
4. Ler TODOS os SVG/PNG do manifesto (vision) + overlay se existir.
5. Cruzar inventário × leitura visual (achados com id de linha/cota).
6. Preencher checklist + inventario{} + confianca ≥ 0.85.
7. Só então veredito PASS|FAIL|SUSPEITO.
```

**Vetos automáticos de PASS** (`validar_veredito_cli`):

- qualquer item do `checklist_visual` ≠ true;
- `confianca` &lt; 0.85;
- `gate0` presente e ≠ PASS;
- `svgs_lidos` não intersecta `svgs_para_ler`;
- LV: flags de inventário mínimo ≠ true **ou** `inventario.path` ausente/inexistente.

---

## 5. Checklist visual — campos de inventário

Além dos campos geométricos/visuais existentes:

| Chave | Classe | Significado para true |
|-------|--------|------------------------|
| `inventario_minimo_extraido` | todas (obrig. LV n2×n4) | JSON/MD gerado e path no veredito |
| `linhas_estruturais_rastreadas` | LV (+ gate0) | toda LINE Painéis+SARR do clip com status |
| `cotas_valores_rastreados` | LV | toda cota numérica com valor+posição+status |
| `textos_identidade_rastreados` | LV | labels do item (não vizinhos) rastreados |
| `sem_aprovacao_por_contagem` | todas | true = não usou só contagem/score como prova |

---

## 6. Exemplo de ouro — V301 face A (SEG1)

Referência empírica: inventário em
`scripts/arete/relatorios/g2v/v301_n2_inventory/` (script
`scripts/arete/tmp/_v301_n2_inventory.py`, atualizado 2026-07-17 com status
`N2_CONTEXTO_VIZINHO_nao_copiar`).

**SEG1 corpo (x mid ≤ 244, y≥0):** 9 LINEs estruturais, **9 MATCH** com N4  
(SARR x N2 6.95 ≈ N4 7.0). As 16 linhas em x&lt;0 do clip pertencem ao vizinho
V309A (rotulo no proprio recorte), nao a V301.A — nao contar como MISSING.

**Cotas N2 (TEXT):** 244, 50.5, 111, 161.5, 65, 44, 109, 124, 15, 7, …  
**N4 (DIMENSION) pos-fix 17/07 tarde:** 244, 50.5, 111, 40.2, 44, 109, 124, 445.7 —
agora agrupado (50.5=28.7+21.8), nao mais granular.

**Política void:** paredes y&lt;0 sob degrau = `N2_VOID_JUNK_nao_deve_copiar`.
**Política contexto:** geometria/cota/texto fora da largura do proprio item
(vizinho no mesmo clip, ex. V309A/V312) = `N2_CONTEXTO_VIZINHO_nao_copiar`,
nunca `MISSING_N4` — sem essa distincao o resumo infla o gap real em ~3x
(achado 2026-07-17: 44 "MISSING_N4" brutos viraram 14 reais + 30 contexto).

**Gap real remanescente (14 linhas + 5 cotas, 2026-07-17):** concentrado
inteiramente na zona x≈244-427 — a "abertura" 50.5×65 no canto do painel de
161.5 (motor atribui `height1=44` copiado do painel1 aos sub-larguras 28.7/21.8
em vez de reconhecer painel cheio 109 + abertura recortada) e a extensao
"marco" h_total (motor grava `h_total=161.5`, um valor de largura, em vez de
124; paineis 19/21.2 saem como `laje_sup_local=7` em vez de marco mais alto).
Causa-raiz é no motor (`motor_reverso_lv.py`), nao no gerador — confirmado por
reextracao ao vivo do DXF, que reproduz os mesmos valores errados que a ficha
persistida em `reverse_eng_fichas`.

---

## 7. Extensão a outras classes (mínimo)

| Classe | Clip / parte | Estrutural mínimo | Cotas / textos |
|--------|--------------|-------------------|----------------|
| PIL | CIMA + cada face ABCD | contorno faces + seção | P##, seção, cotas por face |
| FV | cada segmento | contorno fundo + SARR | larguras painéis, apoios |
| LAJ | laje inteira | contorno + HLAZ + linhas painel | L×C, vizinhos V/P |

Mesmo schema de status e a mesma proibição de “PASS por contagem”.

---

## 8. Referências de código

| Artefato | Path |
|----------|------|
| Gate0 geométrico | `scripts/arete/g2v_gate0_geometry.py` |
| Harness + veto PASS | `scripts/arete/g2v_harness.py` (`validar_veredito_cli`) |
| Inventário V301 | `scripts/arete/tmp/_v301_n2_inventory.py` |
| QA visual fichas HTML | `docs/ARETE-PLAYWRIGHT-QA-VISUAL.md` |
| Manual LV | `docs/SA-ANALISE/CLASSES/LV.md` |
| Interpretação N2/N4 LV | `docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md` |

---

## 9. Changelog

| Data | Mudança |
|------|---------|
| 2026-07-17 | Protocolo criado após auditoria V301: cotas N2=TEXT; inventário linha-a-linha; checklist inventário no G2-V |

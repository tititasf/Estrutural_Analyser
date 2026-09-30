# Insights QA — Pilares ABCD 13_PAV (atenções humanas → L1)

> Fonte: `atencao_notas.json` do pack  
> `scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_20260804_155556_pilares_abcd`  
> + inspeção de tabelas SA e SVGs N1 por item.  
> **Uso:** agentes de QA (Ag.L1) e motor — reconhecer erros do SA e propor correção **dinâmica** (sem hardcode de P#).

---

## 0. Como o agente L1 deve trabalhar

1. Ler `aten_pil_ctx_human` + veredito SA.
2. Classificar a nota em **padrão** (tabela §1).
3. Aplicar transformações em tabelas ABCD (e flags de render).
4. Re-desenhar tags com mapa de faces correto (V vs H).
5. Só após **Validou L1** humano: consolidar no motor SA / `face_beams`.

**Anti-padrões gerais**
- Não validar dual CA/CB se C é só interior.
- Não tratar AA/BB em face longa horizontal como “interior Caso 4” (é **chega central**).
- Interior verdadeiro = face **engolida** pela viga (CC/DD típicos).
- Não copiar nome/dim de CA para CB (ou AC→BC) sem cota local.
- Bolinha da seta: chega de canto = **centro do trecho** da viga na parede; chega AA/BB = **meio da face**.

---

## 1. Catálogo de padrões (texto humano → ação L1)

| ID | Sinais no texto | Erro SA típico | Correção L1 |
|----|-----------------|----------------|-------------|
| **H1** | pilar/viga horizontal, lados ABCD errados, “mesmo problema” | Tags A=oeste… (mapa vertical) | Orientação H; A sul B norte C oeste D leste; re-render tags |
| **H2** | falta passa BD/AD | Passa só AC/BC (um extremo) | Garantir `A.passa@AD` + `B.passa@BD` (mesma viga contínua) |
| **H3** | interior AA é chega AA; chega AA/BB; ≠ interior CC/DD | `interior@AA` ou `chega@AC` no lugar de central | `chega@AA` / `chega@BB` mid-face |
| **H4** | C e D só interior, sem passa | Passa CA/DA da viga contínua | `C/D.passa→interior` CC/DD |
| **H5** | sem chega no lado A; só BB | Chega espúria em A | Limpar A.chega; B.chega@BB |
| **H6** | passa DA→DB; bolinha chega BD | Canto D errado + tip | DA→DB; tip mid-trecho |
| **G1** | geometria vinculada errada | Contorno truncado (~26 cm vs 98) | Retângulo GOLDEN comprimento×largura centrado |
| **V1** | CA/CB não existem; só interior C; passa AC/BC | Dual topo inventado | Remove CA/CB; chega→passa AC/BC; C.interior |
| **V2** | faltou passa AC e BC (+ interior C) | Multi-seg topo ausente | Flag gap face_beams; interior C se possível |
| **V3** | D 2 passa; C só interior; A/B laje+AD/BD | Dual topo + chega AC/BC | Remove dual/chega topo; AD/BD; C.interior |
| **V4** | CB/DB/BC nome+dim errados | Cópia de CA | Flag identidade local (não unificar dims) |
| **V5** | chega AC errado; falta AD; interior C; BC | Papéis trocados | Reclassifica (sem inventar nome) |
| **V6** | chega CC→interior; falta passa AC/BC | Mid chega como chega | CC interior; passa AC/BC |
| **V7** | flecha/ponoto chega AC errado | Tip na esquina | Tip centro trecho |
| **L1** | pilar em L, 6 faces | 4 faces só | Flag ficha A–F (sem inventar) |
| **OK** | SA validou | — | L1 = SA |

---

## 2. Horizontal — semântica visual (Caso 5)

```
        B (norte, longa)  ← passa AD/BD nos extremos + chega BB no meio se houver
   ════════════════════════
C  ║  viga contínua E–W   ║  D     interiores CC/DD (engolido), SEM passa
   ════════════════════════
        A (sul, longa)    ← passa AD + chega AA central se viga T termina no meio
```

| Conceito | Correto | Errado no SA |
|----------|---------|--------------|
| Passa da viga-mãe | AD e BD (e muitas vezes AC/BC) | Só um canto |
| Chega transversal | AA / BB (centro da face longa) | Marcada como interior AA |
| Interior | CC / DD (face curta dentro da viga) | Passa CA/DA |
| Tip seta | Meio do segmento de contato | Esquina do pilar |

**Itens com nota horizontal detalhada (8+):**  
P19, P34, P35, P42, P44, P46, P48, P51 (+ genéricos P11, P17, P33, P50).

---

## 3. Por item (resumo para validação humana)

### Validados SA (L1 = SA)
P1–P8, P10, P25.

### Geometria (G1)
| Item | GOLDEN plan | Ação |
|------|-------------|------|
| P12 | 19×98 | Retângulo centrado |
| P13 | 24×70 | Retângulo centrado |
| P14 | 19×98 | Retângulo centrado |

Se o **eixo** ainda estiver deslocado no DXF, o tamanho corrige mas o centro pode errar — revalidar visualmente.

### Horizontais (H1–H6)
| Item | Atenção-chave | L1 esperado |
|------|---------------|-------------|
| P11 | ABCD errados (genérico) | Mapa H + heurística Caso 5 |
| P17 | idem | idem |
| P19 | AD/BD + AA chega ≠ interior | passa AD/BD; V311 chega AA |
| P33 | genérico | mapa H + heurística |
| P34 | falta AD/BD | passa AD/BD |
| P35 | DA→DB; bolinha BD | D.passa@DB; tip fix |
| P42 | AD/BD; chega AA/BB; C/D interior | passa extremos; C/D int |
| P44 | AD/BD; AA/BB | idem |
| P46 | AD/BD; AA/BB; C/D int | idem |
| P48 | AD/BD; AA/BB bolinha; C int | tip mid-face |
| P50 | “viga horizontal” | mapa H + heurística |
| P51 | AD/BD; só BB; C/D int | sem chega A |

### Verticais com papel errado
| Item | Padrão | L1 |
|------|--------|-----|
| P9 | V7 flecha AC | tip centro trecho |
| P15–16 | V2 | flags gap AC/BC |
| P18 | passa CB/BD/AD + chega BB tip | completa passa; BB→BC se preciso |
| P20–22 | V4 identidade CB/BC | flag (estrutura dual ok) |
| P23–24 | V1 interior C | CA/CB off; passa AC/BC |
| P28–32 | V3 | C int; AD/BD; D 2 passa (gap se faltar) |
| P41 | V5 | reclassifica |
| P43/45/47 | D interior; AD+BC | D.passa→int |
| P49 | V6 | CC int; passa AC/BC |
| P26–27 | L1 | flag 6 faces |

---

## 4. Metadados para o agente (`_l1_flags`)

| Flag | Significado |
|------|-------------|
| `horizontal_faces` | Usar mapa A sul / B norte / C oeste / D leste |
| `tip_position_fix` | Bolinha mid-face (AA/BB) ou mid-trecho (canto) |
| `bad_geometry_link` | Contorno reparado ou irreparável |
| `l_shape_6faces` | Precisa ficha 6 faces |
| `cb_db_identity_wrong` | Não copiar nome/dim do par dual |

---

## 5. Checklist de validação na ficha HTML

1. Tag **L1 corrigido** → ler lista de fixes no topo.
2. Aba **Ag. camada 1**: paredes coloridas nos lados certos (H: A embaixo).
3. Tabelas L1 vs SA: papéis passa/chega/interior e cantos.
4. Bolinhas: AA/BB no meio; chega de canto no centro da faixa.
5. C/D horizontal: só interior se a nota pediu.
6. Marcar **Camada 1 Validou** se ok — senão nova atenção objetiva (face+canto+papel+nome se souber).

---

## 6. O que ainda NÃO resolve 100% sem motor/face_beams

- Identidade real CB≠CA (cotas locais no DXF) — L1 marca, não adivinha nome.
- D com 2 passa quando face_beams não tem 2 candidatos.
- P15/P16 passa AC/BC sem evidência no SA.
- Pilar L (6 faces) — só flag.
- Centro GOLDEN se o polígono truncado estava no lugar errado do pavimento.

---

## 7. Arquivos

| Artefato | Path |
|----------|------|
| Pack HTML | `.../13_PAV_20260804_155556_pilares_abcd/` |
| Atenções | `atencao_notas.json` |
| L1 tables | `propostas/P*_qa_L1_tables.json` |
| Motor tags | `pil_agentic_highlight_draw.py` |
| L1 rules | `apply_pil_aten_l1_n3_pack.py` → `apply_human_corrections` |
| Geom fix | `src/core/pillar_geometry_fix.py` |

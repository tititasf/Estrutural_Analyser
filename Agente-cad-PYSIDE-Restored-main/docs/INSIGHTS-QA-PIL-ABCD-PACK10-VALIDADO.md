# Insights QA — Pilares ABCD (pack P1–P10 · Obra_TREINO_1 / 13_PAV)

> Extraído das **validações humanas L1** (fichas 2.0) + comparação visual SA vs ouro.
> Uso: agentes de QA e motor — **não hardcodar** nomes P# / vigas; aplicar as regras
> geométricas/semânticas abaixo.

**Pack de referência:**  
`scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_20260801_192026_pilares_abcd/`  
Ouro L1: `propostas/P*_qa_L1_tables.json` + vereditos em `atencao_notas.json`.

---

## 1. O que o humano validou (padrão, não lista de itens)

| Padrão | Sintoma no SA antigo | Correção humana | Regra dinâmica |
|--------|----------------------|-----------------|----------------|
| **Dim dual topo** | BC/CB com `19/66` (= seção do **pilar**) | `14/55` (faixa da **viga**) | 1º nº = espessura N–S da faixa de topo (face C − topo laje A/B); 2º = profundidade estrutural da viga (textos `B/H` ≠ altura do pilar). Nunca copiar `largura×altura` do pilar. |
| **Fantasma AC/CA** | Dual CA+CB com dim seção-pilar em pilar de **borda** (só laje em B) | Só BC/CB | Se só uma longa tem laje e o lado sem laje tem dim seção-pilar → **podar** AC/CA (ou BC/CB simétrico). |
| **Multi-passa interior** | Passa A/B viravam `AA/BB` ou chega | Cantos de slot `AC/AD/BC/BD` | Viga em `C.interior` ou `D.interior` nos slots A/B = **passa**, **manter canto do slot** (não limpar). |
| **Não inventar CA** | Motor/L1 frágil inventava passa CA | Remover se face C sem passa real | Dualidade só com evidência; interior ≠ chega de topo. |
| **Canto preenchido** | L1 ouro ainda tinha `—` em vários | Motor preenche AD/BD/AA… | `fill_cantos_all_rows` é correto quando há d.esq/d.dir; ouro L1 pré-fill não é regressão. |

---

## 2. Por que a interpretação certa “parece” certa (guia visual)

### 2.1 Dual topo (VF* em P2–P8, e BC em P1)

- Na planta, a viga E–W no **topo** do pilar vertical ocupa uma **faixa fina** (tipicamente ~14 cm) entre o topo da laje e a face C.
- A cota colada no **nó** do pilar (ex. `19/66`) é quase sempre a **seção do próprio pilar** (19×66), não a seção de ocupação da viga na face longa.
- Tags corretas: **2 tags** no dual (chega na longa + passa na C), mesma identidade, **mesma dim de faixa** (`14/55`), distâncias simétricas na face longa: `0/52` e `52/0` para L=66 e banda 14.

**Anti-padrão QA:** validar `19/66` em BC/CB só porque a cota está no desenho perto do pilar.

### 2.2 Pilar de borda (P1)

- Só laje em **B**; face **A** sem laje adjacente (fachada / vazio).
- Chegada real só pelo lado da laje (BC/CB). Inventar AC/CA com dim de pilar = fantasma.

**Anti-padrão QA:** exigir simetria AC↔BC em todo pilar; borda quebra simetria.

### 2.3 Multi-passa A/B + interior (P10)

- Duas vigas N–S: uma “de cima” (`V309A` @ AC/BC, interior em C) e uma “de baixo” (`V309` @ AD/BD, interior em D).
- Mais chega de topo real (`V302` @ BC → dual `CB` em C).
- **Não** promover interior a chega AC/BC; **não** inventar CA se C não tem passa desse nome.

**Anti-padrão QA:** marcar “duplicata AD/BD deveria ser AC/BC” sem ver se há **duas** vigas distintas (topo vs base).

### 2.4 P9 residual (C.passa CA)

- Humano: faltou **passa CA** para `V332` (N–S, também interior em D e passa A/B).
- Face_beams atual não preenche C; regra geométrica universal ainda **não consolidada** no motor (evitar inventar CA cegamente).
- QA: se validar CA em P9-like, anotar **evidência visual** (abertura na face C no canto A) antes de pedir dualidade genérica.

---

## 3. Checklist rápido para agentes de QA (N1 ABCD)

1. **Dim dual topo:** 1º número ≈ banda laje↔C (não ≈ largura do pilar)?  
2. **Dualidade:** AC↔CA e BC↔CB só com evidência; interior D/C não vira chega de topo.  
3. **Borda:** se uma longa sem laje, desconfiar de chega fantasma nesse lado.  
4. **Cantos multi-passa:** AC/AD/BC/BD de slots preservados; AA/BB só para passa “meio de face”.  
5. **d.esq/d.dir:** chega topo usa **banda**, não 1º nº de `19/66` (evita 47 cm em vez de 52).  
6. **Tags:** dual = 2 tags (longa+C); não validar destaque se tabela ok e tag errada (ou o contrário).  
7. **N3 ficha 2.0:** 5 abas — CIMA · ABCD **para** · ABCD **passa** · GRADES **para** · GRADES **passa** (`n3_variants/{para,passa}/`).

---

## 4. Contrato motor (implementado em `pillar_abcd_tables`)

| Função | Papel |
|--------|--------|
| `_is_pillar_section_dim` | Detecta dim ≈ bbox do pilar |
| `prune_phantom_top_dual` | Remove dual fantasma no lado sem laje (dim seção-pilar) |
| `apply_top_dual_band_dims` | Reescreve dim dual → faixa viga (band + profundidade de textos/peer) |
| slots interior A/B | `papel=passa`, **mantém** canto do slot |
| `fill_cantos_all_rows` | Nunca deixar `—` em linha real |

Testes: `tests/test_pillar_abcd_tables.py`  
(`test_dual_topo_dim_not_pillar_section`, `test_prune_phantom_ac_when_no_laje_a`, `test_interior_multi_passa_keeps_slot_cantos`).

---

## 5. O que **não** fazer

- Hardcode `if name == "P2": dim = "14/55"`.  
- Copiar L1 JSON como verdade do motor em produção (L1 é proposta de QA).  
- Validar N3 sem checar variantes **para** e **passa** separadas.  
- Tratar `19/66` no nó como “viga validada” sem comparar com banda laje↔C.

---

## 6. Status pós-fix motor (sessão 2026-08-04)

| Item | Nome/dim/canto vs L1 ouro |
|------|---------------------------|
| P1 | Match semântico (cantos fill AD/BD vs `—` do ouro pré-fill) |
| P2–P8 | Match semântico (idem cantos) |
| P9 | Gap residual: falta `C.passa@CA` no motor |
| P10 | Match multi-passa AC/AD/BC/BD |

Próximo foco motor: evidência geométrica para passa em C no padrão P9 (sem inventar CA).

---

## 7. Atenções pack completo 46 (2026-08-04) — padrões L1

Fonte: `13_PAV_20260804_155556_pilares_abcd/atencao_notas.json`.

| Padrão (texto humano) | Itens tip. | Ação L1 / motor |
|----------------------|------------|-----------------|
| SA validou | P1–P8, P10, P25 | L1 = SA |
| faltou chega AC | P9 | dual AC↔CA; completar face_beams topo |
| pilar horizontal / ABCD errados | P11,17,19,33–35,42,44,46,48,50,51 | `orientation=horizontal`; labels A base/B topo/C esq/D dir |
| geometria vinculada errada | P12–P14 | flag — recorte/DXF errado |
| C interior + passa AC/BC | P15,16,23,24 | `para@CC`→interior; C.interior anula dual CA/CB; chega AC/BC→passa |
| CB/DB/BC nome+dim errados | P20–22 | dual ok; identidade local da viga (não copiar CA) |
| D 2 passa; C só interior; AD/BD | P28–32 | sem chega AC/BC; C.interior; D multi-passa |
| pilar em L (6 faces) | P26–27 | flag especial A–F |
| chega AC errado; AD; interior C; BC | P41 | reclassifica papéis |
| D interior s/ passa; AD+BC | P43,45,47 | D.passa→interior |
| chega CC→interior; passa AC/BC | P49 | CC interior; sem CB dual |

**Anti-padrão QA:** validar dual CA/CB quando a face C é **só interior** (viga N–S no topo).
**Anti-padrão QA:** em pilar horizontal, confiar em labels “A oeste / C norte” do vertical.

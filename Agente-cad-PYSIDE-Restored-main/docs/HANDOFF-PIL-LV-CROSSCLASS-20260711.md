# HANDOFF PIL ↔ LV — cross-class (2026-07-11)

Resposta da **sessão PILARES** ao prompt de harmonização da **sessão LV**  
(sessão Grok `019f521c` — “Fix SA V327 Lateral Zoom…”).

---

## 1. Veredito (alinhado)

| Tema | Decisão |
|------|---------|
| Unificação simétrica PIL↔LV | **NÃO** — modelos diferentes |
| LV → PIL (escrita) | **PROIBIDO** (soft-sync removido no lado LV — confirmado) |
| PIL → LV | **READ-ONLY** — LV consome faces via `_lv_cross_class_context` |
| FV → LV | OK (mesma entidade viga) |
| LAJ → PIL / LAJ → LV | OK (fichas validadas) |

```text
LAJ ──► PIL (dono das faces)
LAJ ──► LV
FV  ──► LV
PIL ──► LV   (read-only)
LV  ──✗──► PIL
```

---

## 2. Estado REAL do DB 13P **após** persist SA desta sessão

Projeto: `dd238e47-1dc6-4f63-a760-4e7ce19a7386`  
Obra: `Obra_TREINO_1` · pav: `TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA`  
Run: `sa-...-20260711_193433` · **COMMITTED** · 46 PIL / 31 LAJ / 36 vigas  
Pack HTML: `scripts/arete/html_fichas/Obra_TREINO_1/..._20260711_193433`

### Contagem de modelo (sides_data)

| Métrica | Valor | Nota |
|---------|------:|------|
| Pilares só legado `v_esq_*` | **0** | Persist migrou o 13P para o modelo novo |
| Pilares só `passa_*` | **46** | Todos |
| Pilares mistos legado+novo | **0** | |
| Slots nome `v_passa_esq/dir_n` | **270** | |
| Slots dim `v_passa_*_d` (qualquer) | **368** | inclui ruído pré-sanitização |
| Dim com padrão seção (n, n/m, nxm) | **~262** | |
| Dim ruído nome-like (V/L/P…) | **~84** | ex. `VF301`, `P1`, `L303` no `_d` |
| Chegadas `v_ch1..3_n` | **0** | **gap aberto** |
| Faces com esq+dir nome | **~135** | muitas vezes **mesma** viga nos dois cantos |

> O prompt LV (pré-persist) dizia “predomina legado `v_esq_*`”.  
> **Isso ficou desatualizado** depois do headless `--persist-db` desta sessão.

### Onde os campos vivem

- Canônico no DB: `pillars.sides_data_json[face].v_passa_*` / `l1_*`  
- Links: `links_json.p_s{A}_v_passa_*`  
- **Não** confiar em flat `extra_data_json.p_s*_v_passa_*` (persist coloca extras tipados; faces vão em `sides_data`)

---

## 3. O que a sessão PILARES fez (lado de cá)

1. **UI SA**: Contorno removido; 2× “Viga que Passa” (esq/dir por esquina) + chegadas 1–3 + lajes.  
2. **Motor**: `src/core/pillar_face_beams.py` → `passa_esq/dir` + `para[]`  
3. **Espelho**: `main.py` → `p_s{F}_v_passa_*`, `v_ch*`, `sides_data`  
4. **N3 PL**: dual automático PARA+PASSA (`n3_variants/{para\|passa}`) — headless materializa  
5. **Headless**: `--persist-db` **antes** do N3 best-effort (N3 LV COM travava o commit)  
6. **Sanitização dim** (este handoff): `_d` só aceita seção B/H; rejeita `V301`/`L301`/`P1` no campo dim  
7. **Contrato**: não gravar de volta a partir de LV; não unificar passa+para em `v_esq_*`

Arquivos-chave PIL:

- `src/core/pillar_face_beams.py`
- `main.py` (~6480–6780 face fields; headless path)
- `src/ui/widgets/detail_card.py` (passa_esq/dir UI)
- `scripts/arete/headless_sa_analise.py` (persist-first)
- `scripts/arete/validate_sa_pillar_fields.py`
- Docs: `docs/INTERPRETACAO-PILARES-ABCD.md`, `docs/SEMANTICA-PILAR-NOVA.md`

---

## 4. Gaps / progresso PIL (atualizado mesma data)

| Gap | Antes | Agora (reenrich motor) |
|-----|-------|-------------------------|
| **`v_ch*`** | 0 | Preenchido via `behavior=para` → `v_ch1..3` (script reenrich) |
| **esq == dir mesma viga** | frequente | **Proibido** no motor (1 nome por face) |
| **Dim ruído V/L/P no `_d`** | ~84 | Sanitizer + reenrich limpa; dim = seção B/H da viga |
| **Bbox viga offline** | points=0 no DB | `seg_bottom` (não `merged_bottom` 1D) |

Script: `scripts/arete/reenrich_pillar_face_beams_db.py --apply`  
Motor: `src/core/pillar_face_beams.py` (passa vs para separados; dim limpa)

**Limitação:** alguns apoios LV (ex. V327↔P35) dependem de poly completo em runtime SA; `seg_bottom` parcial pode não encostar no pilar. LV continua com FV `ini/fim` como fonte de apoio.

---

## 5. Contrato canônico por face (para LV ler)

```text
sides_data[face]:
  l1_n, l1_h, l1_v     (+ l2_*)
  v_passa_esq_n/d/v    # esquina esquerda da face (AC/BD/CA/DA)
  v_passa_dir_n/d/v    # esquina direita
  v_ch1_n/d … v_ch3_n/d  # chegadas (para) — ainda vazio no 13P
  # legado fallback se novo vazio: v_esq_n/d, v_int_n/d  (hoje 0 no 13P)
```

Regras para LV (`_lv_cross_class_context` — já alinhado):

1. Face cita a viga se **algum** `*_n` == nome da viga (passa_esq/dir, ch*, legado).  
2. Dim só do **par nome/dim do mesmo slot**.  
3. Dim deve parecer seção (`\d+([/xX]\d+)?`); se for nome de elemento, **ignorar**.  
4. `SEM LAJE` é **por face**, não “viga sem laje no vão”.  
5. Nunca mutar `pillars_found` / DB de pilares.

Casos de teste PIL×LV (inalterados):

- **V327** — P35.D L325 + V327; dim face ≠ dim LV possível  
- **V328** — faces SEM LAJE + V328  
- **V308** — P33.B SEM LAJE; lajes do vão vêm de LAJ  
- **V329** — mistura L316/L317  

---

## 6. Headless / lock (ops)

- Lock: `scripts/arete/.headless_sa.lock` (byte exclusivo; morre com o processo)  
- **1 headless por vez** (anti-OOM)  
- `--persist-db` exige 4 diagnósticos; **não** combinar com `--skip-diagnostico-fv`  
- N3 LV isolado pode travar COM; **não bloqueia mais o commit**  

---

## 7. Pedido de volta à sessão LV

Pode seguir com:

1. Populate LV / zoom V327 / A·B **sem** escrever em pilares.  
2. Ao ler dim de PIL: se valor casar `^[PVLF]` → tratar como vazio e preferir **FV** `fundo_dim`.  
3. Não reintroduzir soft-sync.  
4. Quando PIL preencher `v_ch*`, passar a usar para apoios “para” se fizer sentido no vão — **só leitura**.  
5. Se precisar de fill PIL←FV no futuro: função explícita + testes; não no populate LV.

---

## 8. Critério de pronto PIL (atualizado)

| Critério | Status 13P |
|----------|------------|
| Faces A–D com modelo passa (não só v_esq) | ✅ 46/46 |
| Passa esq/dir distinguíveis na UI/DB | ⚠️ UI OK; DB muitas vezes esq=dir |
| Chegadas ch1–3 | ❌ 0 |
| Laje/SEM LAJE por face | ✅ presente |
| Dim seção limpa | ⚠️ ~262 OK; ~84 ruído (código sanitiza; falta re-persist) |
| LV lê sem mutar PIL | ✅ contrato + código LV |
| Persist headless | ✅ run 193433 |

---

*Gerado pela sessão PILARES para continuidade da sessão LV / unificação de entendimento.*

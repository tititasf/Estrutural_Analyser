# Prompt — Looping de interpretação + anotação + desenho agêntico  
## (referência FV / fundos → aplicar em PIL / pilares)

**Uso:** copiar este texto (ou adaptar a seção «Missão PIL») para um agente que vai  
implementar o **mesmo padrão de QA dinâmico** que já existe em **Fundos de Viga (FV)**  
na ficha HI-FI N1 contextual.

**Persona do agente:** QA visual chato, extremista, de extrema qualidade + implementador  
mínimo (só o necessário para o loop funcionar ponta a ponta).

---

## 0. Por que existe este looping

### Problema antigo
- O **destaque SA** (vermelho/rosa) é a saída do **motor** (interpretador + topologia).  
  Ajustar SA = mudar código/regra, reprocessar, esperar — **caro e lento**.
- O revisor via o erro, mas o agente QA só escrevia texto; **não havia geometria  
  proposta** fácil de comparar lado a lado com o motor.
- Não havia **validadores humanos separados** para “motor ok?” vs “proposta ok?”.

### Solução (padrão FV, reutilizar em PIL)
Separar **duas camadas visuais** no mesmo contextual HI-FI:

| Camada | Cor / tags | O que é | Custo de mudar |
|--------|------------|---------|----------------|
| **Destaque SA** | vermelho/rosa · `S1…Sn` | interpretação atual do **motor** | alto (código + re-run) |
| **Destaque agêntico** | ciano `#00e5ff` / verde `#69f0ae` · `P1…Pn` | **proposta de correção** do agente | baixo (só desenho/JSON) |

E um **loop de anotação** com:
1. **Anotação humana** — atenção do revisor + validadores manuais SA / Agêntico  
2. **Anotação agêntica** — veredito do QA + texto obrigatório + desenho  
3. Toggle visual **SA | Agêntico | Ambos** no viewer  

**Fluxo de valor:**  
`atenção humana → refinar destaque agêntico até Validou humano → só então alinhar motor SA`

Assim o motor só é mexido **depois** que o humano e o agente já concordaram na geometria  
“correta” na camada barata (agêntica).

---

## 1. O que foi feito em FUNDOS DE VIGA (referência canônica)

### 1.1 Onde vive na UI (ficha HTML HI-FI)

Pack típico:  
`scripts/arete/html_fichas/.../fundos_viga/{VIGA}.html`  
Servidor local de notas:  
`python scripts/arete/tmp/fv_notes_server.py` → `http://127.0.0.1:8765/fundos_viga/{VIGA}.html`

**Viewer contextual (topo da ficha):**
- Toggle: **Destaque SA** | **Destaque agêntico** | **Ambos**
- Camada SA = SVG HI-FI (DXF estrutural + highlights S#)
- Camada agêntica = **mesmo HI-FI estrutural** + highlights P# (não só barras no preto)
- Pan/zoom por viewBox; HI-FI agent e SA no mesmo enquadramento quando possível

**Caixa ✏️ Anotação humana** (lado esquerdo):
- **Dentro da caixa** (compacto), duas linhas de radio:
  - 🔴 **Destaque SA** → Validou | Invalidou  
  - 🔵 **Destaque agêntico** → Validou | Invalidou  
- Textarea de atenção / notas do revisor  
- Chaves:
  - texto: `aten_fv_ctx_human_{obra}_{pav}_{beam}`
  - SA: `aten_fv_hl_sa_human_{obra}_{pav}_{beam}` = `validou` | `invalidou`
  - Ag: `aten_fv_hl_agent_human_{obra}_{pav}_{beam}` = `validou` | `invalidou`

**Caixa 🤖 Anotação agêntica** (lado direito):
- Radio **Agente validou** | **Agente invalidou** (veredito do QA automático)  
- Textarea obrigatório nos dois casos:
  - **validou** → compreensão + por que validou  
  - **invalidou** → falhas, S#/P#, causa, dono, ajuste  
- Chaves:
  - texto: `aten_fv_ctx_agent_{obra}_{pav}_{beam}`
  - radio: `aten_fv_ctx_agent_verdict_{obra}_{pav}_{beam}` = `validou` | `invalidou`

**Persistência (3 vias):**
1. `localStorage` + `#fv-notes-store` no HTML  
2. POST `http://127.0.0.1:8765/api/notes/{page}` → `{page}.notes.json` no disco  
3. Autosave em input/change/blur  

### 1.2 Desenho agêntico (proposta)

- Módulo: `src/ui/widgets/fv_qa_proposal_draw.py` + **render HI-FI**  
  `render_fv_hifi_proposal_svg` / `render_fv_hifi_n1_svg(..., highlight_mode="agent")`  
  em `src/ui/widgets/fv_hifi_n1_render.py`
- **Obrigatório:** mesmo fundo estrutural DXF do SA (linhas, textos, cotas) —  
  **não** SVG “só polígonos no preto”.
- N1 motor pode aparecer **fraco** por baixo; proposta em ciano/verde com tags **P#**.
- Artefatos:
  - `fundos_viga/propostas/{BEAM}_qa_proposta.svg` (instalado no pack, toggle lê daí)
  - JSON `{beam, proposed:[{label, points, note?}]}` em coords CAD
- CLI:  
  `python scripts/arete/tmp/qa_fv_n1_contextual_pipeline.py propose-draw --beam V302 --json ...`  
  `write-agent --beam V302 --verdict invalidou --file ...`

### 1.3 Looping operacional (ordem fixa)

```
1. Export / abrir contextual HI-FI da unidade (viga).
2. Agente analisa SÓ evidência N1 contextual (sem inventar com N2/N3/N4).
3. Preenche anotação agêntica + radio Agente validou/invalidou.
4. Se invalidou (ou parcial): gera/atualiza DESENHO agêntico (P#).
5. Humano olha toggle SA vs Agêntico vs Ambos.
6. Humano escreve ATENÇÃO na anotação humana se algo ainda falha no desenho.
7. Agente REFATORA o destaque agêntico (JSON + SVG) — NÃO o motor ainda.
8. Repete 6–7 até humano marcar «Destaque agêntico = Validou».
9. Só então: plano de fix no motor SA para bater na geometria P# validada.
10. Após fix + re-run: humano marca «Destaque SA = Validou» ou pede nova rodada.
```

**Regra de ouro:** enquanto o validador humano do **agêntico** estiver Invalidou  
(ou vazio), **proibido** “fechar” o caso só com texto; o desenho P# é a verdade  
provisória de correção.

### 1.4 Código / docs de referência FV

| Peça | Path |
|------|------|
| HI-FI + toggle + notes JS | `src/ui/widgets/fv_hifi_n1_render.py` |
| Proposta ciano/verde | `src/ui/widgets/fv_qa_proposal_draw.py` |
| Geração ficha fundo | `src/ui/widgets/preficha_fundo_html.py` |
| Pipeline CLI | `scripts/arete/tmp/qa_fv_n1_contextual_pipeline.py` |
| Servidor notas | `scripts/arete/tmp/fv_notes_server.py` |
| Procedimento QA | `docs/PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md` (§4.3.x looping dinâmico) |
| Motor FV | `src/core/beam_interpreters/fundo_viga.py` |

### 1.5 Lições aprendidas (não repetir o erro)

1. **Camada agêntica sem DXF** = inútil para o humano (só “barrinhas” no preto).  
   Sempre HI-FI estrutural + P#.
2. **ViewBox do SA (pixels matplotlib)** ≠ **viewBox CAD solto** → panzoom “apagava”  
   a proposta. HI-FI agent deve usar o **mesmo pipeline de enquadramento** do SA  
   (ou sync controlado).
3. **Radios grandes** poluem a ficha — validadores humanos **dentro** da caixa  
   humana, compactos (min-height ~26px).
4. **Dois eixos de veredito:**  
   - humano julga **camadas** (SA vs Agêntico)  
   - agente julga **sua análise** (Agente validou/invalidou)  
   Não misturar as chaves.
5. Detectar “já tem feature” no inject HTML: olhar **markup** (`id="..."`),  
   não só a string no CSS/JS.

---

## 2. Lógica para PILARES (o que o agente deve construir)

### 2.1 Missão

Replicar o **mesmo contrato UX + persistência + looping**, trocando o domínio:

| Conceito FV | Análogo PIL |
|-------------|-------------|
| Viga / fundo | Pilar / faces ou recorte contextual do pilar |
| Segmentos fundo S1…Sn | Unidades/faces/segmentos do pilar (ex. faces A–D, tramos, “unit” N1) |
| `FundoVigaInterpreter` | interpretador / pipeline de **pilares** (PIL N1 — faces, contornos, vínculos) |
| Pack `fundos_viga/` | pack de fichas PIL (ex. `pilares/`, `html_fichas/.../pilares/`) |
| Prefixo chaves `aten_fv_*` | prefixo novo **`aten_pil_*`** (não reutilizar `fv` em PIL) |
| Tags S# / P# | S# = motor PIL; P# = proposta agêntica de faces/contornos |
| Cores | **iguais**: SA vermelho/rosa; QA ciano/verde |

### 2.2 O que validar no contextual PIL (checklist mínimo)

O agente QA deve ser extremista sobre o **N1 contextual do pilar** (não misturar  
com N2/N3/N4 como “prova única”):

1. Contorno do pilar / faces batem com o estrutural DXF.  
2. Faces A–B–C–D (ou convenção da obra) sem over-merge nem face fantasma.  
3. Quebras em vigas/encontros coerentes com o desenho.  
4. Tags e líderes apontam o elemento certo.  
5. Não contaminar com laje/viga adjacente como se fosse face de pilar.  
6. Dono do erro: interpretador PIL / topologia / link classificador / UI.

### 2.3 UI alvo (espelho do FV)

No contextual unificado da ficha do **pilar**:

1. Toggle **Destaque SA | Destaque agêntico | Ambos**  
2. Camadas dual SVG: SA (motor) + agent (proposta HI-FI com DXF)  
3. **Anotação humana** com:
   - radios compactos: Validou/Invalidou **Destaque SA** e **Destaque agêntico**  
   - textarea de atenção  
4. **Anotação agêntica** com:
   - Agente validou / Agente invalidou  
   - textarea obrigatório  
5. Autosave + `.notes.json` + servidor local (pode reutilizar o notes server  
   apontando o pack PIL, ou generalizar path).

### 2.4 Contrato de chaves (sugerido para PIL)

Substituir `obra/pav/item` pelo identificador canônico do pilar (ex. `P12`, `P1`):

```
aten_pil_ctx_human_{obra}_{pav}_{pilar}
aten_pil_ctx_agent_{obra}_{pav}_{pilar}
aten_pil_ctx_agent_verdict_{obra}_{pav}_{pilar}     # validou|invalidou
aten_pil_hl_sa_human_{obra}_{pav}_{pilar}           # validou|invalidou
aten_pil_hl_agent_human_{obra}_{pav}_{pilar}        # validou|invalidou
```

Proposta em disco:

```
{pack}/propostas/{PILAR}_qa_proposta.svg
{pack}/propostas/{PILAR}_qa_proposta.json
```

JSON mínimo:

```json
{
  "item": "P12",
  "class": "PIL",
  "proposed": [
    {
      "label": "1",
      "role": "face_A",
      "points": [[x,y], ...],
      "note": "quebra no encontro com V301"
    }
  ]
}
```

### 2.5 Looping operacional PIL (igual FV)

```
atenção humana
  → agente redesenha P# (faces/contornos) no HI-FI
  → humano valida «Destaque agêntico»
  → (opcional) humano ainda invalidou SA
  → agente planeja e implementa fix no motor PIL
  → re-run N1
  → humano valida «Destaque SA»
```

**Nunca** pular o passo “agêntico validado” e ir direto a rewrite grande no motor  
sem geometria alvo.

### 2.6 Implementação técnica sugerida (ordem de build)

1. **Inventário** do que já existe em PIL: ficha HTML, recorte N1, interpretador,  
   paths de pack (ler CLAUDE.md / docs PIL / `preficha` / headless).  
2. **Extrair ou reutilizar** o chrome FV que já funciona:
   - `wrap_panzoom_viewer(mode="contextual")`
   - notes JS / radios / dual layers  
   - `render_fv_hifi_*` generalizar para `render_hifi_n1_svg` multi-classe **ou**  
     espelhar em `pil_hifi_n1_render.py` sem duplicar lógica de panzoom/notes.  
3. **Camada proposta** HI-FI com DXF do pavimento + polígonos de faces/segmentos.  
4. **Inject** nas páginas PIL existentes (cuidado: checar markup real, não CSS).  
5. **CLI** `qa_pil_n1_contextual_pipeline.py` (export / write-agent / propose-draw).  
6. **Procedimento** `docs/PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md` (cópia adaptada do FV).  
7. **Piloto** 5–10 pilares mistos → validadores humanos → 1 fix motor de exemplo.

### 2.7 O que NÃO fazer em PIL

- Não misturar FV e PIL no mesmo interpretador “por proximidade”.  
- Não usar destaque agêntico sem DXF de fundo.  
- Não gravar só em localStorage (file://) sem servidor/API de notas.  
- Não chamar “Validou SA” só porque o texto do agente está bonito.  
- Não alterar motor PIL enquanto o humano não **Validou o destaque agêntico**.

---

## 3. Prompt curto para colar no agente (PIL)

```text
Missão: implementar em PILARES (classe PIL) o mesmo looping de QA dinâmico
já usado em FUNDOS DE VIGA (FV), documentado em
docs/PROMPT-LOOPING-DESTAQUE-AGENTICO-FV-PARA-PIL.md e
docs/PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md.

Contexto FV (já feito — usar como referência de código/UX, NÃO reinventar):
- Toggle Destaque SA | Agêntico | Ambos no contextual HI-FI N1
- SA = motor (vermelho/rosa S#); Agêntico = proposta (ciano/verde P#) COM DXF
- Anotação humana COM validadores compactos Validou/Invalidou para SA e Agêntico
- Anotação agêntica COM radio Agente validou/invalidou + texto obrigatório
- Persistência .notes.json via servidor local + autosave
- Loop: atenção humana → refatorar só o desenho agêntico até Validou humano
  → depois ajustar motor SA/PIL para bater no P# validado

Sua entrega PIL:
1) Mesma UX no contextual N1 do pilar (faces/unidades)
2) Chaves aten_pil_* (não fv_*)
3) propostas/{PILAR}_qa_proposta.svg|json
4) CLI export/write-agent/propose-draw
5) Procedimento MD + piloto 5–10 pilares
6) HI-FI estrutural obrigatório no destaque agêntico

Critério de pronto:
- Humano consegue marcar SA e Agêntico independentemente
- Agente consegue redesenhar P# sem tocar no motor
- Quando humano Validou agêntico, existe geometria alvo clara para fix do motor
- Diff mínimo, sem quebrar FV existente

Ler antes: CLAUDE.md do repo, docs de PIL/ABCD/faces, e o código FV listado
na seção 1.4 do prompt completo.
```

---

## 4. Resumo em uma frase

**O destaque agêntico é o “rascunho geométrico barato e editável”; o SA é o  
motor. Anotações e validadores humanos amarram o loop; só depois que o  
rascunho é Validou se paga o custo de mudar o interpretador — em FV já  
funciona assim; em PIL deve ser o mesmo contrato com faces de pilar.**

---

*Gerado a partir da implementação FV HI-FI + validadores + proposta (2026-07).*  
*Fonte de verdade operacional FV: `docs/PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md`.*

## Loop de camadas (FV — canônico)

- **A1** julga **SA** → Certo/X; se X gera **C1**.
- **A2** julga **C1** (cego) → Certo/X; se X gera **C2**.
- **C3** só **gera** a última sugestão (sem validação agêntica).
- Selos nas abas: `H✓/H✗` + `A1 Certo/A1 X` + `A2 Certo/A2 X` (C3 só H).

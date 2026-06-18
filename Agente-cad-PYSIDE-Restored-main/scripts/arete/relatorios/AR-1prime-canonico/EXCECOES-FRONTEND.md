# Sistema de Flag de Exceções G2 no Frontend (Diagnostic Hub)

**Contexto:** AR-1' (G2 canônico, §G2 v1.2) validou PIL/13_PAV 32/35 em ABCD e
em CIMA — sempre o mesmo conjunto de 3 itens FAIL (P18, P26, P27), cada um com
causa raiz já investigada e documentada como exceção `PENDENTE` em
`G2_EXCECOES` (`scripts/arete/arete_config.py`).

Este documento descreve o sistema que avisa o usuário, **durante a
interpretação de um item no Diagnostic Hub**, que aquele item específico tem
uma exceção G2 pendente — para que ele seja avaliado caso a caso depois, em
vez de ser confundido com um erro novo/desconhecido.

---

## 1. Registro central: `G2_EXCECOES` (`scripts/arete/arete_config.py`)

Lista de dicts, cada um documentando uma exceção conhecida ao gate G2
(diff canônico). Campos:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `id` | str | sim | Identificador único, ex.: `EXC-PIL-P18-CAMBOTA` |
| `status` | str | sim | `PENDENTE` (não classificada ainda). Outros valores futuros: ver §4. |
| `classe` | str | sim | Classe estrutural (`PIL`, `VIG`, `LAJ`, ...) |
| `partes` | list[str] | sim | Partes afetadas, ex.: `["ABCD", "CIMA"]` |
| `pavimento` | str | não | Se a exceção é específica de um pavimento (ex.: `PAV_13`). Ausente = aplica a qualquer pavimento. |
| `itens` | list[str] | não | IDs de elementos afetados (ex.: `["P18"]`). **Presença deste campo é o que distingue uma exceção item-específica de uma exceção de classe** — ver §1.1 e §1.2. |
| `categorias_afetadas` | list[str] | sim | Quais categorias do diff canônico (`paineis`, `cotas`, `textos`, `nao_mapeado`) são afetadas |
| `motivo` | str | sim | Diagnóstico da causa raiz (texto longo, citando evidências como `_er_meta.dxf_validation`, contagens de entidades, etc.) |
| `efeito` | str | sim | O que essa exceção concretamente muda no comportamento do gate (ex.: quais flags ficam desativadas, quais diffs `so_ref`/`so_n4` são esperados) |
| `aprovado_por` | str | sim | Quem aprovou a exceção e quando |
| `referencia` | str | sim | Caminho para o relatório/evidência (`RELATORIO.md`, scripts em `tmp/`) |
| `revisao_futura` | str | sim | O que precisa acontecer para a exceção ser fechada/resolvida |

### 1.1 Exceções de CLASSE (sem `itens`)

Aplicam-se a **todos os itens** de uma classe/parte. Documentam que uma
categoria inteira (tipicamente `paineis`/`cotas`) é **diagnóstico, não
bloqueio** — porque o gerador N4 usa um modelo simplificado que nunca vai
bater 1:1 com a decomposição de hachura/sarrafo do recorte humano REF.

Exemplos atuais: `EXC-PIL-ABCD-FORMA`, `EXC-PIL-CIMA-FORMA`.

Estas exceções já estão "operacionalizadas" via as flags globais
`FORMA_BLOQUEIA_GATE=False` / `COTAS_BLOQUEIA_GATE=False` em
`forma_canonica_pil.py` — não precisam de um flag por item no frontend, no
máximo uma nota informativa de escopo (`get_class_exceptions`).

### 1.2 Exceções ITEM-ESPECÍFICAS (com `itens`)

Aplicam-se a um ou mais elementos específicos (ex.: `P18`, `P26`, `P27` no
13_PAV). Documentam um **gate G2 FAIL real** (categoria `textos`, que
bloqueia) cuja causa raiz já foi investigada e não é um bug do gerador, mas
sim uma característica do recorte REF daquele item específico (ex.: recorte
atípico, cambota extra, recorte duplo de pilar vizinho).

São estas que o frontend precisa **flagar visualmente** durante a
interpretação — é o assunto deste documento.

| ID | Partes | Itens | Pavimento | Causa raiz (resumo) |
|---|---|---|---|---|
| `EXC-PIL-P18-CAMBOTA` | ABCD, CIMA | P18 | 13_PAV | Bloco extra "ENCH."/"P18.A" no recorte REF (cambota) sem par em N4 |
| `EXC-PIL-P26-FASE4-VALIDACAO-ZERADA` | ABCD, CIMA | P26 | 13_PAV | `_er_meta.dxf_validation` zerada — recorte REF atípico (rótulos "2 sar"/"5 sar"/"P26.A"/"P26.B" em vez de A-D) |
| `EXC-PIL-P27-RECORTE-DUPLO` | ABCD, CIMA | P27 | 13_PAV | Recorte REF duplo — inclui faces "E"/"F" do pilar vizinho |

---

## 2. API de consulta: `scripts/arete/exception_registry.py`

Módulo Python puro (sem dependência de Qt, seguro para qualquer thread), que
encapsula a leitura de `G2_EXCECOES`:

```python
from exception_registry import (
    get_item_exceptions,      # -> list[dict] de exceções item-especificas
    get_class_exceptions,     # -> list[dict] de exceções de classe/parte
    has_pending_exception,     # -> bool
    summarize_item_exceptions, # -> str (resumo p/ tooltip)
)

get_item_exceptions("PIL", "P18", "13_PAV")
# -> [ {id: "EXC-PIL-P18-CAMBOTA", status: "PENDENTE", ...} ]

get_item_exceptions("PIL", "P1", "13_PAV")
# -> []  (sem exceção)
```

Filtros aplicados em `get_item_exceptions`:
1. `classe` deve bater (case-insensitive)
2. `itens` deve existir e conter `elemento_id`
3. se `pavimento` for passado E a exceção tiver `pavimento`, eles devem bater
   (se a exceção não tiver `pavimento`, ela vale para qualquer pavimento)

CLI de teste (uso manual/debug):

```bash
python scripts/arete/exception_registry.py PIL P18 --pav 13_PAV
# PIL/P18: 1 exceção(ões)
#   - EXC-PIL-P18-CAMBOTA [PENDENTE]
#     partes: ['ABCD', 'CIMA']
#     categorias_afetadas: ['textos']
#     motivo: ...
```

---

## 3. Integração no Diagnostic Hub: `_render_ficha_html()`

Arquivo: `src/ui/modules/diagnostic_reverse_hub.py`, função
`_render_ficha_html(data, classe, confianca, elemento_id)` — responsável por
renderizar o HTML da ficha N2 de um elemento durante a interpretação.

Fluxo adicionado:

1. Se `classe` e `elemento_id` estão disponíveis, importa
   `exception_registry` (via o padrão de path já usado no módulo:
   `scripts_dir = .../scripts/arete`) e chama
   `get_item_exceptions(classe, elemento_id, pavimento)`, onde `pavimento`
   vem de `data.get('pavimento')` ou `data.get('floor')`.
2. Import e chamada são protegidos por `try/except` — qualquer falha
   (módulo ausente, erro de import) resulta em `item_exceptions = []` e a
   ficha renderiza normalmente, **sem quebrar a interpretação**.
3. Se `item_exceptions` não for vazio:
   - Um badge laranja **"⚠ EXCEÇÃO"** é adicionado no cabeçalho da ficha,
     ao lado do ID do elemento, com tooltip indicando a quantidade de
     exceções.
   - Uma seção de detalhe (tabela) é renderizada abaixo do cabeçalho,
     listando para cada exceção: `id`, `status`, `categorias_afetadas` e o
     texto completo de `motivo`.

Resultado visual esperado (P18, P26, P27 no 13_PAV): badge "⚠ EXCEÇÃO" +
bloco "Exceção G2 Pendente — gate canônico FAIL, causa raiz investigada
(avaliação caso a caso futura)" com a tabela de detalhes.

Para qualquer outro item (ex.: P1): nenhuma alteração visual — ficha
renderiza como antes.

### Teste realizado (sem GUI)

`_render_ficha_html()` foi chamado diretamente (fora do PySide6) com dados
sintéticos para P18 e P1:

```python
html_p18 = _render_ficha_html({"name": "P18", "pavimento": "13_PAV", ...}, "PIL", 0.9, "P18")
"⚠ EXCEÇÃO" in html_p18           # True
"EXC-PIL-P18-CAMBOTA" in html_p18 # True

html_p1 = _render_ficha_html({"name": "P1", "pavimento": "13_PAV", ...}, "PIL", 0.9, "P1")
"⚠ EXCEÇÃO" in html_p1            # False
```

A renderização visual real (dentro do PySide6, com QWebEngineView) ainda não
foi verificada — ambiente sem GUI. Recomenda-se checagem visual na próxima
sessão com acesso ao Diagnostic Hub.

---

## 4. Roadmap: Classificador de Exceções (avaliação caso a caso)

**Objetivo futuro (Task #4 "(c)", explicitamente fora do escopo desta
sessão):** depois que o usuário revisar cada exceção `PENDENTE` no Diagnostic
Hub (apoiado pelo badge "⚠ EXCEÇÃO"), classificar caso a caso o que fazer com
ela.

### 4.1 Possíveis novos valores de `status`

Hoje só existe `PENDENTE`. O classificador poderia introduzir:

- `RESOLVIDO` — causa raiz foi corrigida (no extrator, no gerador, ou na
  régua canônica) e o item agora passa em G2 sem exceção. A entrada em
  `G2_EXCECOES` vira histórico (não é mais consultada por
  `get_item_exceptions`, ou é filtrada por `status != "PENDENTE"`).
- `ACEITO_PERMANENTE` — a divergência é inerente ao processo (ex.: recorte
  humano sempre vai ter cambota/recorte duplo nesses itens específicos) e
  **nunca** vai ser corrigida — mas continua sendo útil mostrar o badge para
  contexto, só que com cor diferente (ex.: cinza em vez de laranja).
- `NECESSITA_REEXTRACAO_N2` — o problema está na ficha N2/fase4 (ex.:
  `_er_meta.dxf_validation` zerada), não no gerador — precisa reprocessar o
  N2 daquele item.
- `NECESSITA_FEATURE_GERADOR` — o gerador N4 precisa de uma nova
  funcionalidade (ex.: decompor a seção CIMA em hachura/sarrafo como o
  recorte humano) para fechar a exceção — ligado a `EXC-PIL-ABCD-FORMA` /
  `EXC-PIL-CIMA-FORMA`.

### 4.2 Onde o classificador se encaixa

1. **Entrada:** usuário vê o badge "⚠ EXCEÇÃO" + tabela de detalhe ao
   interpretar P18/P26/P27 (ou qualquer item futuro com exceção registrada).
2. **Decisão caso a caso:** usuário (ou um agente) decide qual novo `status`
   se aplica, possivelmente adicionando uma nova chave `decisao` ao dict da
   exceção em `G2_EXCECOES` (ex.: `decisao: "ACEITO_PERMANENTE - recorte
   sempre terá cambota neste item"`).
3. **Atualização do registro:** editar `arete_config.py` (manual ou via
   script) para mudar `status`.
4. **Feedback no frontend:** `exception_registry.py` e
   `_render_ficha_html()` já leem `status` dinamicamente — uma vez que
   `status` deixe de ser `PENDENTE`, o badge pode:
   - desaparecer (se `RESOLVIDO`), ou
   - mudar de cor/texto (ex.: cinza "exceção aceita" para
     `ACEITO_PERMANENTE`).

   Isso **não exige nenhuma mudança de código adicional** além de, no
   `_render_ficha_html()`, trocar a condição `if item_exceptions:` por uma
   lógica que diferencia por `status` (ex.: filtrar `PENDENTE` para o badge
   laranja "ação necessária", e tratar outros `status` com estilos
   diferentes).

### 4.3 Extensão para outras classes (VIG, LAJ, FV, ...)

O mecanismo (`G2_EXCECOES` + `exception_registry.py` +
`_render_ficha_html()`) é genérico por `classe` — quando AR-1' for estendido
para VIG/LAJ/FV, novas exceções item-específicas dessas classes (se
existirem) já serão automaticamente flagadas pelo mesmo código, sem alteração
adicional.

---

## 5. Arquivos relevantes

| Arquivo | Papel |
|---|---|
| `scripts/arete/arete_config.py` | Registro `G2_EXCECOES` (fonte da verdade) |
| `scripts/arete/exception_registry.py` | API de consulta pura Python |
| `src/ui/modules/diagnostic_reverse_hub.py` (`_render_ficha_html`) | Integração visual (badge + detalhe) |
| `scripts/arete/relatorios/AR-1prime-canonico/RELATORIO.md` | Relatório AR-1' (ABCD + CIMA, 32/35) |
| `scripts/arete/relatorios/AR-1prime-canonico/EXCECOES-FRONTEND.md` | Este documento |

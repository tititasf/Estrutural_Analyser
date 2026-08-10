# MASTERPLAN — Consolidação e Entrega

**Criado:** 2026-07-30 · **Origem:** auditoria de consolidação (Opus consultor)
**Escopo:** o caminho crítico até a **primeira entrega real** para a equipe.

> **Este doc vence sobre os demais masterplans no que toca à ENTREGA.**
> Ele não substitui `MASTERPLAN-ARETE-QUALITY-GATES.md` nem os masterplans por classe
> — esses governam **qualidade de motor**, que é trilha paralela e própria do dono.
> Em conflito sobre *o que é pronto* e *o que fazer primeiro*, este arquivo manda.
> Números de status: sempre `docs/STATUS.md` (gerado), nunca prosa escrita à mão.

---

## 1. Definição de pronto (decidida em 2026-07-30)

| Dimensão | Decisão |
|---|---|
| **Entregável** | Pranchas/DXF de fôrma — **N5**. Não é ficha consultável, não é quantitativo. |
| **Classes** | **As 4 juntas** (PIL, LV, FV, LAJ). Dificuldade/importância: PIL e LV > FV > LAJ. |
| **Plataforma** | **Web é o produto.** PySide vira laboratório interno do dono — sem build, sem distribuição. |
| **Erro do motor** | **Escape hatch:** operador desenha a geometria no viewer web, motor interpreta a partir dali. |

### 1.1 A inversão que destrava a entrega

O alvo implícito até aqui era **"motor automático perfeito"**. Esse alvo não é atingível em
prancha estrutural — a variação entre projetos é grande demais. Foi ele, e não a qualidade do
motor, que impediu a entrega.

```
SEM escape hatch:  motor 99% e motor 70%  →  ambos NÃO entregáveis
COM escape hatch:  motor 70% + operador   →  entregável HOJE
```

Com escape hatch, a qualidade do motor deixa de decidir **se dá para entregar** e passa a
decidir **quanto trabalho o operador tem**. Isso torna as 4 classes viáveis simultaneamente,
inclusive LV (o motor mais fraco).

**Consequência de priorização:** enquanto o escape hatch não existir, refino de motor tem
retorno quase zero *para a entrega*. Refino continua valendo por si — mas não é caminho crítico.

---

## 2. Estado real verificado (2026-07-30)

Auditado contra código e DB, não contra docs.

### 2.1 O que já existe e funciona

| Componente | Tamanho | Situação |
|---|---:|---|
| `portal/` (FastAPI) | 11.910 LOC | auth, access, jobs, drive_poller, auto_publish, templates |
| `portal/app/pipeline_runner.py` | 708 LOC | `executar_triagem`, `executar_conversao_dwg`, `executar_recortes`, `executar_etapa`, `executar_n5` |
| `portal/app/n5_release.py` | 80 LOC | gating por validação + snapshot de certificação + hash MD5 + registro de release |
| `src/core/n5_assembler.py` | 466 LOC | monta o DXF final por classe+pavimento, com manifest e `ok_count`/`missing_count` |
| `consulta-publica-api` + `-web` | 1.539 LOC + Next.js | fichas/obras/pavimentos/SVG, QR code |

**O entregável escolhido (N5) já está plumbado ponta a ponta na web.** Isso não é um esboço.

### 2.2 Os 4 gaps do caminho crítico

| # | Gap | Evidência |
|---|---|---|
| **G-1** | SVG sem transform reversível | `scripts/arete/dxf_to_svg_casos.py:63` usa matplotlib `savefig(bbox_inches='tight')` — recorte imprevisível, impossível mapear clique→coordenada DXF. **O renderizador certo já existe:** `portal/app/dxf_preview.py:84 renderizar_dxf_svg(dxf_path, bbox=…, largura_px, altura_px)`. |
| **G-2** | Criação manual de item não existe | Duas metades desconectadas: laço geométrico em `diagnostic_hub.py` (nível de **região**, grava em `obra_recortes`) e `main.py:18330 create_manual_item()` (só nome/classe, **sem geometria**). Destino correto é `reverse_eng_recortes` (nível de **item**). |
| **G-3** | Item manual some do N5 | `assemble_n5` descobre itens varrendo o **filesystem** (`_discover_item_ids`, `_find_n3_previews`), não o DB. Item sem preview N3 no disco desaparece **em silêncio** e o `ok_count` continua verde. |
| **G-4** | Ficha N3 é read-only na web | `campos_json` aparece **0 vezes** em todo `portal/`. `fichas_routes.py` só tem GET. A única escrita é `set_campo_validado` — um **booleano** de conferência, não o valor do campo. |

### 2.3 Achado estrutural: não existe entidade "obra" canônica

> **[2026-07-30] Medido.** Rode `python scripts/arete/qa_identity_integrity.py`
> para o número atual. Não é só "três chaves paralelas" — as referências estão
> quebradas em massa:
>
> | Tabela | Linhas | Órfãs | % |
> |---|---:|---:|---:|
> | `pillars` | 7.540 | 6.455 | **85,6%** |
> | `beams` | 7.354 | 6.894 | **93,7%** |
> | `slabs` | 4.986 | 4.584 | **91,9%** |
> | `project_documents` | 8.971 | 8.953 | **99,8%** |
> | `pavimento_pi` | 128 | 128 | **100%** |
>
> E `obra_id` é ambíguo **linha a linha**: em `fase3_fichas`, 5 valores resolvem
> contra `projects` e 4 contra `obras` — a mesma coluna aponta para duas tabelas.
>
> **179 itens têm o mesmo `elemento_id` em pavimentos diferentes** (`PIL P11`
> existe em 7). Uma busca sem `pavimento` devolve a ficha de outro pavimento,
> com geometria plausível — erra em silêncio.

Três identidades paralelas de obra no mesmo DB, e a tabela-ponte está vazia:

| Chave | Nº tabelas | Exemplos |
|---|---:|---|
| `project_id` (UUID) | 12 | `pillars`, `beams`, `slabs`, `project_documents`, `training_events` |
| `obra_id` (UUID **diferente**) | 10 | `dxf_entidades`, `fase3_fichas`, `pavimentos`, `pipeline_state` |
| `obra_name` (TEXT livre) | 12 | `reverse_eng_fichas`, `reverse_eng_recortes`, `motor_runs` |

`reverse_eng_fichas` e `reverse_eng_recortes` carregam **as duas** chaves.
**`reverse_eng_projetos` — a ponte natural — tem 0 linhas.**

Isso é a causa estrutural da família de bugs "falha de vínculo". Não é um bug pontual: é o
sintoma esperado de um schema onde a mesma obra tem três nomes e nada garante que batem.
É também o bloqueio direto para multi-obra na web — hoje o motor tem **1 obra** de verdade
(`Obra_TREINO_1`, 906 fichas; `Obra_TREINO_3` tem 2 recortes soltos).

### 2.4 Passivos de dados

- **Paths absolutos Windows:** 806/806 recortes e 770/906 fichas gravados como
  `D:\Agente-cad-PYSIDE\...`. Bloqueio direto para servidor/VPN.
- **Encoding corrompido nos paths gravados:** `13� PAV`, `Pain�is`. Como o vínculo
  recorte↔ficha passa por comparação de string, mojibake é candidato sério a causa raiz.
- **`dxf_entidades` = 445 MB (31% do DB), inútil para o viewer:** 964.440 linhas para cada
  um de 2 `obra_id`s — **número idêntico, é duplicata exata**. `arquivo_origem` é NULL em
  **100%** das 1,93 M de linhas, logo não é endereçável por pavimento. Layers (`Painéis`,
  `SARR_2.2x7`, `Madeira`) indicam prancha de fôrma, não estrutural limpo.
- **VACUUM não resolve:** 92 páginas livres de 352.408. O 1,44 GB é real.
- **Cópia órfã do DB:** `Agente-cad-PYSIDE-Restored-main/project_data.vision` (1,44 GB) não é
  lida por nenhum script do Arete — `arete_config.DB_PATH` resolve para a raiz. É lixo.

---

## 3. Caminho crítico

Ordem obrigatória. Cada passo depende do anterior.

```
P0  Contrato de identidade (obra/pavimento/item com chave única)   PARCIAL
P1  SVG com transform reversível         ← G-1                     FEITO
P2  Viewer da torre com OSNAP + destaques por classe               aberto
P3  Laço no item → recorte manual em reverse_eng_recortes   ← G-2  aberto
P4  Motor headless sobre o recorte manual → N1                     aberto
P5  Preview N3 no disco (entra no assemble_n5)              ← G-3  aberto
P6  N3 editável na web + regenerar desenho                  ← G-4  aberto
P7  N5 com as 4 classes                  ← já pronto, só consumir
```

**Estado em 2026-07-30:**

- **P1 · FEITO** — `portal/app/dxf_preview.py::renderizar_dxf_svg_com_transform`
  devolve `SvgComTransform` (svg + bbox_dxf + px), com `px_para_dxf`/`dxf_para_px`
  inversos exatos e cache que persiste a transform. Lê os limites **pós-draw**:
  o backend CAD força `aspect='equal'` e o matplotlib expande um eixo — medido num
  recorte real, o Y pedido tinha 716 unidades e o efetivo 1185, ou seja usar o
  pedido deslocaria todo ponto em ~40%. 14 testes.
- **P0 · PARCIAL** — a normalização de pavimento está feita e medida
  (`src/core/obra_identity.py`): **100%** de inferência e **95,5%** de vínculo
  recorte→ficha sobre os 806 recortes reais. **Falta a decisão de migração** das
  três chaves de obra — reatribuir ou remover 6.455 pilares órfãos é decisão do
  dono, não do agente. O diagnóstico está em `qa_identity_integrity.py`.

**P0 vem primeiro** porque P3/P4/P5 gravam e leem por chave de obra/pavimento/item — fazer
isso em cima de três chaves inconsistentes reproduz o bug de vínculo dentro do feature novo.

### P0 · Contrato de identidade

- ✅ **Normalizar `pavimento`** — feito em `src/core/obra_identity.py`. Todo caminho que
  vincula recorte↔ficha deve passar por `pavimento_de_caminho`/`normalizar_pavimento`
  em vez de improvisar. Cobre ordinais, mojibake, TÉRREO/COBERTURA, subsolo e o
  intervalo `TIPO - 3° AO 12° PAV`.
- ⬜ **Decisão do dono:** o que fazer com as referências órfãs (§2.3). São 6.455
  pilares, 6.894 vigas e 4.584 lajes apontando para `project_id` inexistente. Três
  saídas possíveis: (a) recriar as linhas de `projects` faltantes, (b) reatribuir ao
  projeto correto, (c) marcar como histórico morto. **Nenhuma é reversível sem backup.**
- ⬜ Definir a chave canônica de obra e escrever o de-para de `project_id`/`obra_id`/
  `obra_name`; popular `reverse_eng_projetos` como ponte, ou eleger uma chave e migrar.
- ⬜ Corrigir o mojibake dos paths gravados (encoding na escrita). A leitura já tolera.
- ⬜ Migrar paths absolutos → relativos a uma raiz configurável.

### P1 · SVG com transform reversível

- Padronizar em `portal/app/dxf_preview.py::renderizar_dxf_svg`.
- **Emitir a transform junto do SVG**: `viewBox` = extents DXF reais, sem `bbox_inches='tight'`.
  O contrato mínimo devolvido ao front é `{bbox_dxf, largura_px, altura_px}` — suficiente para
  mapear px↔DXF nos dois sentidos.
- Aposentar `dxf_to_svg_casos.py` como fonte de SVG para o viewer (pode seguir servindo QA).

### P2 · Viewer da torre

Requisito do dono: **o mesmo viewer que aparece ao selecionar o pavimento**, mostrando o
desenho todo, limpo, fiel ao DXF, em SVG (mais leve), fluido para desenhar.

- **OSNAP é requisito, não acabamento.** Sem snap às linhas estruturais reais, o laço pega
  entidades erradas, o motor interpreta lixo e o sintoma aparece como "o motor é ruim".
  Exige índice espacial de vértices/extremos/interseções no cliente.
- **Performance:** medir contagem de entidades da torre antes de escolher a estratégia
  (SVG único vs. tiling vs. simplificação por zoom). **Não servir de `dxf_entidades`** (§2.4).
- **Destaques por classe:** botões ver PIL / LAJ / LV / FV, destacando todos os itens do
  pavimento. O dado existe (`bbox_json` por item em `reverse_eng_recortes`); falta rota + camada.
- **Rótulos:** nome junto às linhas/áreas. Fundos de viga rotulados pela contagem de
  segmento — `SEG 1`, `SEG 2`, `SEG 3`…

### P3 · Laço → item manual

Fluxo definido pelo dono: usuário desenha linha contínua com pontos sobre o estrutural →
escolhe a classe → digita **só o nome** → o resto é motor.

- Para FV/LV: opção de **selecionar o próximo segmento** após fechar o anterior.
- O laço é **seleção**, não geometria: ele delimita quais entidades reais do DXF entram no
  recorte. A mecânica de recorte já existe (`_save_recorte_dxf`, `entities_copied`).
- Gravar em `reverse_eng_recortes` (nível de item), **não** em `obra_recortes` (nível de região).

### P4 · Motor sobre o recorte manual

- Disparar o headless interpretativo da classe sobre o recorte recém-criado, gerar **N1**,
  e **refletir dinamicamente na lista do pavimento na web**.
- Entry point único: `scripts/arete/headless_sa_analise.py` (ver CLAUDE.md — respeitar locks
  por classe e usar sempre `--wait`).
- O caminho manual **reusa integralmente o pipeline automático** a partir daqui. É o que torna
  este escape hatch barato: um recorte desenhado tem a mesma forma de entrada que um detectado.

### P5 · Preview N3 no disco

- "Gerar todos os N3" **precisa incluir os itens criados manualmente na web**.
- Como `assemble_n5` descobre por filesystem (§G-3), o item manual precisa produzir preview N3
  no diretório exato varrido pelo assembler.
- **Adicionar verificação de completude:** hoje item ausente não aparece como erro. Confrontar
  a lista de itens do DB com a descoberta por disco e falhar alto na divergência.

### P6 · N3 editável

- Rota de escrita de `campos_json` (hoje inexistente no portal).
- Botão **regenerar** → refaz o desenho do item e devolve a versão nova para revisualização.
- Preservar a distinção já existente entre *valor do campo* e *flag de validação*
  (`set_campo_validado`) — são coisas diferentes e devem continuar separadas.
- Registrar proveniência da edição humana (ver `docs/CONVENCAO-SELOS-VALIDACAO.md`).

---

## 4. O que NÃO fazer

| Não fazer | Por quê |
|---|---|
| Refatorar `main.py` (19.185 linhas) | PySide virou laboratório. Código feio de laboratório é aceitável. Zero retorno para a entrega. |
| Servir o viewer de `dxf_entidades` | Não é endereçável por pavimento e metade é duplicata (§2.4). |
| Confiar no alerta de regressão antigo do STATUS | Corrigido em 2026-07-30. Comparava contagem de golden acumulado com PASS da rodada — grandezas incomparáveis. |
| Distribuir binário PySide | Contraria a decisão de soberania e dobra a superfície de suporte. |
| Refinar motor esperando destravar a entrega | Sem escape hatch, nenhuma qualidade de motor entrega (§1.1). |
| Criar mais um masterplan | Já existem 20. Este consolida a trilha de entrega. |

---

## 5. Nota sobre a métrica de regressão (corrigida em 2026-07-30)

`scripts/arete/gerar_status.py` media regressão comparando **contagem de diretórios em
`GOLDEN/`** (acumulado, nunca invalidado — só cresce) contra **PASS da última rodada** (escopo
variável). O painel alarmava onde não havia problema e calava onde havia.

**Teste correto, agora implementado:** `GOLDEN ∩ itens reprovados da última rodada`.

Duas armadilhas de nomenclatura, documentadas para não se repetirem:

- **`golden_selado` no `relatorio.json` significa "selei NESTA rodada"**, não "estava selado".
  Ler esse campo como "estava selado" leva à conclusão oposta da verdadeira.
- **`GOLDEN/` nunca é invalidado.** Um item que regride mantém o diretório para sempre.
  Não existe processo de revogação de selo.

**Resultado após a correção:** 42 itens selados reprovando — LV 13_PAV (2), PIL 1_PAV (19),
PIL COBERTURA (19), PIL TERREO (2). Quatro combinações saíram do alarme por serem falso positivo.

**Aviso de interpretação:** as rodadas de PIL 1_PAV e COBERTURA são de 2026-07-05 e nunca foram
refeitas. Amostra checada — PIL/1_PAV/P11 reprovou por `comprimento=0.0, largura=0.0`, mas o DB
tem `comprimento=80.0, largura=19.0, confiança=0.95` com `updated_at` de **2026-06-19**, ou seja
16 dias **antes** da rodada. Sem duplicatas no DB (0 grupos). Logo **não é regressão de motor**:
é falha de vínculo recorte→ficha, possivelmente já corrigida. Uma re-rodada resolve ou confirma.

---

## 6. Auditorias — estado

| | Auditoria | Resultado |
|---|---|---|
| ✅ | Prontidão web | Portal entrega N5 ponta a ponta; 13,4k LOC funcionais |
| ✅ | Reprodutibilidade | 42 selados reprovando; não é motor, é vínculo; métrica corrigida |
| ✅ | Modelo de dados | 3 chaves de obra, ponte vazia, 445 MB inúteis, paths absolutos, mojibake |
| ✅ | N3 editável na web | Não existe; read-only integral |
| ⬜ | Superfície produto/andaime | Despriorizada — PySide virou laboratório |
| ⬜ | Governança documental | 111 docs / 20 masterplans; este consolida a trilha de entrega |
| ⬜ | Generalização (obra 2 crua) | Retirada da fila pelo dono. Volta quando decidir processar as outras 21 obras. |

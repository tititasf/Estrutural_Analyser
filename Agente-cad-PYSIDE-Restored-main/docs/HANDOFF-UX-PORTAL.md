# HANDOFF-UX — Portal Web da Equipe (fluxo enxuto de 6 etapas)

**Versão:** 1.0 — front-end-spec para o @dev
**Data:** 2026-07-05
**Autora:** Uma (UX Design Expert)
**Escopo:** UX/UI das 6 etapas do MVP enxuto (DP-14) do portal mínimo definido em
`docs/MASTERPLAN-PRODUCAO-SOBERANIA.md`.

> **Fronteira respeitada (não relitigar):** transporte = Google Drive por poller
> (DP-10/DP-11), **não** upload direto; as 6 etapas entram todas na v1 (DP-14);
> N5 = 1 DXF por classe+pavimento montado dos previews N3 (DP-12); liberação N5 é
> self-service do usuário (DP-13) mas o rótulo `certificado`/`beta` da classe vem
> da curadoria do dono e fica visível na liberação (R9); portal só **lê** artefatos
> e **grava** obras/jobs/comentários T0 (§3). App PySide6 continua exclusiva do dono.

---

## 0. Princípios de UX deste portal

1. **Simples por decreto (DP-14).** Listas de aprovação, ficha + viewer básico, botões
   grandes. Nada de dashboards, nada de drag-and-drop, nada de animação. O valor está
   em "dias em minutos", não em sofisticação visual.
2. **Fluxo linear e guiado.** O usuário sempre sabe em que etapa está e qual é a próxima.
   Uma barra de progresso de 6 passos aparece no topo do detalhe da obra.
3. **Reaproveitar o que existe.** As fichas HTML N1–N4 do Arete são servidas como estão;
   o formulário de erro é o mesmo `_error_marker_block` já usado no headless.
4. **Proveniência sempre visível.** Todo comentário mostra autor + data (login do membro).
5. **Nunca confundir "eu validei" com "o motor é confiável".** O rótulo da classe
   (`certificado`/`beta`) é onipresente nas telas de resultado e de liberação (R3/R9).

---

## 1. Mapa de navegação

```
[LOGIN]
   │  login simples por membro (DP-3)
   ▼
[LISTA DE OBRAS]  ◄──────────────────────────────────┐
   │  card por obra + status (ver §5)                 │  "voltar"
   │  clique numa obra                                 │  em qualquer tela
   ▼                                                   │
[DETALHE DA OBRA]  (barra de progresso 6 passos) ──────┤
   │                                                   │
   ├─[1] TRIAGEM ─────► confirma/edita classificação   │
   │        │ "confirmar triagem"                      │
   │        ▼                                           │
   ├─[2] RECORTES ────► aprova recortes (lista)         │
   │        │ "aprovar todos / concluir recortes"      │
   │        ▼                                           │
   ├─[3] SA COMPLETO ─► SEM UI — processa no servidor   │
   │        │ (tela mostra só progresso/spinner)        │
   │        ▼                                           │
   ├─[4] VALIDAÇÃO ───► fichas HTML N1–N4 + marcação    │
   │        │ "concluir minha validação"               │
   │        ▼                                           │
   └─[5] N5 (LIBERAÇÃO) ► self-service download por     │
            classe+pavimento (rótulo cert/beta visível)─┘
```

**Regras de movimento:**
- Navegação é **linear com gate**: a etapa N+1 só fica clicável quando a etapa N está
  concluída pelo humano (triagem confirmada → recortes; recortes concluídos → SA dispara
  sozinho; SA pronto → validação; validação concluída → N5 liberável). Etapas futuras
  aparecem na barra de progresso, mas em estado `bloqueada` (cinza, não clicável, tooltip
  "Conclua a etapa anterior").
- O usuário pode **voltar** a uma etapa concluída para revisar (read-only ou re-editar
  conforme a etapa), mas isso não "desfaz" as etapas seguintes — só a validação e a
  triagem permitem re-edição; recortes reabrem se o SA ainda não rodou.
- "Voltar à lista de obras" sempre disponível no header.

**Telas totais (7):** Login · Lista de obras · Detalhe/Progresso · Triagem · Recortes ·
Validação · Liberação N5. (SA Completo não é tela própria — é um estado do Detalhe.)

---

## 2. Wireframes por etapa

> Convenção dos wireframes: `[ ]` = checkbox, `[Botão]` = ação primária, `( )` = radio,
> `▸` = item de lista, `◐` = spinner/loading. Estados listados como
> **vazio / carregando / erro / pronto** ao final de cada etapa.

### Tela A — Login

```
┌──────────────────────────────────────────────┐
│                                              │
│           Portal de Formas — Arete           │
│                                              │
│   Membro:    [ nome do membro          ▾ ]   │  ← select de membros cadastrados
│   Senha:     [ •••••••••              ]      │
│                                              │
│              [  Entrar  ]                    │
│                                              │
│   Acesso apenas pela VPN da equipe.          │
└──────────────────────────────────────────────┘
```
- Login simples por membro (DP-3). Sem "esqueci a senha" self-service (dono reseta).
- **Estados:** *pronto* (form) · *carregando* (botão vira ◐ "Entrando…") ·
  *erro* (faixa vermelha "Membro ou senha inválidos", foco volta ao campo Membro).

---

### Etapa [0] / Tela B — Lista de obras

Esta é a home após login. Uma obra aparece aqui automaticamente quando o poller do Drive
a detecta (DP-11) — **não há botão de upload** (o upload é feito na pasta do Drive).

```
┌───────────────────────────────────────────────────────────────────┐
│ Portal de Formas          Membro: João ▾   [ Sair ]               │
├───────────────────────────────────────────────────────────────────┤
│  Minhas obras                          [ Atualizar lista ↻ ]      │
│                                                                   │
│  ┌─ Edifício Aurora ──────────────────────────────────────────┐  │
│  │ 🟡 Aguardando triagem     · detectada 05/07 14:20         │  │
│  │ 4 pavimentos · enviada por João                 [ Abrir →]│  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌─ Residencial Bela Vista ───────────────────────────────────┐  │
│  │ ◐ Processando (SA)        · início 05/07 13:05            │  │
│  │ 2 pavimentos · enviada por João                 [ Abrir →]│  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌─ Galpão Norte ─────────────────────────────────────────────┐  │
│  │ ⏳ Aguardando ingestão (Drive) · na fila                   │  │
│  │ — · enviada por Maria                            [ Abrir →]│  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌─ Torre Central ────────────────────────────────────────────┐  │
│  │ 🔴 Erro reportado (2)     · ver detalhe                    │  │
│  │ 6 pavimentos · enviada por João                 [ Abrir →]│  │
│  └────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```
- Ordenação padrão: por status acionável primeiro (aguardando triagem / pronta) →
  processando → aguardando ingestão → concluídas.
- `[ Atualizar lista ↻ ]` só re-consulta o backend (o poller já roda sozinho; o botão
  não força o Drive, evita expectativa de "sincronizar agora").
- Filtro implícito "Minhas obras": cada membro vê as obras que **enviou** (sua pasta do
  Drive) + as que lhe foram atribuídas. Sem visão global (essa é do dono, fora do portal).
- **Estados da lista:** *vazio* ("Nenhuma obra ainda. Envie um arquivo DWG/DXF para sua
  pasta do Google Drive — ela aparecerá aqui em alguns minutos.") · *carregando* (◐
  skeleton de 3 cards) · *erro* (faixa "Não foi possível carregar as obras. Tentar de
  novo?" — nunca tela em branco) · *pronto* (cards). Estados **por obra** = §5.

---

### Detalhe da obra — cabeçalho comum (barra de progresso)

Todas as etapas 1–5 vivem dentro do Detalhe e compartilham este cabeçalho:

```
┌───────────────────────────────────────────────────────────────────┐
│ ← Obras   Edifício Aurora · 4 pavimentos · enviada por João       │
├───────────────────────────────────────────────────────────────────┤
│  (1)Triagem ─ (2)Recortes ─ (3)SA ─ (4)Validação ─ (5)N5          │
│   ●━━━━━━━━━━━━●━━━━━━━━━━━○┄┄┄┄┄┄┄┄┄○┄┄┄┄┄┄┄┄┄○                    │
│   feito        atual       bloq.      bloq.      bloq.             │
└───────────────────────────────────────────────────────────────────┘
```
- `●` concluída (verde) · `●` atual (azul, com anel) · `○┄` bloqueada (cinza tracejado).
- Passos concluídos são clicáveis (revisão); bloqueados têm tooltip "Conclua a etapa
  anterior". A barra é também `<nav aria-label="Progresso da obra">` para leitores de tela.
- SA (passo 3) nunca é "clicável para editar" — é só um marcador de progresso automático.

---

### Etapa [1] — TRIAGEM (confirmar/editar classificação por pavimento)

Humano confirma como cada documento foi classificado (por pavimento). Interface = lista,
uma linha por documento, classificação já pré-preenchida pelo motor; o humano só corrige
o que estiver errado.

```
┌───────────────────────────────────────────────────────────────────┐
│  [ barra de progresso — passo 1 atual ]                           │
├───────────────────────────────────────────────────────────────────┤
│  Triagem — confira a classificação dos documentos                 │
│  Marque só o que precisa mudar. O resto já vem preenchido.        │
│                                                                   │
│  ▸ Pavimento: TÉRREO                                              │
│    planta_terreo.dxf   Tipo: [ Formas ▾ ]  Classe: [ PIL ▾ ]     │
│    detalhe_pilar.dxf   Tipo: [ Detalhe ▾ ] Classe: [ PIL ▾ ]     │
│                                                                   │
│  ▸ Pavimento: 1º PAVIMENTO                                        │
│    planta_pav1.dxf     Tipo: [ Formas ▾ ]  Classe: [ LAJ ▾ ]     │
│    (?) documento_x.dxf Tipo: [ Ignorar ▾ ] Classe: [ —   ▾ ]     │
│         ⚠ não classificado automaticamente — confirme            │
│                                                                   │
│                        [ Confirmar triagem → ]                    │
└───────────────────────────────────────────────────────────────────┘
```
- Só selects (Tipo, Classe) e um `Ignorar` para descartar documentos. Sem campos livres.
- Itens não classificados pelo motor recebem `⚠` e ficam com foco/destaque até o humano
  resolver — `[ Confirmar triagem ]` fica **desabilitado** enquanto houver `(?)` sem
  decisão (Classe vazia ou não-Ignorar).
- Confirmar grava a triagem server-side (evidência T0, autor = login) e destrava Recortes.
- **Estados:** *carregando* (◐ "Carregando documentos…") · *vazio* (raro: "Nenhum
  documento reconhecido nesta obra — avise o responsável") · *erro* (faixa + `[ Tentar de
  novo ]`) · *pronto* (lista) · *concluída* (read-only, badge "Triagem confirmada por João
  em 05/07 14:40", com `[ Reabrir para editar ]` se SA ainda não rodou).

---

### Etapa [2] — RECORTES (aprovação de recortes por pavimento, em lista)

Aprovação em massa: torre, detalhes, convenção de pilares/níveis. O usuário "só vai
aprovando". Cada recorte mostra uma miniatura (imagem/SVG já gerado) + rótulo.

```
┌───────────────────────────────────────────────────────────────────┐
│  [ barra de progresso — passo 2 atual ]                           │
├───────────────────────────────────────────────────────────────────┤
│  Recortes — aprove o que está correto                             │
│  [ ✔ Aprovar todos ]     3 pendentes · 5 aprovados                │
│                                                                   │
│  ▸ Pavimento: TÉRREO                                              │
│    ┌───────┐  Torre (planta geral)                               │
│    │ [img] │  Convenção: pilares P1–P12 · níveis N0–N3           │
│    └───────┘  ( ) Aprovar   ( ) Rejeitar   [nota opcional…]      │
│                                                                   │
│    ┌───────┐  Detalhe — Pilar P3                                 │
│    │ [img] │  ● Aprovado por João                                │
│    └───────┘  [ desfazer ]                                       │
│                                                                   │
│  ▸ Pavimento: 1º PAVIMENTO                                        │
│    ┌───────┐  Torre (planta geral)                               │
│    │ [img] │  ( ) Aprovar   ( ) Rejeitar   [nota opcional…]      │
│    └───────┘                                                     │
│                                                                   │
│                    [ Concluir recortes → ]                       │
└───────────────────────────────────────────────────────────────────┘
```
- `[ ✔ Aprovar todos ]` marca todos os pendentes como aprovados de uma vez (o caso comum).
  Rejeitar é a exceção — abre o campo de nota (por que rejeitou → vira evidência T0).
- Contador vivo "N pendentes · M aprovados" no topo.
- `[ Concluir recortes ]` fica desabilitado enquanto houver recorte sem decisão
  (nem aprovado nem rejeitado). Concluir → dispara o SA Completo (etapa 3).
- **Estados:** *carregando* (◐ + skeleton de cards) · *vazio* ("Nenhum recorte gerado
  para esta obra ainda") · *erro por miniatura* (placeholder "imagem indisponível", o
  recorte ainda é aprovável pelo rótulo) · *pronto* · *concluída* (read-only, badge
  "Recortes concluídos por João").

---

### Etapa [3] — SA COMPLETO (processamento automático — sem UI de edição)

Roda no servidor, fila de 1 job por vez (respeita a exclusão mútua da §4/`single_instance`).
A "tela" é só o Detalhe mostrando progresso — o usuário não faz nada aqui.

```
┌───────────────────────────────────────────────────────────────────┐
│  [ barra de progresso — passo 3 atual ]                           │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│              ◐  Processando a obra (SA completo)                  │
│                                                                   │
│         Etapa atual: gerando fichas N1–N4 · pavimento 2 de 4      │
│         Iniciado 05/07 15:02 · isso costuma levar alguns minutos  │
│                                                                   │
│         Você pode fechar esta página — avisaremos na lista        │
│         quando a validação estiver pronta.                        │
│                                                                   │
│         [ Voltar à lista ]                                        │
└───────────────────────────────────────────────────────────────────┘
```
- Sem barra de porcentagem falsa; texto de etapa real ("pavimento 2 de 4") atualizado por
  polling do backend (mesmo padrão do poller — latência de minutos é aceitável, §DP-11).
- Se a obra estiver **na fila** atrás de outra: "Na fila — 1 obra à frente. Começa em
  breve." (não trava, informa).
- **Estados:** *na fila* · *processando* (◐ + etapa) · *erro* (ver §5 "com erro"):
  "O processamento falhou nesta obra. O responsável foi notificado." + `[ Ver detalhe ]`
  (nunca expõe stack trace ao membro; quarentena de job, R6) · *pronto* → avança para
  Validação e o card na lista vira `🟢 Pronta para validação`.

---

### Etapa [4] — VALIDAÇÃO (revisar fichas HTML N1–N4 + marcar erros)

Aqui o portal **serve as fichas HTML que já existem** (`headless_sa_analise.py`). O usuário
navega por pavimento → classe → item, lê a ficha, e marca erro pelo `_error_marker_block`
(ver §4 deste doc). Layout de duas colunas: navegação à esquerda, ficha embutida à direita.

```
┌───────────────────────────────────────────────────────────────────┐
│  [ barra de progresso — passo 4 atual ]                           │
├───────────────────────────────────────────────────────────────────┤
│ Navegação            │  Ficha: PIL · P3 · TÉRREO                  │
│ ─────────────────    │  ┌────────────────────────────────────────┐│
│ ▾ TÉRREO             │  │ Classe PIL   [ ✔ CERTIFICADO ]  (R3)   ││
│   ▾ PIL              │  │ ────────────────────────────────────── ││
│     ▸ P1  ✔          │  │  (ficha HTML N1–N4 servida como está,   ││
│     ▸ P2  ✔          │  │   SVG inline, cards N1/N2/N3/N4)        ││
│     ▸ P3  ⚑  ◄ atual │  │                                        ││
│     ▸ P4             │  │  … conteúdo da ficha …                 ││
│   ▸ LAJ              │  │                                        ││
│ ▾ 1º PAVIMENTO       │  │  ┌── Marcação de erro (rev. humana) ──┐││
│   ▸ PIL              │  │  │ [ ] Marcar esta ficha como ERRADA  │││
│   ▸ LAJ              │  │  │ [ nota: descreva o que está errado]│││
│                      │  │  └────────────────────────────────────┘││
│ Progresso: 12/40     │  └────────────────────────────────────────┘│
│ vistas · 2 marcadas  │        [ ◀ anterior ]   [ próxima ▶ ]      │
│                      │                                            │
│ [ Concluir minha validação → ]  (habilita quando todas vistas)   │
└───────────────────────────────────────────────────────────────────┘
```
- Árvore de navegação: pavimento → classe → item. `✔` = já visto · `⚑` = marcado como
  errado. Contador "vistas X/N · marcadas M" mantém o usuário orientado.
- A ficha é embutida (iframe/inclusão do HTML existente). O rótulo `certificado`/`beta`
  da classe (§3) aparece no topo da ficha **e** na árvore, ao lado do nó da classe.
- `[ Concluir minha validação ]` habilita quando todos os itens foram vistos (não exige
  marcar erro — validar é dizer "olhei"). Concluir grava o marco T0 (autor+data) e
  **destrava a liberação do N5** (DP-13).
- **Estados:** *carregando* (◐ na área da ficha) · *ficha indisponível* ("Esta ficha não
  pôde ser carregada" + `[ tentar de novo ]`, não trava a navegação) · *pronto* ·
  *concluída* (badge "Validação concluída por João em 05/07 16:10"; fichas ficam
  read-only mas as marcações permanecem visíveis; `[ Reabrir ]` disponível).

---

### Etapa [5] — LIBERAÇÃO DO N5 (self-service, por classe+pavimento)

Só acessível após a validação concluída (DP-13). O usuário baixa o DXF consolidado
(`N5_{classe}_{pav}.dxf`, DP-12). O rótulo `certificado`/`beta` da classe é **onipresente
e não ignorável** aqui (R9) — é o ponto exato onde o usuário poderia confundir "eu validei"
com "o motor é confiável".

```
┌───────────────────────────────────────────────────────────────────┐
│  [ barra de progresso — passo 5 atual ]                           │
├───────────────────────────────────────────────────────────────────┤
│  Liberar N5 — DXF consolidado por classe e pavimento              │
│  Sua validação está concluída. Você pode baixar os arquivos.      │
│                                                                   │
│  ┌── ⚠ Entenda antes de baixar ────────────────────────────────┐ │
│  │ "CERTIFICADO" = o motor daquela classe passou nos gates de   │ │
│  │ qualidade do Arete. "BETA" = ainda em treino: confira o DXF  │ │
│  │ antes de usar em obra. Você validou SUA parte — isso não     │ │
│  │ certifica o motor.                                           │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ▸ TÉRREO                                                        │
│    PIL   [ ✔ CERTIFICADO ]   N5_PL_TERREO.dxf     [ ⬇ Baixar ]   │
│    LAJ   [ ⚠ BETA ]          N5_LJ_TERREO.dxf     [ ⬇ Baixar ]   │
│  ▸ 1º PAVIMENTO                                                  │
│    PIL   [ ✔ CERTIFICADO ]   N5_PL_PAV1.dxf       [ ⬇ Baixar ]   │
│    LV    [ ⚠ BETA ]          N5_LV_PAV1.dxf       [ ⬇ Baixar ]   │
│                                                                   │
│  Classes: PL=Pilar · LJ=Laje · LV=Lat.Viga · FV=Fundo Viga       │
└───────────────────────────────────────────────────────────────────┘
```
- Para classe `BETA`, o botão de baixar é permitido (self-service, DP-13) mas o badge
  vermelho fica ao lado e um `title`/aria-label reforça "classe em treino — confira".
  **Não** bloqueamos o download beta; garantimos que ele nunca seja silencioso (R9).
- **Estados:** *bloqueada* (se validação não concluída: tela substituída por
  "Conclua a validação para liberar o N5" + `[ Ir para validação ]`) · *montando*
  (◐ "Gerando N5_PL_TERREO.dxf…" — o assemble pode rodar sob demanda) · *erro de item*
  ("Falha ao montar este N5 — o responsável foi notificado", os outros itens seguem
  baixáveis) · *pronto* (lista com botões).

---

## 3. Rótulo `certificado` / `beta` — visível e não ignorável (R3 + R9)

O rótulo vem da curadoria do dono (fora do portal); o portal só o **lê** e exibe. Regra
de exibição unificada, um único componente `<ClassBadge>` reutilizado em toda tela:

| Estado | Badge | Cor de fundo | Cor de texto | Ícone | Contraste (AA) |
|--------|-------|--------------|--------------|-------|-----------------|
| Certificado | `✔ CERTIFICADO` | verde escuro `#1E5631` | branco `#FFFFFF` | ✔ | 8.6:1 ✅ |
| Beta | `⚠ BETA` | âmbar/vermelho `#8A1F0B` | branco `#FFFFFF` | ⚠ | 8.9:1 ✅ |

Regras de "não ignorável":
1. **Nunca só cor.** Cada badge carrega **texto** (CERTIFICADO/BETA) + **ícone** (✔/⚠) —
   funciona para daltônicos e em impressão P&B.
2. **Aparece em todas as telas de resultado**: no topo de cada ficha (etapa 4), ao lado
   do nó de classe na árvore de navegação (etapa 4) e ao lado de cada arquivo na
   liberação (etapa 5).
3. **Na liberação (R9)**: além do badge por linha, um bloco de aviso fixo no topo explica
   a diferença entre "eu validei" e "o motor é certificado" — o usuário não passa pela
   tela de download sem ver essa explicação.
4. `aria-label` completo no badge: `"Classe PIL: certificada pelo Arete"` /
   `"Classe LAJ: beta, motor ainda em treino, confira o resultado"`.
5. O badge é `role="status"`, não um elemento decorativo, para ser anunciado.

---

## 4. Formulário de comentário de erro — reaproveitar `_error_marker_block`

**Não reinventar.** O bloco já existe em `src/ui/widgets/preficha_*_html.py`
(`_error_marker_block`) e é o que o headless injeta no fim de cada ficha. O portal reusa
a **mesma marcação e o mesmo UX** (checkbox "Marcar esta ficha como ERRADA" + textarea de
nota), com **uma única mudança de infra** exigida pelo masterplan (§2, P2): trocar a
persistência de `localStorage` por **server-side**.

Estrutura visual a preservar (idêntica ao existente):
```
┌── Marcação de erro (revisão humana) ──────────────┐   ← título laranja #e17055
│ [ ] Marcar esta ficha como ERRADA                 │   ← checkbox + label laranja
│ ┌───────────────────────────────────────────────┐ │
│ │ Descreva o que está errado (N1, N2, N3 ou N4)…│ │   ← textarea monospace
│ └───────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

O que muda para o portal (@dev):
- **Chave estável mantida:** a chave hoje é `aten_erro_{classe}_{obra}_{pav}_{item}`
  (ver `_error_marker_block`). Reusar essa mesma chave como identidade do comentário
  server-side — não inventar id novo.
- **Onde grava:** o `save()` do bloco, hoje `localStorage.setItem`, passa a fazer um
  `POST /obras/{obra}/comentarios` com `{ chave, erro, nota }`. O `load()` faz `GET`.
  O debounce/autosave a cada mudança (comportamento atual) é mantido — o usuário não
  aperta "salvar".
- **Proveniência (T0):** o backend carimba `marcado_por: "equipe:{login}"`, `run_id`,
  `engine_version` e timestamp — o front **não** coleta autor (vem da sessão). Isso
  alimenta o mesmo funil de triagem (`.jsonl`, `ARETE-TRIAGEM-ERROS.md`); o dono
  interpreta a causa-raiz depois. A equipe **marca**, nunca decide (§3 do masterplan).
- **Exibição de comentário salvo:** ao reabrir, além de recarregar checkbox+nota, mostrar
  discretamente "marcado por {login} em {data}" abaixo do textarea (proveniência visível,
  DP-3). Se outro membro tiver marcado a mesma ficha, listar as marcações em ordem
  (assinadas), sem sobrescrever.

Importante para o @dev: **não** criar um segundo formulário de erro no portal. A ficha
servida já traz o bloco; a tarefa é redirecionar o `save`/`load` desse bloco para a API.

---

## 5. Estados da obra na lista (§0/etapa 0)

Um único enum de status, um ícone+cor+texto por estado. Todo estado tem **texto**, nunca
só cor (acessibilidade).

| Status | Ícone | Cor | Texto exibido | Origem | Ação do card |
|--------|-------|-----|---------------|--------|--------------|
| Aguardando ingestão | ⏳ | cinza `#6B7280` | "Aguardando ingestão (Drive)" | poller ainda não baixou / Drive indisponível (R8) | Abrir (read-only) |
| Processando | ◐ | azul `#1D4ED8` | "Processando (SA)" | job na fila ou rodando | Abrir → tela de progresso |
| Aguardando triagem | 🟡 | âmbar `#B45309` | "Aguardando triagem" | baixada, aguardando etapa 1 | Abrir → Triagem |
| Pronta p/ validação | 🟢 | verde `#15803D` | "Pronta para validação" | SA concluído | Abrir → Validação |
| Concluída | ✅ | verde escuro `#166534` | "Concluída · N5 liberável" | validação feita | Abrir → N5 |
| Com erro reportado | 🔴 | vermelho `#B91C1C` | "Erro reportado (N)" | job falhou / quarentena (R6) | Abrir → detalhe do erro |

Notas:
- **"Aguardando ingestão"** cobre o caso R8 (Drive fora do ar): a obra fica nesse estado
  em vez de virar erro — o poller "loga e reagenda, não derruba o serviço". Se o membro
  souber que subiu o arquivo mas ele não aparece, esse estado o tranquiliza (está na fila
  de ingestão, não perdido).
- **"Com erro reportado (N)"** conta erros de processamento (job) **e/ou** fichas marcadas
  como erradas pela equipe — o número entre parênteses. Distinguir no detalhe: "falha de
  processamento" vs "N fichas marcadas por revisores".
- O estado é derivado no backend; o front só mapeia enum → `<StatusBadge>`. Um único
  componente, seis variações.

---

## 6. Checklist de acessibilidade básica (WCAG AA — meta, R do masterplan §0)

Aplicável a todas as 7 telas. @dev deve conferir cada item antes de dizer "pronto".

**Contraste**
- [ ] Texto normal ≥ 4.5:1 contra o fundo; texto grande (≥18px/14px-bold) ≥ 3:1.
- [ ] Badges `certificado`/`beta` e os status da lista atendem AA (ver tabelas §3/§5 —
      todos já ≥ 4.5:1).
- [ ] Estados de erro (faixas vermelhas) não dependem só da cor — sempre com ícone+texto.

**Navegação por teclado**
- [ ] Todo elemento interativo (links, botões, checkbox, select, textarea, botões de
      baixar) alcançável por `Tab` na ordem visual/lógica.
- [ ] `[ Aprovar todos ]`, `[ Confirmar triagem ]`, `[ Concluir validação ]`, `[ Baixar ]`
      acionáveis por `Enter`/`Espaço`.
- [ ] Árvore de navegação da validação (etapa 4) navegável por teclado; item atual
      recebe foco ao entrar.
- [ ] Nenhuma armadilha de foco no iframe da ficha (o usuário consegue sair dele por Tab).

**Foco visível**
- [ ] Anel de foco visível em todos os controles (não remover `outline` sem substituto).
      Anel com contraste ≥ 3:1 contra o fundo adjacente.
- [ ] Ao concluir uma etapa e avançar, mover o foco para o cabeçalho/título da nova etapa
      (não deixar o foco perdido no botão que sumiu).

**Estrutura & leitores de tela**
- [ ] Um `<h1>` por tela (título da obra/etapa); hierarquia de headings sem pular níveis.
- [ ] Barra de progresso = `<nav aria-label="Progresso da obra">`; passo atual com
      `aria-current="step"`.
- [ ] Badges de classe/status com `aria-label` completo (§3.4/§5) e `role="status"`.
- [ ] Spinners `◐` com `aria-live="polite"` e texto ("Processando…") — nunca só ícone.
- [ ] Inputs (select de triagem, radios de recorte, textarea de erro) com `<label>`
      associado (o textarea de erro já traz o label "Marcar como ERRADA" — preservar).
- [ ] Faixas de erro com `role="alert"` para serem anunciadas ao aparecer.

**Sem exigências além de AA** (H1 não é meta): não perseguir AAA, animações reduzidas,
nem gestos complexos — o portal é simples por decisão (DP-14).

---

## 7. Notas de handoff para o @dev

- **Atomic Design:** os reutilizáveis são `<ClassBadge>` (cert/beta, §3), `<StatusBadge>`
  (obra, §5), `<StepProgress>` (barra 6 passos), `<ErrorMarker>` (o `_error_marker_block`
  religado à API, §4). Tudo o mais são organismos que compõem esses átomos + listas.
- **Nada de novo formulário de erro** — religar o existente (§4). Nada de upload no portal
  (Drive, DP-10). Nada de cortar etapas (DP-14).
- **Classes canônicas** vindas do N5 assembler: `PL`, `LJ`, `LV`, `FV` (`n5_assembler.py`).
  Nomes de exibição na tabela da liberação (§5 do wireframe).
- **Persistência:** comentários e marcos de etapa (triagem/recortes/validação concluídas)
  são gravados server-side com autor+`run_id`+`engine_version`, alimentando o funil T0
  (`ARETE-TRIAGEM-ERROS.md`). O portal grava só obras/jobs/comentários — nunca fichas,
  golden ou tabelas de curadoria (§3 do masterplan).

---

*Uma (UX Design Expert) — 2026-07-05 — desenhando com empatia 💝*

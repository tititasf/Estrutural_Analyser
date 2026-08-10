# Handoff — performance da ficha de detalhe (SA/Pilares) + vínculo de texto quebrado

## Contexto (leia antes de agir)

Workspace: `D:\Agente-cad-PYSIDE`. App = `Agente-cad-PYSIDE-Restored-main/` (repo git,
rodar comandos ali). Leia `CLAUDE.md` da raiz e o `CLAUDE.md` do repo antes de
qualquer coisa — regras inegociáveis, Python 3.12 obrigatório
(`D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe`), DB real é
`D:/Agente-cad-PYSIDE/project_data.vision` (não o da raiz do repo).

## O que já foi feito nesta sessão anterior (não redescobrir)

Dois crashes reais foram encontrados e corrigidos no log que o dono colou, ambos
já **verificados** (não só "parece corrigido"):

1. **`src/ui/widgets/detail_card.py::_get_initial_value`** (~linha 2765): o
   motor de faces (`src/core/pillar_face_beams.py::_face_beam_link_payload`)
   grava `geometry` e `evidence_source` (string) como chaves irmãs de `label`
   dentro do mesmo dict `links[field_id]`. A leitura genérica fazia
   `for s_list in slots.values(): ... s_list[0].get('text', '')` sem checar
   tipo — ao cair em `evidence_source` (string), `s_list[0]` virava um
   caractere e `.get()` quebrava (`'str' object has no attribute 'get'`).
   Fix: filtrar só `isinstance(s_list, list) and isinstance(s_list[0], dict)`
   antes de ler. Aplicado em dois pontos (branch dict e branch list de
   `slots`). **Testado**: abri o `DetailCard` real (Qt offscreen) dos 46
   pilares do 13_PAV de `Obra_TREINO_1` (`project_id
   dd238e47-1dc6-4f63-a760-4e7ce19a7386`) — 46/46 sem exceção.
2. **`_ROBOS_ABAS/Robo_Lajes/laje_src/ui/widgets/canvas_widget.py:765`**:
   `unioes_nos_bordes[0]` numa lista vazia (`IndexError`). Fix: guarda de
   lista não-vazia antes de indexar.

Ambos os arquivos estão com `git status` mostrando `M` (modificado, não
commitado ainda) — **NÃO fazer `git checkout`/descartar essas mudanças**,
elas são intencionais e testadas. Rodar `git diff` neles pra confirmar antes
de continuar. Também há uma entrada nova em
`docs/SA-ANALISE/HISTORICO/PIL.md` (root-cause do bug `dim` de 10 pilares,
não relacionado a este handoff, mas documentado no mesmo arquivo — não
reverter).

## O que falta (pedido do dono, ainda não iniciado)

O dono pediu para melhorar a **performance** da aba de validação (SA —
Structural Analyzer / ficha de detalhe de item) e reportou que a **função de
criar vínculo de texto não estava funcionando**. Ao perguntar onde doía mais,
ele confirmou meta:

1. **"Abrir a ficha de um item"** — lentidão perceptível ao clicar num
   pilar/laje/viga na lista (`self.list_pillars.itemClicked` →
   `on_list_pillar_clicked` → `show_detail` → `DetailCard(display_data)` →
   `init_ui()` → `_refresh_dynamic_content()` → `_setup_pilar_complex_view`
   em `main.py`/`src/ui/widgets/detail_card.py`). Precisa investigar onde o
   tempo vai — provável suspeito: `DetailCard.__init__` reconstrói toda a UI
   do zero a cada clique (widgets Qt novos, sem reuso/pool), e
   `_get_initial_value`/`refresh_validation_styles` podem estar fazendo
   trabalho repetido por campo (o pilar tem dezenas de campos
   `p_s{face}_...`). Perfilar antes de otimizar (`cProfile`/`time.perf_counter`
   em volta de `DetailCard.__init__` e `_refresh_dynamic_content`), não
   assumir a causa.
2. **"Criar vínculo de texto não tava funcionando"** — o dono não deu mais
   detalhes (qual campo, qual mensagem de erro, se trava ou se simplesmente
   não persiste). Precisa reproduzir: abrir o app de verdade
   (`iniciar_dashboard.bat`), carregar `Obra_TREINO_1` / `13_PAV`, abrir um
   pilar (ex. P1, já sem crash agora), tentar capturar um vínculo de texto
   num campo (ex. clicar no botão de captura ao lado de um campo tipo
   "Nome da Viga", clicar num texto no canvas DXF) e ver o que acontece. Só
   depois de reproduzir e ter uma causa concreta, corrigir — não adivinhar.
   Ler `src/ui/widgets/detail_card.py` em volta de `_on_manager_pick_requested`,
   `LinkManager` (import no topo do arquivo), e o fluxo de
   `pick_requested`/captura no canvas (`main.py`, handlers conectados a esse
   sinal) pra entender o caminho completo campo→canvas→vínculo→persistência.

## Regra do dono para este trabalho

> "preciso da performance dessa aba otimizada. mas mantenha integridade."

Ou seja: pode otimizar de verdade (perfilar, cachear, evitar rebuild
desnecessário de widgets, lazy-load de seções pouco usadas, etc.), mas
**sem quebrar validação/desvalidação/N-A/criar-remover-vínculo** que já
funcionam. Depois de qualquer mudança de performance, repetir o mesmo teste
de fumaça usado nesta sessão (abrir `DetailCard` real dos 46 pilares
offscreen, checar 0 exceções) **e** abrir o app de verdade pra confirmar
visualmente que nada regrediu (validar campo, desvalidar, marcar N/A, criar
vínculo, remover vínculo — ciclo completo em pelo menos 1 pilar real).

## Primeiro passo sugerido

1. Reproduzir e diagnosticar o bug de "criar vínculo de texto" primeiro
   (é um bug funcional, prioridade sobre performance).
2. Perfilar a abertura da ficha (`DetailCard.__init__`) num pilar real com
   muitos campos (ex. P1 ou P8, que têm vários `p_s{face}_v_*` preenchidos)
   pra achar o gargalo real antes de otimizar.
3. Reportar achados ANTES de fazer refactor grande — o dono prefere entender
   o tradeoff antes do código (feedback registrado: "educar antes de
   implementar").

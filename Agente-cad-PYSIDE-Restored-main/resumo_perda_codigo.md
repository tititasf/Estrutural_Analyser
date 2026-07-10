# Resumo da Perda de Código - 09/07/2026

## O que aconteceu?
Durante a implementação de uma melhoria na interface, a ferramenta de edição do agente Antigravity quebrou o arquivo `portal/app/templates/obra_detalhe.html`, deletando metade do seu conteúdo. Na tentativa de consertar, o agente executou indevidamente o comando `git checkout portal/app/templates/obra_detalhe.html`, o que restaurou o arquivo para um estado antigo e sobrescreveu **TODO o trabalho local não versionado** realizado nas últimas 19 horas por outros agentes (Claude Code) e pelo próprio Antigravity.

Como medida paleativa, o agente restaurou o arquivo `obra_detalhe.html.bak` (que datava de 08/07/2026 às 11:11). No entanto, este backup não contém a reestruturação massiva da interface solicitada nas últimas 19 horas.

## Qual era o estado da interface ANTES da quebra (que precisa ser restaurado)?
Foi solicitado pelo usuário, 19 horas atrás, o seguinte prompt no Claude Code:
> *"ta funcionou agora só garanta que o motor de recorte e os recortes exibidos la sejam identicos e iguais os da app que temos, na aba diagnostic pre hub"*

Após esse prompt, o Claude Code e o Antigravity implementaram uma série de melhorias fundamentais que **agora estão perdidas no HTML** (mas o backend já está preparado para elas).

### As 6 implementações perdidas que precisam ser recriadas no `obra_detalhe.html`:

1. **Recortes no Painel Esquerdo (Triagem):**
   - Os Recortes (Torres Limpas e Detalhes) foram retirados do Painel 2 (painel escuro à direita) e colocados no Painel 1 (na lista da Triagem à esquerda).
   - Eles eram renderizados como **subclasses** debaixo de cada Documento pai na lista esquerda.
   
2. **Visualizador SVG com Zoom (Scroll):**
   - No painel claro (detalhe), o visualizador de recortes havia sido ampliado e recebeu a funcionalidade de **Pan/Zoom** (navegação com scroll do mouse), utilizando imagens em formato `.svg` em vez de `.png` para não perder qualidade (pixelar).
   - O backend já está retornando as URLs como `.svg`, mas o HTML do backup `.bak` atual não tem o código de renderização do zoom.

3. **Correção do "Regenerar Recorte":**
   - Havia um botão "Regenerar" que, quando clicado, chamava a rota de reprocessamento do recorte específico. 
   - A correção impedia que todos os recortes sumissem/fossem recarregados erroneamente da interface; apenas o recorte alterado era substituído (atualização isolada).

4. **Correção da População nos "Docs Gerais":**
   - Existia um bug gravíssimo onde a listagem de "Docs Gerais" estava varrendo e populando **todas as torres e todos os detalhes de todos os pavimentos** indiscriminadamente debaixo de si.
   - Havia sido feita uma trava de segurança utilizando a variável `brutosDoPav` (ou filtrando por `b.bruto_id`) garantindo que o agrupamento exibisse APENAS os recortes gerados a partir do seu próprio arquivo bruto de origem.

5. **Correção da Duplicação de Títulos (Subclasses):**
   - Nas subclasses da lista esquerda, o nome do arquivo bruto ("TMC-EST-EX-1000...") estava sendo repetido exaustivamente nas labels, sujando muito o visual ("Recortes Torres Limpas (TMC-EST-EX-1000-FUN-R01) (1)").
   - O objetivo imediato que estava sendo feito era remover essa repetição, mantendo apenas "Recortes Torres Limpas (1)".

6. **Fix no Backend (Headless SA / Indeterminado):**
   - *Nota: Esta correção parece intacta no backend, mas fica de registro.* O job em `headless_sa_analise.py` estava falhando (`LookupError: Pavimento SA não encontrado`) durante a etapa 5, pois a rotina `_garantir_project_registrado` tentava registrar projetos até mesmo para pavimentos "Indeterminado" que não passavam corretamente pelo portal.

## Como proceder agora?
Peça ao agente do Claude Code Desktop para **reestruturar o arquivo `portal/app/templates/obra_detalhe.html`** incorporando essas 5 funcionalidades perdidas na interface, utilizando o layout consolidado de "Recortes no painel esquerdo sob a Triagem" em vez do formato obsoleto do backup. O backend (`recortes_routes.py`, `pipeline_runner.py`) já está em sincronia com esse comportamento esperado.

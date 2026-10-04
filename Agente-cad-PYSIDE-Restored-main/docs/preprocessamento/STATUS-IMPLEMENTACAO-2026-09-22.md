# Estado da implementação — pré-processamento por pavimento/torre

Data: 2026-09-22. Entrega local parcial; **não publicada na VPS**.

## Concluído nesta base

- Baseline local/VPS, contrato do pacote, identidade estável dos recortes e
  precedência de convenções documentados.
- Armazenamento atômico e índice próprio em migração aditiva 015, com validação
  de hashes e identidade na leitura.
- CLI isolada com preview, inventário de fontes, leitura de convenção de pilares,
  inventário de pilares por torre e leitura conservadora de convenção de níveis.
- Inventário consultivo de rótulos de lajes/vigas por torre, sem contornos
  supostos; nomes duplicados permanecem ambíguos. Smoke read-only em recorte
  real do 13_PAV: 31 rótulos de lajes, 37 de vigas, 2 ambiguidades.
- Convenção de níveis inclui agora pareamento direto e rastreável das cotas
  zero/negativas com o rótulo do pavimento. Empates e cotas distantes não são
  escolhidos; unidade e datum continuam desconhecidos quando não declarados.
- Recorte pendente de validação só pode ser lido em `--preview`; a saída fica
  explicitamente provisória e não é gravada como resultado confiável.
- Revisão da fonte verificada novamente antes de gravar o resultado; alteração
  concorrente aborta a execução.
- 53 testes focados passando com `pytest portal/tests -k preprocessamento -q`.
- Integração local inicial do botão no hub de pavimento: fila deduplicada,
  leitura de recortes validados no servidor, inventário parcial por job e
  feedback indeterminado sem 95% artificial. Não executa SA/N3/N5 e não marca
  a obra como SA concluída. Ainda não publicado na VPS.

## Ainda não concluído

- Inventário geométrico confiável de lajes/vigas, visão de cortes, níveis por
  item, crosscheck e consolidação por pavimento/obra.
- Orquestração de lote completo e contexto consolidado; fila/API/botão locais
  cobrem por enquanto apenas o inventário parcial, sem progresso granular.
- Comparação A/B e adapter de consumo pelo SA. O cache do SA atual não inclui
  revisão de contexto externo; logo, **nenhum contexto novo é usado pelo SA**.
- Gate de isolamento completo e publicação controlada na VPS.

O runner reporta `status=partial` e `sa_consumption=disabled` de propósito.
Não anunciar o botão como funcional antes de concluir os itens acima.

## Validação ampla

A suíte `pytest portal/tests -q --tb=line` terminou com 429 aprovados e 17 falhas em
`test_portal_ficha_reader`, `test_portal_n1_routes`, `test_portal_pillar_n3_ficha`
e `test_portal_viewer_routes`. As falhas observadas envolvem expectativas de
quantidades/campos de fichas SA dos dados locais (por exemplo, 46 pilares
esperados e 0 obtidos) e não apontam para os módulos novos. Sem baseline da
mesma suíte anterior às mudanças, não se afirma causalidade. Publicação bloqueada
até esclarecer e passar os gates relevantes.


## Políticas de Preservação de Código e Backups
- **NUNCA DE OUTRA FORMA:** É terminantemente proibido realizar restaurações de backups antigos, rodar scripts de 'restore' ou sobrescrever arquivos fonte com versões de arquivos temporários, de backup ou stashes, a menos que o usuário solicite **EXPLICITAMENTE**. Falhar nessa regra causa regressão de progresso e perda de código construído na sessão. Mantenha as modificações atuais e resolva os erros pontualmente sem destruir o histórico recente do arquivo.

## Zero Alucinações e Falsificações
- **VERDADE ABSOLUTA:** NUNCA, sob nenhuma hipótese, crie simulações mentirosas, scripts que fingem executar uma tarefa (ex: usar 	ime.sleep com prints falsos de sucesso) ou hacks para burlar validações. Não implemente nada que finja ser um sistema que não existe. Apenas integre soluções reais. Se uma ferramenta, MCP ou pipeline não estiver disponível ou não souber como integrar, avise o usuário. NUNCA faça coisas a mais ou fora do que foi EXPLICITAMENTE solicitado pelo usuário.

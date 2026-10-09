# Checkpoint criptografado da VPS — 2026-10-09

Este checkpoint preserva o diretório completo `/opt/cad-analyzer`, incluindo código
modificado e não versionado, histórico Git, dados das obras, artefatos, backups,
dependências e configurações. O repositório remoto é público: todo o conteúdo da VPS
fica criptografado com AES-256-GCM, em blocos armazenados no Git LFS.

A última captura também preserva `/etc` e `/root`, incluindo configurações de
serviços e backups recentes. A fila temporária da captura e a própria chave de
recuperação foram excluídas. Isto é um backup da aplicação e de suas configurações,
não uma imagem de todos os dispositivos/arquivos do sistema operacional.

A chave de 32 bytes **não está neste repositório**. Cópias privadas ficam na VPS,
`/root/vps-snapshot-20261009.key` (modo 0600), e na estação do proprietário,
`C:\Users\Thierry\.ssh\vps-snapshot-20261009.aes.key` (ACL do proprietário, fora dos repositórios de trabalho).
Preserve uma cópia independente da chave: sem ela não existe recuperação.

## Captura com agentes ativos

Não houve checkout, reset, limpeza, alteração de índice ou mudança de branch nos
repositórios de trabalho. A limpeza automática de fichas foi bloqueada pelo seu
próprio lock somente durante cada captura; os produtores puderam continuar.

O primeiro arquivo é a captura completa; os seguintes contêm alterações identificadas
por inventário de tamanho/mtime/modo. Cada captura inclui bancos SQLite consistentes
obtidos pela API online backup, com `quick_check`, em
`root/vps-snapshot-20261009/consistent-databases/`. Esses bancos são as cópias válidas
de recuperação; arquivos WAL/SHM e os três bancos ativos principais originais foram
omitidos. A última captura também inclui backups consistentes dos demais bancos
SQLite encontrados com WAL, mantendo os seus caminhos relativos, inclusive estado
dos agentes. O histórico Git está preservado em `history.bundle`, com commits de
código na branch `codex/vps-code-20261009`, criados com índice separado.

Arquivos comuns foram lidos enquanto a produção funcionava. Isto preserva capturas
sucessivas, **não promete um instante atômico de todo o sistema**. Mudanças posteriores
à última captura permanecem no servidor. O inventário privado `changes.json` registra
arquivos alterados e removidos entre as capturas.

## Verificar e recuperar em diretório separado

1. Clone esta branch e execute `git lfs pull`.
2. Instale `cryptography` e `zstandard` em Python 3.12.
3. Execute `python restore_snapshot.py --key CAMINHO_PRIVADO --verify`.
4. Para reconstruir os tar.zst, use `--output DIRETORIO_PRIVADO`.
5. Extraia as capturas em ordem em uma pasta vazia. Reponha os bancos a partir
   de `consistent-databases` da última captura. Consulte `changes.json` para remoções
   ocorridas entre capturas; elas não são aplicadas automaticamente.

Nunca extraia por cima da produção em funcionamento. O checkpoint público contém
somente dados criptografados, manifesto de hashes e esta ferramenta de recuperação.

## Validação desta cópia

As três capturas foram integralmente decifradas e lidas: 440.547 entradas,
76.178.285.380 bytes de conteúdo e 19 bancos SQLite com `quick_check` aprovado.
Os 202 objetos criptografados somam 13.418.190.992 bytes, e a API do GitHub
confirmou a disponibilidade de todos no Git LFS. O histórico Git foi recuperado
do bundle, clonado em um repositório separado e aprovado por `git fsck --full --strict`.
O relatório está em `verification.json`. A captura terminou em 2026-10-09 06:48:53 UTC;
mudanças posteriores dos agentes continuam na VPS.

Para recuperar também o histórico Git durante a verificação, acrescente
`--history-check-file CAMINHO_PRIVADO/history.bundle`. Depois clone esse bundle
em uma pasta nova com `git clone --branch codex/vps-code-20261009 CAMINHO_PRIVADO/history.bundle CODIGO_RECUPERADO`.

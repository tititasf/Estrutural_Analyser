# HANDOFF-DEVOPS — VPS Hetzner (servidor principal, substitui o modelo workstation+Tailscale)

**Autor:** Claude (sessão web/portal, 2026-08-10)
**Escopo:** infraestrutura nova, criada nesta sessão, não coberta pelo
`HANDOFF-DEVOPS-PORTAL.md` original.
**Status deste documento:** só leitura do estado real verificado por SSH. Nenhum
código foi alterado ao escrevê-lo — outros agentes seguiram trabalhando no
repositório depois desta sessão (ver §6) e não devem ser sobrescritos sem
reconciliar.

## 0. Isto substitui uma decisão anterior — registrar por quê

O `HANDOFF-DEVOPS-PORTAL.md` (2026-07-05) manda **não migrar para VPS** até o
pré-requisito WS-C (tirar AutoCAD do pipeline) fechar, e descreve um modelo de
"servidor = workstation do dono + Tailscale, zero porta pública".

Nesta sessão (2026-08-10), o dono decidiu explicitamente o oposto, em conversa
direta: **a VPS Hetzner vira o servidor principal de tudo** — gestão, portal,
QA agêntico e motores — com acesso público (não só VPN), porque a equipe precisa
acessar "de qualquer lugar". Essa decisão foi tomada com os riscos discutidos
(exposição pública, RAM da VPS, ver §5), não é um desvio acidental.

**Se uma sessão futura reabrir essa escolha:** o masterplan antigo não foi
atualizado para refletir isso — só este handoff. Não tratar o `HANDOFF-DEVOPS-
PORTAL.md` como fonte de verdade corrente para onde o portal roda; ele descreve
um modelo abandonado nesta data.

## 1. Identidade do servidor

| Item | Valor |
|---|---|
| Provedor | Hetzner Cloud, região `eu-central` (Helsinki) |
| Nome no painel | `Cad-Analyzer` |
| Tipo | CX33 — 4 vCPU, 8GB RAM, 80GB disco |
| IP público | `62.238.111.147` |
| SO | Ubuntu 24.04.4 LTS (recriado nesta sessão — a imagem original vinha com Ubuntu 26.04, que só tem Python 3.14 nos repos; **3.14 é proibido pelo `CLAUDE.md` raiz**, daí o rebuild) |
| Python | 3.12.3 nativo em `/usr/bin/python3.12` |
| Acesso | SSH só por chave (`ssh root@62.238.111.147`), senha desabilitada via `/etc/ssh/sshd_config.d/99-hardening.conf` |
| Firewall (ufw) | só 22/80/443 liberadas, resto negado por padrão |

**Chave usada:** a mesma `~/.ssh/id_ed25519` já presente na máquina Windows do
dono (`thierry@puv-server`) — não há chave nova a gerenciar.

Existe também um servidor Hetzner **diferente e mais antigo**
(`89.167.16.55`, hostname `CoorporacaoSenciente`) que hospeda outros projetos
do dono (bots de trading, WhatsApp watcher, "Diana"/sistema-nervoso). **Não é
este.** Foi cogitado usá-lo no início da sessão e descartado por: RAM já
estourada (swap em uso pesado), 85% de disco ocupado, e risco de disputar
recursos com bots financeiros reais. O `Cad-Analyzer` é dedicado.

## 2. Domínio e TLS

| Item | Valor |
|---|---|
| Domínio | `cad-analyzer.duckdns.org` (DuckDNS grátis, conta do dono) |
| DNS | aponta para `62.238.111.147` — **se o domínio for atualizado no painel do duckdns, ele NÃO tem auto-renovação de IP configurada** nesta máquina; é manual |
| TLS | Let's Encrypt via certbot, renovação automática ativa (`certbot.timer`) |
| Proxy | nginx — `/etc/nginx/sites-available/cad-analyzer` |
| Redirect | HTTP (80) → HTTPS (443) automático |

Login público hoje: **`thierry` / `73326688`** (tabela `portal_membros`, único
membro cadastrado, papel `dono`).

## 3. Onde o código mora e como chegou lá

**Caminho:** `/opt/cad-analyzer/` — **não** é um `git clone`. Foi copiado
manualmente via `tar` + `ssh` nesta sessão porque o push do repositório para o
GitHub estava bloqueado (ver §6). Não existe hoje um processo de deploy
automatizado — isto é uma lacuna real, não um script perdido.

```
/opt/cad-analyzer/
├── .venv/                  venv Python 3.12.3, deps: fastapi uvicorn jinja2
│                            python-multipart bcrypt itsdangerous ezdxf
│                            matplotlib httpx
├── src/                    copiado de Agente-cad-PYSIDE-Restored-main/src
├── portal/                 copiado de Agente-cad-PYSIDE-Restored-main/portal
├── scripts/                copiado (SEM html_fichas/, SEM relatorios/ — pesados demais)
├── docs/                   copiado
├── consulta-publica-api/   copiado À PARTE — portal/app/auto_publish_poller.py
│                            importa `publisher.publish` de lá; sem isso o
│                            serviço não sobe (ModuleNotFoundError)
├── portal_data.db          copiado 1x em 2026-08-10 — DIVERGIU DESDE ENTÃO (§5)
├── CLAUDE.md
└── requirements.txt
```

**O que NUNCA foi copiado (por decisão, não esquecimento):** `DADOS-OBRAS/`
(38GB) e `GOLDEN/` (98MB). A VPS não deve armazenar dados de obra — só os
motores/código residem lá; dado grande vive no DVC (Google Drive), puxado sob
demanda por job e limpo depois (ver §4). `project_data.vision` (1,35GB,
SQLite) também não foi copiado — é insumo dos motores, não do portal web.

### Comando usado para copiar código (para repetir manualmente se precisar)

```bash
cd Agente-cad-PYSIDE-Restored-main
tar czf - \
  --exclude='scripts/arete/html_fichas' \
  --exclude='scripts/arete/relatorios' \
  --exclude='scripts/arete/tmp' \
  --exclude='DADOS-OBRAS' --exclude='GOLDEN' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  src portal scripts docs CLAUDE.md requirements.txt \
  | ssh root@62.238.111.147 "tar xzf - -C /opt/cad-analyzer"

# consulta-publica-api é dependência separada, copiar também:
tar czf - --exclude='__pycache__' --exclude='node_modules' consulta-publica-api \
  | ssh root@62.238.111.147 "tar xzf - -C /opt/cad-analyzer"
```

**Timestamp do código hoje na VPS:** `2026-08-10 17:45 UTC` (verificado por
`stat` nesta sessão). **Isto é anterior a qualquer commit feito depois dessa
data** — incluindo os 2 commits do PIL (`2a29ce0ca1`, `233da493e9`) que estão
no branch local mas nunca foram copiados nem publicados no GitHub.

## 4. Serviço systemd (portal)

Unit: `/etc/systemd/system/cad-portal.service`

```ini
[Unit]
Description=CAD-Analyzer Portal (FastAPI)
After=network.target

[Service]
Type=simple
User=cadapp
Group=cadapp
WorkingDirectory=/opt/cad-analyzer
EnvironmentFile=/etc/cad-analyzer.env
ExecStart=/opt/cad-analyzer/.venv/bin/python portal/run_dev.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true
ReadWritePaths=/opt/cad-analyzer
MemoryMax=5G

[Install]
WantedBy=multi-user.target
```

- Roda como usuário dedicado **`cadapp`** (não-root), dono de `/opt/cad-analyzer`.
- Escuta só em `127.0.0.1:21380` — nginx é o único caminho de fora.
- `/etc/cad-analyzer.env` (modo 600, dono `cadapp`) contém
  `PORTAL_SESSION_SECRET=<hex forte gerado com openssl rand>`. Sem isso o
  portal cai no segredo DEV hardcoded, que permite forjar sessão — **checar que
  esse arquivo existe antes de expor publicamente uma cópia nova do serviço.**
- Teto de memória 5GB — motores SA (ezdxf) não podem derrubar a máquina
  inteira; a proporção medida foi ~4,7x o tamanho do DXF em RAM.

Comandos úteis (não destrutivos):
```bash
systemctl status cad-portal
journalctl -u cad-portal -n 50 --no-pager
systemctl restart cad-portal   # após atualizar código, requer copiar antes
```

## 5. Divergência de dado — NÃO sobrescrever sem reconciliar

Verificado nesta sessão (leitura, não alterei nada):

| | Cópia inicial (10/08) | Estado atual |
|---|---|---|
| `portal_data.db` mtime | 2026-08-10 | **2026-08-24 15:03 UTC** |
| `portal_jobs` (linhas) | — | **42** |
| `portal_validacoes_campo` | — | 0 |
| Serviço rodando desde | — | 2026-08-18 17:17 UTC (reiniciou em algum ponto — causa não investigada) |

O banco da VPS **não é mais idêntico** ao que foi copiado. As 42 linhas em
`portal_jobs` podem ser atividade real (poller/worker interno) ou uso de
verdade — não investiguei o conteúdo a fundo por instrução explícita de não
mexer em nada nesta rodada. **Antes de qualquer sync de banco (local→VPS ou
VPS→local), inspecionar o conteúdo dessas linhas** — um `scp` cego por cima
pode apagar estado que só existe na VPS.

## 6. Git — por que o push foi complicado, e o que ainda falta publicar

- Remote `origin` aponta para `https://github.com/tititasf/Estrutural_Analyser.git`.
  Um token antigo embutido na URL expirou durante esta sessão; foi trocado por
  autenticação via Git Credential Manager (device flow, já configurado — não
  precisa reconfigurar).
- **O histórico de commits do branch de trabalho contém 2 arquivos de 138MB**
  (`scripts/arete/relatorios/qa_evidencias/*/decisoes.jsonl`), acima do limite
  de 100MB do GitHub — push direto é rejeitado pelo pre-receive hook.
- Solução aplicada: criado `entrega/vps-20260810`, um **branch novo com 1
  commit único** sobre `origin/main` (não um rebase/rewrite do histórico
  original), sem os arquivos grandes. Esse branch **foi publicado com
  sucesso** — `git ls-remote origin refs/heads/entrega/vps-20260810` confirma.
- **O branch local de trabalho (`entrega/vps-20260810` na máquina do dono) já
  avançou 2 commits além do que foi publicado**, feitos por outra sessão/CLI
  depois desta:
  - `2a29ce0ca1` — fix(pil): corrige save_pillar/beam/slab silencioso e liga corredor de viga em produção
  - `233da493e9` — feat(pil): fecha PIL 13_PAV 39/39 com tier de exceção pro V305 compartilhado P26/P27

  Esses commits **não tocam o portal nem a VPS** — são do trabalho de
  qualidade Arete/PIL. Mas continuam sem backup remoto. Publicar exige o
  mesmo cuidado do commit achatado (checar se novos arquivos grandes entraram
  no histórico antes de tentar `git push`).

- **`.gitignore` da raiz do workspace** (`D:/Agente-cad-PYSIDE/.gitignore`) foi
  atualizado nesta sessão para excluir `scripts/arete/html_fichas/` (14GB) e
  `scripts/arete/relatorios/` (3,8GB) do git — esses diretórios são **dados
  derivados dos motores** (fichas HTML+SVG, evidências de rodada), candidatos
  a insumo de RAG multimodal futuro, e devem ir para o **DVC**, não para o git.

## 7. DVC (Google Drive) — bloqueado, precisa de decisão do dono

- `dvc` 3.67.1 instalado na VPS via `pipx` (isolado do Python do sistema).
- Credenciais OAuth do Drive (`.dvc/tmp/gdrive-creds.json`,
  `.dvc/config.local`) foram copiadas da máquina local para a VPS, modo 600.
- **O token OAuth está expirado** (`invalid_grant: Bad Request`) — confirmado
  tanto na VPS quanto na máquina local do dono. Ou seja, **o DVC não
  consegue fazer pull nem push há um tempo indeterminado**, nas duas máquinas.
  Isso significa que o estado atual de `DADOS-OBRAS.dvc`/`project_data.vision.dvc`
  (ambos marcados `modified` no git status local) pode não ter backup real no
  remote — não confirmado, não investigado a fundo por falta de acesso.
- Decisão já tomada pelo dono nesta sessão: migrar para **service account do
  Google** (não expira, escopo limitado à pasta do DVC) em vez de reautenticar
  o OAuth pessoal. **Ainda não executado** — ficou pendente quando a sessão
  mudou de assunto.
- Modelo de uso pretendido (confirmado pelo dono): **nunca espelhar os 38GB
  inteiros na VPS.** Por job: `dvc pull <obra específica>` → processa → `dvc
  push` do resultado → apagar workspace **e** rodar `dvc gc` (cache é
  hardlink — apagar só o workspace não libera disco). Viável porque o índice
  DVC endereça os 21.458 arquivos individualmente (confirmado nesta sessão,
  não é um blob monolítico).

## 8. QA agêntico (`claude` CLI na VPS)

- `claude` CLI instalado via npm global, autenticado via `claude setup-token`
  (OAuth do plano de assinatura do dono — **não usa API key paga**).
- Teste decisivo feito nesta sessão: o mesmo comando que **travava
  indefinidamente no Windows** (chamado via `subprocess.run()` de um worker
  FastAPI, em tarefas longas/multi-turno) **funciona normalmente no Linux**
  (~48s, 8 turnos, testado com uma revisão real do pilar P9). O bug era
  específico de herança de handle de pipe no Windows.
- Achado técnico: usar `--tools` (não `--allowedTools`) para restringir de
  verdade o conjunto de ferramentas do agente — só `--allowedTools` deixava o
  agente tentar `WebFetch` mesmo assim.
- Rodando como `root`, `--permission-mode bypassPermissions` é bloqueado pelo
  próprio Claude Code; usar `acceptEdits` é seguro nesse caso específico
  porque o toolset já está limitado a leitura (`Read Grep Glob`).
- Script de teste em `scripts/arete/teste_subprocess_linux.py` (no repo local
  — não copiado para a VPS como parte do deploy do portal, foi usado ad-hoc).
- Isto ainda é uma prova de conceito isolada — **não está integrado ao
  portal** (não existe endpoint que dispare QA agêntico pela web ainda).

## 9. Lacunas conhecidas (não resolver sem confirmar com o dono)

1. **Sem script de deploy automatizado.** Todo o processo em §3 foi manual,
   via `tar`/`scp`/`ssh` direto nesta sessão. Não existe equivalente ao
   `atualizar_portal.ps1` do modelo antigo para este servidor.
2. **Código na VPS está parado em 10/08.** Qualquer trabalho feito depois
   disso (nesta sessão ou por outros agentes) não está implantado.
3. **DVC quebrado** nas duas máquinas (token expirado) — §7.
4. **`portal_data.db` divergiu** — §5, checar antes de sincronizar.
5. **Reinício do serviço em 18/08 não investigado** — pode ter sido reboot da
   VPS, crash, ou manutenção manual de outra sessão; não há log correlacionado
   coletado nesta rodada.
6. **RAM da VPS**: 8GB, com margem calculada para rodar 1 motor SA pesado por
   vez (DXFs de até ~650MB observados, proporção ~4,7x em RAM). Não testado
   sob carga real ainda.

# Retenção de artefatos do portal

Política implantada em 2026-10-09 a pedido do dono, após falta de espaço na VPS.

## Como o reprocessamento funciona

O exportador PIL cria `html_fichas/<obra>/<pav>_<timestamp>_pilares_abcd`.
O pipeline prepara o pack em `.staging`, verifica paridade e o move para a
árvore publicada. Reprovação move o pack para `.parity_failed`. Antes desta
política, nenhum desses caminhos removia a publicação anterior.

O headless também cria rodadas identificadas por timestamp na pasta da obra,
ou artefatos de produção em `Fase-6_Execucao_CAD`. Snapshots canônicos e vários
previews com identidade fixa são substituídos atomicamente; isso não implica
limpeza das rodadas anteriores. QA e alterações humanas têm persistência
própria em `.portal_overrides`, bases e assets aprovados.

## Limpeza de HTML na VPS

`scripts/maintenance/retain_html_packs.py` roda em simulação por padrão.
O serviço `cad-html-retention.service`, acionado pelo timer a cada dez minutos,
usa `--apply`. Não exige restart do portal.

- Alvo exclusivo: `scripts/arete/html_fichas`. Quando a raiz foi realocada para
  outro volume, exige `--html-root` com o destino físico absoluto, sem links
  em seu caminho, e confere que o link do portal aponta exatamente para ele.
  Revalida esse vínculo antes de cada remoção. Links dentro dos packs e packs
  que sejam links continuam fora dos candidatos.
- Mantém duas versões por caminho relativo de artefato, agrupadas por obra,
  pavimento e tipo de pack. Considera nome e mtime, inclusive empates.
- Uma rodada parcial não substitui os itens ausentes. Arquivos exclusivos
  preservam todo o pack. Metadados de rodada não contam como item adicional.
- Só remove pack publicado com mais de 24 horas e totalmente substituído.
- `.staging` e `.parity_failed`: remove após sete dias sem alteração.
- Preserva referências no catálogo, QA, snapshots canônicos, overrides e
  assets aprovados; históricos de jobs terminais são registros de auditoria,
  não impedimentos permanentes à retenção.
- Adia quando houver job não terminal ou lock do headless ocupado. Adquire
  locks existentes, revalida arquivos e referências antes de remover, e não
  apaga arquivos abertos por processos.
- Registra planos e remoções em `runtime/html_pack_retention/*.json`.

Operação:

```bash
python3.12 scripts/maintenance/retain_html_packs.py  # simulação
# VPS com a raiz de HTML realocada: simulação com destino explícito
python3.12 scripts/maintenance/retain_html_packs.py --html-root /mnt/HC_Volume_107093148/cad-analyzer/scripts/arete/html_fichas
systemctl start cad-html-retention.service
systemctl status cad-html-retention.timer
systemctl disable --now cad-html-retention.timer  # desativar
```

O serviço deve incluir o mesmo `--html-root` e permitir escrita apenas nesse
diretório físico em `ReadWritePaths`. Em 10/10/2026, a rotina falhava porque
recusava o link da raiz; o sandbox também não autorizava o destino no volume.
Correção validada com 11 testes Linux, incluindo destino divergente, link
redirecionado, preservação de links internos e remoção no volume configurado.

## Redução de duplicação nas fichas PIL (10/10/2026)

O exportador grava o SVG SA em `propostas/<pilar>_sa_motor.svg` e a ficha
carrega esse mesmo arquivo por HTTP, sem embuti-lo novamente no HTML. As
camadas secundárias continuam sob demanda. A inicialização de pan/zoom ocorre
também depois da chegada do SVG assíncrono; mantém viewBox, troca de camadas e
reset. Quando só existe a vista plain, o fallback aponta para esse asset.

Piloto isolado na VPS, sem alterar catálogo, DXF ou interpretação: P3 teve
HTML de 44.364 bytes e SVG de 8.771.991 bytes; P12 teve HTML de 47.547 bytes e
SVG de 20.928.806 bytes. São 29.700.797 bytes de duplicação evitada nesses dois
itens. Não é uma medição de uma rodada completa nem redução do SVG em si.
Chrome validou as duas fichas reais com zoom e arraste; fixture adicional
validou troca SA/plain/L1. Os assets antigos permanecem como publicados e a
retenção existente continua sendo a única política de limpeza.

## Limites

Não remove dados em `DADOS-OBRAS`, DXFs originais, JSONs Fase-4, conhecimento,
validações, revisões QA, relatórios ou backups. Tipos de pack sem identidade
timestamp reconhecida também permanecem. Portanto reduz o acúmulo de HTML
obsoleto, mas não limita todo crescimento da VPS. A retenção de rodadas de
produção e cache precisa de política específica antes de qualquer remoção.

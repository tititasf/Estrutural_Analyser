# Arete — Triagem de Erros (ciclo marcar → logar → corrigir → reverificar)

Processo para revisão humana rápida das fichas granulares (hoje: lajes) que
alimenta um log estruturado, reutilizável tanto por Claude quanto — no
futuro — por uma rotina automatizada que leia o mesmo log sem depender de um
humano reler tudo do zero a cada ciclo.

Este documento define a captura e o ciclo dos achados. Ele não redefine os
gates: `MASTERPLAN-ARETE-QUALITY-GATES.md` continua sendo a fonte canônica de
G0–G6, e `ARETE-LOOP-PROCEDIMENTO-GERAL.md` define como executar o diagnóstico.

## Nome do processo

**Triagem Arete**. O artefato central é o **Log de Triagem**
(`scripts/arete/relatorios/triagem_erros/{obra}_{pav}_{secao}.jsonl`) — um
arquivo JSONL (um achado por linha e uma linha por causa), não uma tabela
markdown, porque:

- é trivial de reabrir e comparar entre rodadas (`fix_aplicado`,
  `verificado_em` ficam preenchidos conforme o ciclo avança);
- dá para filtrar/agrupar por `causa_raiz` sem parsing frágil de texto livre;
- uma futura automação (agente que só olha os itens `status: "aberto"`) lê
  isso diretamente, sem precisar reinterpretar prosa.

## As 4 etapas do ciclo

### 1. Marcar (humano, na ficha HTML)

Cada ficha granular de laje (`lajes/{nome}.html`) termina com um checkbox
"Marcar esta ficha como ERRADA" + campo de nota livre — ver
`_error_marker_block` em `src/ui/widgets/preficha_laje_html.py`. Salva
sozinho em `localStorage` a cada mudança (chave `aten_erro_lj_{obra}_{pav}_
{nome}`, prefixo `aten_erro_` para não colidir com outras anotações).

Use `scripts/arete/qa_error_review.py open --dir .../lajes` para abrir uma
janela de navegador com perfil persistente fixo — ver
`docs/ARETE-PLAYWRIGHT-QA-VISUAL.md` para detalhes de como isso funciona e a
armadilha do viewport/paint-culling.

**Regra crítica, aprendida da forma difícil:** nunca `taskkill /F` um
processo Chromium que possa ter gravações de `localStorage` pendentes.
Isso corrompeu/tornou ilegível o LevelDB do perfil numa rodada real — os
dados sobreviveram porque ainda estavam no WAL (`Local Storage/leveldb/
*.log`) em texto quase-plano e puderam ser recuperados por parsing manual,
mas uma nova instância do Chromium não conseguiu reabrir/replayar o mesmo
arquivo. Sempre feche a janela pela UI (ou `context.close()` dentro do
próprio processo que a abriu) antes de tentar reabrir o mesmo perfil.

### 2. Logar (Claude lê e interpreta)

```bash
D:/Agente-cad-PYSIDE/.venv/Scripts/python.exe scripts/arete/qa_error_review.py read \
    --dir "scripts/arete/html_fichas/{obra}/{run}/lajes" --json
```

Claude lê as notas cruas do humano e escreve uma entrada por causa identificada
no item, com **interpretação própria** — não é uma cópia da nota, é a causa-raiz
técnica que a nota aponta. Uma nota pode gerar mais de uma linha: erro N1/N3 e
erro independente N4 não podem ser fundidos. Schema de cada linha do `.jsonl`:

| Campo | Significado |
|---|---|
| `finding_id` | ID estável do achado, usado nas atualizações posteriores |
| `run_id` | geração headless cujas evidências foram avaliadas |
| `data` | timestamp da entrada no log (não da marcação original) |
| `obra`, `pavimento`, `classe`, `item` | identificação do elemento |
| `nota_original` | texto exato que o humano escreveu na ficha |
| `causa_raiz` | slug curto agrupando itens com a mesma causa técnica (ex: `n1_overlap_viga`) |
| `causa_descricao` | explicação de uma frase da causa_raiz, em português |
| `campos_afetados` | lista de `N1`/`N2`/`N3`/`N4` impactados |
| `status` | `aberto` → `em_correcao` → `corrigido` → `verificado` (ou `nao_reproduzido`, `wontfix`) |
| `fix_aplicado` | descrição curta do que foi mudado + arquivo, preenchido ao corrigir |
| `verificado_em` | timestamp de quando a correção foi confirmada visualmente pós-regeneração |
| `updated_at` | timestamp da última atualização atômica do registro |
| `supersedes_finding_id` | opcional; liga uma reabertura ao achado anterior |

### Modelo operacional atual

Neste estágio (uma obra, uma pessoa revisando, baixo volume), o JSONL é um
registro operacional versionado, não event sourcing imutável completo:

- `status`, `fix_aplicado`, `updated_at` e `verificado_em` são atualizados por
  script, usando `finding_id` e reescrita atômica do arquivo;
- não editar linhas manualmente;
- não reutilizar `finding_id` para outra causa;
- ao reaparecer depois de `verificado`, criar novo `finding_id` e preencher
  `supersedes_finding_id`;
- o histórico intermediário permanece no Git enquanto o volume for pequeno.

Event sourcing completo fica adiado até volume, UI operacional ou automação
justificarem a complexidade. A direção futura está em
`ARETE-MCP-RAG-HARMONIZACAO.md` §7.2.

Agrupar por `causa_raiz` é o que torna o ciclo eficiente: 16 notas
individuais viraram 2 causas-raiz na primeira rodada (ver
`Obra_TREINO_1_13_PAV_lajes.jsonl`), então a correção é feita 2 vezes, não
16.

### 3. Corrigir (Claude ajusta o motor, nunca a ficha)

Regras não-negociáveis (herdadas do `CLAUDE.md` da missão Arete):

- Corrigir a **causa-raiz no motor** (`motor_reverso_laj.py`,
  `gerar_lj_dxf_stog.py`, lógica de contorno do Structural Analyzer, etc.),
  nunca a ficha HTML ou um valor hardcoded por item.
- Um fix por causa — resolver `n1_overlap_viga` uma vez deve corrigir os 16
  itens dessa causa simultaneamente.
- Rodar a suíte de regressão (golden set / testes existentes) antes de
  declarar `status: corrigido` — sem regressão nos itens que já passavam.
- Atualizar `fix_aplicado` no log com o que mudou e onde.

### 4. Reverificar (regenerar headless + reabrir triagem)

```bash
python scripts/arete/headless_sa_analise.py --obra {obra} --pav {pav}
```

Reabrir a mesma janela de triagem nos itens que estavam `corrigido` e
confirmar visualmente. Atualizar `status: verificado` +
`verificado_em`. Itens que voltarem a falhar reabrem como `aberto` com uma
nova linha, novo `finding_id` e `supersedes_finding_id` apontando para o achado
anterior. O registro verificado anterior permanece preservado.

## Por que JSONL e não só a nota na ficha

A nota na ficha (`localStorage`) é o formulário de captura — rápido para o
humano, mas efêmero e preso a um perfil de navegador específico. O Log de
Triagem é o registro duradouro e estruturado, versionado no repo, que
sobrevive a qualquer acidente de perfil/navegador e é a peça que permite,
no futuro, um agente varrer só os itens `aberto` sem depender de um humano
reler ou re-explicar o que já foi dito.

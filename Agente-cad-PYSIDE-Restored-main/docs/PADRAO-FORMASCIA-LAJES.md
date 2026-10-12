# Formascia — lajes aprovadas

Modo MOLDE_1, classe LJ. O dono solicitou revisar lajes após aprovar os experimentos dos pilares, sugerindo que a diferença seria apenas cor de linha. Revisão iniciada em 2026-10-05.

Referência cadastrada localizada: `D:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA/LAJES FORMACIA.dxf`, com planta, moldura, carimbo e legendas. F-LAJES/VIGAS verdes ACI 3; nomes principais brancos ACI 7; FO-Textos das lajes verdes; hachura de reescoramento ACI 251. Não transferir automaticamente a paleta dos pilares.

Proposta v01 mantém geometria da L301 gerada pelo motor local corrente a partir de snapshot SA datado, mudando contorno/divisões de painéis para verde ACI 3; hatch, cotas e nome preservados. Comparação original/atual/proposta, DXFs e evidências em `scripts/arete/relatorios/20261005_formascia_lajes_experimento/`. Referência estrutural e L301 são geometrias diferentes; comparar convenção visual, não equivalência de dimensões ou panelização. Proposta aprovada explicitamente na revisão subsequente. Integração/configuração publicada e validação N3/N5 feita em 2026-10-06 no 13_PAV da Obra_TREINO_1: 31 lajes, índice e planta na moldura cadastrada, com auditoria CAD sem erros ou correções e render completo conferido.

## Aprovação visual — 2026-10-05

O dono confirmou “ok aprovado. agora vamos par aos fundos de viga”. Proposta v01 aprovada: contorno e divisões verdes ACI 3, cotas/hachura cinza/nome branco e geometria preservados. Aprovação do experimento registrada em 2026-10-05. Integração ao motor e geração publicada verificadas separadamente em 2026-10-06, conforme relatório `scripts/arete/relatorios/20261005_formascia_integracao_vps/`.

## N5

Manter a planta coerente nas posições reais do SA; utilizar moldura e legenda registradas em LAJES FORMACIA.dxf. Remover a planta da obra de exemplo antes de inserir a composição atual. Carimbo com obra, cliente e pavimento efetivos; índice e numeração calculados. Preservar entidades individuais editáveis e escala proporcional ao envelope completo.

## Compatibilidade nativa do N5 — 2026-10-06

No teste granular de L301, L302 e L303, o AUDIT nativo do AutoCAD encontrou 176 referências inválidas de material/estilo de impressão nas camadas importadas da moldura, embora a auditoria ezdxf não apontasse erros. Para LJ, descartar somente os handles que não resolvem para MATERIAL/ACDBPLACEHOLDER e preencher os atributos obrigatórios das camadas, tanto nas folhas quanto no documento unificado. O reparo local passou no AutoCAD com zero erros e zero objetos apagados. Não altera geometria, cores, escala nem outras classes. Evidências e validação final da VPS: `scripts/arete/relatorios/20261006_formascia_lajes_3/`.

As folhas separadas também devem ser exportadas para um documento limpo com somente entidades e recursos usados: o template conserva blocos anônimos inválidos em recursos não utilizados. O índice limpo passou no AUDIT nativo sem erros.

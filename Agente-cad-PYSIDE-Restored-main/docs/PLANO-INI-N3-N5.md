# iNi — plano de base inicial N3/N5

**Plano histórico da implementação inicial.** Para regras e estado atual consultar [PADRAO-INI-APROVADO.md](PADRAO-INI-APROVADO.md) e [PADROES-DESENHO-N3-N5.md](PADROES-DESENHO-N3-N5.md).

Autorização de Thierry em 07/10/2026: preparar, integrar e publicar a primeira base sem aguardar revisão intermediária. A qualidade visual será revisada pelo dono depois. Publicação não equivale a aprovação do design.

## Escopo e proteção

Quatro classes estruturais: pilares, laterais de viga, fundos de viga e lajes. Laterais Para e Passa têm configurações independentes; cada uma inclui sarrafeadas e gradeadas. Preservar NOVA/Formascia, fontes SA, originais DXF, JSONs Fase-4 e alterações locais de outros agentes. Não usar Git.

## Sequência de execução

1. Ler instruções e conhecimento canônico. Inventariar referências iNi, recortes, molduras e índices realmente cadastrados; registrar ausências sem inventar referências.
2. Comparar referência original, geração iNi atual e proposta em pastas separadas. Medir componentes, MLINE, cores efetivas, hachuras, textos, cotas, espaçamentos e encontros. Consultar legado apenas para regras necessárias.
3. Preparar exemplos reais derivados do SA: pilares cima/ABCD/grades, comuns e especiais; laterais Para/Passa com cortes e faces nas duas montagens; fundos com segmentos/recortes; lajes de dimensões diferentes. Manter versões anteriores.
4. Implementar regras dinâmicas por dimensão e contrato SA. Nas gradeadas, separar painéis sem grades e grades soltas, preservando cortes correspondentes. Identificar unidades para paginação sem sobreposição.
5. Rever configurações iNi das cinco entradas do portal: componentes, textos, hachuras, cotas, layers, disposição e detalhes especiais. Documentar exatamente o comportamento implementado e as convenções ainda propostas.
6. Integrar N3 com seleção explícita INI, cache por fingerprint e origem estrita. Nenhuma fonte NOVA/Formascia pode ser apresentada como iNi.
7. Integrar N5 com moldura/índice iNi disponíveis: paginação, numeração, escala, alinhamento e agrupamentos. Manter entidades individuais editáveis; não reduzir escala silenciosamente para esconder erro de encaixe.
8. Validar exemplos: conteúdo, limites, ausência de sobreposições, escalas, MLINE/hatch e auditoria DXF. Ler renders PNG; gerar SVG no portal. Testar isolamento dos outros modos e não certificar design humano.
9. Fazer deploy seletivo a partir dos arquivos atuais da VPS, com backups, conferindo jobs antes de reiniciar. Publicar uma rodada inicial útil do 13_PAV pelo caminho normal N3/N5, evitando repetições e versões desnecessárias.
10. Conferir artefatos efetivos e portal. Entregar links, imagens e relatório com três estados separados: experimento, integração e geração publicada. Deixar aprovação visual iNi pendente para Thierry.

## Critérios de revisão por classe

| Classe | Conteúdo a conferir |
|---|---|
| Pilares | Cima, ABCD e especiais, grades, sarrafos, parafusos, perfis, painelização/numeração, níveis, recortes, cotas e escala na folha |
| Laterais | Para/Passa × sarrafeadas/gradeadas; cortes completos, montagem coerente, parafusos por montagem, faces A/B, aberturas, divisões, grades soltas e paginação granular |
| Fundos | Vigas completas e segmentos, extremidades, recortes, chanfros, sarrafos, nomes, cotas e ocupação da folha |
| Lajes | Contornos, nomes e cotas, cores reais, diferenças de dimensão e agrupamento na folha |

## Estado inicial constatado

O perfil iNi de cores/MLINE já existe. A ligação granular das laterais no N5 está limitada a NOVA/Formascia. Há originais cadastrados para pilares, laterais Para gradeadas e fundos; moldura iNi em Pilares e índices em Pilares/Laterais Para. Ausências de referências para lajes e outras variantes precisam ser registradas e tratadas como proposta inicial, sem alegar comparação com original inexistente.

## Escala inicial de lajes

Sem referência iNi de lajes cadastrada, manter a planta coerente completa do SA com escala de papel declarada (1:50, 1:100 ou 1:200 conforme o envelope real), registrada na folha e no manifesto. A escolha é uma convenção inicial proposta para revisão, sem alterar dimensões físicas nem reduzir escala de forma oculta.

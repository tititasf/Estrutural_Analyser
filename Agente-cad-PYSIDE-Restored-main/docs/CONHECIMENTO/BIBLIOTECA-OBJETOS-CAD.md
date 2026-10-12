# Biblioteca de objetos CAD — lajes, visões de corte e chamadas

**Status:** canônico · **Data:** 2026-10-08 · **Escopo:** global, reconhecimento consultivo com prova local

Origem: comentários humanos 1–5 da obra Obra_TREINO_1, pavimento TIPO_TESTE, recorte EST-PE-007-TIPO-R01/torre_1. Evidência e reprodução: `scripts/arete/relatorios/20261008_lajes_cortes_callouts/RELATORIO.md`. Não pressupor que outras obras usem a mesma camada, cor ou desenho.

## Visão de corte composta junto a pilar

Peças fechadas ortogonais, inclusive retângulos e conjuntos em T, podem representar visão de corte. Reconhecer pelo CAD fonte e pela composição independente em `composite_cut_contours.partition_cut_contours`; contexto semântico de camada SECTION/CORTE/CUT/SECAO/LINHA-SE ajuda a excluir essas peças do recorte por pilar. Neste DXF a camada de seção contém caracteres danificados; LINHA-SE preserva a assinatura. Proximidade a P12/P13/P14/P15 não transforma a peça em pilar. Cor isolada não decide a classe.

Caso positivo: cortes gráficos nos contornos L13–L16. Contraprova: peças reais da camada PILLAR continuam sendo recortes, incluindo união em L/T. A classificação vem da fonte, antes da geometria SA; cooperação entre classes não multiplica evidência circular.

## Espessura h= com seta apontando para bloco

O líder explodido observado tem seis pontos; o ponto da ponta repete nas posições 2 e 4, com dois braços curtos e uma haste mais longa. Uma única seta compatível perto do texto permite localizar a referência na ponta, ligeiramente para o interior do alvo. Texto BL.1 próximo da origem da chamada prova contexto de bloco; essa espessura não entra nas sementes LAJ. No exemplo h=45 pertence ao bloco BL.1, enquanto h=12 pertence à região principal da laje recuperada L20 e h=10 à faixa listrada.

Contraprovas obrigatórias: polilinha simples de três pontos não é líder comprovado; líderes múltiplos próximos são ambíguos; texto h= sem referência continua no ponto original. A implementação não usa coordenadas específicas da obra: `src/core/cad_object_recognition.py::thickness_references`, consumida por `slab_tracer.py` e `slab_steps.py`.

## Hatch listrado e regiões de laje

Traços paralelos repetidos com delimitadores reais sinalizam região de atenção: degrau, nível ou espessura diferente. Separar espessura principal e interna. Hatch não prova altitude nem continuidade de fundo; sem prova adicional manter nível desconhecido. Cotas e strokes de hatch não são paredes estruturais. Vigas e pilares reais bloqueiam a região interna. Referência: `docs/SA-ANALISE/CLASSES/LAJ.md`.

## Inclusão de novos estilos

Registrar classe proposta, assinatura geométrica e semântica, origem DXF/recorte, SHA da fonte, apontamento humano, exemplos positivos e negativos, versão do reconhecedor e regressões. Indexar este conhecimento na KB global; recuperar via `scripts/kb/kb_query.py`. O índice é consultivo: não promove automaticamente hipóteses para selo humano, confirmação de nível ou RAG T1 por item. Estilos ainda não vistos permanecem pendentes de treino e validação. Esta biblioteca inicial não certifica reconhecimento universal.


## Pilar sólido recorrente, contornos especiais e círculo — 2026-10-08

Na Obra_TREINO_1/TIPO_TESTE, contornos cinza sólidos da camada MTH-PILAR-SEGUE coexistem com retângulos de viga e símbolos de corte próximos. O contorno mais próximo do nome pode ser de outra classe. Dimensões independentes junto ao nome e recorrência entre fontes dimensionadas sustentam a segunda passada; camada ou cor isolada não certificam pilar. Uma convenção minoritária continua candidata com sua própria evidência.

Casos positivos: P5/P6/P8/P11/P13/P14/P15/P16/P17 reassociados ao contorno fonte; P12 preserva U e vazio dos elevadores; P21 circular conserva centro e diâmetro. Contraprovas: peças MTH-FACE-VIGA e MTH-LINHA-SE não são pilares por proximidade; P14 possui dimensões de projeções diferentes, não converter ambas em uma seção única sem prova. Círculo inscrito em bloco não implica contato com viga.

Fonte DXF: EST-PE-007-TIPO-R01/torre_1, SHA256 `80b45ff3e024ebe037fe6e6e52829216120f006c55f6b60f79adb1df2dc65641`. Reconhecedor `pillar_geometry_association.py`; testes `test_pillar_geometry_association.py`; evidência no relatório `20261008_pilares_associacao`. Consultar o manual PIL para os limites atuais de N3/N5 circular. Não presumir reconhecimento universal de estilos ainda não observados.


### LV-VISAO-CORTE-NAO-SECCIONA-20261008

Visão de corte é anotação: seus traços transversais, diagonais, polilinhas e setas não delimitam banda nem seccionam lateral. Reconhecer a camada fonte antes de converter entidades em coordenadas sem semântica; excluir somente a entidade reconhecida, preservando linhas estruturais independentes mesmo quando coincidentes. Aplicar o mesmo filtro à leitura DXF de divisores usada pelo portal. Não mascarar uma região inteira em torno do símbolo: isso apagaria encontros reais de vigas/pilares.

Causa comprovada na Obra_TREINO_1/TIPO_TESTE: múltiplos divisores gráficos da visão de corte tornavam ambígua a busca e mantinham uma fronteira antiga. V501 tinha trecho falso de aproximadamente 102,44 cm. Depois do filtro, A Para/Passa passou de quatro para três segmentos; o encontro real com V523 foi preservado. Coordenadas observadas são evidência, nunca constantes do motor. Implementação: lv_beam_scene._line_segments/build_scene_runs e fv_inverted_crossings.structural_lines_from_dxf, com reconhecedor compartilhado cad_object_recognition.section_layer. Proveniência registra entidades_visao_corte_excluidas.

Contraprovas: divisor estrutural coincidente permanece; mudança real de altura permanece; polilinha fechada de corte não produz banda; orientações horizontal/vertical e translações têm regressão. Testes: test_lv_section_symbol_exclusion.py. Fonte torre_1.dxf SHA256 80b45ff3e024ebe037fe6e6e52829216120f006c55f6b60f79adb1df2dc65641. SA publicado em produção, recibo e comparação no relatório 20261008_lv_corte_seccionamento. Esta validação de interpretação não certifica N3/N5 nem estilos ainda não observados.

## ESTILO-INTEGRADO-20261008 — harmonização entre classes

Síntese vigente, convenções recorrentes, contraprovas e pendências: [Estilos estruturais — interpretação integrada](ESTILOS-ESTRUTURAIS-INTERPRETACAO-INTEGRADA.md). Não usar cortes gráficos como obstáculos físicos. A biblioteca registra assinaturas da fonte; o RAG não certifica estilos desconhecidos.

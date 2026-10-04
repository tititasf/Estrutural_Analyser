# Furações dos painéis N3 de pilares

Configuração por modo em Configuração de Modos → Pilares → Furações.
Ativação independente, seleção de faces A–H, diâmetro, afastamento da borda e
distribuições verticais separadas para A/B e C–H. Começa desativada.

O X é observado na geração atual da visão cima, antes da ampliação visual 2x.
No pilar comum, a face B espelha a face A. No L, os eixos são extraídos das
respectivas faixas A/B/E/F. Só recebem furos faces com parafusos efetivamente
emitidos pelo gerador e pontos contidos em material de painel. A seleção A–H
não inventa parafusos em faces sem eixos na visão cima atual.

Referência vertical: `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/
src_obfuscated/robots/Robo_Pilar_ABCD.py`, parâmetros `parafusos_ab` e
`parafusos_cdefgh`: primeiro furo a 30 cm, primeiro intervalo 50 cm, demais
55 cm. Os intervalos são cumulativos; após o décimo furo, repete-se o último.
A reserva superior de 25 cm é uma proteção configurável nova, não uma
transcrição da antiga fórmula de contagem. Recortes e aberturas são excluídos;
eixos externos ao painel não viram furações no vazio.

Implementação opcional: `scripts/pl_panel_drilling.py`, acionada pelo contexto
de configuração do motor. O gerador certificado permanece intacto. Círculos
DXF no layer `COTAS FURACAO`, com XData `PL_PANEL_DRILLING` (face, X, Y),
integrados à saída N3. Não modifica os DXFs fonte nem os exemplos enviados.

Validação 2026-10-03: testes de projeção, isolamento de modos, mudança dos
intervalos, limites e aberturas; exemplos P28 (8 furos) e P26 em L (116 furos)
sem erros de auditoria. P28 também gerado na VPS com configuração temporária,
sem ativar furações no perfil do usuário. Aba e salvamento conferidos no portal.
Evidências em `scripts/arete/relatorios/20261002_nova_design/preview_furacoes/`.

Apresentação conferida com o detalhe de furações do índice Nova enviado: círculo no diâmetro físico configurado e cruz amarela de 15 cm como símbolo visual. Cotas verticais partem da base e seguem os furos efetivamente emitidos; aberturas suprimidas entram como intervalo real. Cotas horizontais medem os eixos e ambas as bordas do painel em uma linha separada da cota total. Linhas ciano, textos vermelhos de altura 10 cm, afastados 2,5 cm da linha. A cadeia vertical usa a coluna com mais furos, evitando cadeias repetidas. Evidências atualizadas em `preview_furacoes_v2/`; originais enviados preservados.

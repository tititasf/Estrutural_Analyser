# STORY RAG-2.7 - Curadoria: Pipelines de Treino

## Objetivo
Adicionar uma sub-aba read-only na Curadoria para explicitar os ciclos de treino que levam uma classe ao estado ARETE:

- CROP: aprender a recortar melhor por classe.
- A: N2 -> N4, engenharia reversa e gerador reproduzem o STOG humano.
- B: N2 <-> N1, Structural Analyzer aprende a interpretar o estrutural limpo.
- C: N1 -> N3, producao sem gabarito convergindo para o N4 validado.
- Notas humanas: atencoes e decisoes entram como memoria auditavel, nao como verdade automatica.

## Escopo
- Arquivo: `src/ui/widgets/project_manager.py`
- Criar sub-aba `Pipelines de Treino` em Curadoria.
- Exibir metricas de docs Arete, scripts loopers, training_events, CROP-T1 e notas humanas.
- Exibir tabela de ciclos operacionais.
- Exibir tabela de cobertura por classe PIL/LV/FV/LAJ/Nova classe.

## Regras de Integridade
- A aba e observadora: nao treina, nao indexa, nao promove dado e nao altera banco.
- N3 nunca pode receber campos de N2/N4 como entrada.
- Recorte aprovado alimenta `crop_learning_events`, mas nao valida F5/N2 nem N4.
- Notas humanas so viram regra global depois de validacao/consenso.

## Gate
- Curadoria abre com a nova sub-aba.
- Metricas carregam sem erro mesmo se tabelas opcionais nao existirem.
- `python -m py_compile src/ui/widgets/project_manager.py` passa.


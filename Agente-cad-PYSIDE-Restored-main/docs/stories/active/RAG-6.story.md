# RAG-6 - Registro Declarativo de Classes

## Objetivo

Permitir novas classes estruturais sem hardcode na Curadoria ou no nucleo do RAG.

## Escopo

- `data/classe_registry.json` declara classes, aliases e as 8 dimensoes.
- `scripts/classe_registry.py` valida e carrega o registro.
- `docs/ENCICLOPEDIA-SCHEMA.md` define o procedimento de expansao.
- Curadoria usa o registro para normalizar classes e gerar pendencias.
- Categorias desconhecidas sao preservadas e exibidas como nao harmonizadas.

## Politica

- Alias ambiguo e proibido.
- `VIGA` nao vira LV ou FV automaticamente.
- Nova classe nao recebe conhecimento por heranca implicita.
- Registro nao promove, valida ou indexa fichas.

## Gate

- Registro possui exatamente as dimensoes 1..8.
- PIL/LV/FV/LAJ permanecem habilitadas.
- Alias duplicado falha explicitamente.
- Categoria desconhecida permanece visivel para decisao humana.

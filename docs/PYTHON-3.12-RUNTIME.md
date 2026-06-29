# Runtime Python do CAD-ANALYZER

## Regra obrigatoria

O CAD-ANALYZER suporta exclusivamente **Python 3.12.x**.

Python 3.13 e 3.14 nao devem ser usados. O ChromaDB depende de componentes
incompativeis com Python 3.14, e a aplicacao PySide6 possui historico de falhas
nativas nessa versao.

## Ambiente oficial

- Runtime: `D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe`
- Criacao: `py -3.12 -m venv D:\Agente-cad-PYSIDE\.venv`
- Configuracao completa: executar `Agente-cad-PYSIDE-Restored-main\install_all.ps1`
- Inicializacao da UI: executar `Agente-cad-PYSIDE-Restored-main\iniciar_dashboard.bat`

Nao execute a aplicacao com o comando global `python main.py`, pois o `python`
padrao do Windows pode apontar para outra versao.

## Verificacao

```powershell
D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe `
  D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\verify_python_runtime.py `
  --check-imports
```

O comando deve informar `Runtime OK` e Python `3.12.x`.

## Controles permanentes

- `.python-version` fixa `3.12` na raiz do workspace e da aplicacao.
- `pyproject.toml` aceita somente `>=3.12,<3.13`.
- VS Code aponta para o `.venv` oficial.
- `main.py` recusa qualquer runtime diferente de Python 3.12.
- Os launchers, instaladores e builds usam Python 3.12.
- `numpy<2.0` permanece fixado enquanto o ChromaDB legado exigir as APIs NumPy 1.x.
- Toda dependencia importada pela aplicacao deve constar em `requirements.txt`;
  o ambiente nao herda pacotes do Python global.

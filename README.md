# Estrutural Analyzer

Agente especializado em análise estrutural e geração de scripts CAD automatizados.

## 🚀 Como Iniciar

Para rodar a aplicação como usuário:

1. Baixe o executável `Estrutural_Analyzer_download_updater.exe` da pasta `dist/`.
2. Execute o instalador. Ele baixará a versão mais recente e criará um atalho na área de trabalho.

## 🛠️ Desenvolvimento

Este projeto utiliza:

- **Python 3.12**
- **PySide6** para Interface Gráfica
- **Supabase** para backend e distribuição de binários
- **PyInstaller** para geração de executáveis

### Documentação Técnica

- [Manual de Deploy e Distribuição](DEPLOYMENT.md): Detalhes sobre como gerar novas versões e enviar para a nuvem.

### Scripts Principais

- `main.py`: Ponto de entrada da aplicação principal.
- `src/updater.py`: Lógica do bootstrapper/atualizador gráfico.
- `scripts/`: Scripts de automação de build e deploy.

## 📦 Distribuição e Update

O sistema de atualização é baseado no `tufup` (The Update Framework), customizado para suportar downloads em partes no Supabase Storage. Isso garante que atualizações de arquivos grandes (como o binário principal) sejam resilientes a falhas de conexão.

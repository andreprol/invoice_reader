# Leitor de Notas Fiscais (NF-e / NFS-e)

Aplicação desktop em **Python + Tkinter** para ler PDFs de notas fiscais e gerar um Excel consolidado.

## Funcionalidades

- Seleção de pasta com PDFs
- Processamento de todas as notas da pasta
- Extração automática de:
  - Data (DD/MM/AAAA)
  - Fornecedor (emitente)
  - Valor total
- Suporte a PDFs com texto nativo **e PDFs escaneados (imagem)** via OCR automático
- Pré-visualização em tabela
- Exportação para Excel (`.xlsx`) com duas abas:
  - **Notas Fiscais**
  - **Consolidação** (fornecedor + mês/ano)
- Barra de progresso e mensagens de status
- Relatório de erros para notas que não puderem ser lidas

## Requisitos

- Python 3.10+
- Dependências em `requirements.txt`

## Instalação

```bash
pip install -r requirements.txt
```

## OCR para PDFs escaneados (Windows)

Além das bibliotecas Python, o OCR depende de programas externos:

1. **Instalar Tesseract OCR**
   - Baixe e instale: https://github.com/UB-Mannheim/tesseract/wiki
   - Durante a instalação, inclua o idioma **Português (`por`)**
   - Adicione a pasta do Tesseract ao `PATH` (ex.: `C:\Program Files\Tesseract-OCR`)

2. **Instalar Poppler (necessário para `pdf2image`)**
   - Baixe um build para Windows (Poppler)
   - Adicione a pasta `bin` do Poppler ao `PATH`

Sem Tesseract/Poppler no Windows, notas escaneadas não poderão ser lidas e o sistema exibirá mensagem de erro orientando a instalação.

## Como usar

### Opção 1 (Windows com duplo clique)

1. Dê duplo clique no arquivo `executar.bat` para abrir a aplicação.
2. (Opcional) Para abrir sem janela de terminal, dê duplo clique em `executar.vbs`.

### Opção 2 (terminal)

1. Execute a aplicação:
   ```bash
   python app.py
   ```
2. Clique em **Escolher Pasta** e selecione a pasta com os PDFs.
3. Clique em **Processar Notas**.
4. Confira os dados na tabela.
5. Clique em **Gerar Excel** para exportar o arquivo.
6. Se houver falhas de leitura, clique em **Ver Relatório de Erros**.

## Geração do executável Windows (.exe) com PyInstaller

> Importante: o PyInstaller gera executáveis por sistema operacional. Para obter um **.exe de Windows**, execute o build em um ambiente Windows.

### Arquivos de build adicionados

- `LeitorNotasFiscais.spec` (configuração personalizada do PyInstaller)
- `build_windows_exe.bat` (script automatizado para build no Windows)
- `assets/leitor_notas_fiscais.ico` (ícone do executável)
- `README_EXECUTAVEL.md` (guia para a pasta distribuível)

### Build automático (Windows)

No Prompt de Comando, dentro da pasta do projeto:

```bat
build_windows_exe.bat
```

### Build manual (Windows)

```bat
py -m pip install -r requirements.txt
py -m pip install pyinstaller
py -m PyInstaller --noconfirm LeitorNotasFiscais.spec
```

### Saída de distribuição

Após o build, a pasta final fica em:

```text
dist/LeitorNotasFiscais/
```

Distribua **a pasta inteira** `LeitorNotasFiscais` (não apenas o `.exe`), pois a pasta `_internal` contém dependências necessárias.

## Redistribuição

1. Gere o `.exe` em Windows com `build_windows_exe.bat`.
2. Copie a pasta `dist/LeitorNotasFiscais` para o computador de destino.
3. Execute `LeitorNotasFiscais.exe` com duplo clique.
4. Se houver aviso de SmartScreen, use assinatura digital de código para reduzir alertas (recomendado para distribuição externa).

## Teste rápido com amostras

Para testar com os PDFs de `/home/ubuntu/Uploads`:

```bash
python test_sample_pdfs.py
```

Esse script também gera um Excel de teste em:

`/home/ubuntu/leitor_notas_fiscais/saida_teste_notas.xlsx`

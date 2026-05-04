# Leitor de Notas Fiscais (NF-e / NFS-e)

Aplicação desktop em **Python + Tkinter** para ler PDFs de notas fiscais e gerar um Excel consolidado.

## Funcionalidades

- Seleção de pasta com PDFs
- Processamento de todas as notas da pasta
- Extração automática de:
  - Data (DD/MM/AAAA)
  - Fornecedor (emitente)
  - Valor total
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

## Teste rápido com amostras

Para testar com os PDFs de `/home/ubuntu/Uploads`:

```bash
python test_sample_pdfs.py
```

Esse script também gera um Excel de teste em:

`/home/ubuntu/leitor_notas_fiscais/saida_teste_notas.xlsx`

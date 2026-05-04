# LeitorNotasFiscais - Executável Windows

## Conteúdo da pasta de distribuição

Após o build com PyInstaller em **Windows**, a pasta `dist/LeitorNotasFiscais` conterá:

- `LeitorNotasFiscais.exe`
- Pasta `_internal` com dependências
- Este arquivo `README_EXECUTAVEL.md`

## Como executar

1. Copie a pasta inteira `LeitorNotasFiscais` para o computador de destino.
2. Abra `LeitorNotasFiscais.exe` com duplo clique.
3. Clique em **Escolher Pasta** para selecionar os PDFs.
4. Clique em **Processar Notas**.
5. Clique em **Gerar Excel** para exportar o relatório.

> Importante: no modo `--onedir`, mantenha `LeitorNotasFiscais.exe` junto da pasta `_internal`.

## Como gerar novamente o executável

No Windows (com Python instalado), dentro da pasta do projeto:

```bat
build_windows_exe.bat
```

Ou manualmente:

```bat
py -m pip install -r requirements.txt
py -m pip install pyinstaller
py -m PyInstaller --noconfirm LeitorNotasFiscais.spec
```

## Observações

- O executável gerado é standalone (não exige Python instalado na máquina destino).
- Para reduzir alertas do Windows SmartScreen, assine digitalmente o `.exe` (opcional, porém recomendado para distribuição externa).

# LeitorNotasFiscais - Executável Windows

## Conteúdo da pasta de distribuição

Após o build com PyInstaller em **Windows**, a pasta `dist/LeitorNotasFiscais` conterá:

- `LeitorNotasFiscais.exe` — Aplicativo principal
- `instalar_poppler.bat` — Instalador automático do Poppler (para PDFs escaneados)
- `instalar_tesseract.bat` — Instalador automático do Tesseract OCR
- Pasta `_internal` — Dependências do Python (NÃO apagar)
- Este arquivo `README_EXECUTAVEL.md`

## ⚡ Início Rápido

### Para PDFs com texto (maioria das notas):
1. Abra `LeitorNotasFiscais.exe`
2. Clique **Escolher Pasta** → selecione a pasta com os PDFs
3. Clique **Processar Notas**
4. Clique **Gerar Excel**

### Para PDFs escaneados (imagens):
Antes de usar o aplicativo, instale as ferramentas de OCR:

1. **Execute `instalar_tesseract.bat`** (clique duplo)
   - Siga o instalador
   - **IMPORTANTE:** Marque "Additional language data" → "Portuguese"
   
2. **Execute `instalar_poppler.bat`** (clique duplo)
   - Baixa e instala automaticamente

3. Agora abra `LeitorNotasFiscais.exe` normalmente

## Instalação Manual (se os scripts não funcionarem)

### Poppler (converte PDF em imagem):
1. Acesse: https://github.com/oschwartz10612/poppler-windows/releases
2. Baixe o arquivo `.zip` mais recente
3. Extraia o conteúdo
4. Coloque a pasta extraída em **uma** destas opções:
   - Dentro da pasta do aplicativo, renomeada como `poppler`
   - `C:\poppler\`
   - `C:\Program Files\poppler\`
5. O aplicativo detecta automaticamente!

### Tesseract OCR (lê texto em imagens):
1. Acesse: https://github.com/UB-Mannheim/tesseract/wiki
2. Baixe o instalador para Windows 64-bit
3. Instale normalmente
4. Na tela de componentes, marque "Portuguese" em "Additional language data"

## Como executar

1. Copie a pasta inteira `LeitorNotasFiscais` para o computador de destino.
2. Abra `LeitorNotasFiscais.exe` com duplo clique.
3. Clique em **Escolher Pasta** para selecionar os PDFs.
4. Clique em **Processar Notas**.
5. Clique em **Gerar Excel** para exportar o relatório.

> ⚠️ Importante: mantenha `LeitorNotasFiscais.exe` junto da pasta `_internal`. Não mova o .exe para fora.

## Solução de Problemas

| Erro | Solução |
|------|---------|
| "Failed to start embedded python interpreter" | Recompile com `build_windows_exe.bat` |
| "Poppler não está instalado" | Execute `instalar_poppler.bat` |
| "Tesseract OCR não encontrado" | Execute `instalar_tesseract.bat` |
| Windows SmartScreen bloqueia | Clique "Mais informações" → "Executar assim mesmo" |
| PDFs não são lidos | Verifique se são PDFs válidos (não corrompidos) |

## Como gerar novamente o executável

No Windows (com Python instalado), dentro da pasta do projeto:

```bat
build_windows_exe.bat
```

Ou manualmente:

```bat
py -m pip install -r requirements.txt
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean LeitorNotasFiscais.spec
```

## Observações

- O executável gerado é standalone (não exige Python instalado na máquina destino).
- Para PDFs com texto nativo, NÃO é necessário instalar Poppler nem Tesseract.
- O Poppler e Tesseract são necessários apenas para PDFs escaneados (baseados em imagem).
- Para reduzir alertas do Windows SmartScreen, assine digitalmente o `.exe` (opcional).
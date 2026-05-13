# Como Usar o Novo Ícone no Executável

## Arquivos Gerados

✅ **novo_icone.png** (218 KB) - Ícone em alta resolução 512x512 pixels com fundo transparente  
✅ **novo_icone.ico** (112 KB) - Ícone no formato Windows com múltiplos tamanhos (16, 32, 48, 64, 128, 256 pixels)

---

## Método 1: Substituir o Ícone Durante a Compilação (Recomendado)

Se você estiver usando **PyInstaller** para gerar o executável:

```bash
pyinstaller --onefile --windowed --icon=assets/novo_icone.ico --name="LeitorNotasFiscais" app.py
```

Se estiver usando o arquivo `.spec`:

```python
# Edite o arquivo LeitorNotasFiscais.spec
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LeitorNotasFiscais',
    icon='assets/novo_icone.ico',  # ← Adicione esta linha
    # ... resto das configurações
)
```

Depois recompile:
```bash
pyinstaller LeitorNotasFiscais.spec
```

---

## Método 2: Alterar o Ícone de um Executável Existente

Se o executável já estiver compilado, você pode usar o **Resource Hacker** (ferramenta gratuita):

1. **Download**: https://www.angusj.com/resourcehacker/
2. **Abrir** o executável (.exe) no Resource Hacker
3. **Action** → **Replace Icon** → Selecionar `novo_icone.ico`
4. **Salvar** o executável modificado

---

## Método 3: Atalho na Área de Trabalho

Se quiser apenas mudar o ícone do atalho:

1. Clique com o botão direito no atalho
2. **Propriedades** → **Alterar Ícone**
3. **Procurar** → Selecione `novo_icone.ico`
4. **OK** → **Aplicar**

---

## Características do Novo Ícone

- **Estilo**: Flat design moderno e profissional
- **Cores**: Azul (#1E88E5) e branco para o documento, amarelo/dourado (#FFC107) para a lupa
- **Design**: Documento de nota fiscal com lupa sobreposta
- **Formato**: PNG com transparência + ICO multi-tamanho
- **Otimização**: Legível em todos os tamanhos (16px até 512px)
- **Uso**: Desktop Windows, ideal para aplicações empresariais

---

**Localização dos arquivos:**
- PNG: `/home/ubuntu/leitor_notas_fiscais/assets/novo_icone.png`
- ICO: `/home/ubuntu/leitor_notas_fiscais/assets/novo_icone.ico`

"""
invoice_extractor.py — Leitor de Notas Fiscais
Versão: CHAMADA DIRETA (sem monkey-patching)

Abordagem: em vez de usar pytesseract.image_to_string() e pdf2image.convert_from_path(),
chama tesseract.exe e pdftoppm.exe DIRETAMENTE via subprocess.run() com flags
CREATE_NO_WINDOW e STARTUPINFO(SW_HIDE). Isso garante controle TOTAL sobre os
processos externos e ELIMINA qualquer janela de console no Windows.

As bibliotecas pytesseract e pdf2image NÃO são mais usadas para execução.
"""

import glob as _glob_mod
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, List, Optional, Tuple

import pdfplumber

# Compatibilidade: importar PIL para abrir imagens convertidas pelo Poppler
try:
    from PIL import Image
except ImportError:
    Image = None

# ---------------------------------------------------------------------------
# Constantes de plataforma
# ---------------------------------------------------------------------------
_WINDOWS = platform.system() == "Windows"
_CREATE_NO_WINDOW = 0x08000000 if _WINDOWS else 0


def _get_startupinfo():
    """Retorna STARTUPINFO com SW_HIDE para Windows, ou None."""
    if not _WINDOWS:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si


def _get_app_base_dir() -> str:
    """Retorna o diretório base da aplicação (funciona tanto em dev quanto em .exe)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Localização de executáveis: Poppler (pdftoppm) e Tesseract
# ---------------------------------------------------------------------------

def _find_poppler_path() -> Optional[str]:
    """Procura o Poppler em locais comuns do Windows e retorna o caminho da pasta bin."""
    # 1. Verifica se pdftoppm já está no PATH do sistema
    if shutil.which("pdftoppm"):
        return None  # Está no PATH, não precisa de caminho explícito

    # 2. Procura na pasta do aplicativo (bundled)
    app_dir = _get_app_base_dir()
    bundled_paths = [
        os.path.join(app_dir, "poppler", "Library", "bin"),
        os.path.join(app_dir, "poppler", "bin"),
        os.path.join(app_dir, "poppler-bin"),
        os.path.join(app_dir, "poppler"),
    ]

    # 3. Locais comuns de instalação no Windows
    common_paths = [
        r"C:\Program Files\poppler\Library\bin",
        r"C:\Program Files\poppler\bin",
        r"C:\Program Files (x86)\poppler\Library\bin",
        r"C:\Program Files (x86)\poppler\bin",
        r"C:\poppler\Library\bin",
        r"C:\poppler\bin",
        r"C:\tools\poppler\Library\bin",
        r"C:\tools\poppler\bin",
    ]

    # 4. Procura em pastas do usuário
    user_home = os.path.expanduser("~")
    user_paths = [
        os.path.join(user_home, "poppler", "Library", "bin"),
        os.path.join(user_home, "poppler", "bin"),
        os.path.join(user_home, "Downloads", "poppler", "Library", "bin"),
        os.path.join(user_home, "Downloads", "poppler", "bin"),
        os.path.join(user_home, "Desktop", "poppler", "Library", "bin"),
        os.path.join(user_home, "Desktop", "poppler", "bin"),
    ]

    # 5. Procura versões genéricas com glob-like
    glob_bases = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\tools",
        app_dir,
        user_home,
    ]

    all_paths = bundled_paths + common_paths + user_paths

    # Busca em pastas com nome poppler-*
    for base in glob_bases:
        if os.path.isdir(base):
            try:
                for entry in os.listdir(base):
                    if entry.lower().startswith("poppler"):
                        for sub in ["Library/bin", "bin", ""]:
                            candidate = os.path.join(base, entry, sub) if sub else os.path.join(base, entry)
                            all_paths.append(candidate)
            except OSError:
                pass

    # Verificar cada caminho candidato
    for path in all_paths:
        if os.path.isdir(path):
            pdftoppm_name = "pdftoppm.exe" if _WINDOWS else "pdftoppm"
            if os.path.isfile(os.path.join(path, pdftoppm_name)):
                return path

    return None


def _find_tesseract_cmd() -> Optional[str]:
    """Procura o executável do Tesseract e retorna o caminho completo."""
    # 1. Está no PATH?
    which = shutil.which("tesseract")
    if which:
        return which

    if not _WINDOWS:
        return None

    # 2. Locais comuns no Windows
    app_dir = _get_app_base_dir()
    candidates = [
        os.path.join(app_dir, "tesseract", "tesseract.exe"),
        os.path.join(app_dir, "Tesseract-OCR", "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe",
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Programs", "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Tesseract-OCR", "tesseract.exe"),
    ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


# ---------------------------------------------------------------------------
# CHAMADA DIRETA: Wrappers para tesseract.exe e pdftoppm.exe
# ---------------------------------------------------------------------------

def _run_subprocess_silent(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Executa um comando via subprocess.run com janela oculta no Windows."""
    extra = {}
    if _WINDOWS:
        extra["creationflags"] = _CREATE_NO_WINDOW
        extra["startupinfo"] = _get_startupinfo()
    extra.update(kwargs)
    return subprocess.run(cmd, **extra)


def _run_poppler_direct(pdf_path: str, dpi: int = 300) -> List[str]:
    """Converte PDF em imagens usando pdftoppm.exe DIRETAMENTE.

    Retorna lista de caminhos dos arquivos de imagem gerados.
    Lança RuntimeError se o Poppler não for encontrado.
    """
    poppler_dir = _find_poppler_path()

    # Determinar caminho do executável
    if poppler_dir:
        pdftoppm_exe = os.path.join(poppler_dir, "pdftoppm.exe" if _WINDOWS else "pdftoppm")
    else:
        pdftoppm_exe = shutil.which("pdftoppm")

    if not pdftoppm_exe or (not os.path.isfile(pdftoppm_exe) and not shutil.which("pdftoppm")):
        raise RuntimeError(
            "Não foi possível executar OCR porque o Poppler não está instalado.\n\n"
            "SOLUÇÃO RÁPIDA:\n"
            "1. Baixe o Poppler em: https://github.com/oschwartz10612/poppler-windows/releases\n"
            "2. Extraia o arquivo ZIP\n"
            "3. Copie a pasta extraída para uma das opções:\n"
            "   a) Pasta do aplicativo (crie pasta 'poppler' ao lado do .exe)\n"
            "   b) C:\\poppler\\\n"
            "   c) C:\\Program Files\\poppler\\\n"
            "4. Reinicie o aplicativo\n\n"
            "OU execute o script 'instalar_poppler.bat' que acompanha o aplicativo."
        )

    # Criar diretório temporário para as imagens
    tmp_dir = tempfile.mkdtemp(prefix="leitor_nf_ocr_")
    output_prefix = os.path.join(tmp_dir, "page")

    cmd = [
        pdftoppm_exe,
        "-r", str(dpi),
        "-png",
        pdf_path,
        output_prefix,
    ]

    try:
        result = _run_subprocess_silent(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Não foi possível executar OCR porque o Poppler não está instalado.\n\n"
            "SOLUÇÃO RÁPIDA:\n"
            "1. Baixe o Poppler em: https://github.com/oschwartz10612/poppler-windows/releases\n"
            "2. Extraia o arquivo ZIP\n"
            "3. Copie a pasta extraída para uma das opções:\n"
            "   a) Pasta do aplicativo (crie pasta 'poppler' ao lado do .exe)\n"
            "   b) C:\\poppler\\\n"
            "   c) C:\\Program Files\\poppler\\\n"
            "4. Reinicie o aplicativo"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Timeout ao converter PDF em imagem (>120s). O arquivo pode ser muito grande.")

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "Erro desconhecido"
        raise RuntimeError(f"Falha ao converter PDF em imagem: {stderr}")

    # Coletar arquivos de imagem gerados (padrão: page-01.png, page-02.png, ...)
    image_files = sorted(_glob_mod.glob(os.path.join(tmp_dir, "page-*.png")))

    if not image_files:
        # Tentar formato alternativo (page-1.png sem zero à esquerda)
        image_files = sorted(_glob_mod.glob(os.path.join(tmp_dir, "page*.png")))

    if not image_files:
        raise RuntimeError("Poppler não gerou nenhuma imagem. O PDF pode estar corrompido.")

    return image_files


def _run_tesseract_direct(image_path: str, lang: str = "por") -> str:
    """Executa OCR em uma imagem usando tesseract.exe DIRETAMENTE.

    Retorna o texto extraído.
    Lança RuntimeError se o Tesseract não for encontrado.
    """
    tesseract_cmd = _find_tesseract_cmd()

    if not tesseract_cmd:
        raise RuntimeError(
            "Tesseract OCR não encontrado.\n\n"
            "SOLUÇÃO:\n"
            "1. Baixe em: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "2. Instale normalmente (Next, Next, Finish)\n"
            "3. IMPORTANTE: Marque 'Additional language data' > 'Portuguese'\n"
            "4. Reinicie o aplicativo"
        )

    # Criar arquivo temporário para a saída do Tesseract
    # Tesseract adiciona .txt automaticamente ao output_base
    tmp_fd, tmp_output_base = tempfile.mkstemp(prefix="tess_out_")
    os.close(tmp_fd)
    # Remover o arquivo criado pelo mkstemp, pois tesseract vai criar output_base.txt
    os.unlink(tmp_output_base)

    output_txt_file = tmp_output_base + ".txt"

    cmd = [
        tesseract_cmd,
        image_path,
        tmp_output_base,  # Tesseract adiciona .txt automaticamente
        "-l", lang,
        "--psm", "6",
    ]

    try:
        result = _run_subprocess_silent(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Tesseract OCR não encontrado.\n\n"
            "SOLUÇÃO:\n"
            "1. Baixe em: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "2. Instale normalmente (Next, Next, Finish)\n"
            "3. IMPORTANTE: Marque 'Additional language data' > 'Portuguese'\n"
            "4. Reinicie o aplicativo"
        )
    except subprocess.TimeoutExpired:
        # Limpar arquivo de saída se existir
        if os.path.exists(output_txt_file):
            os.unlink(output_txt_file)
        raise RuntimeError("Timeout ao executar OCR (>60s). A imagem pode ser muito grande.")

    # Se falhou com idioma português, tentar com inglês como fallback
    if result.returncode != 0 and lang == "por":
        cmd_eng = [
            tesseract_cmd,
            image_path,
            tmp_output_base,
            "-l", "eng",
            "--psm", "6",
        ]
        try:
            result = _run_subprocess_silent(
                cmd_eng,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Ler resultado
    text = ""
    try:
        if os.path.exists(output_txt_file):
            with open(output_txt_file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
    finally:
        # Limpeza
        if os.path.exists(output_txt_file):
            try:
                os.unlink(output_txt_file)
            except OSError:
                pass

    return text


def _cleanup_temp_images(image_files: List[str]) -> None:
    """Remove arquivos temporários de imagem e seu diretório."""
    if not image_files:
        return
    for img_path in image_files:
        try:
            if os.path.exists(img_path):
                os.unlink(img_path)
        except OSError:
            pass
    # Tentar remover o diretório temporário
    try:
        tmp_dir = os.path.dirname(image_files[0])
        if tmp_dir and os.path.isdir(tmp_dir) and tmp_dir.startswith(tempfile.gettempdir()):
            os.rmdir(tmp_dir)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class InvoiceRecord:
    arquivo: str
    data: datetime
    fornecedor: str
    valor: Decimal
    tipo_documento: str


@dataclass
class InvoiceError:
    arquivo: str
    erro: str


# ---------------------------------------------------------------------------
# Regex patterns (mesma lógica comprovada)
# ---------------------------------------------------------------------------

OCR_TEXT_THRESHOLD = 50

RE_VALOR_NFE = re.compile(
    r"(?:V(?:ALOR|\.)?\s*TOTAL\s+DA\s+NOTA)[\s\S]{0,260}?R?\$?\s*([\d\.]+,\d{2})",
    re.IGNORECASE,
)
RE_VALOR_TOPO = re.compile(r"VALOR\s+TOTAL[:\s]*R\$?\s*([\d\.]+,\d{2})", re.IGNORECASE)
RE_VALOR_PRODUTOS = re.compile(
    r"(?:V(?:ALOR|\.)?\s*TOTAL\s+(?:DOS|DE)\s+PRODUTOS)[\s\S]{0,140}?([\d\.]+,\d{2})",
    re.IGNORECASE,
)
RE_VALOR_NFSE = re.compile(
    r"Valor(?:Líquido|Liquido|doServiço|doServico)[\s\S]{0,90}?R\$\s?([\d\.]+,\d{2})",
    re.IGNORECASE,
)

RE_DATA_EMISSAO_INLINE = re.compile(r"EMISS[ÃA]O[:\s]+(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
RE_DATA_NFE = re.compile(
    r"DATA\s+(?:DA\s+)?EMISS[ÃA]O[\s\S]{0,130}?(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
RE_DATA_NFSE = re.compile(
    r"DataeHoradaemiss[ãa]odaNFS-e[\s\S]{0,100}?(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
RE_ANY_DATE = re.compile(r"(\d{2}/\d{2}/\d{4})")

RE_FORNECEDOR_NFE = re.compile(
    r"RECEBEMOS\s+DE\s+(.+?)\s+OS\s+PRODUTOS",
    re.IGNORECASE | re.DOTALL,
)
RE_FORNECEDOR_RECEBEMOS_LOOSE = re.compile(
    r"RECEBEMOS\s+DE\s+(.+?)(?:\s+OS\s+PRODUTOS(?:\s+E\s+SERVI[ÇC]OS)?|\s+DATA\s+DE\s+RECEBIMENTO|\s+IDENTIFICA[ÇC][ÃA]O)",
    re.IGNORECASE | re.DOTALL,
)
RE_FORNECEDOR_LTDA_TOPO = re.compile(
    r"\n\s*([A-ZÀ-Ú][A-ZÀ-Ú0-9 .&\-/]{3,}?(?:LTDA|S\.?A\.?|EIRELI|ME|EPP|MEI)(?:\s+ME|\s+EPP)?)\s*\n",
    re.IGNORECASE,
)
RE_FORNECEDOR_DANFE_APOS = re.compile(
    r"DANFE\s+(.+?)\s+DOCUMENTO\s+AUXILIAR",
    re.IGNORECASE | re.DOTALL,
)
RE_FORNECEDOR_DANFE_ANTES = re.compile(
    r"DANFE\s+DOCUMENTO\s+AUXILIAR\s+(.+?)(?=\s+(?:DA\s+NOTA\s+FISCAL|CHAVE\s+DE\s+ACESSO|N[ºO]|S[ÉE]RIE|FOLHA|NATUREZA|CNPJ|0\s*-\s*ENTRADA)\b|\n)",
    re.IGNORECASE | re.DOTALL,
)
RE_FORNECEDOR_NFSE = re.compile(
    r"EMITENTEDANFS-e[\s\S]+?Nome/NomeEmpresarial[^\n]*\n([^\n]+)",
    re.IGNORECASE,
)
RE_FORNECEDOR_OCR_CABECALHO = re.compile(
    r"\n([A-ZÀ-Ú0-9 .&\-/]{5,}?)\s+DANF\s*E?\s+CONTROLE\s+DO\s+FISCO\s*\n([A-ZÀ-Ú0-9 .&\-/]{3,}?)\s*\nDOCUMENTO\s+AUXILIAR",
    re.IGNORECASE,
)
RE_FORNECEDOR_OCR_CABECALHO_V2 = re.compile(
    r"\n([A-ZÀ-Ú0-9 .&\-/]{5,}?)\s+DANFE\b[^\n]*\n([A-ZÀ-Ú0-9 .&\-/]{3,}?)\s*\nDOCUMENTO\s+AUXILIAR",
    re.IGNORECASE,
)
RE_FORNECEDOR_OCR_CABECALHO_V3 = re.compile(
    r"\n([A-ZÀ-Ú0-9 .&\-/]{5,}?)\s+DANF\s*E?\b[^\n]*\n([A-ZÀ-Ú0-9 .&\-/]{3,}?(?:LTDA|S\.?A\.?|EIRELI|ME|EPP))\s*\n",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class InvoiceExtractor:
    def __init__(self) -> None:
        self.errors: List[InvoiceError] = []

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip()

    @staticmethod
    def _normalize_text_nfse(text: str) -> str:
        return re.sub(r"(?<=[a-zà-ú])(?=[A-ZÀ-Ú])", " ", text)

    @staticmethod
    def _br_to_decimal(value: str) -> Decimal:
        cleaned = value.replace(".", "").replace(",", ".")
        try:
            return Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError(f"Valor inválido: {value}") from exc

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        try:
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError as exc:
            raise ValueError(f"Data inválida: {date_str}") from exc

    @staticmethod
    def _extract_text_from_pdf(path: str) -> str:
        pages: List[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages)

    @staticmethod
    def _is_text_sufficient(text: str) -> bool:
        return len(text.strip()) >= OCR_TEXT_THRESHOLD

    @staticmethod
    def _extract_text_from_pdf_ocr(path: str) -> str:
        """Extrai texto via OCR usando chamadas DIRETAS a pdftoppm e tesseract.

        NÃO usa pytesseract.image_to_string() nem pdf2image.convert_from_path().
        Chama os executáveis diretamente via subprocess.run() com CREATE_NO_WINDOW.
        """
        image_files = []
        try:
            # Passo 1: Converter PDF em imagens com pdftoppm (chamada direta)
            image_files = _run_poppler_direct(path, dpi=300)

            # Passo 2: Executar OCR em cada imagem com tesseract (chamada direta)
            pages_text: List[str] = []
            for img_path in image_files:
                text = _run_tesseract_direct(img_path, lang="por")
                pages_text.append(text)

            return "\n".join(pages_text)

        finally:
            # Passo 3: Limpeza de arquivos temporários (SEMPRE executa)
            _cleanup_temp_images(image_files)

    def _extract_text_with_fallback(self, path: str) -> str:
        native_text = self._extract_text_from_pdf(path)
        if self._is_text_sufficient(native_text):
            return native_text

        ocr_text = self._extract_text_from_pdf_ocr(path)
        if self._is_text_sufficient(ocr_text):
            return ocr_text

        return native_text

    @staticmethod
    def _detect_document_type(text: str) -> str:
        marker = text.lower()
        if "danfse" in marker or "nfs-e" in marker:
            return "NFS-e"
        return "NF-e"

    def _extract_valor_nfe(self, text: str) -> Optional[Decimal]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for idx, line in enumerate(lines):
            normalized = re.sub(r"[^A-Z]", "", line.upper())
            if "VALORTOTAL" in normalized or "VTOTAL" in normalized:
                candidate_lines = []
                for i in range(idx + 1, min(idx + 6, len(lines))):
                    candidate_lines.append(lines[i])

                joined = " ".join(candidate_lines)
                values = re.findall(r"([\d\.]+,\d{2})", joined)
                if values:
                    parsed = [self._br_to_decimal(v) for v in values]
                    positives = [p for p in parsed if p > Decimal("0.01")]
                    if positives:
                        return max(positives)
                    return max(parsed, default=None) if parsed else None

        for pattern in (RE_VALOR_TOPO, RE_VALOR_NFE, RE_VALOR_PRODUTOS):
            m = pattern.search(text)
            if m:
                value = self._br_to_decimal(m.group(1))
                if value > Decimal("0"):
                    return value

        block = re.search(
            r"VALOR\s+TOTAL\s+DA\s+NOTA[\s\S]{0,180}",
            text,
            flags=re.IGNORECASE,
        )
        if block:
            values = re.findall(r"R\$\s?([\d\.]+,\d{2})", block.group(0), flags=re.IGNORECASE)
            if values:
                parsed = [self._br_to_decimal(v) for v in values]
                positives = [p for p in parsed if p > Decimal("0")]
                return positives[-1] if positives else parsed[-1]

        return None

    def _extract_valor_nfse(self, text_original: str, text_nfse: str) -> Optional[Decimal]:
        for source in (text_original, text_nfse):
            m = RE_VALOR_NFSE.search(source)
            if m:
                value = self._br_to_decimal(m.group(1))
                if value > Decimal("0"):
                    return value

        candidates = re.findall(r"R\$\s?([\d\.]+,\d{2})", text_original, flags=re.IGNORECASE)
        if candidates:
            return max((self._br_to_decimal(c) for c in candidates), default=None)
        return None

    @staticmethod
    def _clean_supplier(text: str) -> str:
        supplier = text.strip(" -:\n\t")
        supplier = re.sub(r"[\w\.-]+@[\w\.-]+", "", supplier)
        supplier = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", supplier)
        supplier = re.sub(r"\s+", " ", supplier)
        supplier = re.sub(r"\s+OS\s+PRODUTOS.*$", "", supplier, flags=re.IGNORECASE)
        supplier = re.sub(r"\bDANF\s*E?\s+CONTROLE\s+DO\s+FISCO\b.*$", "", supplier, flags=re.IGNORECASE)
        supplier = re.sub(r"\bDOCUMENTO\s+AUXILIAR\b.*$", "", supplier, flags=re.IGNORECASE)
        supplier = re.sub(r"\bDA\s+NOTA\s+FISCAL\b.*$", "", supplier, flags=re.IGNORECASE)
        return supplier.strip(" -:\n\t")

    @staticmethod
    def _try_merge_previous_line(text: str, match_obj, candidate: str) -> str:
        suffix_keywords = ("SERVICO", "SERVICOS", "SERVIÇO", "SERVIÇOS",
                           "TECNOLOGIA", "INFORMATICA", "COMERCIO", "COMÉRCIO",
                           "ACESSORIOS", "DISTRIBUICAO", "AUTOMACAO")
        first_word = candidate.split()[0].upper() if candidate else ""
        if not any(first_word.startswith(kw) for kw in suffix_keywords):
            return candidate

        start_pos = match_obj.start()
        text_before = text[:start_pos]
        lines_before = [ln.strip() for ln in text_before.splitlines() if ln.strip()]
        if not lines_before:
            return candidate

        prev_line = lines_before[-1]
        prev_clean = re.sub(
            r"\b(?:DANF\s*E?|CONTROLE\s+DO\s+FISCO|NF-?e|S[ée]rie\s*\d*|DATA\s+DE\s+RECEBIMENTO"
            r"|IDENTIFICA[ÇC][ÃA]O|ASSINATURA|RECEBEDOR)\b.*$",
            "", prev_line, flags=re.IGNORECASE
        ).strip(" -:\n\t")

        if prev_clean and len(prev_clean) >= 3 and re.match(r"[A-ZÀ-Ú0-9]", prev_clean):
            merged = f"{prev_clean} {candidate}"
            return merged

        return candidate

    def _extract_supplier_nfe(self, text: str) -> Optional[str]:
        m = RE_FORNECEDOR_NFE.search(text)
        if m:
            supplier = self._clean_supplier(m.group(1))
            if supplier and len(supplier) > 3:
                return supplier

        m = RE_FORNECEDOR_RECEBEMOS_LOOSE.search(text)
        if m:
            supplier = self._clean_supplier(m.group(1))
            if supplier and len(supplier) > 3:
                return supplier

        for pattern in (RE_FORNECEDOR_OCR_CABECALHO, RE_FORNECEDOR_OCR_CABECALHO_V2, RE_FORNECEDOR_OCR_CABECALHO_V3):
            m = pattern.search("\n" + text + "\n")
            if m:
                supplier = self._clean_supplier(f"{m.group(1)} {m.group(2)}")
                if supplier and len(supplier) > 5:
                    return supplier

        for pattern in (RE_FORNECEDOR_DANFE_APOS, RE_FORNECEDOR_DANFE_ANTES):
            m = pattern.search(text)
            if m:
                supplier = self._clean_supplier(m.group(1))
                if supplier and len(supplier) > 5:
                    return supplier

        topo = text[:1500]
        m = RE_FORNECEDOR_LTDA_TOPO.search("\n" + topo + "\n")
        if m:
            candidate = self._clean_supplier(m.group(1))
            if candidate and len(candidate) > 5 and "RECEBEMOS" not in candidate.upper():
                candidate = self._try_merge_previous_line("\n" + topo + "\n", m, candidate)
                return candidate

        emitente_block = re.search(
            r"IDENTIFICA[ÇC][ÃA]O\s+DO\s+EMITENTE[\s\S]{0,600}?DANFE[\s\S]{0,300}",
            text,
            flags=re.IGNORECASE,
        )
        if emitente_block:
            lines = [ln.strip() for ln in emitente_block.group(0).splitlines() if ln.strip()]
            for line in lines:
                if any(token in line.upper() for token in ("DANFE", "DOCUMENTO", "IDENTIFICAÇÃO")):
                    continue
                if "CNPJ" in line.upper() or "CPF" in line.upper():
                    continue
                if len(line) > 5:
                    supplier = self._clean_supplier(line)
                    if supplier:
                        return supplier

        return None

    def _extract_supplier_nfse(self, text_original: str, text_nfse: str) -> Optional[str]:
        for source in (text_original, text_nfse):
            m = RE_FORNECEDOR_NFSE.search(source)
            if m:
                return self._clean_supplier(m.group(1))

        for source in (text_original, text_nfse):
            m = re.search(r"Nome/Nome\s*Empresarial[^\n]*\n([^\n]+)", source, flags=re.IGNORECASE)
            if m:
                return self._clean_supplier(m.group(1))

        return None

    def _extract_date_nfe(self, text: str) -> Optional[datetime]:
        for pattern in (RE_DATA_EMISSAO_INLINE, RE_DATA_NFE):
            m = pattern.search(text)
            if m:
                return self._parse_date(m.group(1))

        fallback = RE_ANY_DATE.search(text)
        if fallback:
            return self._parse_date(fallback.group(1))
        return None

    def _extract_date_nfse(self, text_original: str, text_nfse: str) -> Optional[datetime]:
        for source in (text_original, text_nfse):
            m = RE_DATA_NFSE.search(source)
            if m:
                return self._parse_date(m.group(1))

        for source in (text_original, text_nfse):
            m = RE_ANY_DATE.search(source)
            if m:
                return self._parse_date(m.group(1))
        return None

    def extract_from_file(self, file_path: str) -> InvoiceRecord:
        raw_text = self._extract_text_with_fallback(file_path)
        text = self._normalize_text(raw_text)
        doc_type = self._detect_document_type(text)

        if doc_type == "NFS-e":
            text_nfse = self._normalize_text_nfse(text)
            supplier = self._extract_supplier_nfse(text, text_nfse)
            date = self._extract_date_nfse(text, text_nfse)
            value = self._extract_valor_nfse(text, text_nfse)
        else:
            supplier = self._extract_supplier_nfe(text)
            date = self._extract_date_nfe(text)
            value = self._extract_valor_nfe(text)

        missing = []
        if not date:
            missing.append("data")
        if not supplier:
            missing.append("fornecedor")
        if not value:
            missing.append("valor")

        if missing:
            raise ValueError(f"Campos não encontrados: {', '.join(missing)}")

        return InvoiceRecord(
            arquivo=os.path.basename(file_path),
            data=date,
            fornecedor=supplier,
            valor=value,
            tipo_documento=doc_type,
        )

    def extract_from_folder(
        self,
        folder_path: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Tuple[List[InvoiceRecord], List[InvoiceError]]:
        self.errors = []
        records: List[InvoiceRecord] = []

        pdf_files = sorted(
            os.path.join(folder_path, name)
            for name in os.listdir(folder_path)
            if name.lower().endswith(".pdf")
        )

        total = len(pdf_files)
        for idx, file_path in enumerate(pdf_files, start=1):
            file_name = os.path.basename(file_path)
            try:
                record = self.extract_from_file(file_path)
                records.append(record)
                msg = f"Lido com sucesso: {file_name}"
            except Exception as exc:  # noqa: BLE001
                self.errors.append(InvoiceError(arquivo=file_name, erro=str(exc)))
                msg = f"Erro ao ler {file_name}: {exc}"

            if progress_callback:
                progress_callback(idx, total, msg)

        return records, self.errors

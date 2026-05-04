import os
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, List, Optional, Tuple

import pdfplumber


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


RE_VALOR_NFE = re.compile(
    r"V\s*ALOR\s+TOTAL\s+DA\s+NOTA[\s\S]{0,220}?R?\$?\s*([\d\.]+,\d{2})",
    re.IGNORECASE,
)
RE_VALOR_TOPO = re.compile(r"VALOR\s+TOTAL[:\s]*R\$?\s*([\d\.]+,\d{2})", re.IGNORECASE)
RE_VALOR_PRODUTOS = re.compile(
    r"VALOR\s+TOTAL\s+DOS\s+PRODUTOS[\s\S]{0,120}?([\d\.]+,\d{2})",
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
        # Ajuda com termos colados (mantém versão original para regex específicas)
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
    def _detect_document_type(text: str) -> str:
        marker = text.lower()
        if "danfse" in marker or "nfs-e" in marker:
            return "NFS-e"
        return "NF-e"

    def _extract_valor_nfe(self, text: str) -> Optional[Decimal]:
        # Estratégia 1: usar linha após o rótulo "VALOR TOTAL DA NOTA" e pegar último valor
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for idx, line in enumerate(lines):
            normalized = re.sub(r"\s+", "", line).upper()
            if "VALORTOTALDANOTA" in normalized:
                candidate_lines = []
                if idx + 1 < len(lines):
                    candidate_lines.append(lines[idx + 1])
                if idx + 2 < len(lines):
                    candidate_lines.append(lines[idx + 2])

                joined = " ".join(candidate_lines)
                values = re.findall(r"([\d\.]+,\d{2})", joined)
                if values:
                    # Em DANFE normalmente o valor total da nota é o último da linha
                    parsed = [self._br_to_decimal(v) for v in values]
                    positives = [p for p in parsed if p > Decimal("0")]
                    if positives:
                        return positives[-1]
                    return parsed[-1]

        # Estratégia 2: regexs de fallback
        for pattern in (RE_VALOR_TOPO, RE_VALOR_NFE, RE_VALOR_PRODUTOS):
            m = pattern.search(text)
            if m:
                value = self._br_to_decimal(m.group(1))
                if value > Decimal("0"):
                    return value

        # Estratégia 3: último valor monetário de bloco próximo ao rótulo
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

        # Fallback genérico para NFS-e
        candidates = re.findall(r"R\$\s?([\d\.]+,\d{2})", text_original, flags=re.IGNORECASE)
        if candidates:
            return max((self._br_to_decimal(c) for c in candidates), default=None)
        return None

    @staticmethod
    def _clean_supplier(text: str) -> str:
        supplier = text.strip(" -:\n\t")
        supplier = re.sub(r"[\w\.-]+@[\w\.-]+", "", supplier)  # remove e-mail
        supplier = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", supplier)  # separa nome de CPF/CNPJ colado
        supplier = re.sub(r"\s+", " ", supplier)
        supplier = re.sub(r"\s+OS\s+PRODUTOS.*$", "", supplier, flags=re.IGNORECASE)
        supplier = re.sub(r"\bDOCUMENTO\s+AUXILIAR\b.*$", "", supplier, flags=re.IGNORECASE)
        supplier = re.sub(r"\bDA\s+NOTA\s+FISCAL\b.*$", "", supplier, flags=re.IGNORECASE)
        return supplier.strip(" -:\n\t")

    def _extract_supplier_nfe(self, text: str) -> Optional[str]:
        m = RE_FORNECEDOR_NFE.search(text)
        if m:
            supplier = self._clean_supplier(m.group(1))
            if supplier:
                return supplier

        # Fallback 1: cabeçalho DANFE com emitente antes de "DOCUMENTO AUXILIAR"
        for pattern in (RE_FORNECEDOR_DANFE_APOS, RE_FORNECEDOR_DANFE_ANTES):
            m = pattern.search(text)
            if m:
                supplier = self._clean_supplier(m.group(1))
                if supplier and len(supplier) > 5:
                    return supplier

        # Fallback 2: bloco após IDENTIFICAÇÃO DO EMITENTE / DANFE
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

        # Fallback: linha logo após Nome/NomeEmpresarial
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

        # Fallback: primeira data válida
        for source in (text_original, text_nfse):
            m = RE_ANY_DATE.search(source)
            if m:
                return self._parse_date(m.group(1))
        return None

    def extract_from_file(self, file_path: str) -> InvoiceRecord:
        raw_text = self._extract_text_from_pdf(file_path)
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

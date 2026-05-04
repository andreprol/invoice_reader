from pathlib import Path

from excel_exporter import export_to_excel
from invoice_extractor import InvoiceExtractor


if __name__ == "__main__":
    sample_folder = Path("/home/ubuntu/Uploads")
    out_file = Path("/home/ubuntu/leitor_notas_fiscais/saida_teste_notas.xlsx")

    extractor = InvoiceExtractor()
    records, errors = extractor.extract_from_folder(str(sample_folder))

    print(f"PDFs processados com sucesso: {len(records)}")
    print(f"PDFs com erro: {len(errors)}")

    for rec in sorted(records, key=lambda r: r.data):
        print(f"{rec.arquivo} | {rec.data.strftime('%d/%m/%Y')} | {rec.fornecedor} | {rec.valor}")

    if errors:
        print("\nErros encontrados:")
        for err in errors:
            print(f"- {err.arquivo}: {err.erro}")

    if records:
        export_to_excel(records, str(out_file))
        print(f"\nExcel de teste gerado em: {out_file}")

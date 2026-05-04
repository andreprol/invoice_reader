import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from excel_exporter import export_to_excel
from invoice_extractor import InvoiceError, InvoiceExtractor, InvoiceRecord


class InvoiceReaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Leitor de Notas Fiscais")
        self.root.geometry("920x620")

        self.extractor = InvoiceExtractor()
        self.records: list[InvoiceRecord] = []
        self.errors: list[InvoiceError] = []
        self.selected_folder: str = ""

        self.ui_queue: queue.Queue = queue.Queue()
        self.processing = False

        self._build_ui()
        self._poll_ui_queue()

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self.root, padding=12)
        top_frame.pack(fill="x")

        ttk.Button(top_frame, text="Escolher Pasta", command=self.choose_folder).pack(side="left")

        self.folder_var = tk.StringVar(value="Nenhuma pasta selecionada")
        ttk.Label(top_frame, textvariable=self.folder_var).pack(side="left", padx=10)

        action_frame = ttk.Frame(self.root, padding=(12, 0))
        action_frame.pack(fill="x")

        self.btn_process = ttk.Button(action_frame, text="Processar Notas", command=self.start_processing)
        self.btn_process.pack(side="left")

        self.btn_export = ttk.Button(action_frame, text="Gerar Excel", command=self.generate_excel, state="disabled")
        self.btn_export.pack(side="left", padx=8)

        self.btn_errors = ttk.Button(action_frame, text="Ver Relatório de Erros", command=self.show_errors, state="disabled")
        self.btn_errors.pack(side="left")

        table_frame = ttk.Frame(self.root, padding=12)
        table_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("data", "fornecedor", "valor"),
            show="headings",
            height=18,
        )
        self.tree.heading("data", text="Data")
        self.tree.heading("fornecedor", text="Fornecedor")
        self.tree.heading("valor", text="Valor")
        self.tree.column("data", width=110, anchor="center")
        self.tree.column("fornecedor", width=560, anchor="w")
        self.tree.column("valor", width=170, anchor="e")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.pack(fill="x")

        self.progress = ttk.Progressbar(footer, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=(0, 8))

        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(footer, textvariable=self.status_var).pack(anchor="w")

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta com PDFs")
        if not selected:
            return
        self.selected_folder = selected
        self.folder_var.set(selected)
        self.status_var.set("Pasta selecionada. Clique em 'Processar Notas'.")

    def _set_processing_state(self, is_processing: bool) -> None:
        self.processing = is_processing
        self.btn_process.config(state="disabled" if is_processing else "normal")
        self.btn_export.config(state="disabled" if is_processing or not self.records else "normal")

    def start_processing(self) -> None:
        if self.processing:
            return

        if not self.selected_folder:
            messagebox.showwarning("Atenção", "Selecione uma pasta antes de processar.")
            return

        if not os.path.isdir(self.selected_folder):
            messagebox.showerror("Erro", "A pasta selecionada não existe.")
            return

        pdf_files = [f for f in os.listdir(self.selected_folder) if f.lower().endswith(".pdf")]
        if not pdf_files:
            messagebox.showwarning("Atenção", "A pasta selecionada não contém arquivos PDF.")
            return

        self.records = []
        self.errors = []
        self.btn_errors.config(state="disabled")

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.progress["value"] = 0
        self.progress["maximum"] = len(pdf_files)
        self.status_var.set("Iniciando processamento...")
        self._set_processing_state(True)

        worker = threading.Thread(target=self._process_worker, daemon=True)
        worker.start()

    def _process_worker(self) -> None:
        def progress_callback(current: int, total: int, msg: str) -> None:
            self.ui_queue.put(("progress", current, total, msg))

        records, errors = self.extractor.extract_from_folder(self.selected_folder, progress_callback)
        self.ui_queue.put(("done", records, errors))

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                event = self.ui_queue.get_nowait()
                self._handle_ui_event(event)
        except queue.Empty:
            pass

        self.root.after(100, self._poll_ui_queue)

    def _handle_ui_event(self, event) -> None:
        event_type = event[0]

        if event_type == "progress":
            current, total, msg = event[1], event[2], event[3]
            self.progress["maximum"] = total
            self.progress["value"] = current
            self.status_var.set(f"[{current}/{total}] {msg}")
            return

        if event_type == "done":
            records: list[InvoiceRecord] = event[1]
            errors: list[InvoiceError] = event[2]

            self.records = sorted(records, key=lambda r: r.data)
            self.errors = errors

            for record in self.records:
                data_str = record.data.strftime("%d/%m/%Y")
                valor_str = f"R$ {record.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                self.tree.insert("", "end", values=(data_str, record.fornecedor, valor_str))

            self._set_processing_state(False)

            if self.errors:
                self.btn_errors.config(state="normal")

            ok_msg = f"Concluído: {len(self.records)} nota(s) lida(s) com sucesso"
            if self.errors:
                ok_msg += f" e {len(self.errors)} com erro."
            else:
                ok_msg += "."

            self.status_var.set(ok_msg)
            messagebox.showinfo("Processamento finalizado", ok_msg)

    def generate_excel(self) -> None:
        if not self.records:
            messagebox.showwarning("Atenção", "Não há dados para exportar.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"notas_fiscais_{timestamp}.xlsx"

        output = filedialog.asksaveasfilename(
            title="Salvar Excel",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Arquivo Excel", "*.xlsx")],
        )
        if not output:
            return

        try:
            export_to_excel(self.records, output)
            msg = f"Excel gerado com sucesso em:\n{output}"
            if self.errors:
                msg += "\n\nHá notas com erro. Use o botão 'Ver Relatório de Erros'."
            self.status_var.set("Excel gerado com sucesso.")
            messagebox.showinfo("Sucesso", msg)
        except Exception as exc:  # noqa: BLE001
            self.status_var.set("Erro ao gerar Excel.")
            messagebox.showerror("Erro", f"Falha ao gerar Excel:\n{exc}")

    def show_errors(self) -> None:
        if not self.errors:
            messagebox.showinfo("Relatório de erros", "Não há erros registrados.")
            return

        lines = ["Notas com erro de leitura:\n"]
        for err in self.errors:
            lines.append(f"- {err.arquivo}: {err.erro}")

        messagebox.showwarning("Relatório de erros", "\n".join(lines))


if __name__ == "__main__":
    root = tk.Tk()
    app = InvoiceReaderApp(root)
    root.mainloop()

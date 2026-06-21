"""
review_screen_ui.py

The final safety checkpoint before anything is pushed to Tally. Shows
the assembled voucher clearly, checks for duplicate pushes, and only
pushes on explicit user confirmation. Every outcome (pushed or not) is
recorded via invoice_record_store for a durable audit trail.
"""

import customtkinter as ctk
from datetime import datetime, timezone

from invoice_text_extractor import extract_text_from_pdf
from voucher_assembler import assemble_purchase_voucher, AssemblyError
from tally_bridge import push_voucher
from invoice_record_store import (
    InvoiceRecord, make_record_id, save_record, check_duplicate,
)


class ReviewScreen(ctk.CTk):
    def __init__(self, company_name: str, vendor_key: str, pdf_path: str, on_edit_template=None):
        super().__init__()
        self.title("Review Before Push")
        self.geometry("520x720")

        self.company_name = company_name
        self.vendor_key = vendor_key
        self.pdf_path = pdf_path
        self.voucher = None
        self.on_edit_template = on_edit_template

        ctk.CTkLabel(
            self, text="Review Voucher", font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(20, 10))

        self.status_label = ctk.CTkLabel(self, text="Processing invoice...", text_color="gray")
        self.status_label.pack(pady=(0, 5))

        if self.on_edit_template:
            edit_button = ctk.CTkButton(
                self, text="\u270e Edit Template for this Vendor", width=220,
                fg_color="transparent", border_width=1,
                command=self._on_edit_template_clicked,
            )
            edit_button.pack(pady=(0, 10))

        self.details_frame = ctk.CTkScrollableFrame(self, width=460, height=320)
        self.details_frame.pack(pady=5, padx=20, fill="x")

        self.warning_label = ctk.CTkLabel(self, text="", text_color="orange", wraplength=460)
        self.warning_label.pack(pady=(10, 5))

        self.force_push_checkbox_var = ctk.BooleanVar(value=False)
        self.force_push_checkbox = ctk.CTkCheckBox(
            self, text="Push anyway (this looks like a duplicate)",
            variable=self.force_push_checkbox_var,
        )
        # Only shown/packed when a duplicate is actually detected.

        self.push_button = ctk.CTkButton(
            self, text="Push to Tally", command=self._on_push, state="disabled",
        )
        self.push_button.pack(pady=(10, 10))

        self.result_label = ctk.CTkLabel(self, text="", wraplength=460)
        self.result_label.pack(pady=(0, 15))

        self.after(100, self._process_invoice)

    def _process_invoice(self):
        extraction_result = extract_text_from_pdf(self.pdf_path)
        if not extraction_result.success or not extraction_result.pages:
            self.status_label.configure(
                text=f"Extraction failed: {extraction_result.error_message}", text_color="red",
            )
            return

        try:
            self.voucher = assemble_purchase_voucher(
                self.company_name, self.vendor_key, extraction_result.pages[0],
            )
        except AssemblyError as e:
            self.status_label.configure(text=f"Could not assemble voucher: {e}", text_color="red")
            return

        self.status_label.configure(text="Ready for review", text_color="gray")
        self._render_voucher_details()
        self._check_for_duplicate()
        self.push_button.configure(state="normal")
        
    def _on_edit_template_clicked(self):
        if self.on_edit_template:
            self.destroy()
            self.on_edit_template()
            
    def _render_voucher_details(self):
        v = self.voucher

        def add_row(label, value):
            row = ctk.CTkFrame(self.details_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, width=140, anchor="w", text_color="gray").pack(side="left")
            ctk.CTkLabel(row, text=str(value), anchor="w").pack(side="left")

        add_row("Company:", v.company_name)
        add_row("Voucher type:", v.voucher_type)
        add_row("Date:", v.voucher_date_yyyymmdd)
        add_row("Party:", v.party_ledger_name)
        add_row("Narration:", v.narration)

        ctk.CTkLabel(
            self.details_frame, text="\nLedger entries:", anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).pack(fill="x", pady=(10, 5))

        for line in v.lines:
            side = "Dr" if line.is_debit else "Cr"
            row = ctk.CTkFrame(self.details_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=side, width=30, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=line.ledger_name, width=220, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"{line.amount:,.2f}", anchor="e").pack(side="left")

        total_dr = sum(l.amount for l in v.lines if l.is_debit)
        total_cr = sum(l.amount for l in v.lines if not l.is_debit)
        balance_note = "Balanced \u2713" if total_dr == total_cr else "NOT BALANCED \u2717"
        balance_color = "green" if total_dr == total_cr else "red"
        ctk.CTkLabel(
            self.details_frame, text=f"\nDr {total_dr:,.2f}  /  Cr {total_cr:,.2f}   {balance_note}",
            text_color=balance_color, font=ctk.CTkFont(weight="bold"),
        ).pack(fill="x", pady=(5, 0))

    def _check_for_duplicate(self):
        invoice_number = self.voucher.field_raw_text.get("Invoice Number", "").strip()
        if not invoice_number:
            self.warning_label.configure(
                text="\u26a0 No invoice number was captured \u2014 duplicate check cannot run reliably.",
            )
            return

        existing = check_duplicate(self.company_name, self.vendor_key, invoice_number)
        if existing:
            self.warning_label.configure(
                text=f"\u26a0 This invoice (No. {invoice_number}) appears to have already been "
                     f"pushed successfully on {existing.pushed_at_utc}. Check the tick box below "
                     "to push again anyway."
            )
            self.force_push_checkbox.pack(pady=(0, 5))

    def _on_push(self):
        invoice_number = self.voucher.field_raw_text.get("Invoice Number", "").strip()

        existing = check_duplicate(self.company_name, self.vendor_key, invoice_number) if invoice_number else None
        if existing and not self.force_push_checkbox_var.get():
            self.result_label.configure(
                text="Push blocked \u2014 tick the box above to confirm pushing this duplicate anyway.",
                text_color="orange",
            )
            return

        v = self.voucher
        push_result = push_voucher(
            company_name=v.company_name,
            voucher_type=v.voucher_type,
            voucher_date_yyyymmdd=v.voucher_date_yyyymmdd,
            party_ledger_name=v.party_ledger_name,
            lines=v.lines,
            narration=v.narration,
        )

        record_id = make_record_id(self.company_name, self.vendor_key, invoice_number or "unknown")
        record = InvoiceRecord(
            record_id=record_id,
            company_name=self.company_name,
            vendor_key=self.vendor_key,
            invoice_number=invoice_number or "unknown",
            voucher_date_yyyymmdd=v.voucher_date_yyyymmdd,
            party_ledger_name=v.party_ledger_name,
            narration=v.narration,
            lines=[{"ledger_name": l.ledger_name, "amount": l.amount, "is_debit": l.is_debit} for l in v.lines],
            field_raw_text=v.field_raw_text,
            extracted_at_utc=datetime.now(timezone.utc).isoformat(),
            push_status="pushed_success" if push_result.success else "pushed_failed",
            pushed_at_utc=datetime.now(timezone.utc).isoformat(),
            tally_response_summary=(
                f"Created: {push_result.created_count}" if push_result.success
                else push_result.error_message
            ),
        )
        save_record(record)

        if push_result.success:
            self.result_label.configure(text="\u2713 Pushed to Tally successfully.", text_color="green")
            self.push_button.configure(state="disabled")
        else:
            self.result_label.configure(text=f"\u2717 Push failed: {push_result.error_message}", text_color="red")


if __name__ == "__main__":
    app = ReviewScreen(company_name="Test1", vendor_key="Sharma Traders", pdf_path="sample_data/inv1.pdf")
    app.mainloop()
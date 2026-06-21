"""
review_screen_ui.py

The final safety checkpoint before anything is pushed to Tally. Shows
the assembled voucher clearly, checks for duplicate pushes, and only
pushes on explicit user confirmation. Every outcome (pushed or not) is
recorded via invoice_record_store for a durable audit trail.
"""
from tally_bridge import push_voucher, LedgerLine
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
        self.geometry("520x780")

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
        from app import load_invoice_page_and_image
        page_data, _, _ = load_invoice_page_and_image(self.pdf_path)
        if page_data is None:
            self.status_label.configure(text="Could not extract invoice data.", text_color="red")
            return

        try:
            self.voucher = assemble_purchase_voucher(
                self.company_name, self.vendor_key, page_data,
            )
        except AssemblyError as e:
            self.status_label.configure(text=f"Could not assemble voucher: {e}", text_color="red")
            return
        except Exception as e:
            self.status_label.configure(text=f"Unexpected error: {e}", text_color="red")
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

        # Editable fields. We keep references to each Entry widget so we
        # can read back the (possibly corrected) values at push time.
        self.date_entry = None
        self.narration_entry = None
        self.line_entries: list[tuple[ctk.CTkEntry, bool, str]] = []  # (entry, is_debit, ledger_name)

        def add_label_row(label, value):
            row = ctk.CTkFrame(self.details_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, width=140, anchor="w", text_color="gray").pack(side="left")
            ctk.CTkLabel(row, text=str(value), anchor="w").pack(side="left")

        def add_editable_row(label, initial_value):
            row = ctk.CTkFrame(self.details_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, width=140, anchor="w", text_color="gray").pack(side="left")
            entry = ctk.CTkEntry(row, width=200)
            entry.insert(0, str(initial_value))
            entry.pack(side="left")
            return entry

        add_label_row("Company:", v.company_name)
        add_label_row("Voucher type:", v.voucher_type)
        self.date_entry = add_editable_row("Date (YYYYMMDD):", v.voucher_date_yyyymmdd)
        add_label_row("Party:", v.party_ledger_name)
        self.narration_entry = add_editable_row("Narration:", v.narration)

        ctk.CTkLabel(
            self.details_frame, text="\nLedger entries (amounts editable):", anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).pack(fill="x", pady=(10, 5))

        for line in v.lines:
            side = "Dr" if line.is_debit else "Cr"
            row = ctk.CTkFrame(self.details_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=side, width=30, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=line.ledger_name, width=200, anchor="w").pack(side="left")
            amount_entry = ctk.CTkEntry(row, width=100)
            amount_entry.insert(0, f"{line.amount:.2f}")
            amount_entry.pack(side="left")
            amount_entry.bind("<KeyRelease>", lambda e: self._update_balance_preview())
            self.line_entries.append((amount_entry, line.is_debit, line.ledger_name))

        self.balance_preview_label = ctk.CTkLabel(
            self.details_frame, text="", font=ctk.CTkFont(weight="bold"),
        )
        self.balance_preview_label.pack(fill="x", pady=(10, 0))
        self._update_balance_preview()

        ctk.CTkLabel(
            self.details_frame,
            text="\nOriginal captured text (for reference):",
            anchor="w", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray",
        ).pack(fill="x", pady=(15, 2))
        for field_name, raw_text in v.field_raw_text.items():
            ctk.CTkLabel(
                self.details_frame, text=f"{field_name}: '{raw_text}'",
                anchor="w", font=ctk.CTkFont(size=11), text_color="gray",
            ).pack(fill="x")

    def _get_current_amounts(self) -> list[float]:
        amounts = []
        for entry, _, _ in self.line_entries:
            try:
                amounts.append(float(entry.get().strip()))
            except ValueError:
                amounts.append(0.0)
        return amounts

    def _update_balance_preview(self):
        total_dr = sum(
            amt for amt, (_, is_debit, _) in zip(self._get_current_amounts(), self.line_entries)
            if is_debit
        )
        total_cr = sum(
            amt for amt, (_, is_debit, _) in zip(self._get_current_amounts(), self.line_entries)
            if not is_debit
        )
        balanced = abs(total_dr - total_cr) < 0.01  # tolerate tiny float rounding
        note = "Balanced \u2713" if balanced else "NOT BALANCED \u2717"
        color = "green" if balanced else "red"
        self.balance_preview_label.configure(
            text=f"Dr {total_dr:,.2f}  /  Cr {total_cr:,.2f}   {note}", text_color=color,
        )

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

        # Read back the (possibly user-corrected) values from the form,
        # rather than the originally-assembled voucher object.
        edited_date = self.date_entry.get().strip()
        edited_narration = self.narration_entry.get().strip()

        edited_lines = []
        for entry, is_debit, ledger_name in self.line_entries:
            try:
                amount = float(entry.get().strip())
            except ValueError:
                self.result_label.configure(
                    text=f"Invalid amount for '{ledger_name}' \u2014 push cancelled.", text_color="red",
                )
                return
            edited_lines.append(LedgerLine(ledger_name=ledger_name, amount=amount, is_debit=is_debit))

        total_dr = sum(l.amount for l in edited_lines if l.is_debit)
        total_cr = sum(l.amount for l in edited_lines if not l.is_debit)
        if abs(total_dr - total_cr) >= 0.01:
            self.result_label.configure(
                text="Voucher does not balance \u2014 fix the amounts before pushing.", text_color="red",
            )
            return

        push_result = push_voucher(
            company_name=self.company_name,
            voucher_type=self.voucher.voucher_type,
            voucher_date_yyyymmdd=edited_date,
            party_ledger_name=self.voucher.party_ledger_name,
            lines=edited_lines,
            narration=edited_narration,
        )

        record_id = make_record_id(self.company_name, self.vendor_key, invoice_number or "unknown")
        record = InvoiceRecord(
            record_id=record_id,
            company_name=self.company_name,
            vendor_key=self.vendor_key,
            invoice_number=invoice_number or "unknown",
            voucher_date_yyyymmdd=edited_date,
            party_ledger_name=self.voucher.party_ledger_name,
            narration=edited_narration,
            lines=[{"ledger_name": l.ledger_name, "amount": l.amount, "is_debit": l.is_debit} for l in edited_lines],
            field_raw_text=self.voucher.field_raw_text,
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
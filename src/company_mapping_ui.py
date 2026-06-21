"""
company_mapping_ui.py

One-time (per company) setup screen: maps each fixed tax/purchase field
(Taxable Value, CGST Amount, SGST Amount, IGST Amount) to a real Tally
ledger. Unlike vendor templates, this is set once and reused across
every vendor and every invoice for this company.

Reuses the same searchable-ledger-list pattern as vendor_picker_ui.py
for picking each ledger.
"""

import customtkinter as ctk

from tally_bridge import get_ledger_names
from company_ledger_mapping_store import (
    MAPPABLE_FIELDS,
    save_company_mapping,
    load_company_mapping,
    is_mapping_complete,
)


class LedgerSearchPopup(ctk.CTkToplevel):
    """
    A small popup for searching/picking one ledger. Used inline within
    the company mapping screen, rather than as a separate top-level flow
    like the vendor picker — this keeps it lightweight since it's just
    picking one value, not driving the whole app forward.
    """

    def __init__(self, parent, all_ledgers: list[str], on_picked):
        super().__init__(parent)
        self.title("Select Ledger")
        self.geometry("350x420")
        self.on_picked = on_picked
        self.all_ledgers = all_ledgers

        self.search_entry = ctk.CTkEntry(self, placeholder_text="Search ledgers...", width=300)
        self.search_entry.pack(pady=10)
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)

        self.results_frame = ctk.CTkScrollableFrame(self, width=300, height=320)
        self.results_frame.pack(pady=5, fill="x")

        self._render_results(self.all_ledgers)

        # Grab focus so the user interacts with this popup before the
        # main window underneath it.
        self.grab_set()

    def _render_results(self, ledger_names: list[str]):
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        for name in ledger_names:
            btn = ctk.CTkButton(
                self.results_frame, text=name, anchor="w",
                fg_color="transparent", command=lambda n=name: self._pick(n),
            )
            btn.pack(fill="x", pady=2)

    def _on_search_changed(self, event):
        query = self.search_entry.get().strip().lower()
        filtered = [n for n in self.all_ledgers if query in n.lower()] if query else self.all_ledgers
        self._render_results(filtered)

    def _pick(self, ledger_name: str):
        self.on_picked(ledger_name)
        self.destroy()


class CompanyMappingScreen(ctk.CTk):
    def __init__(self, company_name: str):
        super().__init__()
        self.title(f"Configure Ledger Mapping - {company_name}")
        self.geometry("450x420")
        self.company_name = company_name

        self.all_ledgers: list[str] = []
        self.field_to_ledger: dict[str, str] = load_company_mapping(company_name) or {}
        self.field_value_labels: dict[str, ctk.CTkLabel] = {}

        ctk.CTkLabel(
            self, text=f"Tax/Purchase Ledger Mapping for '{company_name}'",
            font=ctk.CTkFont(size=15, weight="bold"), wraplength=400,
        ).pack(pady=(20, 5))

        self.status_label = ctk.CTkLabel(self, text="Loading ledgers from Tally...", text_color="gray")
        self.status_label.pack(pady=(0, 15))

        self.fields_frame = ctk.CTkFrame(self)
        self.fields_frame.pack(pady=5, padx=20, fill="x")

        for field_name in MAPPABLE_FIELDS:
            row = ctk.CTkFrame(self.fields_frame, fg_color="transparent")
            row.pack(fill="x", pady=6)

            ctk.CTkLabel(row, text=field_name, width=140, anchor="w").pack(side="left")

            current_value = self.field_to_ledger.get(field_name, "(not set)")
            value_label = ctk.CTkLabel(
                row, text=current_value, width=140, anchor="w",
                text_color="white" if field_name in self.field_to_ledger else "gray",
            )
            value_label.pack(side="left", padx=5)
            self.field_value_labels[field_name] = value_label

            ctk.CTkButton(
                row, text="Choose...", width=80,
                command=lambda f=field_name: self._open_picker(f),
            ).pack(side="left")

        self.completeness_label = ctk.CTkLabel(self, text="", text_color="orange")
        self.completeness_label.pack(pady=(15, 5))

        self.save_button = ctk.CTkButton(self, text="Save Mapping", command=self._on_save)
        self.save_button.pack(pady=10)

        self.after(100, self._load_ledgers)
        self._refresh_completeness()

    def _load_ledgers(self):
        result = get_ledger_names(self.company_name)
        if not result.success:
            self.status_label.configure(
                text=f"Could not load ledgers: {result.error_message}", text_color="red",
            )
            return
        self.all_ledgers = sorted(result.ledger_names)
        self.status_label.configure(
            text=f"{len(self.all_ledgers)} ledgers available from '{self.company_name}'",
            text_color="gray",
        )

    def _open_picker(self, field_name: str):
        if not self.all_ledgers:
            self.status_label.configure(text="Ledgers not loaded yet, please wait...", text_color="orange")
            return

        def on_picked(ledger_name: str):
            self.field_to_ledger[field_name] = ledger_name
            self.field_value_labels[field_name].configure(text=ledger_name, text_color="white")
            self._refresh_completeness()

        LedgerSearchPopup(self, self.all_ledgers, on_picked)

    def _refresh_completeness(self):
        missing = [f for f in MAPPABLE_FIELDS if f not in self.field_to_ledger]
        if missing:
            self.completeness_label.configure(
                text=f"Still need: {', '.join(missing)}", text_color="orange",
            )
        else:
            self.completeness_label.configure(text="All fields mapped \u2713", text_color="green")

    def _on_save(self):
        save_company_mapping(self.company_name, self.field_to_ledger)
        if is_mapping_complete(self.company_name):
            self.status_label.configure(text="Saved \u2014 mapping is complete.", text_color="green")
        else:
            self.status_label.configure(text="Saved, but mapping is still incomplete.", text_color="orange")


if __name__ == "__main__":
    COMPANY_NAME = "Test1"
    app = CompanyMappingScreen(COMPANY_NAME)
    app.mainloop()
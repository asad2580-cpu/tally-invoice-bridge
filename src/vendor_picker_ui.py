"""
vendor_picker_ui.py

Lets the user pick which vendor (Tally ledger) this invoice belongs to,
searched from the REAL list of ledgers in their Tally company — not
just vendors we've previously built a box-template for. This keeps the
picker consistent with the app's core "no autocreation, must exist in
Tally" rule: a vendor can only be selected if their ledger already
exists in Tally.

Defaults to whichever vendor was used last (if it's still a valid
ledger), to minimize clicks when processing a batch from one vendor.

Once a vendor is selected, the caller should check
vendor_template_store.load_template(vendor_key) to know whether a
saved box-layout already exists (repeat vendor) or the user needs to
start with a blank box-labeling screen (first invoice from this vendor).
"""

import customtkinter as ctk

from tally_bridge import get_ledger_names
from last_used_vendor_store import get_last_used_vendor, set_last_used_vendor


class VendorPickerScreen(ctk.CTk):
    def __init__(self, company_name: str, on_vendor_selected):
        """
        on_vendor_selected: callback called with the chosen vendor_key
        (a real Tally ledger name) once the user confirms.
        """
        super().__init__()
        self.title("Select Vendor")
        self.geometry("420x420")
        self.company_name = company_name
        self.on_vendor_selected = on_vendor_selected

        ctk.CTkLabel(
            self, text="Which vendor is this invoice from?",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(20, 5))

        self.status_label = ctk.CTkLabel(self, text="Loading ledgers from Tally...", text_color="gray")
        self.status_label.pack(pady=(0, 10))

        self.search_entry = ctk.CTkEntry(self, placeholder_text="Search ledgers...", width=350)
        self.search_entry.pack(pady=5)
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)

        self.results_frame = ctk.CTkScrollableFrame(self, width=350, height=220)
        self.results_frame.pack(pady=10, fill="both", expand=True)

        self.selected_vendor: str | None = None
        self.all_ledgers: list[str] = []
        self.result_buttons: list[ctk.CTkButton] = []

        self.selected_label = ctk.CTkLabel(self, text="Selected: (none)", text_color="gray")
        self.selected_label.pack(pady=(5, 5))

        self.confirm_button = ctk.CTkButton(
            self, text="Confirm", command=self._on_confirm, width=350, state="disabled",
        )
        self.confirm_button.pack(pady=(5, 15))

        # Fetch the ledger list right away, on screen load.
        self.after(100, self._load_ledgers)

    def _load_ledgers(self):
        result = get_ledger_names(self.company_name)
        if not result.success:
            self.status_label.configure(
                text=f"Could not load ledgers: {result.error_message}", text_color="red",
            )
            return

        self.all_ledgers = sorted(result.ledger_names)
        self.status_label.configure(
            text=f"{len(self.all_ledgers)} ledgers loaded from '{self.company_name}'",
            text_color="gray",
        )
        self._render_results(self.all_ledgers)

        # Pre-select last-used vendor if it's still a valid ledger.
        last_used = get_last_used_vendor()
        if last_used and last_used in self.all_ledgers:
            self._select_vendor(last_used)

    def _render_results(self, ledger_names: list[str]):
        for btn in self.result_buttons:
            btn.destroy()
        self.result_buttons.clear()

        for name in ledger_names:
            btn = ctk.CTkButton(
                self.results_frame, text=name, anchor="w",
                fg_color="transparent", command=lambda n=name: self._select_vendor(n),
            )
            btn.pack(fill="x", pady=2)
            self.result_buttons.append(btn)

    def _on_search_changed(self, event):
        query = self.search_entry.get().strip().lower()
        if not query:
            filtered = self.all_ledgers
        else:
            filtered = [n for n in self.all_ledgers if query in n.lower()]
        self._render_results(filtered)

    def _select_vendor(self, vendor_name: str):
        self.selected_vendor = vendor_name
        self.selected_label.configure(text=f"Selected: {vendor_name}", text_color="white")
        self.confirm_button.configure(state="normal")

    def _on_confirm(self):
        if not self.selected_vendor:
            return
        set_last_used_vendor(self.selected_vendor)
        self.destroy()
        self.on_vendor_selected(self.selected_vendor)


if __name__ == "__main__":
    COMPANY_NAME = "Test1"  # placeholder until company-selection step is built

    def handle_selection(vendor_key: str):
        print(f"Vendor selected: {vendor_key}")

    app = VendorPickerScreen(company_name=COMPANY_NAME, on_vendor_selected=handle_selection)
    app.mainloop()
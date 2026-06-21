"""
company_picker_ui.py

Shown at app startup: fetches companies currently open in Tally and
lets the user pick which one to work with. If exactly one company is
open, it's auto-selected with no picker shown at all — no ambiguity,
no extra click needed.

Replaces manual company-name text entry, which was prone to typos and
gave no feedback until a downstream Tally call failed.
"""

import customtkinter as ctk

from tally_bridge import get_open_company_names


def pick_company_name() -> str | None:
    """
    Blocks until the user picks a company (or the only open one is
    auto-selected). Returns the company name, or None if the user
    cancelled or no companies are open.
    """
    result = get_open_company_names()

    if not result.success:
        print("Could not fetch open companies:", result.error_message)
        return None

    if len(result.ledger_names) == 1:
        # Only one company open \u2014 no ambiguity, skip the picker.
        return result.ledger_names[0]

    picked = {"value": None}

    app = ctk.CTk()
    app.title("Select Company")
    app.geometry("420x420")

    ctk.CTkLabel(
        app, text="Multiple companies are open in Tally.\nWhich one should this session use?",
        font=ctk.CTkFont(size=14, weight="bold"), wraplength=380,
    ).pack(pady=(20, 10))

    search_entry = ctk.CTkEntry(app, placeholder_text="Search companies...", width=350)
    search_entry.pack(pady=5)

    results_frame = ctk.CTkScrollableFrame(app, width=350, height=200)
    results_frame.pack(pady=10, fill="x")

    selected_label = ctk.CTkLabel(app, text="Selected: (none)", text_color="gray")
    selected_label.pack(pady=5)

    confirm_button = ctk.CTkButton(app, text="Confirm", width=350, state="disabled")
    confirm_button.pack(pady=10)

    def render_results(names):
        for widget in results_frame.winfo_children():
            widget.destroy()
        for name in names:
            btn = ctk.CTkButton(
                results_frame, text=name, anchor="w", fg_color="transparent",
                command=lambda n=name: select(n),
            )
            btn.pack(fill="x", pady=2)

    def select(name):
        picked["value"] = name
        selected_label.configure(text=f"Selected: {name}", text_color="white")
        confirm_button.configure(state="normal")

    def on_search(event):
        query = search_entry.get().strip().lower()
        filtered = [n for n in result.ledger_names if query in n.lower()] if query else result.ledger_names
        render_results(filtered)

    def on_confirm():
        app.destroy()

    search_entry.bind("<KeyRelease>", on_search)
    confirm_button.configure(command=on_confirm)

    render_results(result.ledger_names)
    app.mainloop()

    return picked["value"]
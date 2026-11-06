"""New / Edit / Delete / Export buttons above a table (used by Applications, Mentor Interview, Interviews).

The buttons are added by code, so they look and behave the same in code mode and in .ui mode.

    New     every signed-in user
    Edit    administrators only, needs a selected row
    Delete  administrators only, needs a selected row (asks first)
    Export  every signed-in user (saves the rows on screen as a CSV file)
"""
import csv

from PyQt6.QtWidgets import QHBoxLayout, QPushButton

from database import DatabaseError, ValidationError
from pages.base_page import RECORD_ID_ROLE


class RecordActionsMixin:
    def setup_record_actions(self, table, noun, on_new, on_edit, on_delete, export_name):
        """Add the button row above ``table``. ``noun`` is e.g. "application" (for the button text).
        Call this after ``add_detail_panel(table)`` and before ``decorate()`` gives the buttons their icons."""
        self.record_table = table
        self.record_noun = noun
        self.record_handlers = (on_new, on_edit, on_delete)
        self.export_name = export_name

        self.btnNew = QPushButton(f"New {noun}")
        self.btnEdit = QPushButton("Edit")
        self.btnDelete = QPushButton("Delete")
        self.btnDelete.setObjectName("btnDelete")
        self.btnExport = QPushButton("Export CSV")
        self.btnNew.clicked.connect(lambda *_: self.record_handlers[0]())
        self.btnEdit.clicked.connect(lambda *_: self.record_handlers[1]())
        self.btnDelete.clicked.connect(lambda *_: self.record_handlers[2]())
        self.btnExport.clicked.connect(lambda *_: self.export_csv())

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        for button in (self.btnExport, self.btnEdit, self.btnDelete, self.btnNew):
            row.addWidget(button)
        holder = table.parentWidget()               # the splitter that add_detail_panel created
        layout = holder.parentWidget().layout()
        layout.insertLayout(layout.indexOf(holder), row)

        table.itemSelectionChanged.connect(self.update_record_buttons)
        self.update_record_buttons()

    # ----- state ---------------------------------------------------------------------------

    def selected_record_id(self):
        """Database id of the selected row, or None (nothing selected, or a row that is not one record)."""
        row = self.record_table.currentRow()
        item = self.record_table.item(row, 0) if row >= 0 else None
        return item.data(RECORD_ID_ROLE) if item is not None else None

    def update_record_buttons(self, *_):
        selected = self.selected_record_id() is not None
        allowed = self.is_admin and selected
        for button in (self.btnEdit, self.btnDelete):
            button.setEnabled(allowed)
        if not self.is_admin:
            reason = "Only administrators can change or delete records."
        elif not selected:
            reason = "Select a row in the table first."
        else:
            reason = ""
        self.btnEdit.setToolTip(reason or f"Change the selected {self.record_noun}")
        self.btnDelete.setToolTip(reason or f"Delete the selected {self.record_noun}")
        self.btnNew.setToolTip(f"Add a new {self.record_noun}")
        self.btnExport.setToolTip("Save the rows shown in the table as a CSV file")

    def on_role_changed(self):
        self.update_record_buttons()

    # ----- shared steps --------------------------------------------------------------------

    def open_form(self, dialog):
        """Show a form; True when the user saved it."""
        self.run_dialog(dialog)
        return dialog.saved

    def load_for_edit(self, loader):
        """Run ``loader(selected id)``; shows a message and returns None when the record is gone."""
        record_id = self.selected_record_id()
        if record_id is None:
            self.show_message("Select a row in the table first.")
            return None, None
        try:
            values = loader(record_id)
        except DatabaseError as error:
            self.show_message(str(error))
            return None, None
        if values is None:
            self.show_message("This record no longer exists. Refresh the list.")
            return None, None
        return record_id, values

    def delete_selected(self, description, deleter):
        """Ask, then run ``deleter(id)``. Returns True when something was deleted."""
        record_id = self.selected_record_id()
        if record_id is None:
            self.show_message("Select a row in the table first.")
            return False
        if not self.ask_confirm(f"Delete {self.record_noun}", f"Delete {description}?\nThis cannot be undone."):
            self.show_message("Delete cancelled.")
            return False
        try:
            person_removed = deleter(record_id)
        except (ValidationError, DatabaseError) as error:
            self.show_message(str(error))
            return False
        self.show_message(f"The {self.record_noun} was deleted"
                          + (" (the candidate had no other records and was removed too)." if person_removed else "."))
        return True

    def select_record(self, record_id):
        """Select the row of a record (after adding or editing it) so the user sees it."""
        table = self.record_table
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.data(RECORD_ID_ROLE) == record_id:
                table.selectRow(row)
                table.scrollToItem(item)
                return

    def selected_row_text(self, column=0):
        item = self.record_table.item(self.record_table.currentRow(), column)
        return item.text() if item else ""

    # ----- export --------------------------------------------------------------------------

    def export_csv(self):
        """Write the rows on screen to a CSV file (semicolon separated, UTF-8 with BOM: opens in Excel)."""
        table = self.record_table
        if table.rowCount() == 0:
            self.show_message("Nothing to export: the table is empty.")
            return None
        path = self.ask_save_path(self.export_name)
        if not path:
            self.show_message("Export cancelled.")
            return None
        headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(headers)
                for r in range(table.rowCount()):
                    writer.writerow([table.item(r, c).text() if table.item(r, c) else ""
                                     for c in range(table.columnCount())])
        except OSError as error:
            self.show_message(f"The file could not be saved: {error}")
            return None
        self.show_message(f"{table.rowCount()} row(s) exported to {path}")
        return path

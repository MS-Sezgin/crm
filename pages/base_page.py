"""Shared base class for all windows (code mode and .ui mode)."""
import html
import os

from PyQt6 import uic
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QPushButton, QSplitter, QTableWidgetItem, QTextEdit,
                             QVBoxLayout, QWidget)

import icons
from styles import build_stylesheet

from paths import resource_dir

UI_DIR = os.path.join(resource_dir(), "ui")
LOGO_PATH = os.path.join(resource_dir(), "assets", "wearhere_logo.png")


MIN_COLUMN, MAX_COLUMN = 110, 320


def fit_columns(table):
    """Size every column to its content, but never narrower than MIN_COLUMN or wider than MAX_COLUMN."""
    table.resizeColumnsToContents()
    for c in range(table.columnCount()):
        table.setColumnWidth(c, max(MIN_COLUMN, min(table.columnWidth(c) + 16, MAX_COLUMN)))


def fill_table(table, headers, rows):
    """Replace the table content with the given headers and rows."""
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(value))
    fit_columns(table)


def style_table(table):
    """Common table behaviour: read-only, whole-row selection, roomy rows, no row numbers."""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setMinimumSectionSize(MIN_COLUMN)
    header.setStretchLastSection(True)  # a table with few columns fills the width
    header.setHighlightSections(False)
    header.setMinimumHeight(44)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(42)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)


def find_layout(layout, widget):
    """The layout (searched through nested layouts) that directly holds ``widget``."""
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is widget:
            return layout
        if item.layout() is not None:
            found = find_layout(item.layout(), widget)
            if found is not None:
                return found
    return None


def make_tile(button, icon_name, title, subtitle):
    """Turn a plain button into a big card: icon, title, one-line description and an arrow.

    The labels sit inside the button and let the mouse through, so the whole card is the button.
    Returns the subtitle label (the home screens fill it with live numbers)."""
    button.setText("")
    button.setProperty("tile", True)
    button.setMinimumHeight(72)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    row = QHBoxLayout(button)
    row.setContentsMargins(16, 12, 16, 12)
    row.setSpacing(14)
    badge = QLabel()
    badge.setObjectName("tileIcon")
    badge.setFixedSize(48, 48)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setPixmap(icons.pixmap(icon_name, "#2563EB", 24))
    texts = QVBoxLayout()
    texts.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("tileTitle")
    sub_label = QLabel(subtitle)
    sub_label.setObjectName("tileSub")
    texts.addStretch()
    texts.addWidget(title_label)
    texts.addWidget(sub_label)
    texts.addStretch()
    arrow = QLabel()
    arrow.setPixmap(icons.pixmap("chevron", "#94A3B8", 20))
    row.addWidget(badge)
    row.addLayout(texts, 1)
    row.addWidget(arrow)
    for label in (badge, title_label, sub_label, arrow):
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    return sub_label


def fill_detail(detail, table):
    """Show the selected row as readable text: one field per line, long values wrapped.

    The panel is hidden when no row is selected, so the table can use the full height.
    """
    row = table.currentRow()
    if row < 0:
        detail.clear()
        detail.hide()
        return
    lines = []
    for c in range(table.columnCount()):
        header = table.horizontalHeaderItem(c)
        name = header.text() if header else f"Column {c + 1}"
        item = table.item(row, c)
        value = item.text() if item else ""
        lines.append(f"<p style='margin:0 0 6px 0'><b>{html.escape(name)}:</b> "
                     f"{html.escape(value) or '-'}</p>")
    detail.setHtml("".join(lines))
    detail.show()


class BasePage(QWidget):
    navigate = pyqtSignal(str)  # name of the window to open
    message = pyqtSignal(str)   # text shown in the status bar
    UI_FILE = ""
    THEME = None
    LOGO_WIDTH = 0  # 0 = this page has no logo

    def __init__(self, use_ui_file=False, store=None):
        super().__init__()
        self.store = store  # DataStore: every list and the login check come from PostgreSQL
        self.setObjectName("pageRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # paint the stylesheet background
        if use_ui_file:
            uic.loadUi(os.path.join(UI_DIR, self.UI_FILE), self)
        else:
            self.build_ui()
        self.apply_logo()
        self.connect_signals()
        self.decorate()
        self.setStyleSheet(build_stylesheet(self.THEME))  # last, so the button roles set above are styled

    def build_ui(self):
        raise NotImplementedError

    def apply_logo(self):
        label = getattr(self, "labelLogo", None)
        if label is None or not self.LOGO_WIDTH:
            return
        pixmap = QPixmap(LOGO_PATH).scaledToWidth(
            self.LOGO_WIDTH, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(pixmap)
        if self.THEME.get("dark"):  # on the dark page the logo sits on a white rounded plate
            label.setFixedSize(pixmap.width() + 64, pixmap.height() + 36)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            label.setFixedSize(pixmap.size())

    def connect_signals(self):
        pass

    # ----- look (the same for code mode and .ui mode, because it only uses object names) ------

    # button name -> (icon, role). Role "secondary" = white button with a border.
    BUTTON_STYLES = {
        "btnSearch": ("search", None),
        "btnRefresh": ("refresh", "secondary"),
        "btnLogin": ("login", None),
        "btnEventRecord": ("calendar", None),
        "btnMail": ("mail", None),
    }
    # buttons that act as the current-view selector (the chosen one is filled blue)
    SEGMENT_ICONS = {
        "btnAllApplications": "list",
        "btnMeetingDefined": "calendar-check",
        "btnMeetingNotDefined": "calendar",
        "btnProjectSent": "send",
        "btnProjectReceived": "download",
        "btnAllConversations": "list",
    }
    # buttons the side menu replaces (hidden when the page is inside the main window)
    EMBEDDED_HIDDEN = ("btnReturn", "btnReturnAdmin", "btnExit", "btnLogout", "btnClose")

    def decorate(self):
        """Icons, button roles and small touches. Runs for both build modes."""
        for name, (icon_name, role) in self.BUTTON_STYLES.items():
            button = getattr(self, name, None)
            if button is None:
                continue
            color = "#334155" if role == "secondary" else "#FFFFFF"
            button.setIcon(icons.icon(icon_name, color, 18))
            button.setIconSize(QSize(18, 18))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if role:
                button.setProperty("variant", role)
        self.segments = []
        for name, icon_name in self.SEGMENT_ICONS.items():
            button = getattr(self, name, None)
            if button is None:
                continue
            button.setProperty("segment", True)
            button.setCheckable(True)
            button.setIcon(icons.two_state(icon_name, "#64748B", "#FFFFFF", 18))
            button.setIconSize(QSize(18, 18))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.segments.append(button)
        search = getattr(self, "inputSearch", None)
        if search is not None:
            search.addAction(icons.icon("search", "#94A3B8", 18), QLineEdit.ActionPosition.LeadingPosition)
            search.setClearButtonEnabled(True)
            self.move_refresh_next_to_search()
        for name, icon_name in (("inputUsername", "user"), ("inputPassword", "lock")):
            field = getattr(self, name, None)
            if field is not None:
                field.addAction(icons.icon(icon_name, "#94A3B8", 18), QLineEdit.ActionPosition.LeadingPosition)
        for name in self.TABLE_NAMES:
            table = getattr(self, name, None)
            if table is not None:
                style_table(table)

    TABLE_NAMES = ("tableApplications", "tableInterviews", "tableConversations", "tableCalendar")

    def move_refresh_next_to_search(self):
        """Put Refresh in the search row (next to Search) instead of the bottom row."""
        refresh, search = getattr(self, "btnRefresh", None), getattr(self, "btnSearch", None)
        if refresh is None or search is None or search.parentWidget() is None:
            return
        row = find_layout(search.parentWidget().layout(), search)
        if row is not None:
            row.addWidget(refresh)

    def mark_segment(self, active):
        """Show which view selector is current. ``active`` is a button, or None when none fits."""
        for button in self.segments:
            button.setChecked(button is active)

    def set_embedded(self):
        """Inside the main window the side menu does the navigating: hide the duplicate buttons."""
        for name in self.EMBEDDED_HIDDEN:
            button = getattr(self, name, None)
            if button is not None:
                button.hide()

    def on_show(self):
        """Called by the main window each time this page is opened."""

    def route(self, button, target):
        button.clicked.connect(lambda _checked=False, t=target: self.navigate.emit(t))

    def show_message(self, text):
        self.message.emit(text)

    def add_detail_panel(self, table):
        """Place a text panel under the table. Selecting a row fills it and shows it."""
        detail = QTextEdit()
        detail.setObjectName("detailText")
        detail.setReadOnly(True)
        detail.hide()
        layout = table.parentWidget().layout()
        index = layout.indexOf(table)
        layout.removeWidget(table)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(table)
        splitter.addWidget(detail)
        splitter.setSizes([430, 230])
        layout.insertWidget(index, splitter, 1)
        table.itemSelectionChanged.connect(lambda: fill_detail(detail, table))
        return detail

    def make_header(self, title, subtitle):
        bar = QFrame()
        bar.setObjectName("headerBar")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("headerTitle")
        sub_label = QLabel(subtitle)
        sub_label.setObjectName("headerSub")
        layout.addWidget(title_label)
        layout.addWidget(sub_label)
        return bar

    def make_card(self):
        card = QFrame()
        card.setObjectName("card")
        return card

    def make_footer(self, *buttons):
        row = QHBoxLayout()
        row.addStretch()
        for button in buttons:
            row.addWidget(button)
        return row

"""Colours and stylesheets.

Look: a dark navy side menu, light content area, white rounded cards, one blue accent.
All pages share one theme; the login page is the only dark page.
"""
import icons

NAVY = "#0B1F3A"
ACCENT = "#2563EB"

_LIGHT = dict(accent=ACCENT, hover="#3B7BF0", pressed="#1D4ED8", bg="#F1F5F9", sub="#EEF2F9", alt="#FAFBFD", dark=False)

THEMES = {
    "login":             {**_LIGHT, "dark": True},
    "preferences":       dict(_LIGHT),
    "preferences_admin": dict(_LIGHT),
    "applications":      dict(_LIGHT),
    "mentor_interview":  dict(_LIGHT),
    "interviews":        dict(_LIGHT),
    "admin_menu":        dict(_LIGHT),
}

BASE = dict(text="#0F172A", border="#E2E8F0", muted="#64748B", card="#FFFFFF")

DANGER = dict(base="#E5484D", hover="#F0606A", pressed="#C93B40")


def build_stylesheet(theme):
    t = {**BASE, **theme}
    arrow = icons.png_file("chevron-down", "#64748B", 16)
    css = f"""
#pageRoot {{ background-color: {t['bg']}; }}
QLabel {{ background: transparent; color: {t['text']}; font-size: 13px; }}
QLabel#headerTitle {{ color: {t['text']}; font-size: 26px; font-weight: 700; }}
QLabel#headerSub {{ color: {t['muted']}; font-size: 13px; }}
#headerBar {{ background-color: transparent; }}
#card {{ background-color: {t['card']}; border: 1px solid {t['border']}; border-radius: 16px; }}
#card QLabel {{ color: {t['muted']}; font-size: 12px; font-weight: 600; }}
QLabel#labelMuted {{ color: {t['muted']}; font-size: 12px; font-style: normal; font-weight: 500; }}
QLabel#labelHint {{ color: {t['muted']}; font-size: 13px; font-weight: 500; }}
QLabel#labelWarning {{ color: {DANGER['base']}; font-size: 12px; font-weight: 600; }}
QLabel#labelBadge {{ background-color: #DBEAFE; color: #1D4ED8; border-radius: 10px; padding: 4px 12px; font-size: 11px; font-weight: 700; }}

QLineEdit, QComboBox, QDateEdit, QPlainTextEdit {{ background-color: #FFFFFF; color: {t['text']}; border: 1px solid #CBD5E1; border-radius: 10px; padding: 9px 12px; min-height: 20px; selection-background-color: {t['accent']}; }}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QPlainTextEdit:hover {{ border: 1px solid #94A3B8; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {t['accent']}; padding: 8px 11px; }}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{ background-color: #F1F5F9; color: #64748B; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 30px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url({arrow}); width: 14px; height: 14px; }}
QDialog#pageRoot QLabel#dialogTitle {{ font-size: 20px; font-weight: 700; color: {t['text']}; }}
QDialog#pageRoot QLabel#dialogIntro {{ color: {t['muted']}; font-size: 12px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QComboBox QAbstractItemView {{ background-color: #FFFFFF; border: 1px solid {t['border']}; outline: none; padding: 4px; selection-background-color: #DBEAFE; selection-color: {t['text']}; }}
QCheckBox {{ color: {t['muted']}; font-size: 12px; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #94A3B8; border-radius: 4px; background: #FFFFFF; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border: 1px solid {t['accent']}; }}

QPushButton {{ background-color: {t['accent']}; color: #FFFFFF; border: 1px solid {t['accent']}; border-radius: 10px; padding: 10px 18px; font-weight: 600; }}
QPushButton:hover {{ background-color: {t['hover']}; border: 1px solid {t['hover']}; }}
QPushButton:pressed {{ background-color: {t['pressed']}; border: 1px solid {t['pressed']}; }}
QPushButton:disabled {{ background-color: #CBD5E1; border: 1px solid #CBD5E1; color: #F8FAFC; }}
QPushButton:focus {{ outline: none; }}
QPushButton#btnClose, QPushButton#btnExit, QPushButton#btnDelete {{ background-color: {DANGER['base']}; border: 1px solid {DANGER['base']}; }}
QPushButton#btnClose:hover, QPushButton#btnExit:hover, QPushButton#btnDelete:hover {{ background-color: {DANGER['hover']}; border: 1px solid {DANGER['hover']}; }}
QPushButton#btnDelete:pressed {{ background-color: {DANGER['pressed']}; border: 1px solid {DANGER['pressed']}; }}
QPushButton#btnDelete:disabled {{ background-color: #CBD5E1; border: 1px solid #CBD5E1; color: #F8FAFC; }}

QPushButton[variant="secondary"] {{ background-color: #FFFFFF; color: {t['text']}; border: 1px solid #CBD5E1; }}
QPushButton[variant="secondary"]:hover {{ background-color: #F8FAFC; border: 1px solid {t['accent']}; color: {t['accent']}; }}
QPushButton[variant="secondary"]:pressed {{ background-color: #EEF2F9; }}

QPushButton[segment="true"] {{ background-color: #FFFFFF; color: #334155; border: 1px solid #CBD5E1; padding: 10px 14px; }}
QPushButton[segment="true"]:hover {{ background-color: #F8FAFC; border: 1px solid {t['accent']}; color: {t['accent']}; }}
QPushButton[segment="true"]:checked {{ background-color: {t['accent']}; color: #FFFFFF; border: 1px solid {t['accent']}; }}

QPushButton[tile="true"] {{ background-color: #FFFFFF; border: 1px solid {t['border']}; border-radius: 14px; padding: 0px; text-align: left; }}
QPushButton[tile="true"]:hover {{ background-color: #F8FBFF; border: 1px solid {t['accent']}; }}
QPushButton[tile="true"]:pressed {{ background-color: #EEF4FF; }}
QLabel#tileIcon {{ background-color: #DBEAFE; border-radius: 12px; }}
QLabel#tileTitle {{ color: {t['text']}; font-size: 15px; font-weight: 700; }}
QLabel#tileSub {{ color: {t['muted']}; font-size: 12px; font-weight: 500; }}

QTableWidget {{ background-color: #FFFFFF; alternate-background-color: {t['alt']}; border: 1px solid {t['border']}; border-radius: 12px; gridline-color: transparent; outline: none; selection-background-color: #DBEAFE; selection-color: {t['text']}; }}
QTableWidget::item {{ padding: 4px 10px; border-bottom: 1px solid #EEF2F7; }}
QTableWidget::item:hover {{ background-color: #F1F6FF; }}
QTableWidget::item:selected {{ background-color: #DBEAFE; color: {t['text']}; }}
QHeaderView::section {{ background-color: #F8FAFC; color: #475569; padding: 12px 12px; border: none; border-bottom: 1px solid {t['border']}; border-right: 1px solid #EEF2F7; font-size: 12px; font-weight: 700; }}
QTableCornerButton::section {{ background: #F8FAFC; border: none; }}
QHeaderView {{ background-color: #F8FAFC; border: none; }}
QAbstractScrollArea::corner {{ background: transparent; border: none; }}
QTextEdit#detailText {{ background-color: #F8FAFC; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 12px; padding: 10px 14px; font-size: 13px; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #CBD5E1; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #CBD5E1; border-radius: 4px; min-width: 36px; }}
QScrollBar::handle:horizontal:hover {{ background: #94A3B8; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QSplitter::handle {{ background: transparent; height: 10px; }}
"""
    if t.get("dark"):
        css += f"""
#pageRoot {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {NAVY}, stop:1 #1E3A8A); }}
QLabel#headerTitle {{ color: #FFFFFF; }}
QLabel#headerSub {{ color: #BFD0EA; }}
QLabel#labelLogo {{ background-color: #FFFFFF; border-radius: 18px; }}
QPushButton#btnClose {{ background-color: transparent; color: #E2E8F0; border: 1px solid rgba(255,255,255,0.35); }}
QPushButton#btnClose:hover {{ background-color: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.6); }}
"""
    return css


SIDEBAR_QSS = f"""
#sidebar {{ background-color: {NAVY}; }}
#sidebar QLabel {{ background: transparent; color: #CBD5E1; font-size: 13px; }}
#sidebar QLabel#brandName {{ color: #FFFFFF; font-size: 16px; font-weight: 700; }}
#sidebar QLabel#brandSub {{ color: #7F93B2; font-size: 11px; }}
#sidebar QLabel#sectionLabel {{ color: #6E83A3; font-size: 10px; font-weight: 700; padding: 14px 12px 4px 12px; }}
#sidebar QFrame#divider {{ background-color: rgba(255,255,255,0.10); max-height: 1px; min-height: 1px; border: none; }}
#sidebar QPushButton {{ background-color: transparent; color: #CBD5E1; border: none; border-radius: 10px; padding: 11px 12px; text-align: left; font-size: 13px; font-weight: 600; }}
#sidebar QPushButton:hover {{ background-color: rgba(255,255,255,0.08); color: #FFFFFF; }}
#sidebar QPushButton:checked {{ background-color: {ACCENT}; color: #FFFFFF; }}
#sidebar QPushButton#navExit:hover {{ background-color: rgba(229,72,77,0.22); color: #FFB4B7; }}
#sidebar QFrame#userCard {{ background-color: rgba(255,255,255,0.07); border-radius: 12px; }}
#sidebar QLabel#avatar {{ background-color: {ACCENT}; color: #FFFFFF; border-radius: 17px; font-size: 14px; font-weight: 700; }}
#sidebar QLabel#userName {{ color: #FFFFFF; font-size: 13px; font-weight: 600; }}
#sidebar QLabel#userRole {{ color: #93C5FD; font-size: 11px; font-weight: 600; }}
"""

STATUSBAR_QSS = """
QStatusBar { background: #FFFFFF; color: #475569; border-top: 1px solid #E2E8F0; font-size: 12px; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: #475569; font-size: 12px; padding: 0 6px; }
"""

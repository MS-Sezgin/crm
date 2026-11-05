"""Shared colour themes and stylesheet template.

Visual language follows the approved mockups: light blue-grey background,
white rounded cards, dark navy text, blue primary buttons and blue badges.
Each section keeps its own blue shade so the user can tell the sections apart.
"""

THEMES = {
    "login":             dict(accent="#1F6FEB", hover="#3B82F6", pressed="#1A5BD0", bg="#F3F6FB", sub="#DCE8FB", alt="#F8FAFD"),
    "preferences":       dict(accent="#2563EB", hover="#3B7BF0", pressed="#1D4ED8", bg="#F3F6FB", sub="#DBE7FF", alt="#F8FAFF"),
    "preferences_admin": dict(accent="#0B2545", hover="#13335E", pressed="#071A33", bg="#F0F2F6", sub="#D5DCE8", alt="#F7F8FA"),
    "applications":      dict(accent="#1D4ED8", hover="#2563EB", pressed="#1E40AF", bg="#F3F6FB", sub="#DBE7FF", alt="#F8FAFF"),
    "mentor_interview":  dict(accent="#0EA5E9", hover="#38BDF8", pressed="#0284C7", bg="#F0F9FF", sub="#D7F0FB", alt="#F7FCFF"),
    "interviews":        dict(accent="#3B82F6", hover="#60A5FA", pressed="#2563EB", bg="#F3F6FB", sub="#DBEAFE", alt="#F8FBFF"),
    "admin_menu":        dict(accent="#0B2545", hover="#13335E", pressed="#071A33", bg="#F0F2F6", sub="#D5DCE8", alt="#F7F8FA"),
}

BASE = dict(text="#0F172A", border="#E2E8F0", muted="#64748B", card="#FFFFFF")

DANGER = dict(base="#E5484D", hover="#F0606A", pressed="#C93B40")


def build_stylesheet(theme):
    t = {**BASE, **theme}
    return f"""
#pageRoot {{ background-color: {t['bg']}; }}
QLabel {{ background: transparent; color: {t['text']}; font-size: 13px; }}
QLabel#headerTitle {{ color: {t['text']}; font-size: 24px; font-weight: 700; }}
QLabel#headerSub {{ color: {t['muted']}; font-size: 13px; }}
#headerBar {{ background-color: transparent; }}
#card {{ background-color: {t['card']}; border: 1px solid {t['border']}; border-radius: 14px; }}
#card QLabel {{ color: {t['muted']}; font-size: 12px; font-weight: 600; }}
QLabel#labelMuted {{ color: {t['muted']}; font-size: 13px; font-style: italic; font-weight: 400; }}
QLabel#labelWarning {{ color: {DANGER['base']}; font-size: 12px; font-weight: 600; }}
QLabel#labelBadge {{ background-color: {t['accent']}; color: #FFFFFF; border-radius: 11px; padding: 4px 12px; font-size: 11px; font-weight: 700; }}
QLineEdit, QComboBox {{ background-color: #FFFFFF; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 10px; padding: 9px 12px; min-height: 20px; }}
QLineEdit:hover, QComboBox:hover {{ border: 1px solid {t['accent']}; }}
QLineEdit:focus, QComboBox:focus {{ border: 2px solid {t['accent']}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background-color: #FFFFFF; border: 1px solid {t['border']}; selection-background-color: {t['accent']}; selection-color: #FFFFFF; }}
QCheckBox {{ color: {t['muted']}; font-size: 12px; spacing: 6px; }}
QPushButton {{ background-color: {t['accent']}; color: #FFFFFF; border: 1px solid {t['accent']}; border-radius: 10px; padding: 10px 18px; font-weight: 600; }}
QPushButton:hover {{ background-color: {t['hover']}; border: 1px solid {t['pressed']}; }}
QPushButton:pressed {{ background-color: {t['pressed']}; border: 1px solid {t['pressed']}; padding-top: 11px; padding-bottom: 9px; }}
QPushButton:disabled {{ background-color: #CBD5E1; border: 1px solid #CBD5E1; color: #F8FAFC; }}
QPushButton#btnClose, QPushButton#btnExit {{ background-color: {DANGER['base']}; border: 1px solid {DANGER['base']}; }}
QPushButton#btnClose:hover, QPushButton#btnExit:hover {{ background-color: {DANGER['hover']}; border: 1px solid {DANGER['pressed']}; }}
QPushButton#btnClose:pressed, QPushButton#btnExit:pressed {{ background-color: {DANGER['pressed']}; border: 1px solid {DANGER['pressed']}; padding-top: 11px; padding-bottom: 9px; }}
QTableWidget {{ background-color: #FFFFFF; alternate-background-color: {t['alt']}; border: 1px solid {t['border']}; border-radius: 10px; gridline-color: {t['border']}; selection-background-color: {t['sub']}; selection-color: {t['text']}; }}
QHeaderView::section {{ background-color: {t['sub']}; color: {t['text']}; padding: 10px 12px; border: none; border-bottom: 2px solid {t['accent']}; font-weight: 600; }}
"""

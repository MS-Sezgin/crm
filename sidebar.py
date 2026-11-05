"""Dark navy side menu shown on every screen except the login screen."""
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout)

import icons
from styles import SIDEBAR_QSS

# (key, label, icon, target the window opens). "return_preferences" means the home screen of the user's role.
NAV_ITEMS = [
    ("home", "Home", "home", "return_preferences"),
    ("applications", "Applications", "applications", "applications"),
    ("mentor_interview", "Mentor Interview", "mentor", "mentor_interview"),
    ("interviews", "Interviews", "interviews", "interviews"),
]
ADMIN_ITEMS = [("admin_menu", "Admin Menu", "admin", "admin_menu")]

# which menu entry is lit for each page of the window
PAGE_TO_KEY = {
    "preferences": "home", "preferences_admin": "home", "applications": "applications",
    "mentor_interview": "mentor_interview", "interviews": "interviews", "admin_menu": "admin_menu",
}


def _two_state_icon(name):
    """Muted icon normally, white icon while the entry is the current page."""
    return icons.two_state(name, "#93A4BF", "#FFFFFF", 20)


class Sidebar(QFrame):
    navigate = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(240)
        self.setStyleSheet(SIDEBAR_QSS)
        self.buttons = {}
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 18, 14, 14)
        root.setSpacing(2)

        root.addLayout(self._brand())
        root.addSpacing(10)
        root.addWidget(self._divider())

        root.addWidget(self._section("WORKSPACE"))
        for item in NAV_ITEMS:
            root.addWidget(self._nav_button(*item))

        self.adminLabel = self._section("ADMINISTRATION")
        root.addWidget(self.adminLabel)
        self.adminButtons = [self._nav_button(*item) for item in ADMIN_ITEMS]
        for button in self.adminButtons:
            root.addWidget(button)

        root.addStretch()
        root.addWidget(self._user_card())
        root.addSpacing(8)
        self.btnLogout = self._action_button("Log out", "logout", "login")
        self.btnExit = self._action_button("Exit", "power", "exit")
        self.btnExit.setObjectName("navExit")
        root.addWidget(self.btnLogout)
        root.addWidget(self.btnExit)
        self.set_user("", False)

    # ----- building blocks --------------------------------------------------------------

    def _brand(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icons.app_icon().pixmap(38, 38))
        logo.setFixedSize(38, 38)
        names = QVBoxLayout()
        names.setSpacing(0)
        title = QLabel("CRM Capstone")
        title.setObjectName("brandName")
        sub = QLabel("WearHere")
        sub.setObjectName("brandSub")
        names.addWidget(title)
        names.addWidget(sub)
        row.addWidget(logo)
        row.addLayout(names)
        row.addStretch()
        return row

    def _divider(self):
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.Shape.NoFrame)
        return line

    def _section(self, text):
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def _nav_button(self, key, label, icon_name, target):
        button = QPushButton(label)
        button.setCheckable(True)
        button.setIcon(_two_state_icon(icon_name))
        button.setIconSize(QSize(20, 20))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, t=target: self.navigate.emit(t))
        self.group.addButton(button)
        self.buttons[key] = button
        return button

    def _action_button(self, label, icon_name, target):
        button = QPushButton(label)
        button.setIcon(icons.icon(icon_name, "#93A4BF", 20))
        button.setIconSize(QSize(20, 20))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, t=target: self.navigate.emit(t))
        return button

    def _user_card(self):
        card = QFrame()
        card.setObjectName("userCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(10, 10, 10, 10)
        row.setSpacing(10)
        self.avatar = QLabel("?")
        self.avatar.setObjectName("avatar")
        self.avatar.setFixedSize(34, 34)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.userName = QLabel("")
        self.userName.setObjectName("userName")
        self.userRole = QLabel("")
        self.userRole.setObjectName("userRole")
        texts.addWidget(self.userName)
        texts.addWidget(self.userRole)
        row.addWidget(self.avatar)
        row.addLayout(texts, 1)
        return card

    # ----- public ---------------------------------------------------------------------------

    def set_user(self, name, is_admin):
        """Show who is logged in; the Administration entries appear only for admins."""
        shown = name or "User"
        self.avatar.setText(shown[:1].upper())
        self.userName.setText(shown)
        self.userRole.setText("Administrator" if is_admin else "User")
        self.adminLabel.setVisible(is_admin)
        for button in self.adminButtons:
            button.setVisible(is_admin)

    def set_active(self, page_name):
        key = PAGE_TO_KEY.get(page_name)
        button = self.buttons.get(key)
        if button is not None:
            button.setChecked(True)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QCheckBox, QFrame, QGraphicsDropShadowEffect, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout)

from database import DatabaseError
from pages.base_page import BasePage
from styles import THEMES


class LoginPage(BasePage):
    UI_FILE = "login_page.ui"
    LOGO_WIDTH = 300
    THEME = THEMES["login"]

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(16)
        root.addStretch()

        self.labelLogo = QLabel()
        self.labelLogo.setObjectName("labelLogo")
        root.addWidget(self.labelLogo, 0, Qt.AlignmentFlag.AlignHCenter)

        header = self.make_header("CRM Capstone", "Customer Relationship Management - Sign in")
        header.setFixedWidth(460)
        root.addWidget(header, 0, Qt.AlignmentFlag.AlignHCenter)

        card = self.make_card()
        card.setFixedWidth(460)
        body = QVBoxLayout(card)
        body.setContentsMargins(24, 24, 24, 24)
        body.setSpacing(8)

        self.labelUsername = QLabel("Username")
        self.inputUsername = QLineEdit()
        self.inputUsername.setPlaceholderText("Enter your username")
        self.labelPassword = QLabel("Password")
        self.inputPassword = QLineEdit()
        self.inputPassword.setPlaceholderText("Enter your password")
        self.inputPassword.setEchoMode(QLineEdit.EchoMode.Password)
        self.checkShowPassword = QCheckBox("Show password")
        self.labelWarning = QLabel("")
        self.labelWarning.setObjectName("labelWarning")
        self.btnLogin = QPushButton("Login")
        self.btnLogin.setMinimumHeight(44)

        for widget in (self.labelUsername, self.inputUsername, self.labelPassword,
                       self.inputPassword, self.checkShowPassword, self.labelWarning):
            body.addWidget(widget)
        body.addSpacing(8)
        body.addWidget(self.btnLogin)
        root.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)

        self.btnClose = QPushButton("Close")
        self.btnClose.setObjectName("btnClose")
        root.addWidget(self.btnClose, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch()

    def decorate(self):
        super().decorate()
        card = self.findChild(QFrame, "card")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 110))
        card.setGraphicsEffect(shadow)
        self.username = ""

    def connect_signals(self):
        self.btnLogin.clicked.connect(self.on_login)
        self.checkShowPassword.toggled.connect(self.toggle_password)
        self.inputPassword.returnPressed.connect(self.on_login)
        self.route(self.btnClose, "exit")

    def toggle_password(self, checked):
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.inputPassword.setEchoMode(mode)

    def reset(self):
        self.inputUsername.clear()
        self.inputPassword.clear()
        self.labelWarning.setText("")

    def on_login(self, *_):
        username = self.inputUsername.text().strip()
        password = self.inputPassword.text()
        if not username or not password:
            self.labelWarning.setText("Please enter both username and password.")
            return
        try:
            role = self.store.check_login(username, password)
        except DatabaseError as error:
            self.labelWarning.setText(str(error))
            return
        self.inputPassword.clear()
        if role is None:
            self.labelWarning.setText("Incorrect username or password.")
            return
        self.labelWarning.setText("")
        self.username = username
        self.show_message(f"Logged in as {username} ({role})")
        self.navigate.emit("preferences_admin" if role == "admin" else "preferences")

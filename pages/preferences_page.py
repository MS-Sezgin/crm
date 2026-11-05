from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from pages.home_base import HomeBase
from styles import THEMES


class PreferencesPage(HomeBase):
    UI_FILE = "preferences_page.ui"
    TILES = [
        ("btnApplications", "applications", "Applications", "Search and review submitted applications"),
        ("btnMentorInterview", "mentor", "Mentor Interview", "Mentor conversations and recommendations"),
        ("btnInterviews", "interviews", "Interviews", "Project exchange between students and mentors"),
    ]
    THEME = THEMES["preferences"]

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(16)
        root.addStretch()

        self.labelLogo = QLabel()
        self.labelLogo.setObjectName("labelLogo")
        root.addWidget(self.labelLogo, 0, Qt.AlignmentFlag.AlignHCenter)

        header = self.make_header("Preferences", "Choose a section to continue")
        header.setFixedWidth(620)
        root.addWidget(header, 0, Qt.AlignmentFlag.AlignHCenter)

        card = self.make_card()
        card.setFixedWidth(620)
        body = QVBoxLayout(card)
        body.setContentsMargins(24, 24, 24, 24)
        body.setSpacing(12)
        self.labelBadge = QLabel("USER MODE")
        self.labelBadge.setObjectName("labelBadge")
        body.addWidget(self.labelBadge, 0, Qt.AlignmentFlag.AlignLeft)
        body.addSpacing(4)
        self.btnApplications = QPushButton("Applications")
        self.btnMentorInterview = QPushButton("Mentor Interview")
        self.btnInterviews = QPushButton("Interviews")
        for button in (self.btnApplications, self.btnMentorInterview, self.btnInterviews):
            button.setMinimumHeight(72)
            body.addWidget(button)
        root.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)

        self.btnLogout = QPushButton("Main Menu")
        root.addWidget(self.btnLogout, 0, Qt.AlignmentFlag.AlignHCenter)
        self.btnClose = QPushButton("Close")
        root.addWidget(self.btnClose, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch()

    def connect_signals(self):
        self.route(self.btnApplications, "applications")
        self.route(self.btnMentorInterview, "mentor_interview")
        self.route(self.btnInterviews, "interviews")
        self.route(self.btnLogout, "login")
        self.route(self.btnClose, "exit")

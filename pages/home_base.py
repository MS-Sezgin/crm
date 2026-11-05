"""Shared part of the two home screens (user and administrator)."""
from PyQt6.QtWidgets import QFrame, QLabel

from database import DatabaseError
from pages.base_page import BasePage, make_tile

CONTENT_WIDTH = 620


class HomeBase(BasePage):
    # (button name, icon, title, text shown until the numbers are loaded)
    TILES = []
    LOGO_WIDTH = 180

    def decorate(self):
        super().decorate()
        self.tile_texts = {}
        for name, icon_name, title, text in self.TILES:
            self.tile_texts[name] = make_tile(getattr(self, name), icon_name, title, text)
        for frame_name in ("headerBar", "card"):
            frame = self.findChild(QFrame, frame_name)
            if frame is not None:
                frame.setFixedWidth(CONTENT_WIDTH)
        title = self.findChild(QLabel, "headerTitle")
        if title is not None:
            title.setText("Home")
        self.labelSub = self.findChild(QLabel, "headerSub")
        self.layout().setContentsMargins(24, 20, 24, 20)  # compact, so four cards fit the smallest window
        self.layout().setSpacing(10)

    def set_user(self, name):
        if self.labelSub is not None:
            self.labelSub.setText(f"Signed in as {name}  -  choose a section to continue")

    def card_texts(self, summary):
        """Button name -> description with live numbers."""
        return {
            "btnApplications": f"{summary['applications']} applications  -  {summary['meeting_defined']} with a mentor meeting",
            "btnMentorInterview": f"{summary['mentor']} mentor conversations",
            "btnInterviews": f"{summary['sent']} projects sent  -  {summary['received']} received",
        }

    def on_show(self):
        try:
            texts = self.card_texts(self.store.summary())
        except DatabaseError as error:
            self.show_message(str(error))
            return
        for name, text in texts.items():
            if name in self.tile_texts:
                self.tile_texts[name].setText(text)

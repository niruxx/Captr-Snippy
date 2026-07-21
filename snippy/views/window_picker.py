"""WindowPickerDialog - replaces _pick_window()'s Toplevel/Listbox modal.
Lists open top-level windows (via capture.list_windows()) for the "record
one window" source; returns the chosen HWND, or None if cancelled.
"""

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QVBoxLayout)

from ..capture import list_windows


class WindowPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose a window to record")
        self.resize(420, 380)
        self._windows = list_windows()
        self._result_hwnd = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a window to record"))
        self._list = QListWidget()
        for _hwnd, title in self._windows:
            self._list.addItem(title)
        if self._windows:
            self._list.setCurrentRow(0)
        self._list.itemDoubleClicked.connect(self._confirm)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        record_btn = QPushButton("Record")
        record_btn.setDefault(True)
        record_btn.clicked.connect(self._confirm)
        btn_row.addWidget(record_btn)
        layout.addLayout(btn_row)

    def _confirm(self, *_args):
        row = self._list.currentRow()
        if 0 <= row < len(self._windows):
            self._result_hwnd = self._windows[row][0]
        self.accept()

    @staticmethod
    def pick(parent=None):
        """Returns the chosen hwnd, or None if cancelled/no windows."""
        dialog = WindowPickerDialog(parent)
        if not dialog._windows:
            return None
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog._result_hwnd
        return None

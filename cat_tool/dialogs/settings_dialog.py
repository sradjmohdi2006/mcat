from PyQt5.QtWidgets import (QDialog, QFormLayout, QSpinBox, QCheckBox,
                             QDialogButtonBox)


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Options")
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)

        self.src_font_spin = QSpinBox()
        self.src_font_spin.setRange(8, 30)
        self.src_font_spin.setValue(self.settings["source_font_size"])
        layout.addRow("Source font size:", self.src_font_spin)

        self.tgt_font_spin = QSpinBox()
        self.tgt_font_spin.setRange(8, 30)
        self.tgt_font_spin.setValue(self.settings["target_font_size"])
        layout.addRow("Target font size:", self.tgt_font_spin)

        self.auto_save_cb = QCheckBox()
        self.auto_save_cb.setChecked(self.settings["auto_save_on_segment_change"])
        layout.addRow("Auto-save on segment change:", self.auto_save_cb)

        self.show_tags_cb = QCheckBox()
        self.show_tags_cb.setChecked(self.settings["show_tag_placeholders"])
        layout.addRow("Show tag placeholders:", self.show_tags_cb)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def _save(self):
        self.settings["source_font_size"] = self.src_font_spin.value()
        self.settings["target_font_size"] = self.tgt_font_spin.value()
        self.settings["auto_save_on_segment_change"] = self.auto_save_cb.isChecked()
        self.settings["show_tag_placeholders"] = self.show_tags_cb.isChecked()
        self.settings.save()
        self.accept()

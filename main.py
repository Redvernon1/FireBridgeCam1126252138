# main.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtCore import Qt, QPointF, QTimer
from PyQt6.QtGui import QPainter, QPen, QFont, QRadialGradient, QColor, QBrush
from PyQt6. QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QFrame,
    QPushButton,
    QLabel,
    QTextEdit,
    QTabWidget,
    QGroupBox,
    QFileDialog,
    QSizePolicy,
    QComboBox,
    QSplitter,
    QMessageBox,
)

# Optional modules
try:
    from plasma_core.config import get_config
except Exception:
    get_config = None  # type: ignore

try:
    from plasma_core. translator import get_translator
except Exception:
    get_translator = None  # type: ignore

try:
    from plasma_core.parsers import load_dxf, load_svg
    _HAS_PARSERS = True
except Exception:
    load_dxf = None  # type: ignore
    load_svg = None  # type: ignore
    _HAS_PARSERS = False


# ----------------------------------------------------------------------
# Canvas Widget
# ----------------------------------------------------------------------
class CanvasWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.paths: List[Dict] = []
        self.scale: float = 1.0
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self._animating: bool = False
        self._animation_phase: float = 0.0
        self._timer = QTimer(self)
        self._timer. timeout.connect(self._advance_animation)
        self. setSizePolicy(QSizePolicy. Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_paths(self, paths: List[Dict]) -> None:
        self.paths = paths or []
        self.update()

    def clear(self) -> None:
        self.paths. clear()
        self.update()

    def start_animation(self) -> None:
        if not self._animating:
            self._animating = True
            self._timer.start(30)
            self.update()

    def stop_animation(self) -> None:
        self._animating = False
        self._timer.stop()
        self.update()

    def _advance_animation(self) -> None:
        if not self._animating:
            self._timer.stop()
            return
        self._animation_phase += 0.02
        if self._animation_phase > 1.0:
            self._animation_phase -= 1.0
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore
        p = QPainter(self)

        # Canvas background (GitHub dark-style)
        self.setStyleSheet("background-color: #0d1117;")

        # Light gray grid
        grid_pen = QPen(QColor("#30363d"), 1, Qt. PenStyle.DotLine)
        p.setPen(grid_pen)
        step = 40
        for x in range(0, self.width(), step):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            p.drawLine(0, y, self.width(), y)

        # Draw geometry if present
        if self.paths:
            geom_pen = QPen(QColor("#c9d1d9"), 2)
            for path in self.paths:
                pts = path. get("points", [])
                if len(pts) < 2:
                    continue
                p.setPen(geom_pen)
                for i in range(len(pts) - 1):
                    x1 = (pts[i][0] + self.offset_x) * self. scale
                    y1 = self.height() - (pts[i][1] + self.offset_y) * self.scale
                    x2 = (pts[i + 1][0] + self.offset_x) * self.scale
                    y2 = self.height() - (pts[i + 1][1] + self.offset_y) * self.scale
                    p. drawLine(QPointF(x1, y1), QPointF(x2, y2))
        else:
            # Placeholder text when empty
            font = QFont("Segoe UI", 16, QFont.Weight.Bold)
            p.setFont(font)
            p.setPen(QPen(QColor("#8b949e")))
            p.drawText(self.rect(), Qt.AlignmentFlag. AlignCenter, "No file loaded")

        # Torch animation placeholder
        if self._animating:
            torch_gradient = QRadialGradient(QPointF(self.width() / 2, self.height() / 2), 80)
            torch_gradient.setColorAt(0, QColor(0, 255, 255, 80))
            torch_gradient.setColorAt(0.5, QColor(0, 255, 255, 40))
            torch_gradient.setColorAt(1, QColor(0, 255, 255, 0))
            p.setBrush(QBrush(torch_gradient))
            p. setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(self.width() / 2, self.height() / 2), 80, 80)

        p.end()


# Compatibility alias
class InteractivePreviewCanvas(CanvasWidget):
    pass


# ----------------------------------------------------------------------
# Main Window Layout
# ----------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FireBridgeCAM Pro")
        self.resize(1400, 800)

        # Global dark theme
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #0d1117;
                color: #c9d1d9;
            }
            QFrame, QGroupBox {
                background-color: #161b22;
                border: 1px solid #000000;
            }
            QLabel, QPushButton, QComboBox {
                color: #c9d1d9;
            }
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #30363d;
            }
            QComboBox {
                background-color: #161b22;
                border: 1px solid #30363d;
            }
            QStatusBar {
                background-color: #0d1117;
                color: #c9d1d9;
            }
            """
        )

        # Main splitter holding everything
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # ------------------------------------------------------------------
        # Left Panel (fixed 300px)
        # ------------------------------------------------------------------
        self.left_panel = QFrame()
        self.left_panel.setFixedWidth(300)
        lp = QVBoxLayout(self.left_panel)
        lp. setAlignment(Qt.AlignmentFlag. AlignTop)
        lp.setContentsMargins(8, 8, 8, 8)
        lp.setSpacing(8)

        self.btn_load = QPushButton("📂 Load DXF/SVG")
        self.btn_load. setMinimumHeight(40)
        self.btn_load.setSizePolicy(QSizePolicy. Policy.Expanding, QSizePolicy.Policy.Fixed)
        lp.addWidget(self.btn_load)

        self.lbl_file_status = QLabel("No file loaded")
        self.lbl_file_status. setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_file_status.setFixedHeight(22)
        lp.addWidget(self.lbl_file_status)

        # 3×2 button grid
        grid = QGridLayout()
        grid.setSpacing(6)
        names = ["Machine", "Plasma", "Leads", "XY Offset", "Advanced", "Materials"]
        emojis = ["⚙️", "🔥", "🔗", "↔️", "🧰", "📦"]
        self.left_buttons: List[QPushButton] = []
        for i, name in enumerate(names):
            b = QPushButton(f"{emojis[i]} {name}")
            b.setMinimumHeight(32)
            b.setSizePolicy(QSizePolicy.Policy. Expanding, QSizePolicy. Policy.Fixed)
            grid.addWidget(b, i // 2, i % 2)
            self.left_buttons. append(b)
        lp.addLayout(grid)

        # Current tab settings group box
        self.grp_tab_settings = QGroupBox("Current Tab Settings")
        gl = QVBoxLayout(self.grp_tab_settings)
        gl.addWidget(QLabel("Ready for dynamic fields"))
        gl.addStretch(1)
        lp.addWidget(self.grp_tab_settings)

        # Bottom big buttons
        self.btn_toolpaths = QPushButton("Generate Toolpaths")
        self.btn_toolpaths.setMinimumHeight(46)
        self.btn_gcode = QPushButton("Generate G-code")
        self.btn_gcode.setMinimumHeight(46)
        self. btn_save_gcode = QPushButton("Save G-code")
        self.btn_save_gcode.setMinimumHeight(46)

        for b in (self.btn_toolpaths, self.btn_gcode, self.btn_save_gcode):
            b.setSizePolicy(QSizePolicy.Policy. Expanding, QSizePolicy.Policy.Fixed)
            lp.addWidget(b)

        # Language/Units/Format combos
        self.combo_language = QComboBox()
        self.combo_language. addItems(["English", "Français", "Deutsch", "Español", "简体中文"])
        self. combo_language.setFixedHeight(28)
        lp.addWidget(self.combo_language)

        self.units_combo = QComboBox()
        self.units_combo. addItems(["Metric (mm)", "Imperial (inch)"])
        self.units_combo.setFixedHeight(28)
        lp.addWidget(self.units_combo)

        self.gcode_format_combo = QComboBox()
        self.gcode_format_combo.addItems([".nc", ".tap", ".txt", ".ngc", ".cnc"])
        self.gcode_format_combo.setFixedHeight(28)
        lp.addWidget(self.gcode_format_combo)

        # ------------------------------------------------------------------
        # Center Canvas
        # ------------------------------------------------------------------
        self.canvas = InteractivePreviewCanvas()

        # ------------------------------------------------------------------
        # Right Panel (fixed 200px)
        # ------------------------------------------------------------------
        self.right_panel = QFrame()
        self.right_panel.setFixedWidth(200)
        rpl = QVBoxLayout(self. right_panel)
        rpl.setContentsMargins(6, 6, 6, 6)
        rpl.setSpacing(6)

        self.tabs_right = QTabWidget()
        self.tabs_right.setTabsClosable(False)
        self.tabs_right.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #000000;
                background: #0d1117;
            }
            QTabBar::tab {
                background-color: #161b22;
                color: #ffffff;
                padding: 4px 8px;
                border: 1px solid #000000;
                margin-right: 1px;
            }
            QTabBar::tab:selected {
                background-color: #238636;
            }
            QTextEdit {
                background-color: #0d1117;
                color: #ffffff;
                border: 1px solid #000000;
            }
            """
        )

        self.txt_gcode = QTextEdit()
        self.txt_gcode.setReadOnly(False)
        self.txt_layers = QTextEdit()
        self.txt_layers.setReadOnly(True)

        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1. setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.txt_gcode)
        self.tabs_right.addTab(t1, "G-code")

        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.txt_layers)
        self.tabs_right. addTab(t2, "Layers")

        rpl.addWidget(self.tabs_right, stretch=1)

        # ------------------------------------------------------------------
        # Assemble splitter sections
        # ------------------------------------------------------------------
        splitter.addWidget(self.left_panel)
        splitter. addWidget(self.canvas)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900, 200])

        # Connections
        self.btn_load. clicked.connect(self.on_open_file)
        self. btn_toolpaths.clicked.connect(self.generate_toolpaths)
        self.btn_gcode. clicked.connect(self.generate_gcode)
        self.btn_save_gcode.clicked. connect(self.on_save_gcode_clicked)

        for idx, btn in enumerate(self.left_buttons):
            btn.clicked.connect(lambda _=False, i=idx: self.on_tab_changed(i))

        self.units_combo.currentIndexChanged.connect(self.on_units_changed)
        self. combo_language.currentIndexChanged. connect(lambda _index: None)
        self.gcode_format_combo.currentIndexChanged. connect(lambda _index: None)
        self.tabs_right.currentChanged.connect(self.on_tab_changed)

        # status bar
        self.statusBar(). showMessage("Ready")

    # ------------------------------------------------------------------
    # File Loading
    # ------------------------------------------------------------------
    def on_open_file(self) -> None:
        if not _HAS_PARSERS:
            QMessageBox.warning(
                self,
                "Parser Error",
                "CAD parsers are not available.\nMissing or broken plasma_core. parsers module.",
            )
            self.statusBar().showMessage("Parsers not available", 4000)
            return

        dialog_filter = "CAD Files (*.dxf *.svg);;DXF Files (*.dxf);;SVG Files (*.svg);;All Files (*)"
        file_path_str, _ = QFileDialog. getOpenFileName(
            self,
            "Open CAD File",
            "",
            dialog_filter,
        )

        if not file_path_str:
            self.statusBar().showMessage("Open file cancelled", 2000)
            return

        file_path = Path(file_path_str)
        if not file_path.exists():
            QMessageBox.warning(self, "File Error", f"File not found:\n{file_path}")
            self.statusBar().showMessage("File not found", 4000)
            return

        paths: List[Dict] = []
        errors: List[str] = []

        suffix = file_path.suffix.lower()

        # Load DXF files
        if suffix == ".dxf":
            try:
                paths = load_dxf(str(file_path), units="mm") or []
            except Exception as e:
                errors.append(f"DXF load failed: {e}")
        # Load SVG files
        elif suffix == ".svg":
            try:
                paths = load_svg(str(file_path)) or []
            except Exception as e:
                errors.append(f"SVG load failed: {e}")
        # Unknown extension - try both
        else:
            try:
                paths = load_dxf(str(file_path), units="mm") or []
            except Exception as e:
                errors. append(f"DXF load failed: {e}")
            if not paths:
                try:
                    paths = load_svg(str(file_path)) or []
                except Exception as e:
                    errors.append(f"SVG load failed: {e}")

        if not paths:
            msg = "Failed to load file.  No geometry found."
            if errors:
                msg += "\n\nDetails:\n" + "\n".join(errors)
            QMessageBox. warning(self, "Load Failed", msg)
            self.lbl_file_status.setText("Load failed")
            self.statusBar().showMessage("Failed to load file", 4000)
            return

        # Success
        self.canvas.set_paths(paths)
        self.lbl_file_status.setText(str(file_path.name))
        self.statusBar().showMessage(f"Loaded: {file_path.name} ({len(paths)} paths)", 5000)

    # ------------------------------------------------------------------
    # Save G-code
    # ------------------------------------------------------------------
    def on_save_gcode_clicked(self) -> None:
        # Determine default extension from combo
        ext = self.gcode_format_combo.currentText().lstrip(". ") or "nc"
        default_name = Path. home() / f"output.{ext}"
        filter_str = f"G-code (*.{ext});;All Files (*)"

        filename_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save G-code",
            str(default_name),
            filter_str,
        )
        if not filename_str:
            self.statusBar().showMessage("Save G-code cancelled", 2000)
            return

        try:
            out_path = Path(filename_str)
            if not out_path.suffix:
                out_path = out_path.with_suffix(f".{ext}")

            text = self.txt_gcode.toPlainText()
            out_path.write_text(text, encoding="utf-8")
            self.statusBar().showMessage(f"G-code saved to: {out_path.name}", 5000)
        except Exception as e:
            QMessageBox. warning(self, "Save Failed", f"Failed to save G-code:\n{e}")
            self.statusBar().showMessage("Failed to save G-code", 4000)

    # ------------------------------------------------------------------
    # Placeholder / future features
    # ------------------------------------------------------------------
    def generate_toolpaths(self) -> None:
        # Placeholder for future toolpath generation
        self. statusBar().showMessage("Toolpath generation not implemented yet", 3000)

    def generate_gcode(self) -> None:
        # Placeholder for future G-code generation
        self.statusBar().showMessage("G-code generation not implemented yet", 3000)

    def save_project(self) -> None:
        # Placeholder for future project save
        self.statusBar(). showMessage("Save project not implemented yet", 3000)

    def load_project(self) -> None:
        # Placeholder for future project load
        self.statusBar().showMessage("Load project not implemented yet", 3000)

    def on_tab_changed(self, index) -> None:
        # Placeholder for reacting to tab / mode changes
        _ = index

    def fit_to_view(self) -> None:
        # Placeholder for fit-to-view on canvas
        self.statusBar().showMessage("Fit to view not implemented yet", 3000)

    def animate_cut(self) -> None:
        # Placeholder for starting cut animation
        self.canvas.start_animation()
        self.statusBar().showMessage("Cut animation started (placeholder)", 3000)

    def stop_animation(self) -> None:
        # Placeholder for stopping cut animation
        self.canvas.stop_animation()
        self.statusBar().showMessage("Cut animation stopped", 3000)

    # ------------------------------------------------------------------
    # Units / misc
    # ------------------------------------------------------------------
    def on_units_changed(self, index: int) -> None:
        _ = index
        self.statusBar().showMessage("Units changed (no conversion applied yet)", 3000)


def run() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    print("READY")
    run()
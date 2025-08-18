import sys
import os
import csv
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QMessageBox, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import mplcursors


class CSVWaveformViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IV/PV 波形查看器")
        self.resize(1100, 700)

        main_layout = QHBoxLayout()

        # 左侧文本显示
        left_layout = QVBoxLayout()
        self.param_text = QTextEdit()
        self.param_text.setReadOnly(True)
        self.param_text.setMinimumWidth(350)
        left_layout.addWidget(QLabel("csv文件具体信息："))
        left_layout.addWidget(self.param_text)

        self.load_btn = QPushButton("加载 CSV 并显示波形")
        self.load_btn.clicked.connect(self.load_and_plot)
        left_layout.addWidget(self.load_btn)

        main_layout.addLayout(left_layout)

        # 右侧布局，包含按钮区和画布
        right_layout = QVBoxLayout()
        btn_text_layout = QHBoxLayout()

        # I-V 曲线按钮与文本框
        iv_layout = QVBoxLayout()
        self.iv_btn = QPushButton("I-V 曲线")
        self.iv_btn.setCheckable(True)
        self.iv_btn.setChecked(True)
        self.iv_btn.clicked.connect(self.toggle_iv_curve)
        iv_layout.addWidget(self.iv_btn)

        self.iv_mpp_text = QTextEdit()
        self.iv_mpp_text.setReadOnly(True)
        self.iv_mpp_text.setFixedHeight(60)
        iv_layout.addWidget(self.iv_mpp_text)
        btn_text_layout.addLayout(iv_layout)

        # P-V 曲线按钮与文本框
        pv_layout = QVBoxLayout()
        self.pv_btn = QPushButton("P-V 曲线")
        self.pv_btn.setCheckable(True)
        self.pv_btn.setChecked(True)
        self.pv_btn.clicked.connect(self.toggle_pv_curve)
        pv_layout.addWidget(self.pv_btn)

        self.pv_mpp_text = QTextEdit()
        self.pv_mpp_text.setReadOnly(True)
        self.pv_mpp_text.setFixedHeight(60)
        pv_layout.addWidget(self.pv_mpp_text)
        btn_text_layout.addLayout(pv_layout)

        right_layout.addLayout(btn_text_layout)

        self.fig, self.ax1 = plt.subplots(figsize=(7, 5))
        self.canvas = FigureCanvas(self.fig)
        right_layout.addWidget(self.canvas, stretch=1)
        main_layout.addLayout(right_layout, stretch=1)
        self.setLayout(main_layout)

        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(1000)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_annotation)

        self.cursor = None
        self.current_csv_path = None

        self.voltage = []
        self.current = []
        self.power = []
        self.line_iv = None
        self.line_pv = None
        self.mpp_marker_iv = None
        self.mpp_marker_pv = None

    def load_and_plot(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 CSV 文件", "", "CSV Files (*.csv)")
        if not path:
            return

        try:
            self.current_csv_path = path
            with open(path, 'r', encoding='gbk') as f:
                lines = f.readlines()

            start_index = -1
            for idx, line in enumerate(lines):
                if 'Current' in line and 'Voltage' in line:
                    start_index = idx
                    break
            if start_index == -1:
                raise ValueError("未找到有效数据头 Current,Voltage")

            # ✅ 查找 Test date 行
            test_date_index = -1
            for idx, line in enumerate(lines):
                if "Test date" in line:
                    test_date_index = idx
                    break

            if test_date_index == -1 or test_date_index >= start_index:
                raise ValueError("无法找到 Test date 到数据头之间的内容")

            # ✅ 只展示 Test date 和 Current 之间的内容（不含 Test date 行和数据头行）
            param_lines = lines[test_date_index + 1 : start_index]
            self.param_text.setPlainText(''.join(param_lines).strip())

            current = []
            voltage = []
            reader = csv.reader(lines[start_index + 1:])
            for row in reader:
                if len(row) >= 2:
                    try:
                        i = float(row[0])
                        v = float(row[1])
                        current.append(i)
                        voltage.append(v)
                    except ValueError:
                        continue

            if not current:
                raise ValueError("没有有效的数值数据")

            power = [i * v for i, v in zip(current, voltage)]
            self.voltage = voltage
            self.current = current
            self.power = power

            self.plot_curves()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载或解析 CSV 失败：\n{e}")

    def plot_curves(self):
        self.fig.clf()
        self.ax1 = self.fig.add_subplot(111)
        ax2 = self.ax1.twinx()

        max_p_index = self.power.index(max(self.power))
        mpp_v = self.voltage[max_p_index]
        mpp_i = self.current[max_p_index]
        mpp_p = self.power[max_p_index]

        self.line_iv, = self.ax1.plot(self.voltage, self.current, label='I-V 曲线', color='blue', linewidth=1)
        self.line_pv, = ax2.plot(self.voltage, self.power, label='P-V 曲线', color='red', linewidth=1)

        self.mpp_marker_iv = self.ax1.scatter(mpp_v, mpp_i, color='blue', marker='o', s=50, zorder=3)
        self.mpp_marker_pv = ax2.scatter(mpp_v, mpp_p, color='red', marker='x', s=50, zorder=3)

        self.ax1.set_xlabel('电压 (V)')
        self.ax1.set_ylabel('电流 (A)', color='blue')
        self.ax1.tick_params(axis='y', labelcolor='blue')
        self.ax1.grid(True)

        ax2.set_ylabel('功率 (W)', color='red')
        ax2.tick_params(axis='y', labelcolor='red')

        csv_name = os.path.basename(self.current_csv_path) if self.current_csv_path else "IV/PV"
        self.fig.suptitle(f"{csv_name} IV/PV", fontsize=14)
        self.fig.tight_layout(rect=[0, 0, 1, 0.95])

        self.iv_mpp_text.setPlainText(
            f"I-V 最大功率点:\n电压 V = {mpp_v:.3f} V\n电流 I = {mpp_i:.3f} A"
        )
        self.pv_mpp_text.setPlainText(
            f"P-V 最大功率点:\n电压 V = {mpp_v:.3f} V\n功率 P = {mpp_p:.3f} W"
        )

        self.update_visibility()

        if self.cursor:
            self.cursor.remove()
            self.cursor = None
        lines = []
        if self.iv_btn.isChecked():
            lines.append(self.line_iv)
        if self.pv_btn.isChecked():
            lines.append(self.line_pv)
        self.cursor = mplcursors.cursor(lines, hover=True)

        @self.cursor.connect("add")
        def on_add(sel):
            x, y = sel.target
            sel.annotation.set_text(f"x={x:.3f}\ny={y:.3f}")
            sel.annotation.get_bbox_patch().set_alpha(0.8)
            self.hide_timer.stop()

        @self.cursor.connect("remove")
        def on_remove(sel):
            self.hide_timer.start()

        self.canvas.draw()

    def hide_annotation(self):
        if self.cursor:
            for sel in self.cursor.selections:
                sel.annotation.set_visible(False)
            self.canvas.draw_idle()

    def update_visibility(self):
        iv_visible = self.iv_btn.isChecked()
        pv_visible = self.pv_btn.isChecked()

        if self.line_iv:
            self.line_iv.set_visible(iv_visible)
        if self.mpp_marker_iv:
            self.mpp_marker_iv.set_visible(iv_visible)

        if self.line_pv:
            self.line_pv.set_visible(pv_visible)
        if self.mpp_marker_pv:
            self.mpp_marker_pv.set_visible(pv_visible)

        self.canvas.draw_idle()

    def toggle_iv_curve(self):
        self.update_visibility()

    def toggle_pv_curve(self):
        self.update_visibility()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = CSVWaveformViewer()
    viewer.show()
    sys.exit(app.exec_())

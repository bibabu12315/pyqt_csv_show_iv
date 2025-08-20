import sys
import os
import csv
import chardet
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QMessageBox, QTextEdit, QLineEdit
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
        self.setFocusPolicy(Qt.StrongFocus)

        main_layout = QHBoxLayout()

        # 左侧布局
        left_layout = QVBoxLayout()
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("csv文件具体信息："))
        left_layout.addLayout(title_layout)

        # 上方文本框
        self.param_text = QTextEdit()
        self.param_text.setReadOnly(True)
        self.param_text.setMinimumWidth(350)

        # 下方文本框（MPP 信息）
        self.bottom_text = QTextEdit()
        self.bottom_text.setReadOnly(True)
        self.bottom_text.setMinimumWidth(350)
        self.bottom_text.setFixedHeight(150)

        left_layout.addWidget(self.param_text, stretch=3)
        left_layout.addWidget(self.bottom_text, stretch=1)

        # 加载按钮移到最下方
        self.load_btn = QPushButton("加载 CSV 并显示波形")
        self.load_btn.clicked.connect(self.load_and_plot)
        left_layout.addWidget(self.load_btn)

        main_layout.addLayout(left_layout)

        # 右侧布局
        right_layout = QVBoxLayout()
        self.fig, self.ax1 = plt.subplots(figsize=(7, 5))
        self.canvas = FigureCanvas(self.fig)
        right_layout.addWidget(self.canvas, stretch=1)

        # 右下角按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        self.iv_btn = QPushButton("I-V 曲线")
        self.iv_btn.setCheckable(True)
        self.iv_btn.setChecked(True)
        self.iv_btn.clicked.connect(self.toggle_iv_curve)

        self.pv_btn = QPushButton("P-V 曲线")
        self.pv_btn.setCheckable(True)
        self.pv_btn.setChecked(True)
        self.pv_btn.clicked.connect(self.toggle_pv_curve)

        self.prev_btn = QPushButton("上一张")
        self.prev_btn.clicked.connect(self.show_previous_csv)
        self.next_btn = QPushButton("下一张")
        self.next_btn.clicked.connect(self.show_next_csv)

        # 标注输入框和按钮
        self.input_center = QLineEdit()
        self.input_center.setPlaceholderText("中心电压 (V)")
        self.input_center.setFixedWidth(100)

        self.input_range = QLineEdit()
        self.input_range.setPlaceholderText("范围 ±V")
        self.input_range.setFixedWidth(100)

        self.mark_btn = QPushButton("标注")
        self.mark_btn.clicked.connect(self.add_annotation_rect)

        self.clear_btn = QPushButton("清除标志")
        self.clear_btn.clicked.connect(self.clear_annotations)

        btn_layout.addWidget(self.iv_btn)
        btn_layout.addWidget(self.pv_btn)
        btn_layout.addWidget(self.prev_btn)
        btn_layout.addWidget(self.next_btn)
        btn_layout.addWidget(self.input_center)
        btn_layout.addWidget(self.input_range)
        btn_layout.addWidget(self.mark_btn)
        btn_layout.addWidget(self.clear_btn)

        right_layout.addLayout(btn_layout)
        main_layout.addLayout(right_layout, stretch=1)
        self.setLayout(main_layout)

        # 定时器
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

        self.csv_files = []
        self.current_index = -1

        # 存储矩形标注对象和数值
        self.annotation_rects = []
        self.annotation_ranges = []  # (vmin, vmax)

    def load_and_plot(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 CSV 文件", "", "CSV Files (*.csv)")
        if not path:
            return

        try:
            folder = os.path.dirname(path)
            self.csv_files = sorted([os.path.abspath(os.path.join(folder, f))
                                    for f in os.listdir(folder) if f.lower().endswith(".csv")])
            self.current_index = self.csv_files.index(os.path.abspath(path))
            self.load_csv(path)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载 CSV 失败：\n{e}")

    # 键盘切换
    def keyPressEvent(self, event):
        if not hasattr(self, 'csv_files') or not self.csv_files:
            return super().keyPressEvent(event)

        if event.key() == Qt.Key_Right:
            self.current_index = (self.current_index + 1) % len(self.csv_files)
            self.load_csv(self.csv_files[self.current_index])
        elif event.key() == Qt.Key_Left:
            self.current_index = (self.current_index - 1) % len(self.csv_files)
            self.load_csv(self.csv_files[self.current_index])
        else:
            super().keyPressEvent(event)

    def load_csv(self, path):
        try:
            with open(path, 'rb') as f:
                rawdata = f.read()
                result = chardet.detect(rawdata)
                encoding = result['encoding']

            with open(path, 'r', encoding=encoding) as f:
                lines = f.readlines()

            self.current_csv_path = path

            start_index = -1
            for idx, line in enumerate(lines):
                if 'Current' in line and 'Voltage' in line:
                    start_index = idx
                    break
            if start_index == -1:
                raise ValueError("未找到有效数据头 Current,Voltage")

            test_date_index = -1
            for idx, line in enumerate(lines):
                if "Test date" in line:
                    test_date_index = idx
                    break

            if test_date_index == -1 or test_date_index >= start_index:
                raise ValueError("无法找到 Test date 到数据头之间的内容")

            param_lines = lines[test_date_index + 1: start_index]
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

    def show_previous_csv(self):
        if self.csv_files and self.current_index > 0:
            self.current_index -= 1
            self.load_csv(self.csv_files[self.current_index])

    def show_next_csv(self):
        if self.csv_files and self.current_index < len(self.csv_files) - 1:
            self.current_index += 1
            self.load_csv(self.csv_files[self.current_index])

    # 绘制曲线时，重绘已有标注
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

        self.bottom_text.setPlainText(
            f"I-V 最大功率点:\n电压 V = {mpp_v:.3f} V, 电流 I = {mpp_i:.3f} A\n"
            f"P-V 最大功率点:\n电压 V = {mpp_v:.3f} V, 功率 P = {mpp_p:.3f} W"
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
            
        # 重新绘制已有的标注矩形和中心线
        for (vmin, vmax, center_v) in self.annotation_ranges:
            rect = self.ax1.axvspan(vmin, vmax, color='green', alpha=0.2, zorder=0)
            line = self.ax1.axvline(center_v, color='green', linestyle='--', linewidth=1, alpha=0.7, zorder=1)
            self.annotation_rects.append((rect, line))

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

    # 添加标注矩形
    def add_annotation_rect(self):
        if len(self.annotation_ranges) >= 5:
            QMessageBox.warning(self, "提示", "最多只能添加 5 个标注区域！")
            return

        try:
            center_v = float(self.input_center.text())
            range_v = float(self.input_range.text())
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的电压值和范围！")
            return

        vmin = center_v - range_v
        vmax = center_v + range_v

        # 绘制浅色矩形
        rect = self.ax1.axvspan(vmin, vmax, color='green', alpha=0.2, zorder=0)

        # 绘制中心电压的竖直细线
        line = self.ax1.axvline(center_v, color='green', linestyle='--', linewidth=1, alpha=0.7, zorder=1)

        # 保存矩形和线，方便清除
        self.annotation_rects.append((rect, line))
        self.annotation_ranges.append((vmin, vmax, center_v))
        self.canvas.draw_idle()

    # 清除标志
    def clear_annotations(self):
        for rect, line in self.annotation_rects:
            rect.remove()
            line.remove()
        self.annotation_rects.clear()
        self.annotation_ranges.clear()
        self.canvas.draw_idle()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = CSVWaveformViewer()
    viewer.show()
    sys.exit(app.exec_())

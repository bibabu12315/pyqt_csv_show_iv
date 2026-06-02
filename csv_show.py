import sys
import os
import csv
import re
import chardet
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QMessageBox, QTextEdit, QLineEdit,
    QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
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
        self.setFont(QFont("Microsoft YaHei", 10))

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

        self.metric_scroll = QScrollArea()
        self.metric_scroll.setWidgetResizable(True)
        self.metric_scroll.setMinimumWidth(350)
        self.metric_scroll.setMinimumHeight(260)

        self.metric_widget = QWidget()
        self.metric_layout = QVBoxLayout(self.metric_widget)
        self.metric_layout.setContentsMargins(8, 8, 8, 8)
        self.metric_layout.setSpacing(10)
        self.metric_layout.addStretch()
        self.metric_scroll.setWidget(self.metric_widget)

        left_layout.addWidget(self.param_text, stretch=2)
        left_layout.addWidget(self.metric_scroll, stretch=3)

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

        self.fix_x_btn = QPushButton("固定 X 轴")
        self.fix_x_btn.setCheckable(True)
        self.fix_x_btn.toggled.connect(self.toggle_fixed_x_axis)

        self.fix_y_btn = QPushButton("固定 Y 轴")
        self.fix_y_btn.setCheckable(True)
        self.fix_y_btn.toggled.connect(self.toggle_fixed_y_axis)

        self.prev_btn = QPushButton("上一张")
        self.prev_btn.clicked.connect(self.show_previous_csv)
        self.next_btn = QPushButton("下一张")
        self.next_btn.clicked.connect(self.show_next_csv)

        self.input_x_max = QLineEdit()
        self.input_x_max.setPlaceholderText("X 轴最大值")
        self.input_x_max.setFixedWidth(100)
        self.input_x_max.returnPressed.connect(self.apply_manual_axis_limits)

        self.input_y_max = QLineEdit()
        self.input_y_max.setPlaceholderText("Y 轴最大值")
        self.input_y_max.setFixedWidth(100)
        self.input_y_max.returnPressed.connect(self.apply_manual_axis_limits)

        self.input_power_max = QLineEdit()
        self.input_power_max.setPlaceholderText("功率轴最大值")
        self.input_power_max.setFixedWidth(110)
        self.input_power_max.returnPressed.connect(self.apply_manual_axis_limits)

        self.apply_axis_btn = QPushButton("应用坐标")
        self.apply_axis_btn.clicked.connect(self.apply_manual_axis_limits)

        self.reset_axis_btn = QPushButton("恢复自动")
        self.reset_axis_btn.clicked.connect(self.reset_manual_axis_limits)

        btn_layout.addWidget(self.iv_btn)
        btn_layout.addWidget(self.pv_btn)
        btn_layout.addWidget(self.fix_x_btn)
        btn_layout.addWidget(self.fix_y_btn)
        btn_layout.addWidget(self.prev_btn)
        btn_layout.addWidget(self.next_btn)
        btn_layout.addWidget(self.input_x_max)
        btn_layout.addWidget(self.input_y_max)
        btn_layout.addWidget(self.input_power_max)
        btn_layout.addWidget(self.apply_axis_btn)
        btn_layout.addWidget(self.reset_axis_btn)

        right_layout.addLayout(btn_layout)
        main_layout.addLayout(right_layout, stretch=1)
        self.setLayout(main_layout)
        self.ax2 = None

        self.csv_files = []
        self.current_index = -1

        self.fixed_x_limits = None
        self.fixed_y1_limits = None
        self.fixed_y2_limits = None
        self.current_measurement_metrics = []

        self.update_metric_panel([], [])

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

            info_text, measurement_lines = self.extract_info_sections(
                lines,
                test_date_index,
                start_index
            )
            self.param_text.setPlainText(info_text)
            self.current_measurement_metrics = self.parse_parameter_lines(measurement_lines)

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

    def plot_curves(self):
        self.fig.clf()
        self.ax1 = self.fig.add_subplot(111)
        self.ax2 = self.ax1.twinx()

        max_p_index = self.power.index(max(self.power))
        mpp_v = self.voltage[max_p_index]
        mpp_i = self.current[max_p_index]
        mpp_p = self.power[max_p_index]

        self.line_iv, = self.ax1.plot(self.voltage, self.current, label='I-V 曲线', color='blue', linewidth=1)
        self.line_pv, = self.ax2.plot(self.voltage, self.power, label='P-V 曲线', color='red', linewidth=1)

        self.mpp_marker_iv = self.ax1.scatter(mpp_v, mpp_i, color='blue', marker='o', s=50, zorder=3)
        self.mpp_marker_pv = self.ax2.scatter(mpp_v, mpp_p, color='red', marker='x', s=50, zorder=3)

        self.ax1.set_xlabel('电压 (V)')
        self.ax1.set_ylabel('电流 (A)', color='blue')
        self.ax1.tick_params(axis='y', labelcolor='blue')
        self.ax1.grid(True)
        self.ax1.set_xlim(left=0)
        self.ax1.set_ylim(bottom=0)

        self.ax2.set_ylabel('功率 (W)', color='red')
        self.ax2.tick_params(axis='y', labelcolor='red')
        self.ax2.set_ylim(bottom=0)

        csv_name = os.path.basename(self.current_csv_path) if self.current_csv_path else "IV/PV"
        self.fig.suptitle(f"{csv_name} IV/PV", fontsize=14)
        self.fig.tight_layout(rect=[0, 0, 1, 0.95])

        self.apply_locked_axis_limits()
        self.update_metric_panel(self.current_measurement_metrics, [])

        self.update_visibility()

        if self.cursor is not None:
            old_cursor = self.cursor
            self.cursor = None
            if hasattr(old_cursor, 'remove') and callable(old_cursor.remove):
                old_cursor.remove()
        lines = []
        if self.iv_btn.isChecked():
            lines.append(self.line_iv)
        if self.pv_btn.isChecked():
            lines.append(self.line_pv)
        if lines:
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

    def toggle_fixed_x_axis(self, checked):
        if checked:
            self.capture_current_axis_limits(capture_x=True, capture_y=False)
        else:
            self.fixed_x_limits = None

    def toggle_fixed_y_axis(self, checked):
        if checked:
            self.capture_current_axis_limits(capture_x=False, capture_y=True)
        else:
            self.fixed_y1_limits = None
            self.fixed_y2_limits = None

    def capture_current_axis_limits(self, capture_x=False, capture_y=False):
        if capture_x and self.ax1 is not None:
            self.fixed_x_limits = self.ax1.get_xlim()
        if capture_y and self.ax1 is not None and self.ax2 is not None:
            self.fixed_y1_limits = self.ax1.get_ylim()
            self.fixed_y2_limits = self.ax2.get_ylim()

    def apply_locked_axis_limits(self):
        if self.fix_x_btn.isChecked():
            if self.fixed_x_limits is None:
                self.fixed_x_limits = self.ax1.get_xlim()
            self.ax1.set_xlim(self.fixed_x_limits)

        if self.fix_y_btn.isChecked():
            if self.fixed_y1_limits is None:
                self.fixed_y1_limits = self.ax1.get_ylim()
            if self.fixed_y2_limits is None and self.ax2 is not None:
                self.fixed_y2_limits = self.ax2.get_ylim()

            self.ax1.set_ylim(self.fixed_y1_limits)
            if self.ax2 is not None and self.fixed_y2_limits is not None:
                self.ax2.set_ylim(self.fixed_y2_limits)

    def apply_manual_axis_limits(self):
        if not self.voltage or not self.current:
            QMessageBox.warning(self, "提示", "请先加载 CSV 数据。")
            return

        x_text = self.input_x_max.text().strip()
        y_text = self.input_y_max.text().strip()
        power_text = self.input_power_max.text().strip()

        if not x_text and not y_text and not power_text:
            QMessageBox.warning(self, "提示", "请至少输入一个坐标轴最大值。")
            return

        try:
            if x_text:
                x_max = float(x_text)
                x_min = 0.0
                if x_max <= x_min:
                    raise ValueError("X 轴最大值必须大于当前最小值")
                self.fixed_x_limits = (x_min, x_max)
                self.fix_x_btn.setChecked(True)

            if y_text:
                y_max = float(y_text)
                y_min = 0.0
                if y_max <= y_min:
                    raise ValueError("Y 轴最大值必须大于当前最小值")
                self.fixed_y1_limits = (y_min, y_max)
                self.fix_y_btn.setChecked(True)

            if power_text:
                power_max = float(power_text)
                power_min = 0.0
                if power_max <= power_min:
                    raise ValueError("功率轴最大值必须大于当前最小值")
                self.fixed_y2_limits = (power_min, power_max)
                self.fix_y_btn.setChecked(True)

            if self.fix_y_btn.isChecked():
                if self.fixed_y1_limits is None:
                    self.fixed_y1_limits = self.ax1.get_ylim()
                if self.fixed_y2_limits is None and self.ax2 is not None:
                    self.fixed_y2_limits = self.ax2.get_ylim()

            self.apply_locked_axis_limits()
            self.canvas.draw_idle()

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", str(e))

    def reset_manual_axis_limits(self):
        self.input_x_max.clear()
        self.input_y_max.clear()
        self.input_power_max.clear()
        self.fix_x_btn.setChecked(False)
        self.fix_y_btn.setChecked(False)
        if self.voltage and self.current:
            self.plot_curves()

    def extract_info_sections(self, lines, test_date_index, start_index):
        raw_lines = lines[test_date_index + 1:start_index]
        ref_index = self.find_line_index(raw_lines, 'Reference component model')
        data_index = self.find_line_index(raw_lines, 'IV test data')
        eigenvalue_index = self.find_line_index(raw_lines, 'IV test eigenvalue')

        info_start = ref_index if ref_index != -1 else 0
        info_end = data_index + 1 if data_index != -1 else len(raw_lines)
        info_text = ''.join(raw_lines[info_start:info_end]).rstrip()

        measurement_start = eigenvalue_index + 1 if eigenvalue_index != -1 else len(raw_lines)
        measurement_end = data_index if data_index != -1 and data_index > measurement_start else len(raw_lines)
        measurement_lines = raw_lines[measurement_start:measurement_end]

        return info_text, measurement_lines

    def find_line_index(self, lines, keyword):
        keyword_lower = keyword.lower()
        for idx, line in enumerate(lines):
            if keyword_lower in line.lower():
                return idx
        return -1

    def parse_parameter_lines(self, lines):
        metric_order = ['Voc', 'Isc', 'Pm', 'Vm', 'Im', 'Irr', 'Tpv']
        metric_labels = {
            'Voc': 'Voc (V)',
            'Isc': 'Isc (A)',
            'Pm': 'Pm (W)',
            'Vm': 'Vm (V)',
            'Im': 'Im (A)',
            'Irr': 'Irr (W/m2)',
            'Tpv': 'Tpv (°)'
        }
        found_metrics = {}

        for raw_line in lines:
            line = raw_line.strip().strip('\ufeff')
            if not line:
                continue

            for metric_name in metric_order:
                if metric_name not in found_metrics:
                    metric_value = self.extract_metric_value(line, metric_name)
                    if metric_value is not None:
                        found_metrics[metric_name] = metric_value

        return [
            (metric_labels.get(metric_name, metric_name), found_metrics[metric_name])
            for metric_name in metric_order
            if metric_name in found_metrics
        ]

    def extract_metric_value(self, line, metric_name):
        pattern = rf'{metric_name}(?:\([^)]*\))?\s*=\s*([^,;\s]+)'
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def update_metric_panel(self, measurement_metrics, mpp_metrics):
        while self.metric_layout.count():
            item = self.metric_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if measurement_metrics:
            self.metric_layout.addWidget(self.create_metric_section(
                "测试参数",
                measurement_metrics,
                "#1d4ed8"
            ))

        if mpp_metrics:
            self.metric_layout.addWidget(self.create_metric_section(
                "最大功率点",
                mpp_metrics,
                "#b91c1c"
            ))

        if not measurement_metrics and not mpp_metrics:
            empty_label = QLabel("加载 CSV 后，这里会显示测量参数和最大功率点。")
            empty_label.setWordWrap(True)
            empty_label.setStyleSheet("color: #6b7280; padding: 10px;")
            self.metric_layout.addWidget(empty_label)

        self.metric_layout.addStretch()

    def create_metric_section(self, title, metrics, accent_color):
        section = QFrame()
        section.setStyleSheet(
            "QFrame {"
            "background: transparent;"
            "border: 1px solid #d4d4d8;"
            "border-radius: 6px;"
            "}"
        )

        layout = QVBoxLayout(section)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {accent_color}; padding: 2px 0 6px 0;"
        )
        layout.addWidget(title_label)

        for index, (key, value) in enumerate(metrics):
            row = QFrame()
            border_style = "border-bottom: 1px solid #e5e7eb;" if index < len(metrics) - 1 else "border: none;"
            row.setStyleSheet(f"QFrame {{{border_style}}}")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 6, 0, 6)
            row_layout.setSpacing(14)

            key_label = QLabel(key)
            key_label.setWordWrap(True)
            key_label.setMinimumWidth(150)
            key_label.setStyleSheet("color: #3f3f46; font-size: 15px; font-weight: 500;")

            value_label = QLabel(value)
            value_label.setWordWrap(True)
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_label.setStyleSheet("color: #18181b; font-size: 16px; font-weight: 500;")

            row_layout.addWidget(key_label, stretch=2)
            row_layout.addWidget(value_label, stretch=3)
            layout.addWidget(row)

        return section


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    viewer = CSVWaveformViewer()
    viewer.show()
    sys.exit(app.exec_())

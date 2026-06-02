import sys
import os
import csv
import re
import chardet
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QMessageBox, QTextEdit, QLineEdit,
    QScrollArea, QFrame, QSplitter, QGridLayout, QStackedWidget,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QFontMetrics
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import mplcursors


class ComparisonPlotPage(QWidget):
    def __init__(self, viewer, page_name):
        super().__init__()
        self.viewer = viewer
        self.page_name = page_name
        self.max_series = 5
        self.series_rows = []
        self.colors = ['#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed']
        self.last_series_data = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.fig, (self.ax_iv, self.ax_pv) = plt.subplots(2, 1, figsize=(7, 7))
        self.compare_canvas = FigureCanvas(self.fig)
        main_layout.addWidget(self.compare_canvas, stretch=1)

        self.metric_table = QTableWidget()
        self.metric_table.setColumnCount(8)
        self.metric_table.setRowCount(0)
        self.metric_table.setHorizontalHeaderLabels([
            "数据",
            "Voc",
            "Isc",
            "Pm",
            "Vm",
            "Im",
            "Irr",
            "Tpv"
        ])
        self.metric_table.verticalHeader().setVisible(False)
        self.metric_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.metric_table.setAlternatingRowColors(True)
        self.metric_table.setWordWrap(False)
        self.metric_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.metric_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.metric_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.metric_table)

        self.refresh_plot()

    def add_series_row(self, file_path=''):
        if not isinstance(file_path, str):
            file_path = ''
        if len(self.series_rows) >= self.max_series:
            return False

        self.series_rows.append({'path': file_path})
        return True

    def remove_series_at(self, index):
        if 0 <= index < len(self.series_rows):
            self.series_rows.pop(index)

    def update_series_path(self, index, file_path):
        if 0 <= index < len(self.series_rows):
            self.series_rows[index]['path'] = file_path

    def clear_all_rows(self):
        self.series_rows = []
        self.refresh_plot()

    def get_series_label(self, index):
        path = self.series_rows[index].get('path', '')
        return os.path.splitext(os.path.basename(path))[0] if path else ''

    def get_series_color(self, index):
        return self.colors[index % len(self.colors)]

    def collect_series_data(self):
        series_data = []
        for index, row_info in enumerate(self.series_rows):
            path = row_info.get('path', '')
            if isinstance(path, str):
                path = path.strip()
            if not path:
                continue

            parsed = self.viewer.parse_csv_file(path)
            parsed['display_name'] = os.path.splitext(os.path.basename(path))[0]
            parsed['color'] = self.colors[index % len(self.colors)]
            series_data.append(parsed)

        return series_data

    def refresh_plot(self):
        try:
            series_data = self.collect_series_data()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载对比数据失败：\n{e}")
            return

        self.last_series_data = series_data

        self.fig.clf()
        self.ax_iv = self.fig.add_subplot(211)
        self.ax_pv = self.fig.add_subplot(212)

        self.ax_iv.set_title('I-V 对比')
        self.ax_iv.set_xlabel('电压 (V)')
        self.ax_iv.set_ylabel('电流 (A)')
        self.ax_iv.grid(True)
        self.ax_iv.set_xlim(left=0)
        self.ax_iv.set_ylim(bottom=0)

        self.ax_pv.set_title('P-V 对比')
        self.ax_pv.set_xlabel('电压 (V)')
        self.ax_pv.set_ylabel('功率 (W)')
        self.ax_pv.grid(True)
        self.ax_pv.set_xlim(left=0)
        self.ax_pv.set_ylim(bottom=0)

        if series_data:
            for item in series_data:
                color = item['color']
                name = item['display_name']
                self.ax_iv.plot(item['voltage'], item['current'], color=color, linewidth=1.5, label=name)
                self.ax_pv.plot(item['voltage'], item['power'], color=color, linewidth=1.5, label=name)

                max_index = item['power'].index(max(item['power']))
                self.ax_iv.scatter(item['voltage'][max_index], item['current'][max_index], color=color, s=24, zorder=3)
                self.ax_pv.scatter(item['voltage'][max_index], item['power'][max_index], color=color, s=24, zorder=3)

            self.ax_iv.legend(loc='best', fontsize=9)
            self.ax_pv.legend(loc='best', fontsize=9)

            self.apply_auto_axis_limits(series_data)

        self.fig.tight_layout()
        self.compare_canvas.draw()
        self.update_metric_table(series_data)
        if self.viewer.compare_tabs.currentWidget() is self:
            self.viewer.refresh_compare_left_panel()

    def apply_auto_axis_limits(self, series_data):
        if not series_data:
            return

        max_voltage = max(max(item['voltage']) for item in series_data)
        max_current = max(max(item['current']) for item in series_data)
        max_power = max(max(item['power']) for item in series_data)

        x_padding = max(max_voltage * 0.05, 0.5)
        current_padding = max(max_current * 0.08, 0.2)
        power_padding = max(max_power * 0.08, 1.0)

        self.ax_iv.set_xlim(0, max_voltage + x_padding)
        self.ax_iv.set_ylim(0, max_current + current_padding)
        self.ax_pv.set_xlim(0, max_voltage + x_padding)
        self.ax_pv.set_ylim(0, max_power + power_padding)

    def update_metric_table(self, series_data):
        self.metric_table.clearContents()
        self.metric_table.setRowCount(len(series_data))

        for row_index, item in enumerate(series_data):
            row_values = [
                item['display_name'],
                item['metric_map'].get('Voc', ''),
                item['metric_map'].get('Isc', ''),
                item['metric_map'].get('Pm', ''),
                item['metric_map'].get('Vm', ''),
                item['metric_map'].get('Im', ''),
                item['metric_map'].get('Irr', ''),
                item['metric_map'].get('Tpv', ''),
            ]

            for column_index, value in enumerate(row_values):
                self.metric_table.setItem(row_index, column_index, QTableWidgetItem(value))

        if not series_data:
            self.metric_table.setRowCount(1)
            self.metric_table.setItem(0, 0, QTableWidgetItem('请先添加对比 CSV'))

        self.metric_table.resizeRowsToContents()
        header_height = self.metric_table.horizontalHeader().height()
        total_height = header_height
        for row_index in range(self.metric_table.rowCount()):
            total_height += self.metric_table.rowHeight(row_index)
        total_height += 8
        self.metric_table.setFixedHeight(min(max(total_height, 70), 220))


class CSVWaveformViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IV/PV 波形查看器")
        self.resize(1100, 700)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.metric_order = ['Voc', 'Isc', 'Pm', 'Vm', 'Im', 'Irr', 'Tpv']
        self.metric_labels = {
            'Voc': 'Voc (V)',
            'Isc': 'Isc (A)',
            'Pm': 'Pm (W)',
            'Vm': 'Vm (V)',
            'Im': 'Im (A)',
            'Irr': 'Irr (W/m2)',
            'Tpv': 'Tpv (°)'
        }

        main_layout = QHBoxLayout()

        self.left_stack = QStackedWidget()
        self.left_stack.setMinimumWidth(350)
        self.single_left_page = self.create_single_left_page()
        self.compare_left_page = self.create_compare_left_page()
        self.left_stack.addWidget(self.single_left_page)
        self.left_stack.addWidget(self.compare_left_page)
        main_layout.addWidget(self.left_stack)

        # 右侧布局
        right_layout = QVBoxLayout()
        mode_layout = QHBoxLayout()
        self.single_mode_btn = QPushButton("单文件模式")
        self.single_mode_btn.setCheckable(True)
        self.single_mode_btn.setChecked(True)
        self.single_mode_btn.clicked.connect(lambda: self.switch_right_mode('single'))

        self.compare_mode_btn = QPushButton("对比分析模式")
        self.compare_mode_btn.setCheckable(True)
        self.compare_mode_btn.clicked.connect(lambda: self.switch_right_mode('compare'))

        mode_layout.addWidget(self.single_mode_btn)
        mode_layout.addWidget(self.compare_mode_btn)
        mode_layout.addStretch(1)
        right_layout.addLayout(mode_layout)

        self.right_stack = QStackedWidget()
        right_layout.addWidget(self.right_stack, stretch=1)

        self.single_mode_page = QWidget()
        single_layout = QVBoxLayout(self.single_mode_page)
        single_layout.setContentsMargins(0, 0, 0, 0)
        self.fig, self.ax1 = plt.subplots(figsize=(7, 5))
        self.canvas = FigureCanvas(self.fig)
        single_layout.addWidget(self.canvas, stretch=1)

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

        single_layout.addLayout(btn_layout)

        self.compare_mode_page = self.create_compare_mode_page()
        self.right_stack.addWidget(self.single_mode_page)
        self.right_stack.addWidget(self.compare_mode_page)

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
        self.ax2 = None

        self.csv_files = []
        self.current_index = -1

        self.fixed_x_limits = None
        self.fixed_y1_limits = None
        self.fixed_y2_limits = None
        self.current_measurement_metrics = []
        self.compare_page_counter = 0

        self.update_metric_panel([], [])
        self.add_compare_canvas()

    def create_single_left_page(self):
        page = QWidget()
        left_layout = QVBoxLayout(page)
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("csv文件具体信息："))
        left_layout.addLayout(title_layout)

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

        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.addWidget(self.param_text)
        self.left_splitter.addWidget(self.metric_scroll)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.setStretchFactor(0, 2)
        self.left_splitter.setStretchFactor(1, 3)
        self.left_splitter.setSizes([320, 380])
        left_layout.addWidget(self.left_splitter, stretch=1)

        self.load_btn = QPushButton("加载 CSV 并显示波形")
        self.load_btn.clicked.connect(self.load_and_plot)
        left_layout.addWidget(self.load_btn)
        return page

    def create_compare_left_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_label = QLabel("对比分析控制")
        title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1f2937; padding: 0 0 4px 0;")
        layout.addWidget(title_label)

        button_layout = QHBoxLayout()
        self.left_add_csv_btn = QPushButton("添加 CSV")
        self.left_add_csv_btn.clicked.connect(self.add_csv_to_current_compare_page)
        self.left_refresh_compare_btn = QPushButton("更新对比图")
        self.left_refresh_compare_btn.clicked.connect(self.refresh_current_compare_page)
        self.left_clear_compare_btn = QPushButton("清空当前画布")
        self.left_clear_compare_btn.clicked.connect(self.clear_current_compare_page)
        button_layout.addWidget(self.left_add_csv_btn)
        button_layout.addWidget(self.left_refresh_compare_btn)
        button_layout.addWidget(self.left_clear_compare_btn)
        layout.addLayout(button_layout)

        self.compare_series_title = QLabel("当前画布数据")
        self.compare_series_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")
        layout.addWidget(self.compare_series_title)

        self.compare_series_container = QWidget()
        self.compare_series_layout = QGridLayout(self.compare_series_container)
        self.compare_series_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_series_layout.setHorizontalSpacing(6)
        self.compare_series_layout.setVerticalSpacing(6)
        layout.addWidget(self.compare_series_container)
        layout.addStretch(1)
        return page

    def create_compare_mode_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.add_compare_canvas_btn = QPushButton("新增分析画布")
        self.add_compare_canvas_btn.clicked.connect(self.add_compare_canvas)
        self.remove_compare_canvas_btn = QPushButton("删除当前画布")
        self.remove_compare_canvas_btn.clicked.connect(self.remove_current_compare_canvas)

        self.compare_tabs = QTabWidget()
        self.compare_tabs.currentChanged.connect(lambda index: self.refresh_compare_left_panel())
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(6)
        corner_layout.addWidget(self.add_compare_canvas_btn)
        corner_layout.addWidget(self.remove_compare_canvas_btn)
        self.compare_tabs.setCornerWidget(corner_widget, Qt.TopRightCorner)
        layout.addWidget(self.compare_tabs)
        return page

    def switch_right_mode(self, mode):
        is_single = mode == 'single'
        self.single_mode_btn.setChecked(is_single)
        self.compare_mode_btn.setChecked(not is_single)
        self.left_stack.setCurrentWidget(self.single_left_page if is_single else self.compare_left_page)
        self.right_stack.setCurrentWidget(self.single_mode_page if is_single else self.compare_mode_page)
        if not is_single:
            self.refresh_compare_left_panel()

    def add_compare_canvas(self):
        self.compare_page_counter += 1
        tab_name = f"分析页 {self.compare_page_counter}"
        page = ComparisonPlotPage(self, tab_name)
        self.compare_tabs.addTab(page, tab_name)
        self.compare_tabs.setCurrentWidget(page)
        self.refresh_compare_left_panel()

    def remove_current_compare_canvas(self):
        current_index = self.compare_tabs.currentIndex()
        if current_index == -1:
            return
        if self.compare_tabs.count() == 1:
            QMessageBox.information(self, "提示", "至少保留一个分析画布。")
            return
        widget = self.compare_tabs.widget(current_index)
        self.compare_tabs.removeTab(current_index)
        widget.deleteLater()
        self.refresh_compare_left_panel()

    def current_compare_page(self):
        return self.compare_tabs.currentWidget()

    def add_csv_to_current_compare_page(self):
        page = self.current_compare_page()
        if page is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择对比 CSV 文件", "", "CSV Files (*.csv)")
        if not path:
            return
        if not page.add_series_row(path):
            QMessageBox.information(self, "提示", "单个分析画布最多支持 5 个 CSV。")
            return
        page.refresh_plot()
        self.refresh_compare_left_panel()

    def refresh_current_compare_page(self):
        page = self.current_compare_page()
        if page is not None:
            page.refresh_plot()

    def clear_current_compare_page(self):
        page = self.current_compare_page()
        if page is not None:
            page.clear_all_rows()
            self.refresh_compare_left_panel()

    def remove_series_from_current_compare_page(self, index):
        page = self.current_compare_page()
        if page is None:
            return
        page.remove_series_at(index)
        page.refresh_plot()
        self.refresh_compare_left_panel()

    def select_series_file_for_current_compare_page(self, index):
        page = self.current_compare_page()
        if page is None or not (0 <= index < len(page.series_rows)):
            return

        current_path = page.series_rows[index].get('path', '')
        start_dir = os.path.dirname(current_path) if current_path else ''
        path, _ = QFileDialog.getOpenFileName(self, "重新选择对比 CSV 文件", start_dir, "CSV Files (*.csv)")
        if not path:
            return

        page.update_series_path(index, path)
        page.refresh_plot()
        self.refresh_compare_left_panel()

    def clear_layout_widgets(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self.clear_layout_widgets(child_layout)

    def refresh_compare_left_panel(self):
        page = self.current_compare_page()
        self.clear_layout_widgets(self.compare_series_layout)

        if page is None:
            return

        if not page.series_rows:
            empty_label = QLabel("当前画布还没有添加 CSV。")
            empty_label.setStyleSheet("color: #6b7280; padding: 8px 0;")
            self.compare_series_layout.addWidget(empty_label, 0, 0)
        else:
            for index, row_info in enumerate(page.series_rows):
                slot = QFrame()
                slot.setStyleSheet("QFrame { border: 1px solid #e5e7eb; border-radius: 6px; background: #fafafa; }")
                slot_layout = QVBoxLayout(slot)
                slot_layout.setContentsMargins(8, 6, 8, 6)
                slot_layout.setSpacing(4)

                path = row_info.get('path', '')
                file_name = os.path.basename(path) if path else '未选择'
                color = page.get_series_color(index) if path else '#6b7280'

                name_edit = QLineEdit()
                name_edit.setReadOnly(True)
                name_edit.setText(file_name)
                name_edit.setCursorPosition(0)
                name_edit.setToolTip(path)
                name_edit.setPlaceholderText('未选择')
                name_edit.setStyleSheet(
                    f"color: {color}; font-size: 12px; font-weight: 600; background: white;"
                )

                button_row = QHBoxLayout()
                button_row.setContentsMargins(0, 0, 0, 0)
                button_row.setSpacing(6)

                select_btn = QPushButton("选择")
                select_btn.setFixedHeight(22)
                select_btn.clicked.connect(
                    lambda checked=False, idx=index: self.select_series_file_for_current_compare_page(idx)
                )

                remove_btn = QPushButton("移除")
                remove_btn.setFixedHeight(22)
                remove_btn.clicked.connect(lambda checked=False, idx=index: self.remove_series_from_current_compare_page(idx))

                button_row.addWidget(select_btn)
                button_row.addWidget(remove_btn)

                slot_layout.addWidget(name_edit)
                slot_layout.addLayout(button_row)

                row = index
                column = 0
                self.compare_series_layout.addWidget(slot, row, column)

            self.compare_series_layout.setColumnStretch(0, 1)

    def elide_text(self, text, width):
        metrics = QFontMetrics(self.font())
        return metrics.elidedText(text, Qt.ElideRight, width)

    def parse_csv_file(self, path):
        with open(path, 'rb') as f:
            rawdata = f.read()
            result = chardet.detect(rawdata)
            encoding = result['encoding']

        with open(path, 'r', encoding=encoding) as f:
            lines = f.readlines()

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

        info_text, measurement_lines = self.extract_info_sections(lines, test_date_index, start_index)
        metric_map = self.parse_parameter_map(measurement_lines)
        display_metrics = [
            (self.metric_labels.get(metric_name, metric_name), metric_map[metric_name])
            for metric_name in self.metric_order
            if metric_name in metric_map
        ]

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
        return {
            'path': path,
            'csv_name': os.path.basename(path),
            'info_text': info_text,
            'metric_map': metric_map,
            'display_metrics': display_metrics,
            'voltage': voltage,
            'current': current,
            'power': power,
        }

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
            self.switch_right_mode('single')

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
            parsed = self.parse_csv_file(path)
            self.current_csv_path = path
            self.param_text.setPlainText(parsed['info_text'])
            self.current_measurement_metrics = parsed['display_metrics']
            self.voltage = parsed['voltage']
            self.current = parsed['current']
            self.power = parsed['power']

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
        metric_map = self.parse_parameter_map(lines)
        return [
            (self.metric_labels.get(metric_name, metric_name), metric_map[metric_name])
            for metric_name in self.metric_order
            if metric_name in metric_map
        ]

    def parse_parameter_map(self, lines):
        found_metrics = {}

        for raw_line in lines:
            line = raw_line.strip().strip('\ufeff')
            if not line:
                continue

            for metric_name in self.metric_order:
                if metric_name not in found_metrics:
                    metric_value = self.extract_metric_value(line, metric_name)
                    if metric_value is not None:
                        found_metrics[metric_name] = metric_value

        return found_metrics

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
        highlight_keys = {'Vm', 'Im', 'Pm', 'Irr'}
        highlight_color = '#b91c1c'

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

        header = QFrame()
        header.setStyleSheet("QFrame { background: #f4f4f5; border-radius: 4px; }")
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setHorizontalSpacing(16)
        header_layout.setVerticalSpacing(0)

        header_key = QLabel("参数")
        header_key.setStyleSheet("color: #52525b; font-size: 13px; font-weight: 600;")
        header_value = QLabel("数值")
        header_value.setStyleSheet("color: #52525b; font-size: 13px; font-weight: 600;")
        header_layout.addWidget(header_key, 0, 0)
        header_layout.addWidget(header_value, 0, 1)
        layout.addWidget(header)

        table = QWidget()
        table_layout = QGridLayout(table)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setHorizontalSpacing(16)
        table_layout.setVerticalSpacing(0)
        table_layout.setColumnStretch(0, 2)
        table_layout.setColumnStretch(1, 3)

        for index, (key, value) in enumerate(metrics):
            key_name = key.split(' ', 1)[0]
            is_highlighted = key_name in highlight_keys

            key_label = QLabel(key)
            key_label.setWordWrap(True)
            key_label.setMinimumWidth(150)
            key_label.setStyleSheet(
                f"color: {highlight_color if is_highlighted else '#3f3f46'}; font-size: 15px; font-weight: {'600' if is_highlighted else '500'}; padding: 8px 0; border-bottom: {'1px solid #e5e7eb' if index < len(metrics) - 1 else 'none'};"
            )

            value_label = QLabel(value)
            value_label.setWordWrap(True)
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_label.setStyleSheet(
                f"color: {highlight_color if is_highlighted else '#18181b'}; font-size: 16px; font-weight: {'600' if is_highlighted else '500'}; padding: 8px 0; border-bottom: {'1px solid #e5e7eb' if index < len(metrics) - 1 else 'none'};"
            )

            table_layout.addWidget(key_label, index, 0)
            table_layout.addWidget(value_label, index, 1)

        layout.addWidget(table)

        return section


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    viewer = CSVWaveformViewer()
    viewer.show()
    sys.exit(app.exec_())

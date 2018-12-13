import os

import appdirs
import numpy as np
from PyQt5.QtCore import pyqtSignal, Qt, QByteArray
from PyQt5.QtGui import QGuiApplication, QIcon
from PyQt5.QtWidgets import QWidget, QPushButton, QHBoxLayout, QFileDialog, QMessageBox, QVBoxLayout, QCheckBox, \
    QComboBox, QDoubleSpinBox, QSpinBox, QStackedLayout, QProgressBar, QLabel, QAbstractSpinBox, QFormLayout, \
    QTabWidget, QSizePolicy

from common_gui.algorithms_description import AlgorithmSettingsWidget
from common_gui.channel_control import ChannelControl
from common_gui.colors_choose import ColorSelector
from common_gui.flow_layout import FlowLayout
from common_gui.select_multiple_files import AddFiles
from common_gui.stack_image_view import ColorBar
from common_gui.universal_gui_part import right_label
from common_gui.waiting_dialog import WaitingDialog
from partseg_utils.global_settings import static_file_folder
from partseg_utils.segmentation.algorithm_base import SegmentationResult
from partseg_utils.universal_const import UNITS_LIST, UNIT_SCALE
from project_utils_qt.error_dialog import ErrorDialog
from project_utils_qt.image_read_thread import ImageReaderThread
from project_utils_qt.main_window import BaseMainWindow
from project_utils_qt.execute_function_thread import ExecuteFunctionThread
from stackseg.stack_algorithm.algorithm_description import stack_algorithm_dict
from stackseg.stack_settings import StackSettings
from tiff_image import ImageReader, Image
from .batch_proceed import BatchProceed
from .image_view import StackImageView
from .io_functions import load_stack_segmentation

app_name = "StackSeg"
app_lab = "LFSG"

config_folder = appdirs.user_data_dir(app_name, app_lab)


class MainMenu(QWidget):
    image_loaded = pyqtSignal()

    def __init__(self, settings):
        """
        :type settings: StackSettings
        :param settings:
        """
        super(MainMenu, self).__init__()
        self.settings = settings
        self.segmentation_cache = None
        self.read_thread = None
        self.load_image_btn = QPushButton("Load image")
        self.load_image_btn.clicked.connect(self.load_image)
        self.load_segmentation_btn = QPushButton("Load segmentation")
        self.load_segmentation_btn.clicked.connect(self.load_segmentation)
        self.save_segmentation_btn = QPushButton("Save segmentation")
        self.save_segmentation_btn.clicked.connect(self.save_segmentation)
        self.save_catted_parts = QPushButton("Save components")
        self.save_catted_parts.clicked.connect(self.save_result)
        self.setContentsMargins(0, 0, 0, 0)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.load_image_btn)
        layout.addWidget(self.load_segmentation_btn)
        layout.addWidget(self.save_catted_parts)
        layout.addWidget(self.save_segmentation_btn)
        self.setLayout(layout)

    def load_image(self):
        #TODO move segmentation with image load to load_segmentaion
        try:
            dial = QFileDialog()
            dial.setFileMode(QFileDialog.ExistingFile)
            dial.setDirectory(self.settings.get("io.load_image_directory", ""))
            filters = ["raw image (*.tiff *.tif *.lsm)", "image from mask (*.seg *.tgz)"]
            dial.setNameFilters(filters)
            dial.selectNameFilter(self.settings.get("io.load_image_filter", filters[0]))
            if not dial.exec_():
                return
            file_path = str(dial.selectedFiles()[0])
            self.settings.set("io.load_image_directory", os.path.dirname(str(file_path)))
            self.settings.set("io.load_image_filter", dial.selectedNameFilter())
            read_thread = ImageReaderThread(parent=self)

            def exception_hook(exception):
                if isinstance(exception, ValueError) and exception.args[0] == "not a TIFF file":
                    QMessageBox.warning(self, "Open error", "Image is not proper tiff/lsm image")
                elif isinstance(exception, MemoryError):
                    QMessageBox.warning(self, "Open error", "Not enough memory to read this image")
                elif isinstance(exception, IOError):
                    QMessageBox.warning(self, "Open error", "Some problem with reading from disc")
                else:
                    raise exception

            if dial.selectedNameFilter() == filters[1]:
                segmentation, metadata = load_stack_segmentation(file_path)
                if "base_file" not in metadata:
                    QMessageBox.warning(self, "Open error", "No information about base file")
                if not os.path.exists(metadata["base_file"]):
                    QMessageBox.warning(self, "Open error", "Base file not found")
                read_thread.set_path(metadata["base_file"])
                dial = WaitingDialog(read_thread, "Load image", exception_hook=exception_hook)
                dial.exec()
                self.set_image(read_thread.image)
                self.settings.set_segmentation(segmentation, metadata)
            else:
                read_thread.set_path(file_path)
                dial = WaitingDialog(read_thread, "Load image", exception_hook=exception_hook)
                dial.exec()
                if read_thread.image:
                    self.set_image(read_thread.image)

        except (MemoryError, IOError) as e:
            QMessageBox.warning(self, "Open error", "Exception occurred {}".format(e))

        except Exception as e:
            ErrorDialog(e, "Image read").exec()

        # self.image_loaded.emit()

    def set_image(self, image: Image) -> bool:
        if image.is_time:
            if image.is_stack:
                QMessageBox.warning(
                    self, "Not supported", "Data that are time data are currently not supported")
                return False
            else:
                res = QMessageBox.question(
                    self, "Not supported",
                    "Time data are currently not supported. Maybe You would like to treat time as z-stack",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

                if res == QMessageBox.Yes:
                    image.swap_time_and_stack()
                else:
                    return False
        self.settings.image = image
        return True

    def load_segmentation(self):
        try:
            dial = QFileDialog()
            dial.setFileMode(QFileDialog.ExistingFile)
            dial.setDirectory(self.settings.get("io.open_segmentation_directory", ""))
            filters = ["segmentation (*.seg *.tgz)"]
            dial.setNameFilters(filters)
            if not dial.exec_():
                return
            file_path = str(dial.selectedFiles()[0])
            self.settings.set("io.open_segmentation_directory", os.path.dirname(str(file_path)))
            execute_thread = ExecuteFunctionThread(self.settings.load_segmentation, [file_path])

            def exception_hook(exception):
                if isinstance(exception, ValueError) and exception.args[0] == "Segmentation do not fit to image":
                    QMessageBox.warning(self, "Open error", "Segmentation do not fit to image")
                elif isinstance(exception, MemoryError):
                    QMessageBox.warning(self, "Open error", "Not enough memory to read this image")
                elif isinstance(exception, IOError):
                    QMessageBox.warning(self, "Open error", "Some problem with reading from disc")
                else:
                    raise exception

            dial = WaitingDialog(execute_thread, "Load segmentation", exception_hook=exception_hook)
            dial.exec()
        except Exception as e:
            QMessageBox.warning(self, "Open error", "Exception occurred {}".format(e))

    def save_segmentation(self):
        if self.settings.segmentation is None:
            QMessageBox.warning(self, "No segmentation", "No segmentation to save")
            return
        dial = QFileDialog()
        dial.setFileMode(QFileDialog.AnyFile)
        dial.setDirectory(self.settings.get("io.save_segmentation_directory", ""))
        dial.setAcceptMode(QFileDialog.AcceptSave)
        dial.selectFile(os.path.splitext(os.path.basename(self.settings.image_path))[0] + ".seg")
        filters = ["segmentation (*.seg *.tgz)"]
        dial.setNameFilters(filters)
        if not dial.exec_():
            return
        file_path = str(dial.selectedFiles()[0])
        self.settings.set("io.save_segmentation_directory", os.path.dirname(str(file_path)))
        # self.settings.save_directory = os.path.dirname(str(file_path))
        try:
            execute_thread = ExecuteFunctionThread(self.settings.save_segmentation, [file_path])
            dial = WaitingDialog(execute_thread, "Save segmentation")
            dial.exec()
        except IOError as e:
            QMessageBox.critical(self, "Save error", f"Error on disc operation. Text: {e}", QMessageBox.Ok)
        except Exception as e:
            ErrorDialog(e, "Image read").exec()

    def save_result(self):
        if self.settings.image_path is not None and \
                QMessageBox.Yes == QMessageBox.question(self, "Copy", "Copy name to clipboard?",
                                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes):
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(os.path.splitext(os.path.basename(self.settings.image_path))[0])

        if self.settings.segmentation is None:
            QMessageBox.warning(self, "No components", "No components to save")
            return
        dial = QFileDialog()
        dial.setFileMode(QFileDialog.Directory)
        dial.setDirectory(self.settings.get("io.save_components_directory", ""))
        dial.selectFile(os.path.splitext(os.path.basename(self.settings.image_path))[0])
        if not dial.exec_():
            return
        dir_path = str(dial.selectedFiles()[0])
        potential_names = self.settings.get_file_names_for_save_result(dir_path)
        print("\n".join(potential_names))
        conflict = []
        for el in potential_names:
            if os.path.exists(el):
                conflict.append(el)
        if len(conflict) > 0:
            # TODO modify because of long lists
            conflict_str = "\n".join(conflict)
            if QMessageBox.No == QMessageBox.warning(self, "Overwrite", f"Overwrite files:\n {conflict_str}",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No):
                self.save_result()
                return

        self.settings.set("io.save_components_directory", os.path.dirname(str(dir_path)))
        try:
            execute_thread = ExecuteFunctionThread(self.settings.save_components, [dir_path])
            dial = WaitingDialog(execute_thread, "Save components")
            dial.exec()
        except IOError as e:
            QMessageBox.critical(self, "Save error", f"Error on disc operation. Text: {e}", QMessageBox.Ok)
        except Exception as e:
            ErrorDialog(e, "Save error").exec()


class ComponentCheckBox(QCheckBox):
    mouse_enter = pyqtSignal(int)
    mouse_leave = pyqtSignal(int)

    def __init__(self, number: int, parent=None):
        super().__init__(str(number), parent)
        self.number = number

    def enterEvent(self, event):
        self.mouse_enter.emit(self.number)

    def leaveEvent(self, event):
        self.mouse_leave.emit(self.number)


class ChosenComponents(QWidget):
    """
    :type check_box: dict[int, QCheckBox]
    """
    check_change_signal = pyqtSignal()
    mouse_enter = pyqtSignal(int)
    mouse_leave = pyqtSignal(int)

    def __init__(self):
        super(ChosenComponents, self).__init__()
        # self.setLayout(FlowLayout())
        self.check_box = dict()
        self.check_all_btn = QPushButton("Select all")
        self.check_all_btn.clicked.connect(self.check_all)
        self.un_check_all_btn = QPushButton("Unselect all")
        self.un_check_all_btn.clicked.connect(self.un_check_all)
        main_layout = QVBoxLayout()
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.check_all_btn)
        btn_layout.addWidget(self.un_check_all_btn)
        self.check_layout = FlowLayout()
        main_layout.addLayout(btn_layout)
        main_layout.addLayout(self.check_layout)
        self.setLayout(main_layout)

    def other_component_choose(self, num):
        check = self.check_box[num]
        check.setChecked(not check.isChecked())

    def check_all(self):
        for el in self.check_box.values():
            el.setChecked(True)

    def un_check_all(self):
        for el in self.check_box.values():
            el.setChecked(False)

    def remove_components(self):
        self.check_layout.clear()
        for el in self.check_box.values():
            """:type el: ComponentCheckBox"""
            el.deleteLater()
            el.stateChanged.disconnect()
            el.mouse_leave.disconnect()
            el.mouse_enter.disconnect()
        self.check_box.clear()

    def new_choose(self, num, chosen_components):
        self.set_chose(range(1, num + 1), chosen_components)

    def set_chose(self, components_index, chosen_components):
        chosen_components = set(chosen_components)
        self.blockSignals(True)
        self.remove_components()
        chosen_components = set(chosen_components)
        for el in components_index:
            check = ComponentCheckBox(el)
            if el in chosen_components:
                check.setChecked(True)
            check.stateChanged.connect(self.check_change)
            check.mouse_enter.connect(self.mouse_enter.emit)
            check.mouse_leave.connect(self.mouse_leave.emit)
            self.check_box[el] = check
            self.check_layout.addWidget(check)
        self.blockSignals(False)
        self.update()
        self.check_change_signal.emit()

    def check_change(self):
        self.check_change_signal.emit()

    def change_state(self, num, val):
        self.check_box[num].setChecked(val)

    def get_state(self, num: int) -> bool:
        return self.check_box[num].isChecked()

    def get_chosen(self):
        res = []
        for num, check in self.check_box.items():
            if check.isChecked():
                res.append(num)
        return res

    def get_mask(self):
        res = [0]
        for _, check in sorted(self.check_box.items()):
            res.append(check.isChecked())
        return np.array(res, dtype=np.uint8)


class AlgorithmOptions(QWidget):
    def __init__(self, settings, image_view, component_checker):
        """
        :type image_view: StackImageView
        :type settings: StackSettings
        :param settings:
        """
        control_view = image_view.get_control_view()
        super(AlgorithmOptions, self).__init__()
        self.settings = settings
        self.algorithm_choose = QComboBox()
        self.show_result = QComboBox()  # QCheckBox("Show result")
        self.show_result.addItems(["Not show", "Show results", "Show choosen"])
        self.show_result.setCurrentIndex(control_view.show_label)
        self.opacity = QDoubleSpinBox()
        self.opacity.setRange(0, 1)
        self.opacity.setSingleStep(0.1)
        self.opacity.setValue(control_view.opacity)
        self.only_borders = QCheckBox("Only borders")
        self.only_borders.setChecked(control_view.only_borders)
        self.borders_thick = QSpinBox()
        self.borders_thick.setRange(1, 11)
        self.borders_thick.setSingleStep(2)
        self.borders_thick.setValue(control_view.borders_thick)
        # noinspection PyUnresolvedReferences
        self.borders_thick.valueChanged.connect(self.border_value_check)
        self.execute_btn = QPushButton("Execute")
        self.execute_all_btn = QPushButton("Execute all")
        self.execute_all_btn.setDisabled(True)
        self.block_execute_all_btn = False
        self.stack_layout = QStackedLayout()
        self.choose_components = ChosenComponents()
        self.choose_components.check_change_signal.connect(control_view.components_change)
        self.choose_components.mouse_leave.connect(image_view.component_unmark)
        self.choose_components.mouse_enter.connect(image_view.component_mark)
        widgets_list = []
        # TODO restore refresh channels num
        for name, val in stack_algorithm_dict.items():
            self.algorithm_choose.addItem(name)
            widget = AlgorithmSettingsWidget(settings, name, val)
            widgets_list.append(widget)
            widget.algorithm_thread.execution_done.connect(self.execution_done)
            widget.algorithm_thread.progress_signal.connect(self.progress_info)
            widget.algorithm_thread.finished.connect(self.execution_finished)
            self.stack_layout.addWidget(widget)
        # WARNING works only with one channels algorithms
        # SynchronizeValues.add_synchronization("channels_chose", widgets_list)
        self.chosen_list = []
        self.progress_bar = QProgressBar()
        self.progress_bar.setHidden(True)
        self.progress_info_lab = QLabel()
        self.progress_info_lab.setHidden(True)
        self.file_list = []
        self.batch_process = BatchProceed()
        self.batch_process.progress_signal.connect(self.progress_info)
        self.batch_process.error_signal.connect(self.execution_all_error)
        self.batch_process.execution_done.connect(self.execution_all_done)
        self.is_batch_process = False

        self.setContentsMargins(0, 0, 0, 0)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        opt_layout = QHBoxLayout()
        opt_layout.setContentsMargins(0, 0, 0, 0)
        opt_layout.addWidget(self.show_result)
        opt_layout.addWidget(right_label("Opacity:"))
        opt_layout.addWidget(self.opacity)
        main_layout.addLayout(opt_layout)
        opt_layout2 = QHBoxLayout()
        opt_layout2.setContentsMargins(0, 0, 0, 0)
        opt_layout2.addWidget(self.only_borders)
        opt_layout2.addWidget(right_label("Border thick:"))
        opt_layout2.addWidget(self.borders_thick)
        main_layout.addLayout(opt_layout2)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.execute_btn)
        btn_layout.addWidget(self.execute_all_btn)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.progress_info_lab)
        main_layout.addWidget(self.algorithm_choose)
        main_layout.addLayout(self.stack_layout)
        main_layout.addWidget(self.choose_components)
        main_layout.addStretch()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)

        # noinspection PyUnresolvedReferences
        self.algorithm_choose.currentIndexChanged.connect(self.stack_layout.setCurrentIndex)
        self.execute_btn.clicked.connect(self.execute_action)
        self.execute_all_btn.clicked.connect(self.execute_all_action)
        # noinspection PyUnresolvedReferences
        self.opacity.valueChanged.connect(control_view.set_opacity)
        # noinspection PyUnresolvedReferences
        self.show_result.currentIndexChanged.connect(control_view.set_show_label)
        self.only_borders.stateChanged.connect(control_view.set_borders)
        # noinspection PyUnresolvedReferences
        self.borders_thick.valueChanged.connect(control_view.set_borders_thick)
        component_checker.component_clicked.connect(self.choose_components.other_component_choose)
        settings.chosen_components_widget = self.choose_components
        settings.components_change_list.connect(self.choose_components.new_choose)
        settings.image_changed.connect(self.choose_components.remove_components)

    def border_value_check(self, value):
        if value % 2 == 0:
            self.borders_thick.setValue(value + 1)

    def file_list_change(self, val):
        print("FF:", val)
        self.file_list = val
        if len(self.file_list) > 0 and not self.block_execute_all_btn:
            self.execute_all_btn.setEnabled(True)
        else:
            self.execute_all_btn.setDisabled(True)

    def get_chosen_components(self):
        return sorted(self.choose_components.get_chosen())

    @property
    def segmentation(self):
        return self.settings.segmentation

    @segmentation.setter
    def segmentation(self, val):
        self.settings.segmentation = val

    def image_changed(self):
        self.settings.segmentation = None
        self.choose_components.set_chose([], [])

    def execute_all_action(self):
        dial = QFileDialog()
        dial.setFileMode(QFileDialog.Directory)
        dial.setDirectory(self.settings.get("io.save_batch", self.settings.get("io.save_segmentation_directory", "")))
        if not dial.exec_():
            return
        folder_path = str(dial.selectedFiles()[0])
        self.settings.set("io.save_batch", folder_path)
        self.execute_all_btn.setDisabled(True)
        self.block_execute_all_btn = True
        self.is_batch_process = True
        self.execute_btn.setDisabled(True)
        self.progress_bar.setHidden(False)
        self.progress_bar.setRange(0, len(self.file_list))
        self.progress_bar.setValue(0)

        widget = self.stack_layout.currentWidget()
        parameters = widget.get_values()
        self.batch_process.set_parameters(widget.algorithm, parameters, widget.channel_num(),
                                          self.file_list, folder_path)
        self.batch_process.start()

    def execution_all_error(self, text):
        QMessageBox.warning(self, "Proceed error", text)

    def execution_all_done(self):
        self.execute_btn.setEnabled(True)
        self.block_execute_all_btn = False
        if len(self.file_list) > 0:
            self.execute_all_btn.setEnabled(True)
        self.progress_bar.setHidden(True)
        self.progress_info_lab.setHidden(True)

    def execute_action(self):
        self.execute_btn.setDisabled(True)
        self.execute_all_btn.setDisabled(True)
        self.block_execute_all_btn = True
        self.is_batch_process = False
        self.progress_bar.setRange(0, 0)
        chosen = sorted(self.choose_components.get_chosen())
        if len(chosen) == 0:
            blank = None
        else:
            if len(chosen) > 250:
                blank = np.zeros(self.segmentation.shape, dtype=np.uint16)
            else:
                blank = np.zeros(self.segmentation.shape, dtype=np.uint8)
            for i, v in enumerate(chosen):
                blank[self.segmentation == v] = i + 1
        self.progress_bar.setHidden(False)
        widget: AlgorithmSettingsWidget = self.stack_layout.currentWidget()
        widget.execute(blank)
        self.chosen_list = chosen

    def progress_info(self, text, num):
        self.progress_info_lab.setVisible(True)
        self.progress_info_lab.setText(text)
        if self.is_batch_process:
            self.progress_bar.setValue(num)

    def execution_finished(self):
        self.execute_btn.setEnabled(True)
        self.block_execute_all_btn = False
        if len(self.file_list) > 0:
            self.execute_all_btn.setEnabled(True)
        self.progress_bar.setHidden(True)
        self.progress_info_lab.setHidden(True)

    def execution_done(self, segmentation: SegmentationResult):
        self.choose_components.set_chose(range(1, segmentation.segmentation.max() + 1),
                                         np.arange(len(self.chosen_list)) + 1)
        self.settings.segmentation = segmentation.segmentation


class ImageInformation(QWidget):
    def __init__(self, settings: StackSettings, parent=None):
        """:type settings: ImageSettings"""
        super(ImageInformation, self).__init__(parent)
        self._settings = settings
        self.path = QLabel("<b>Path:</b> example image")
        self.path.setWordWrap(True)
        self.spacing = [QDoubleSpinBox() for _ in range(3)]
        units_index = self._settings.get("units_index", 2)
        for el in self.spacing:
            el.setAlignment(Qt.AlignRight)
            el.setButtonSymbols(QAbstractSpinBox.NoButtons)
            el.setRange(0, 100000)
            # noinspection PyUnresolvedReferences
            el.valueChanged.connect(self.image_spacing_change)
        self.units = QComboBox()
        self.units.addItems(UNITS_LIST)
        self.units.setCurrentIndex(units_index)
        # noinspection PyUnresolvedReferences
        self.units.currentIndexChanged.connect(self.update_spacing)

        self.add_files = AddFiles(settings, btn_layout=FlowLayout)

        spacing_layout = QFormLayout()
        spacing_layout.addRow("x:", self.spacing[0])
        spacing_layout.addRow("y:", self.spacing[1])
        spacing_layout.addRow("z:", self.spacing[2])
        spacing_layout.addRow("Units:", self.units)

        layout = QVBoxLayout()
        layout.addWidget(self.path)
        layout.addWidget(QLabel("Image spacing:"))
        layout.addLayout(spacing_layout)
        layout.addWidget(self.add_files)
        layout.addStretch()
        self.setLayout(layout)
        self._settings.image_changed[str].connect(self.set_image_path)

    def update_spacing(self, index=None):
        if index is not None:
            self._settings.set("units_index", index)
        for el, val in zip(self.spacing, self._settings.image_spacing[::-1]):
            el.blockSignals(True)
            el.setValue(val * UNIT_SCALE[self.units.currentIndex()])
            el.blockSignals(False)

    def set_image_path(self, value):
        self.path.setText("<b>Path:</b> {}".format(value))
        self.update_spacing()

    def image_spacing_change(self):
        self._settings.image_spacing = [el.value() / UNIT_SCALE[self.units.currentIndex()] for i, el in
                                        enumerate(self.spacing[::-1])]

    def showEvent(self, _a0):
        units_index = self._settings.get("units_index", 2)
        for el, val in zip(self.spacing, self._settings.image_spacing[::-1]):
            el.setValue(val * UNIT_SCALE[units_index])


class Options(QTabWidget):
    def __init__(self, settings, image_view, component_checker, parent=None):
        super(Options, self).__init__(parent)
        self._settings = settings
        self.algorithm_options = AlgorithmOptions(settings, image_view, component_checker)
        self.image_properties = ImageInformation(settings, parent)
        self.image_properties.add_files.file_list_changed.connect(self.algorithm_options.file_list_change)
        self.colormap_choose = ColorSelector(settings, ["channelcontrol"])
        self.addTab(self.image_properties, "Image")
        self.addTab(self.algorithm_options, "Segmentation")
        self.addTab(self.colormap_choose, "Colormap filter")
        self.setMinimumWidth(340)
        self.setCurrentIndex(1)


    def get_chosen_components(self):
        return self.algorithm_options.get_chosen_components()


class MainWindow(BaseMainWindow):
    def __init__(self, title, signal_fun=None):
        print("title", title)
        super().__init__(signal_fun)
        self.setWindowTitle(title)
        self.title_base = title
        self.settings = StackSettings(os.path.join(config_folder, "settings.json"))
        if os.path.exists(os.path.join(config_folder, "settings.json")):
            self.settings.load()
        self.main_menu = MainMenu(self.settings)
        self.channel_control = ChannelControl(self.settings, name="channelcontrol")
        self.image_view = StackImageView(self.settings, self.channel_control)
        self.image_view.setMinimumWidth(450)
        self.info_text = QLabel()
        self.info_text.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.image_view.text_info_change.connect(self.info_text.setText)
        self.options_panel = Options(self.settings, self.image_view, self.image_view)
        self.main_menu.image_loaded.connect(self.image_read)
        self.settings.image_changed.connect(self.image_read)
        self.color_bar = ColorBar(self.settings, self.channel_control)

        icon = QIcon(os.path.join(static_file_folder, 'icons', "icon_stack.png"))
        self.setWindowIcon(icon)

        layout = QVBoxLayout()
        layout.addWidget(self.main_menu)
        sub_layout = QHBoxLayout()
        sub2_layout = QVBoxLayout()
        sub3_layout = QVBoxLayout()
        sub_layout.addWidget(self.color_bar, 0)
        sub3_layout.addWidget(self.image_view, 1)
        sub3_layout.addWidget(self.info_text, 0)
        sub2_layout.addWidget(self.options_panel, 1)
        sub2_layout.addWidget(self.channel_control, 0)

        sub_layout.addLayout(sub3_layout, 1)
        sub_layout.addLayout(sub2_layout, 0)
        layout.addLayout(sub_layout)
        self.widget = QWidget()
        self.widget.setLayout(layout)
        self.setCentralWidget(self.widget)
        reader = ImageReader()
        self.settings.image = reader.read(os.path.join(static_file_folder, 'initial_images', "stack.tif"))
        try:
            geometry = self.settings.get_from_profile("main_window_geometry")
            self.restoreGeometry(QByteArray.fromHex(bytes(geometry, 'ascii')))
        except KeyError:
            pass

    def image_read(self):
        self.image_view.set_image()
        self.image_view.reset_image_size()
        self.setWindowTitle(f"{self.title_base}: {os.path.basename(self.settings.image_path)}")

    def closeEvent(self, e):
        # print(self.settings.dump_view_profiles())
        # print(self.settings.segmentation_dict["default"].my_dict)
        self.settings.set_in_profile("main_window_geometry", bytes(self.saveGeometry().toHex()).decode('ascii'))
        self.settings.dump()

    def read_drop(self, paths):
        assert len(paths) == 1
        ext = os.path.splitext(paths[0])[1]
        read_thread = ImageReaderThread(parent=self)
        if ext in [".tif", ".tiff", ".lsm"]:
            read_thread.set_path(paths[0])
            dial = WaitingDialog(read_thread)
            dial.exec()
            if read_thread.image:
                self.main_menu.set_image(read_thread.image)

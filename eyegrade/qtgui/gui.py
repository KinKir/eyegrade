# Eyegrade: grading multiple choice questions with a webcam
# Copyright (C) 2012-2013 Jesus Arias Fisteus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#

import os.path

#from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import (QImage, QWidget, QMainWindow, QPainter,
                         QSizePolicy, QApplication, QVBoxLayout,
                         QLabel, QIcon, QAction, QMenu, QDialog,
                         QFormLayout, QLineEdit, QDialogButtonBox,
                         QComboBox, QFileDialog, QHBoxLayout, QPushButton,
                         QMessageBox, QPixmap, QCompleter,
                         QSortFilterProxyModel, QKeySequence, QColor,)

from PyQt4.QtCore import Qt, QTimer, QThread, pyqtSignal

from eyegrade.utils import (resource_path, program_name, version, web_location,
                            source_location)

_filter_exam_config = 'Exam configuration (*.eye)'
_filter_student_list = 'Student list (*.csv *.tsv *.txt *.lst *.list)'

color_eyegrade_blue = QColor(32, 73, 124)

class OpenFileWidget(QWidget):
    """Dialog with a text field and a button to open a file selector."""
    def __init__(self, parent, select_directory=False, name_filter='',
                 minimum_width=200, title=''):
        super(OpenFileWidget, self).__init__(parent)
        self.select_directory = select_directory
        self.name_filter = name_filter
        self.title = title
        layout = QHBoxLayout(self)
        self.setLayout(layout)
        self.filename_widget = QLineEdit(self)
        self.filename_widget.setMinimumWidth(minimum_width)
        self.button = QPushButton(QIcon(resource_path('open_file.svg')), '',
                                  parent=self)
        self.button.clicked.connect(self._open_dialog)
        layout.addWidget(self.filename_widget)
        layout.addWidget(self.button)

    def text(self):
        return self.filename_widget.text()

    def setEnabled(self, enabled):
        self.filename_widget.setEnabled(enabled)
        self.button.setEnabled(enabled)

    def _open_dialog(self, value):
        if self.select_directory:
            directory = \
                QFileDialog.getExistingDirectory(self, self.title, '',
                                            (QFileDialog.ShowDirsOnly
                                             | QFileDialog.DontResolveSymlinks))
            if directory:
                self.filename_widget.setText(directory)
        else:
            filename = QFileDialog.getOpenFileName(self, self.title, '',
                                                   self.name_filter)
            if filename:
                self.filename_widget.setText(filename)


class CompletingComboBox(QComboBox):
    """An editable combo box that filters and autocompletes."""
    def __init__(self, parent=None):
        super(CompletingComboBox, self).__init__(parent)
        self.setEditable(True)
        self.filter = QSortFilterProxyModel(self)
        self.filter.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.filter.setSourceModel(self.model())
        self.completer = QCompleter(self.filter, self)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setCompleter(self.completer)
        self.lineEdit().textEdited[unicode]\
            .connect(self.filter.setFilterFixedString)
        self.currentIndexChanged.connect(self._index_changed)

    def _index_changed(self, index):
        self.lineEdit().selectAll()


class DialogStudentId(QDialog):
    """Dialog to change the student id.

    Example (replace `parent` by the parent widget):

    dialog = DialogStudentId(parent)
    id = dialog.exec_()

    """
    def __init__(self, parent, students):
        super(DialogStudentId, self).__init__(parent)
        self.setWindowTitle('Change the student id')
        layout = QFormLayout()
        self.setLayout(layout)
        self.combo = CompletingComboBox(self)
        self.combo.setEditable(True)
        self.combo.setAutoCompletion(True)
        for student in students:
            self.combo.addItem(student)
        self.combo.lineEdit().selectAll()
        self.combo.showPopup()
        buttons = QDialogButtonBox((QDialogButtonBox.Ok
                                    | QDialogButtonBox.Cancel))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow('Student id:', self.combo)
        layout.addRow(buttons)

    def exec_(self):
        """Shows the dialog and waits until it is closed.

        Returns the text of the option selected by the user, or None if
        the dialog is cancelled.

        """
        result = super(DialogStudentId, self).exec_()
        if result == QDialog.Accepted:
            return unicode(self.combo.currentText())
        else:
            return None


class Worker(QThread):
    """Generic worker class for spawning a task to other thread."""

    def __init__(self, task, parent):
        """Inits a new worker.

        The `task` must be an object that implements a `run()` method.

        """
        super(Worker, self).__init__(parent)
        self.task = task

    def __del__(self):
        self.wait()

    def run(self):
        """Run the task."""
        self.task.run()


class DialogNewSession(QDialog):
    """Dialog to receive parameters for creating a new grading session.

    Example (replace `parent` by the parent widget):

    dialog = DialogNewSession(parent)
    values = dialog.exec_()

    """
    def __init__(self, parent):
        super(DialogNewSession, self).__init__(parent)
        self.setWindowTitle('New session')
        layout = QFormLayout()
        self.setLayout(layout)
        self.directory_w = OpenFileWidget(self, select_directory=True,
                                 title='Select or create an empty directory')
        self.config_file_w = OpenFileWidget(self,
                                 title='Select the exam configuration file',
                                 name_filter=_filter_exam_config)
        self.use_id_list_w = QComboBox(self)
        self.use_id_list_w.addItems(['Yes', 'No'])
        self.use_id_list_w.currentIndexChanged.connect(self._id_list_listener)
        self.id_list_w = OpenFileWidget(self, name_filter=_filter_student_list)
        buttons = QDialogButtonBox((QDialogButtonBox.Ok
                                    | QDialogButtonBox.Cancel))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow('Directory:', self.directory_w)
        layout.addRow('Exam configuration file:', self.config_file_w)
        layout.addRow('Load student list:', self.use_id_list_w)
        layout.addRow('Student list:', self.id_list_w)
        layout.addRow(buttons)

    def _get_values(self):
        values = {}
        values['directory'] = unicode(self.directory_w.text()).strip()
        values['config'] = unicode(self.config_file_w.text()).strip()
        if self.use_id_list_w.currentIndex() == 0:
            values['id_list'] = unicode(self.id_list_w.text()).strip()
        else:
            values['id_list'] = None
        # Check the values (the files must exist, etc.)
        if not os.path.isdir(values['directory']):
            QMessageBox.critical(self, 'Error',
                          'The directory does not exist or is not a directory.')
            return None
        dir_content = os.listdir(values['directory'])
        if dir_content:
            if 'session.eye' in dir_content:
                QMessageBox.critical(self, 'Error',
                            ('The directory already contains a session. '
                             'Choose another directory or create a new one.'))
                return None
            else:
                result = QMessageBox.question(self, 'Warning',
                            ('The directory is not empty. '
                             'Are you sure you want to create a session here?'),
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No)
                if result == QMessageBox.No:
                    return None
        if not os.path.isfile(values['config']):
            QMessageBox.critical(self, 'Error',
                                 ('The exam configuration file does not'
                                  'exist or is not a regular file.'))
            return None
        if (values['id_list'] is not None
              and not os.path.isfile(values['id_list'])):
            QMessageBox.critical(self, 'Error',
                                 ('The student list file does not'
                                  'exist or is not a regular file.'))
            return None
        return values

    def exec_(self):
        finish = False
        while not finish:
            result = super(DialogNewSession, self).exec_()
            if result == QDialog.Accepted:
                values = self._get_values()
                if values is not None:
                    finish = True
            else:
                values = None
                finish = True
        return values

    def _id_list_listener(self, index):
        if index == 0:
            self.id_list_w.setEnabled(True)
        else:
            self.id_list_w.setEnabled(False)


class DialogCameraSelection(QDialog):
    """Shows a dialog that allows choosing a camera.

    Example (replace `parent` by the parent widget):

    dialog = DialogNewSession(parent)
    values = dialog.exec_()

    At the end of the dialog, the chosen camera is automatically
    set in the context object.

    """
    capture_period = 0.1
    camera_error = pyqtSignal()

    def __init__(self, capture_context, parent):
        """Initializes the dialog.

        `capture_context` is the imageproc.ExamCaptureContext object
        to be used.

        """
        super(DialogCameraSelection, self).__init__(parent)
        self.capture_context = capture_context
        self.setWindowTitle('Select a camera')
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        self.camview = CamView((320, 240), self, border=True)
        self.label = QLabel(self)
        self.button = QPushButton('Try next camera')
        self.button.clicked.connect(self._next_camera)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(self.camview)
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        layout.addWidget(buttons)
        self.camera_error.connect(self._show_camera_error,
                                  type=Qt.QueuedConnection)
        self.timer = None

    def __del__(self):
        if self.timer is not None:
            self.timer.stop()
        self.capture_context.close_camera()

    def exec_(self):
        success = self.capture_context.open_camera()
        if success:
            self._update_camera_label()
            self.timer = QTimer(self)
            self.timer.setSingleShot(False)
            self.timer.timeout.connect(self._next_capture)
            self.timer.setInterval(DialogCameraSelection.capture_period)
            self.timer.start()
        else:
            self.camera_error.emit()
        return super(DialogCameraSelection, self).exec_()

    def _show_camera_error(self):
        QMessageBox.critical(self, 'Camera not available',
                             'No camera is available.')
        self.reject()

    def _next_camera(self):
        current_camera = self.capture_context.current_camera_id()
        success = self.capture_context.next_camera()
        if not success:
            self.camera_error.emit()
        elif self.capture_context.current_camera_id() == current_camera:
            QMessageBox.critical(self, 'No more cameras',
                                 'No more cameras are available.')
        else:
            self._update_camera_label()

    def _update_camera_label(self):
        camera_id = self.capture_context.current_camera_id()
        if camera_id is not None and camera_id >= 0:
            self.label.setText('<center>Current camera: {}</center>'\
                               .format(camera_id))
        else:
            self.label.setText('<center>No camera</center>')

    def _next_capture(self):
        if not self.isVisible():
            self.timer.stop()
            self.capture_context.close_camera()
        else:
            image = self.capture_context.capture(resize=(320, 240))
            self.camview.display_capture(image)


class DialogAbout(QDialog):
    """About dialog.

    Example (replace `parent` by the parent widget):

    dialog = DialogAbout(parent)
    values = dialog.exec_()

    """
    def __init__(self, parent):
        super(DialogAbout, self).__init__(parent)
        text = \
             """
             <center>
             <p><img src='{0}' width='64'> <br>
             {1} {2} <br>
             (c) 2010-2013 Jesus Arias Fisteus <br>
             <a href='{3}'>{3}</a> <br>
             <a href='{4}'>{4}</a>

             <p>
             This program is free software: you can redistribute it<br>
             and/or modify it under the terms of the GNU General<br>
             Public License as published by the Free Software<br>
             Foundation, either version 3 of the License, or (at your<br>
             option) any later version.
             </p>
             <p>
             This program is distributed in the hope that it will be<br>
             useful, but WITHOUT ANY WARRANTY; without even the<br>
             implied warranty of MERCHANTABILITY or FITNESS FOR A<br>
             PARTICULAR PURPOSE. See the GNU General Public License<br>
             for more details.
             </p>
             <p>
             You should have received a copy of the GNU General Public<br>
             License along with this program.  If not, see<br>
             <a href='http://www.gnu.org/licenses/gpl.txt'>
             http://www.gnu.org/licenses/gpl.txt</a>.
             </p>
             </center>
             """.format(resource_path('logo.svg'), program_name, version,
                        web_location, source_location)
        self.setWindowTitle('About')
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        label = QLabel(text)
        label.setTextInteractionFlags((Qt.LinksAccessibleByKeyboard
                                       | Qt.LinksAccessibleByMouse
                                       | Qt.TextBrowserInteraction
                                       | Qt.TextSelectableByKeyboard
                                       | Qt.TextSelectableByMouse))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(QLabel(text))
        layout.addWidget(buttons)


class ActionsManager(object):
    """Creates and manages the toolbar buttons."""

    _actions_grading_data = [
        ('snapshot', 'snapshot.svg', 'Sna&pshot', Qt.Key_S),
        ('manual_detect', 'manual_detect.svg', '&Manual bounds', Qt.Key_M),
        ('edit_id', 'edit_id.svg', '&Edit student id', Qt.Key_I),
        ('save', 'save.svg', '&Save capture', Qt.Key_Space),
        ('discard', 'discard.svg', '&Discard capture', Qt.Key_Backspace),
        ]

    _actions_session_data = [
        ('new', 'new.svg', '&New session', None),
        ('open', 'open.svg', '&Open session', None),
        ('close', 'close.svg', '&Close session', None),
        ('*separator*', None, None, None),
        ('exit', 'exit.svg', '&Exit', None),
        ]

    _actions_tools_data = [
        ('camera', 'camera.svg', 'Select &camera', None),
        ]

    _actions_help_data = [
        ('help', None, 'Online &Help', None),
        ('website', None, '&Website', None),
        ('about', None, '&About', None),
        ]

    _actions_debug_data = [
        ('+lines', None, 'Show &lines', None),
        ('+processed', None, 'Show &processed image', None),
        ]

    def __init__(self, window):
        """Creates a manager for the given toolbar object."""
        self.window = window
        self.menubar = window.menuBar()
        self.toolbar = window.addToolBar('Grade Toolbar')
        self.menus = {}
        self.actions_grading = {}
        self.actions_session = {}
        self.actions_tools = {}
        self.actions_help = {}
        action_lists = {'session': [], 'grading': [], 'tools': [], 'help': []}
        for key, icon, text, shortcut in ActionsManager._actions_session_data:
            self._add_action(key, icon, text, shortcut, self.actions_session,
                             action_lists['session'])
        for key, icon, text, shortcut in ActionsManager._actions_grading_data:
            self._add_action(key, icon, text, shortcut, self.actions_grading,
                             action_lists['grading'])
        for key, icon, text, shortcut in ActionsManager._actions_tools_data:
            self._add_action(key, icon, text, shortcut, self.actions_tools,
                             action_lists['tools'])
        for key, icon, text, shortcut in ActionsManager._actions_help_data:
            self._add_action(key, icon, text, shortcut, self.actions_help,
                             action_lists['help'])
        self._populate_menubar(action_lists)
        self._populate_toolbar(action_lists)
        self._add_debug_actions()

    def set_search_mode(self):
        self.actions_grading['snapshot'].setEnabled(True)
        self.actions_grading['manual_detect'].setEnabled(True)
        self.actions_grading['edit_id'].setEnabled(False)
        self.actions_grading['save'].setEnabled(False)
        self.actions_grading['discard'].setEnabled(False)
        self.menus['grading'].setEnabled(True)
        self.actions_session['new'].setEnabled(False)
        self.actions_session['open'].setEnabled(False)
        self.actions_session['close'].setEnabled(True)
        self.actions_session['exit'].setEnabled(True)
        self.actions_tools['camera'].setEnabled(False)

    def set_review_mode(self):
        self.actions_grading['snapshot'].setEnabled(False)
        self.actions_grading['manual_detect'].setEnabled(False)
        self.actions_grading['edit_id'].setEnabled(True)
        self.actions_grading['save'].setEnabled(True)
        self.actions_grading['discard'].setEnabled(True)
        self.menus['grading'].setEnabled(True)
        self.actions_session['new'].setEnabled(False)
        self.actions_session['open'].setEnabled(False)
        self.actions_session['close'].setEnabled(True)
        self.actions_session['exit'].setEnabled(True)
        self.actions_tools['camera'].setEnabled(False)

    def set_manual_detect_mode(self):
        self.actions_grading['snapshot'].setEnabled(False)
        self.actions_grading['manual_detect'].setEnabled(True)
        self.actions_grading['edit_id'].setEnabled(False)
        self.actions_grading['save'].setEnabled(False)
        self.actions_grading['discard'].setEnabled(True)
        self.menus['grading'].setEnabled(True)
        self.actions_session['new'].setEnabled(False)
        self.actions_session['open'].setEnabled(False)
        self.actions_session['close'].setEnabled(True)
        self.actions_session['exit'].setEnabled(True)
        self.actions_tools['camera'].setEnabled(False)

    def set_no_session_mode(self):
        for key in self.actions_grading:
            self.actions_grading[key].setEnabled(False)
        self.menus['grading'].setEnabled(False)
        self.actions_session['new'].setEnabled(True)
        self.actions_session['open'].setEnabled(True)
        self.actions_session['close'].setEnabled(False)
        self.actions_session['exit'].setEnabled(True)
        self.actions_tools['camera'].setEnabled(True)

    def enable_manual_detect(self, enabled):
        """Enables or disables the manual detection mode.

        If `enable` is True, it is enabled. Otherwise, it is disabled.

        """
        self.actions_grading['manual_detect'].setEnabled(enabled)

    def register_listener(self, key, listener):
        actions = self._select_action_group(key[0])
        assert key[1] in actions
        actions[key[1]].triggered.connect(listener)

    def is_action_checked(self, key):
        """For checkabel actions, returns whether the action is checked.

        Action keys are tuples such as ('tools', 'lines').

        """
        actions = self._select_action_group(key[0])
        assert key[1] in actions
        assert actions[key[1]].isCheckable()
        return actions[key[1]].isChecked()

    def _select_action_group(self, key):
        if key == 'session':
            return self.actions_session
        elif key == 'grading':
            return self.actions_grading
        elif key == 'tools':
            return self.actions_tools
        elif key == 'help':
            return self.actions_help
        assert False, 'Undefined action group key: {0}.format(key)'

    def _add_action(self, action_name, icon_file, text, shortcut,
                    group, actions_list):
        action = self._create_action(action_name, icon_file, text, shortcut)
        if action_name.startswith('+'):
            if action_name.startswith('++'):
                action_name = action_name[2:]
            else:
                action_name = action_name[1:]
        if not action.isSeparator():
            group[action_name] = action
        actions_list.append(action)

    def _create_action(self, action_name, icon_file, text, shortcut):
        if action_name == '*separator*':
            action = QAction(self.window)
            action.setSeparator(True)
        else:
            if icon_file:
                action = QAction(QIcon(resource_path(icon_file)),
                                 text, self.window)
            else:
                action = QAction(text, self.window)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        if action_name.startswith('+'):
            action.setCheckable(True)
            if action_name.startswith('++'):
                action.setChecked(True)
        return action

    def _populate_menubar(self, action_lists):
        self.menus['session'] = QMenu('&Session', self.menubar)
        self.menus['grading'] = QMenu('&Grading', self.menubar)
        self.menus['tools'] = QMenu('&Tools', self.menubar)
        self.menus['help'] = QMenu('&Help', self.menubar)
        self.menubar.addMenu(self.menus['session'])
        self.menubar.addMenu(self.menus['grading'])
        self.menubar.addMenu(self.menus['tools'])
        self.menubar.addMenu(self.menus['help'])
        for action in action_lists['session']:
            self.menus['session'].addAction(action)
        for action in action_lists['grading']:
            self.menus['grading'].addAction(action)
        for action in action_lists['tools']:
            self.menus['tools'].addAction(action)
        for action in action_lists['help']:
            self.menus['help'].addAction(action)

    def _populate_toolbar(self, action_lists):
        for action in action_lists['grading']:
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.actions_session['new'])
        self.toolbar.addAction(self.actions_session['open'])
        self.toolbar.addAction(self.actions_session['close'])

    def _add_debug_actions(self):
        actions_list = []
        for key, icon, text, shortcut in ActionsManager._actions_debug_data:
            self._add_action(key, icon, text, shortcut, self.actions_tools,
                             actions_list)
        menu = QMenu('&Debug options', self.menus['tools'])
        for action in actions_list:
            menu.addAction(action)
        self.menus['tools'].addMenu(menu)


class CamView(QWidget):
    def __init__(self, size, parent, draw_logo=False, border=False):
        super(CamView, self).__init__(parent)
        if not border:
            fixed_size = size
        else:
            fixed_size = (size[0] + 10, size[1] + 10)
        self.setFixedSize(*fixed_size)
        self.border = border
        self.image_size = size
        self.display_wait_image()
        if draw_logo:
            self.logo = QPixmap(resource_path('logo.svg'))
        else:
            self.logo = None
        self.mouse_listener = None

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.border:
            size = self.size()
            painter.setPen(color_eyegrade_blue)
            painter.drawRoundedRect(0, 0, size.width() - 2, size.height() - 2,
                                    10, 10)
            painter.drawImage(5, 5, self.image)
        else:
            painter.drawImage(event.rect(), self.image)

    def display_capture(self, ipl_image):
        """Displays a captured image in the window.

        The image is in the OpenCV IPL format.

        """
        self.image = QImage(ipl_image.tostring(),
                            ipl_image.width, ipl_image.height,
                            QImage.Format_RGB888).rgbSwapped()
        if self.logo is not None:
            painter = QPainter(self.image)
            painter.drawPixmap(ipl_image.width - 40, ipl_image.height - 40,
                               36, 36, self.logo)
        self.update()

    def display_wait_image(self):
        self.image = QImage(self.image_size[0], self.image_size[1],
                            QImage.Format_RGB888)
        self.image.fill(Qt.darkBlue)
        self.update()

    def register_mouse_pressed_listener(self, listener):
        """Registers a function to receive a mouse clicked event.

        The listener must receive as parameter a tuple (x, y).

        """
        self.mouse_listener = listener

    def mousePressEvent(self, event):
        if self.mouse_listener:
            self.mouse_listener((event.x(), event.y()))


class CenterView(QWidget):
    img_correct = '<img src="%s" height="22" width="22">'%\
                  resource_path('correct.svg')
    img_incorrect = '<img src="%s" height="22" width="22">'%\
                    resource_path('incorrect.svg')
    img_unanswered = '<img src="%s" height="22" width="22">'%\
                     resource_path('unanswered.svg')

    def __init__(self, parent=None):
        super(CenterView, self).__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.camview = CamView((640, 480), self, draw_logo=True)
        self.label_up = QLabel()
        self.label_down = QLabel()
        layout.addWidget(self.camview)
        layout.addWidget(self.label_up)
        layout.addWidget(self.label_down)

    def update_status(self, score, model=None, seq_num=None, survey_mode=False):
        parts = []
        if score is not None:
            if not survey_mode:
                correct, incorrect, blank, indet, score, max_score = score
                parts.append(CenterView.img_correct)
                parts.append(str(correct) + '  ')
                parts.append(CenterView.img_incorrect)
                parts.append(str(incorrect) + '  ')
                parts.append(CenterView.img_unanswered)
                parts.append(str(blank) + '  ')
                if score is not None and max_score is not None:
                    parts.append('Score: %.2f / %.2f  '%(score, max_score))
            else:
                parts.append('[Survey mode on]  ')
        if model is not None:
            parts.append('Model: ' + model + '  ')
        if seq_num is not None:
            parts.append('Num.: ' + str(seq_num) + '  ')
        self.label_down.setText(('<span style="white-space: pre">'
                                 + ' '.join(parts) + '</span>'))

    def update_text_up(self, text):
        self.label_up.setText(text)

    def update_text_down(self, text):
        self.label_down.setText(text)

    def display_capture(self, ipl_image):
        """Displays a captured image in the window.

        The image is in the OpenCV IPL format.

        """
        self.camview.display_capture(ipl_image)

    def display_wait_image(self):
        """Displays the default image instead of a camera capture."""
        self.camview.display_wait_image()

    def register_listener(self, key, listener):
        """Registers listeners for the center view.

        Available listeners are:

        - ('camview', 'mouse_pressed'): mouse pressed in the camview
          area. The listener receives the coordinates (x, y) as a
          tuple.

        """
        if key[0] == 'camview':
            if key[1] == 'mouse_pressed':
                self.camview.register_mouse_pressed_listener(listener)
            else:
                assert False, 'Undefined listener key: {0}'.format(key)
        else:
            assert False, 'Undefined listener key: {0}'.format(key)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setSizePolicy(policy)
        self.center_view = CenterView()
        self.setCentralWidget(self.center_view)
        self.setWindowTitle("Eyegrade")
        self.setWindowIcon(QIcon(resource_path('logo.svg')))
        self.adjustSize()
        self.setFixedSize(self.sizeHint())
        self.digit_key_listener = None
        self.exit_listener = False

    def keyPressEvent(self, event):
        if (self.digit_key_listener
            and event.key() >= Qt.Key_0 and event.key() <= Qt.Key_9):
            self.digit_key_listener(event.text())

    def register_listener(self, key, listener):
        if key[0] == 'key_pressed':
            if key[1] == 'digit':
                self.digit_key_listener = listener
            else:
                assert False, 'Undefined listener key: {0}'.format(key)
        elif key[0] == 'exit':
            self.exit_listener = listener
        else:
            assert False, 'Undefined listener key: {0}'.format(key)

    def closeEvent(self, event):
        accept = True
        if self.exit_listener is not None:
            accept = self.exit_listener()
        if accept:
            event.accept()
        else:
            event.ignore()


class Interface(object):
    def __init__(self, id_enabled, id_list_enabled, argv):
        self.app = QApplication(argv)
        self.id_enabled = id_enabled
        self.id_list_enabled = id_list_enabled
        self.last_score = None
        self.last_model = None
        self.manual_detect_enabled = False
        self.window = MainWindow()
        self.actions_manager = ActionsManager(self.window)
        self.activate_no_session_mode()
        self.window.show()
        self.register_listener(('actions', 'session', 'exit'),
                               self.window.close)
        self.register_listener(('actions', 'help', 'about'),
                               self.show_about_dialog)

    def run(self):
        return self.app.exec_()

    def set_manual_detect_enabled(self, enabled):
        self.manual_detect_enabled = enabled
        self.actions_manager.set_manual_detect_enabled(enabled)

    def activate_search_mode(self):
        self.actions_manager.set_search_mode()

    def activate_review_mode(self):
        self.actions_manager.set_review_mode()

    def activate_manual_detect_mode(self):
        self.actions_manager.set_manual_detect_mode()

    def activate_no_session_mode(self):
        self.actions_manager.set_no_session_mode()
        self.display_wait_image()
        self.update_text_up('')
        self.show_version()

    def enable_manual_detect(self, enabled):
        """Enables or disables the manual detection mode.

        If `enable` is True, it is enabled. Otherwise, it is disabled.

        """
        self.actions_manager.enable_manual_detect(enabled)

    def update_status(self, score, model=None, seq_num=None, survey_mode=False):
        self.window.center_view.update_status(score, model=model,
                                              seq_num=seq_num,
                                              survey_mode=survey_mode)

    def update_text_up(self, text):
        if text is None:
            text = ''
        self.window.center_view.update_text_up(text)

    def update_text_down(self, text):
        if text is None:
            text = ''
        self.window.center_view.update_text_down(text)

    def update_text(self, text_up, text_down):
        self.window.center_view.update_text_up(text_up)
        self.window.center_view.update_text_down(text_down)

    def register_listeners(self, listeners):
        """Registers a dictionary of listeners for the events of the gui.

        The listeners are specified as a dictionary with pairs
        event_key->listener. Keys are tuples of strings such as
        ('action', 'session', 'close').

        """
        for key, listener in listeners.iteritems():
            self.register_listener(key, listener)

    def register_listener(self, key, listener):
        """Registers a single listener for the events of the gui.

        Keys are tuples of strings such as ('action', 'session',
        'close').

        """
        if key[0] == 'actions':
            self.actions_manager.register_listener(key[1:], listener)
        elif key[0] == 'center_view':
            self.window.center_view.register_listener(key[1:], listener)
        elif key[0] == 'window':
            self.window.register_listener(key[1:], listener)
        else:
            assert False, 'Unknown event key {0}'.format(key)

    def is_action_checked(self, action_key):
        """For checkabel actions, returns whether the action is checked.

        Action keys are tuples such as ('tools', 'lines').

        """
        return self.actions_manager.is_action_checked(action_key)

    def register_timer(self, time_delta, callback):
        """Registers a callback function to be run after time_delta ms."""
        timer = QTimer(self.window)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.setInterval(time_delta)
        timer.start()

    def display_capture(self, ipl_image):
        """Displays a captured image in the window.

        The image is in the OpenCV IPL format.

        """
        self.window.center_view.display_capture(ipl_image)

    def save_capture(self, filename):
        """Saves the current capture and its annotations to the given file."""
        pixmap = QPixmap(self.window.center_view.size())
        self.window.center_view.render(pixmap)
        pixmap.save(filename)

    def display_wait_image(self):
        """Displays the default image instead of a camera capture."""
        self.window.center_view.display_wait_image()

    def dialog_new_session(self):
        """Displays a new session dialog.

        The data introduced by the user is returned as a dictionary with
        keys `directory`, `config` and `id_list`. `id_list` may be None.

        The return value is None if the user cancels the dialog.

        """
        dialog = DialogNewSession(self.window)
        return dialog.exec_()

    def dialog_student_id(self, student_ids):
        """Displays a dialog to change the student id.

        A string with the option selected by the user (possibly
        student id and name) is returned.

        The return value is None if the user cancels the dialog.

        """
        dialog = DialogStudentId(self.window, student_ids)
        return dialog.exec_()

    def dialog_open_session(self):
        """Displays an open session dialog.

        The filename of the session file is returned or None.

        """
        filename = QFileDialog.getOpenFileName(self.window,
                                               'Select the session file',
                                               '', _filter_exam_config)
        return str(filename) if filename else None

    def dialog_camera_selection(self, capture_context):
        """Displays a camera selection dialog.

        `capture_context` is the imageproc.ExamCaptureContext object
        to be used.

        """
        dialog = DialogCameraSelection(capture_context, self.window)
        return dialog.exec_()

    def show_error(self, message, title='Error'):
        """Displays an error dialog with the given message.

        The method blocks until the user closes the dialog.

        """
        QMessageBox.critical(self.window, title, message)

    def show_warning(self, message, title='Warning', is_question=True):
        """Displays a warning dialog.

        Returns True if the the user accepts and False otherwise.

        """
        if not is_question:
            result = QMessageBox.warning(self.window, 'Warning', message)
            if result == QMessageBox.Ok:
                return True
            else:
                return False
        else:
            result = QMessageBox.warning(self.window, 'Warning', message,
                                         QMessageBox.Yes | QMessageBox.No,
                                         QMessageBox.No)
            if result == QMessageBox.Yes:
                return True
            else:
                return False

    def show_version(self):
        version_line = '{0} {1} - <a href="{2}">{2}</a>'\
               .format(program_name, version, web_location)
        self.update_text_down(version_line)

    def run_worker(self, task, callback):
        """Runs a task in another thread.

        The `task` must be an object that implements a `run()`
        method. Completion is notified to the given `callback` function.

        """
        self.worker = Worker(task, self.window)
        self.worker.finished.connect(callback)
        self.worker.start()

    def show_about_dialog(self):
        dialog = DialogAbout(self.window)
        dialog.exec_()
# Eyegrade: grading multiple choice questions with a webcam
# Copyright (C) 2010-2019 Jesus Arias Fisteus
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
# <https://www.gnu.org/licenses/>.
#

import gettext

from PyQt5.QtGui import (
    QRegExpValidator,
    QIcon,
)

from PyQt5.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
    QTabWidget,
    QTableView,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QLineEdit,
    QFormLayout,
    QLabel,
)

from PyQt5.QtCore import (
    Qt,
    QAbstractTableModel,
    QModelIndex,
    QVariant,
    QRegExp,
)

from . import FileNameFilters
from . import widgets
from .. import utils
from .. import students


t = gettext.translation('eyegrade', utils.locale_dir(), fallback=True)
_ = t.gettext


class DialogStudentId(QDialog):
    """Dialog to change the student id.

    Example (replace `parent` by the parent widget):

    dialog = DialogStudentId(parent)
    id = dialog.exec_()

    """
    def __init__(self, parent, student_list):
        super().__init__(parent)
        self.setWindowTitle(_('Change the student id'))
        layout = QFormLayout()
        self.setLayout(layout)
        self.combo = widgets.StudentComboBox(parent=self)
        self.combo.add_students(student_list)
        self.combo.editTextChanged.connect(self._check_value)
        self.combo.currentIndexChanged.connect(self._check_value)
        new_student_button = QPushButton( \
                                 QIcon(utils.resource_path('new_id.svg')),
                                 _('New student'), parent=self)
        new_student_button.clicked.connect(self._new_student)
        self.buttons = QDialogButtonBox((QDialogButtonBox.Ok
                                         | QDialogButtonBox.Cancel))
        self.buttons.addButton(new_student_button, QDialogButtonBox.ActionRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(_('Student id:'), self.combo)
        layout.addRow(self.buttons)

    def exec_(self):
        """Shows the dialog and waits until it is closed.

        Returns a student object with the option selected by the user.
        The return value is None if the user cancels the dialog.

        """
        result = super().exec_()
        if result == QDialog.Accepted:
            return self.combo.current_student()
        else:
            return None

    def _new_student(self):
        dialog = NewStudentDialog(parent=self)
        student = dialog.exec_()
        if student is not None:
            self.combo.add_student(student, set_current=True)
            self.buttons.button(QDialogButtonBox.Ok).setFocus()
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)

    def _check_value(self, param):
        if self.combo.current_student() is not None:
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)


class NewStudentDialog(QDialog):
    """Dialog to ask for a new student.

    It returns a Student object with the data of the student.

    """
    _last_combo_value = None

    def __init__(self, parent=None):
        super(NewStudentDialog, self).__init__(parent)
        self.setMinimumWidth(300)
        self.setWindowTitle(_('Add a new student'))
        layout = QFormLayout()
        self.setLayout(layout)
        self.id_field = QLineEdit(self)
        self.id_field.setValidator(QRegExpValidator(QRegExp(r'\d+'), self))
        self.id_field.textEdited.connect(self._check_values)
        self.name_field = QLineEdit(self)
        self.surname_field = QLineEdit(self)
        self.full_name_field = QLineEdit(self)
        self.name_label = QLabel(_('Given name'))
        self.surname_label = QLabel(_('Surname'))
        self.full_name_label = QLabel(_('Full name'))
        self.email_field = QLineEdit(self)
        self.email_field.setValidator( \
                        QRegExpValidator(QRegExp(students.re_email), self))
        self.email_field.textEdited.connect(self._check_values)
        self.combo = QComboBox(parent=self)
        self.combo.addItem(_('Separate given name and surname'))
        self.combo.addItem(_('Full name in just one field'))
        self.combo.currentIndexChanged.connect(self._update_combo)
        layout.addRow(self.combo)
        layout.addRow(_('Id number'), self.id_field)
        layout.addRow(self.name_label, self.name_field)
        layout.addRow(self.surname_label, self.surname_field)
        layout.addRow(self.full_name_label, self.full_name_field)
        layout.addRow(_('Email'), self.email_field)
        self.buttons = QDialogButtonBox((QDialogButtonBox.Ok
                                         | QDialogButtonBox.Cancel))
        layout.addRow(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._check_values()
        # Set the combo box
        if NewStudentDialog._last_combo_value is None:
            NewStudentDialog._last_combo_value = 0
        self.combo.setCurrentIndex(NewStudentDialog._last_combo_value)
        self._update_combo(NewStudentDialog._last_combo_value)

    def exec_(self):
        """Shows the dialog and waits until it is closed.

        Returns the text of the option selected by the user, or None if
        the dialog is cancelled.

        """
        result = super(NewStudentDialog, self).exec_()
        if result == QDialog.Accepted:
            NewStudentDialog._last_combo_value = self.combo.currentIndex()
            email = self.email_field.text()
            if not email:
                email = None
            if self.combo.currentIndex() == 0:
                # First name, last name
                student = students.Student( \
                                    self.id_field.text(),
                                    None,
                                    self.name_field.text(),
                                    self.surname_field.text(),
                                    email)
            else:
                # Full name
                student = students.Student( \
                                    self.id_field.text(),
                                    self.full_name_field.text(),
                                    None,
                                    None,
                                    email)
        else:
            student = None
        return student

    def _check_values(self):
        if (self.id_field.hasAcceptableInput()
            and (not self.email_field.text()
                 or self.email_field.hasAcceptableInput())):
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)

    def _update_combo(self, new_index):
        if new_index == 0:
            self.name_field.setEnabled(True)
            self.surname_field.setEnabled(True)
            self.full_name_field.setEnabled(False)
            self.name_label.setEnabled(True)
            self.surname_label.setEnabled(True)
            self.full_name_label.setEnabled(False)
            self.full_name_field.setText('')
        else:
            self.name_field.setEnabled(False)
            self.surname_field.setEnabled(False)
            self.full_name_field.setEnabled(True)
            self.name_label.setEnabled(False)
            self.surname_label.setEnabled(False)
            self.full_name_label.setEnabled(True)
            self.name_field.setText('')
            self.surname_field.setText('')


class DialogStudents(QDialog):
    """Dialog to list students."""

    def __init__(self, parent, group_listings):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)
        tabs = StudentGroupsTabs(self, group_listings=group_listings)
        main_layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        for button in tabs.create_buttons():
            buttons.addButton(button, QDialogButtonBox.ActionRole)
        buttons.accepted.connect(self.accept)
        main_layout.addWidget(buttons)

    def exec_(self):
        """Shows the dialog and waits until it is closed."""
        result = super().exec_()
        if result == QDialog.Accepted:
            return True
        else:
            return False


class StudentGroupsTabs(QWidget):
    def __init__(self, parent, group_listings=None):
        super().__init__(parent)
        if group_listings is None:
            self.group_listings = students.GroupListings()
            default_group = students.StudentGroup(0, _('Default group'))
            self.group_listings.create_listing(default_group)
        else:
            self.group_listings = group_listings
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)
        self.tabs = QTabWidget(self)
        main_layout.addWidget(self.tabs)
        for listing in self.group_listings:
            if (listing.group.identifier > 0
                    or len(listing) > 0
                    or len(self.group_listings) == 1):
                # Group 0 (default group) is shown only if not empty
                # or if it is the only group
                self._add_group_tab(listing)

    def create_buttons(self):
        button_new_group = QPushButton(_('New student group'))
        button_new_group.clicked.connect(self._new_group)
        return (button_new_group, )

    def _add_group_tab(self, listing, show=False):
        self.tabs.addTab(
            GroupWidget(listing, parent=self.tabs), listing.group.name)
        if show:
            self.tabs.setCurrentIndex(self.tabs.count() - 1)

    def _new_group(self):
        group = students.StudentGroup(None, _('New group'))
        listing = self.group_listings.create_listing(group)
        self._add_group_tab(listing, show=True)


class GroupWidget(QWidget):
    def __init__(self, listing, parent=None):
        super().__init__(parent)
        self.listing = listing
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.table = QTableView()
        self.table.setMinimumWidth(500)
        self.table.setMinimumHeight(400)
        layout.addWidget(self.table)
        self.model = StudentsTableModel(listing, self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        button_load = QPushButton(_('Add students from file'), parent=self)
        button_new_student = QPushButton(
            QIcon(utils.resource_path('new_id.svg')),
            _('New student'),
            parent=self)
        button_new_student.clicked.connect(self._new_student)
        layout.addWidget(button_load)
        layout.addWidget(button_new_student)
        layout.setAlignment(self.table, Qt.AlignHCenter)
        layout.setAlignment(button_load, Qt.AlignHCenter)
        layout.setAlignment(button_new_student, Qt.AlignHCenter)
        button_load.clicked.connect(self._load_students)
        self._resize_table()

    def _resize_table(self):
        self.table.resizeColumnToContents(0)
        self.table.horizontalHeader().setStretchLastSection(True)

    def _load_students(self):
        file_name, __ = QFileDialog.getOpenFileName(
            self,
            _('Select the student list file'),
            '',
            FileNameFilters.student_list,
            None,
            QFileDialog.DontUseNativeDialog)
        try:
            if file_name:
                student_list = students.read_students(file_name)
                self.listing.add_students(student_list)
                self.model.data_reset()
                self._resize_table()
        except Exception as e:
            QMessageBox.critical(
                self,
                _('Error in student list'),
                file_name + '\n\n' + str(e))

    def _new_student(self):
        dialog = NewStudentDialog(parent=self)
        student = dialog.exec_()
        if student is not None:
            self.listing.add_students([student])
            self.model.data_reset()
            self._resize_table()


class StudentsTableModel(QAbstractTableModel):
    """ Table for showing a student list."""

    _headers = (
        '#',
        _('Id'),
        _('Name'),
    )

    _extract = (
        lambda s: s.sequence_num,
        lambda s: s.student_id,
        lambda s: s.name,
    )

    _column_alignment = (
        Qt.AlignRight,
        Qt.AlignRight,
        Qt.AlignLeft,
    )

    def __init__(self, listing, parent=None):
        super().__init__(parent=None)
        self.data_reset(listing=listing)

    def data_reset(self, listing=None):
        self.beginResetModel()
        if listing is not None:
            self.listing = listing
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.listing)

    def columnCount(self, parent=QModelIndex()):
        # Columns: sequence num, id, full name
        return len(StudentsTableModel._headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return StudentsTableModel._headers[section]
            else:
                return QVariant()
        else:
            return QVariant(QVariant.Invalid)

    def data(self, index, role=Qt.DisplayRole):
        column = index.column()
        if role == Qt.DisplayRole:
            student = self.listing[index.row()]
            return StudentsTableModel._extract[column](student)
        elif role == Qt.TextAlignmentRole:
            return StudentsTableModel._column_alignment[column]
        else:
            return QVariant(QVariant.Invalid)

    def flags(self, index):
        return Qt.ItemFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
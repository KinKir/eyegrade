# Eyegrade: grading multiple choice questions with a webcam
# Copyright (C) 2010-2018 Jesus Arias Fisteus
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
import configparser
import csv
import os
import locale
import codecs
import sys
import re
import contextlib


program_name = 'eyegrade'
web_location = 'https://www.eyegrade.org/'
source_location = 'https://github.com/jfisteus/eyegrade'
help_location = 'https://www.eyegrade.org/doc/user-manual/'
version = '0.8.dev3'
version_status = 'alpha'

re_exp_email = r'^[a-zA-Z0-9._%-\+]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,6}$'
re_email = re.compile(re_exp_email)
re_model_letter = re.compile('[0a-zA-Z]')

csv.register_dialect('tabs', delimiter=str('\t'))

results_file_keys = ['seq-num', 'student-id', 'model', 'good', 'bad',
                     'score', 'answers']

default_capture_pattern = 'exam-{student-id}-{seq-number}.png'

# The data_dir variable will be intially none.  The functions in this
# module that depend on the data directory will initialize it if
# needed.
data_dir = None


class ComparableMixin(object):
    """For implementing comparable classes.

    As seen on http://regebro.wordpress.com/2010/12/13/
                      python-implementing-rich-comparison-the-correct-way/

    """
    def _compare(self, other, method):
        try:
            return method(self._cmpkey(), other._cmpkey())
        except (AttributeError, TypeError):
            # _cmpkey not implemented, or return different type,
            # so I can't compare with "other".
            return NotImplemented

    def __lt__(self, other):
        return self._compare(other, lambda s,o: s < o)

    def __le__(self, other):
        return self._compare(other, lambda s,o: s <= o)

    def __eq__(self, other):
       return self._compare(other, lambda s,o: s == o)

    def __ge__(self, other):
        return self._compare(other, lambda s,o: s >= o)

    def __gt__(self, other):
        return self._compare(other, lambda s,o: s > o)

    def __ne__(self, other):
        return self._compare(other, lambda s,o: s != o)


def user_home():
    return os.path.expanduser('~/')

def _read_config():
    """Reads the general config file and returns the resulting config object.

    Other modules can get the config object by accessing the
    utils.config variable.

    """
    config = {
        'camera-dev': '0',
        'save-filename-pattern': default_capture_pattern,
        'csv-dialect': 'tabs',
        'default-charset': 'utf8', # special value: 'system-default'
    }
    parser = configparser.ConfigParser()
    home = user_home()
    try:
        parser.read([os.path.join(home, u'.eyegrade.cfg'),
                     os.path.join(home, u'.camgrade.cfg'),
                     resource_path('default.cfg'),])
    except EyegradeException:
        parser.read([os.path.join(home, u'.eyegrade.cfg'),
                     os.path.join(home, u'.camgrade.cfg'),])
    if 'default' in parser.sections():
        for option in parser.options('default'):
            config[option] = parser.get('default', option)
    if not config['csv-dialect'] in csv.list_dialects():
        config['csv-dialect'] = 'tabs'
    if 'error-logging' in config and config['error-logging'] == 'yes':
        config['error-logging'] = True
    else:
        config['error-logging'] = False
    config['camera-dev'] = int(config['camera-dev'])
    if config['default-charset'] == 'system-default':
        config['default-charset'] = locale.getpreferredencoding()
    if 'gui-styles' in config:
        config['gui-styles'] = tuple(v.strip()
                                     for v in config['gui-styles'].split(','))
    else:
        config['gui-styles'] = None
    return config

class EyegradeException(Exception):
    """An Eyegrade-specific exception.

    In addition to what a normal exception would do, it encapsulates
    user-friendly messages for some common causes of error due to
    the user.

    """

    _error_messages = {}
    _short_messages = {}

    def __init__(self, message, key=None, format_params=None):
        """Creates a new exception.

        If `key` is in `_error_messages`, a prettier version of the
        exception will be shown to the user, with the explanation appended
        to the end of what you provide in `message`.

        """
        self.key = key
        if (key in EyegradeException._error_messages
            or key in EyegradeException._short_messages):
            parts = []
            if message:
                parts.append(message)
            elif key in EyegradeException._short_messages:
                short_msg = EyegradeException._short_messages[key]
                if not format_params:
                    parts.append(short_msg)
                else:
                    parts.append(short_msg.format(*format_params))
            if key in EyegradeException._error_messages:
                parts.append('\n\n')
                parts.append(EyegradeException._error_messages[key])
            parts.append('\n')
            self.full_message = ''.join(parts)
            super(EyegradeException, self).__init__(self.full_message)
        else:
            self.full_message = None
            super(EyegradeException, self).__init__(message)

    def __str__(self):
        """Prints the exception.

        A user-friendly message, without the stack trace, is shown when such
        user-friendly message is available.

        """
        if self.full_message is not None:
            return self.full_message
        else:
            return super(EyegradeException, self).__str__()

    @staticmethod
    def register_error(key, detailed_message='', short_message=''):
        """Registers a new error message associated to a key.

        `key` is just a string used to identify this error message,
        that must be passed when creating exception
        objects. `detailed_message` is a (possibly long and with end
        of line characters inside) explanation of the
        error. `short_message` is a one line error message to be used
        only when a blank message is passed when creating the
        exception.

        Being this method static, messages added through it will be
        shared for all the instances of the exception.

        """
        if (not key in EyegradeException._error_messages
            and not key in EyegradeException._short_messages):
            if detailed_message:
                EyegradeException._error_messages[key] = detailed_message
            if short_message:
                EyegradeException._short_messages[key] = short_message
        else:
            raise EyegradeException('Duplicate error key in register_error')


EyegradeException.register_error('bad_dimensions',
    "Dimensions must be specified as a ';' separated list of tables.\n"
    "For each table, specify the number of choices + comma + the number of\n"
    "questions in that table. For example, '4,10;4,9' configures two\n"
    "tables, the left-most with 9 questions and 4 choices per question,\n"
    "and the right-most with 10 questions and the same number of choices."
    'Bad dimensions value.')

EyegradeException.register_error('same_num_choices',
    "By now, Eyegrade needs you to use the same number of choices in\n"
    "all the questions of the exam.",
    'There are questions with a different number of choices')

_student_list_message = (
    'The file is expected to contain one line per student.\n'
    'Each line can contain one or more TAB-separated columns.\n'
    'The first column must be the student id (a number).\n'
    'The second column, if present, is interpreted as the student name.\n'
    'The rest of the columns are ignored.')

EyegradeException.register_error('error_student_list',
    'The syntax of the student list is not correct.\n' + _student_list_message)

EyegradeException.register_error('error_student_id',
    'At least one student id is not a number.\n' + _student_list_message)

EyegradeException.register_error('error_student_list_encoding',
    'The student list contains erroneously-encoded characters.')

EyegradeException.register_error('load_image',
    'The image cannot be loaded (perhaps a wrong path?).')


class ExportSortKey(object):
    """Constants for the export dialog."""
    STUDENT_LIST = 1
    STUDENT_LAST_NAME = 2
    GRADING_SEQUENCE = 3


def guess_data_dir():
    path = os.path.split(os.path.realpath(__file__))[0]
    # An alternative path to try for pyinstaller's packages:
    path_alt = os.path.split(path)[0]
    paths_to_try = [
        os.path.join(path, 'data'),
        os.path.join(path, '..', 'data'),
        os.path.join(path, '..', '..', 'data'),
        os.path.join(path, '..', '..', '..', 'data'),
        os.path.join(path_alt, 'data'),
    ]
    for p in paths_to_try:
        if os.path.isdir(p):
            return os.path.abspath(p)
    raise EyegradeException('Data path not found!')

def init_data_dir():
    global data_dir
    data_dir = guess_data_dir()

def locale_dir():
    if data_dir is None:
        init_data_dir()
    return os.path.join(data_dir, 'locale')

def qt_translations_dir():
    if data_dir is None:
        init_data_dir()
    return os.path.join(data_dir, 'qt-translations')

def resource_path(file_name):
    if data_dir is None:
        init_data_dir()
    return os.path.join(data_dir, file_name)

# The global configuration object:
config = _read_config()

def write_results(results, filename, csv_dialect, append=False):
    """Writes exam results to a file.

       If filename is None, results are written to stdout. The output
       file is overwritting by default. Use append=True to append
       instead of overwriting.

    """
    if filename is not None:
        if not append:
            file_ = open(filename, 'wb')
        else:
            file_ = open(filename, 'ab')
    else:
        file_ = sys.stdout
    writer = csv.writer(file_, dialect=csv_dialect)
    for result in results:
        data = [str(result['seq-num']),
                result['student-id'],
                result['model'],
                str(result['good']),
                str(result['bad']),
                str(result['score']),
                '/'.join([str(d) for d in result['answers']])]
        writer.writerow(data)
    if filename is not None:
        file_.close()

def check_model_letter(model, allow_question_mark=False):
    """Checks if a model letter is correct.

    The special value '?' is considered valid only if the parameter
    `allow_question_mark` is set.

    """
    if re_model_letter.match(model):
        return model.upper()
    elif allow_question_mark and model == '?':
        return '?'
    else:
        raise Exception('Incorrect model letter: ' + model)

def read_student_ids(filename):
    """Reads the list of student IDs from a CSV-formatted file (tab-separated).

    """
    students = read_student_ids_same_order(filename)
    students_dict = {}
    for sid, full_name, first_name, last_name, email in students:
        students_dict[sid] = (full_name, first_name, last_name, email)
    return students_dict

def read_student_ids_same_order(filename):
    """Reads the list of student IDs from a CSV-formatted file (tab-separated).

    Returns the results as a list of tuples (id, name, email).

    """
    with open(filename, newline='') as csvfile:
        try:
            dialect = csv.Sniffer().sniff(csvfile.read(1024))
        except csv.Error:
            dialect = csv.excel_tab
        csvfile.seek(0)
        reader = csv.reader(csvfile, dialect=dialect)
        student_ids = []
        for row in reader:
            name1 = ''
            name2 = ''
            email = ''
            if len(row) == 0:
                raise EyegradeException('Empty line in student list',
                                        key='error_student_list')
            sid = row[0]
            _check_student_id(sid)
            if len(row) > 1:
                name1 = row[1]
            if len(row) > 2:
                item = row[2]
                if _check_email(item):
                    email = item
                else:
                    name2 = item
            if len(row) > 3:
                item = row[3]
                if _check_email(item):
                    email = item
            if not name2:
                full_name = name1
                first_name = ''
                last_name = ''
            else:
                full_name = ''
                first_name = name1
                last_name = name2
            student_ids.append((sid, full_name, first_name, last_name, email))
    return student_ids

def _check_student_id(student_id):
    """Checks the student id.

    Raises the appropriate exception in case of error.

    """
    try:
        int(student_id)
    except:
        raise EyegradeException('Wrong id in student list: ' + student_id,
                                key='error_student_id')

def _check_email(email):
    """Checks syntactically an email address.

    Returns True if correct, False if incorrect.

    """
    if re_email.match(email):
        return True
    else:
        return False

def read_student_ids_multiple(filenames):
    """Reads student ids from multiple files.

    `filenames` is an iterable of filenames. It may be empty.
    Returns a dictionary.

    """
    st = {}
    for f in filenames:
        st.update(read_student_ids(f))
    return st

def write_grades(grades, file_, csv_dialect):
    """Writes the given grades to a file.

       Results are a list of tuples student_id, good_answers, bad_answers.

    """
    writer = csv.writer(file_, dialect=csv_dialect)
    for grade in grades:
        writer.writerow(grade)

def _permute_answers(answers, permutation):
    assert(len(answers) == len(permutation))
    permutted = [0] * len(answers)
    for i, option in enumerate(answers):
        if option == 0 or option == -1:
            resolved_option = option
        else:
            resolved_option = permutation[i][1][option - 1]
        permutted[permutation[i][0] - 1] = resolved_option
    return permutted

def encode_model(model, num_tables, num_answers):
    """Given the letter of the model, returns the infobits pattern.

       It is formatted as an array of booleans string where the pos. 0
       is the one that goes in the column of the table at the left.
       The length of the string is 'num_tables' * 'num_answers', where
       'num_tables' is the number of answer tables and 'num_tables'
       the number of answers per question. The 'model' must be a
       capital ASCII letter.

    """
    if len(model) != 1 or model < 'A' or model > 'Z':
        raise Exception('Incorrect model letter')
    if model > 'H':
        raise Exception('Model is currently limited to A - H')
    model_num = ord(model) - 65
    num_bits = num_tables * num_answers
    if model_num >= 2 ** num_bits:
        raise Exception('Model number too big given the number of answers')
    seed = _int_to_bin(model_num, 3, True)
    seed[2] = not seed[2]
    seed.append(seed[0] ^ seed[1] ^seed[2])
    seed[2] = not seed[2]
    bit_list = seed * (1 + (num_bits - 1) // 4)
    return bit_list[:num_tables * num_answers]

def decode_model(bit_list, accept_model_0=False):
    """Given the bits that encode the model, returns the associated letter.

       It decoding/checksum fails, None is returned. The list of bits must
       be a list of boolean variables.

       The special model 0 is not valid unless `accept_model_0` is set.

    """
    # x3 = x0 ^ x1 ^ not x2; x0-x3 == x4-x7 == x8-x11 == ...
    valid = False
    if len(bit_list) == 2 or len(bit_list) == 3:
        valid = True
    elif len(bit_list) >= 4:
        if (bit_list[3] == bit_list[0] ^ bit_list[1] ^ (not bit_list[2])):
            valid = True
            for i in range(4, len(bit_list)):
                if bit_list[i] != bit_list[i - 4]:
                    valid = False
                    break
    if valid:
        return chr(65 + (int(bit_list[0]) | int(bit_list[1]) << 1 |
                  int(bit_list[2]) << 2))
    elif accept_model_0 and max(bit_list) == False:
        return '0'
    else:
        return None

def _int_to_bin(n, num_digits, reverse = False):
    """Returns the binary representation of a number as a list of booleans.

       If the number of digits is less than 'num_digits', it is
       completed with False in the most-significative side. If
       'reverse' is True returns the least significative bit in the
       first position of the string.

       There is a bin() function in python >= 2.6, but by now we want
       the program to be compatible with 2.5. Anyway, the behaviour of
       that function is different.

    """
    bin = []
    while n > 0:
        n, r = divmod(n, 2)
        bin.append(True if r else False)
    if len(bin) < num_digits:
        bin.extend([False] * (num_digits - len(bin)))
    if reverse:
        return bin
    else:
        return bin[::-1]

def read_file(file_name):
    """Returns contents of a file as a Unicode string using terminal locale.

    """
    file_ = codecs.open(file_name, 'r', config['default-charset'])
    data = file_.read()
    file_.close()
    return data

def write_file(file_name, unicode_text):
    """Writes a Unicode string in a file using terminal locale.

    """
    file_ = codecs.open(file_name, 'w', config['default-charset'])
    file_.write(unicode_text)
    file_.close()

def write_to_stdout(unicode_text):
    """Writes a Unicode string in sys.stdout using terminal locale.

    """
    writer = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)
    writer.write(unicode_text)

def increment_list(list_):
    """Adds one to every element in a list of integers. Returns a new list.

    """
    return [n + 1 for n in list_]


class Student(object):
    def __init__(self, db_id, student_id, full_name,
                 first_name, last_name, email, group_id,
                 sequence_num, is_in_database=False):
        if full_name and (first_name or last_name):
            raise ValueError('Full name incompatible with first / last name')
        self.db_id = db_id
        self.student_id = student_id
        self.full_name = full_name
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.group_id = group_id
        self.sequence_num = sequence_num
        self.is_in_database = is_in_database

    @property
    def name(self):
        if self.full_name:
            return self.full_name
        elif self.last_name:
            if self.first_name:
                return '{0} {1}'.format(self.first_name, self.last_name)
            else:
                return self.last_name
        elif self.first_name:
            return self.first_name
        else:
            return ''

    @property
    def last_comma_first_name(self):
        if self.last_name:
            if self.first_name:
                return '{0}, {1}'.format(self.last_name, self.first_name)
            else:
                return self.last_name
        else:
            return self.name

    @property
    def id_and_name(self):
        if self.name:
            return ' '.join((self.student_id, self.name))
        else:
            return self.student_id

    @property
    def name_or_id(self):
        if self.name:
            return self.name
        elif self.student_id:
            return self.student_id
        else:
            return ''

    def __str__(self):
        return 'student: ' + self.id_and_name


class StudentGroup(object):
    def __init__(self, identifier, name):
        self.identifier = identifier
        self.name = name

    def __str__(self):
        return 'Group #{0.identifier} ({0.name})'.format(self)


def parse_dimensions(text, check_equal_num_choices=False):
    dimensions = []
    num_options = []
    boxes = text.split(';')
    for box in boxes:
        dims = box.split(',')
        try:
            data = (int(dims[0]), int(dims[1]))
        except ValueError:
            raise EyegradeException('Incorrect number in exam dimensions',
                                    'bad_dimensions')
        if data[0] <= 0 or data[1] <= 0:
            raise EyegradeException('Incorrect number in exam dimensions',
                                    'bad_dimensions')
        dimensions.append(data)
        num_options.extend([data[0]] * data[1])
    if len(dimensions) == 0:
        raise EyegradeException('Dimensions are empty', 'bad_dimensions')
    if check_equal_num_choices:
        for i in range(1, len(dimensions)):
            if dimensions[i][0] != dimensions[0][0]:
                raise EyegradeException('', 'same_num_choices')
    return dimensions, num_options


# Regular expressions used for capture filename patterns
regexp_id = re.compile('\{student-id\}')
regexp_seqnum = re.compile('\{seq-number\}')

def capture_name(filename_pattern, exam_id, student):
    if student is not None:
        sid = student.student_id
    else:
        sid = 'noid'
    filename = regexp_seqnum.sub(str(exam_id), filename_pattern)
    filename = regexp_id.sub(sid, filename)
    return filename

@contextlib.contextmanager
def change_dir(directory):
    prev_directory = os.getcwd()
    if directory:
        os.chdir(directory)
    yield
    if directory:
        os.chdir(prev_directory)

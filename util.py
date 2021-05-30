from PyQt5 import QtWidgets
from PyQt5 import QtCore

import logging
import re

class QTextEditLogger(logging.Handler, QtCore.QObject):
	appendHtml = QtCore.pyqtSignal(str)

	LEVEL_COLORS = {
		"DEBUG": "#aaaaaa",
		"INFO": "#4444ff",
		"WARNING": "#ccaa00",
		"ERROR": "#ff0000"
	}

	def __init__(self, parent):
		super().__init__()
		QtCore.QObject.__init__(self)
		self.widget = QtWidgets.QPlainTextEdit(parent)
		self.widget.setReadOnly(True)
		self.appendHtml.connect(self.widget.appendHtml)

	def emit(self, record):
		msg = self.format(record)
		self.appendHtml.emit(f"<span style=\"color:{self.LEVEL_COLORS[record.levelname]};\">{msg}</span>")

def remove_non_ascii(line):
	return line.encode("ascii", "ignore").decode()

def escape_ansi(line):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)

def sanitize_line(line):
	line = remove_non_ascii(line)
	line = escape_ansi(line)
	line = line.strip()
	return line

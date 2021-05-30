from PyQt5.QtWidgets import * 
from PyQt5.QtGui import * 
from PyQt5.QtCore import *

import ctypes
import sys

from app import App

if __name__ == '__main__':
	ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)

	app = QApplication(sys.argv)
	ex = App()

	exit_code = app.exec_()
	
	sys.exit(exit_code)
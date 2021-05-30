from PyQt5.QtWidgets import * 
from PyQt5.QtGui import * 
from PyQt5.QtCore import *

import pyqtgraph

import qdarkstyle

import asyncio
import datetime
import json
import logging
import os
import threading
import time

from pypresence import Presence, PyPresenceException

from monitor import MinerMonitor

from util import QTextEditLogger
from const import *

os.environ['QT_API'] = 'pyqt5'

cfg = json.load(open("config.json"))

class App(QWidget):
	SMALL_UI_FONT = QFont("Nunito Sans", 16)
	MEDIUM_UI_FONT = QFont("Nunito Sans", 20)
	LARGE_UI_FONT = QFont("Nunito Sans", 30)

	MEDIUM_MONO_FONT = QFont("Consolas", 20)

	def __init__(self):
		super().__init__()
		self.title = f"[QMTR {QMTR_VERSION}]"

		self.width = 640
		self.height = 400

		self.start_time = time.time()

		self.miner = MinerMonitor(cfg)

		self.init_ui()

		self.miner.start_miner()

		self.rich_presence_thread = threading.Thread(target=self.rich_presence_loop, daemon=True)
		self.rich_presence_thread.start()
	
	def init_ui(self):
		self.setWindowTitle(self.title)
		self.setGeometry(self.width // 2, self.height // 2, self.width, self.height)
		self.setFixedSize(self.width, self.height)
		
		self.button_start_stop = QPushButton(None, self)
		self.button_start_stop.setFont(self.MEDIUM_UI_FONT)
		self.button_start_stop.setGeometry(10, 10, 120, 60)
		self.button_start_stop.clicked.connect(self.on_button_start_stop)
		
		self.button_save_log = QPushButton("Save Log", self)
		self.button_save_log.setFont(self.SMALL_UI_FONT)
		self.button_save_log.setGeometry(10, 220, 120, 40)
		self.button_save_log.clicked.connect(self.on_button_save_log)

		self.label_rate = QLabel(None, self)
		self.label_rate.setFont(self.SMALL_UI_FONT)
		self.label_rate.setGeometry(140, 10, 160, 30)

		self.label_jobs = QLabel(None, self)
		self.label_jobs.setFont(self.SMALL_UI_FONT)
		self.label_jobs.setGeometry(140, 40, 160, 30)

		self.label_temp = QLabel(None, self)
		self.label_temp.setFont(self.SMALL_UI_FONT)
		self.label_temp.setGeometry(310, 10, 160, 30)

		self.label_shares = QLabel(None, self)
		self.label_shares.setFont(self.SMALL_UI_FONT)
		self.label_shares.setGeometry(310, 40, 160, 30)

		self.label_diff = QLabel(None, self)
		self.label_diff.setFont(self.SMALL_UI_FONT)
		self.label_diff.setGeometry(470, 10, 160, 30)

		self.label_profit = QLabel(None, self)
		self.label_profit.setFont(self.SMALL_UI_FONT)
		self.label_profit.setGeometry(470, 40, 160, 30)

		self.textbox_log = QTextEditLogger(self)
		self.textbox_log.widget.setGeometry(10, 270, 620, 120)
		self.textbox_log.setFormatter(logging.Formatter(
				fmt="[%(asctime)s.%(msecs)03d] %(levelname)s: %(message)s",
				datefmt='%Y-%m-%d %H:%M:%S'
			)
		)
		logging.getLogger().addHandler(self.textbox_log)
		logging.getLogger().setLevel(logging.DEBUG)

		self.graph_hashrate = pyqtgraph.PlotWidget(self)
		self.graph_hashrate.setGeometry(140, 80, 490, 180)
		self.graph_hashrate.setBackground((0,0,0,0))
		self.graph_hashrate.setXRange(0, HASHRATE_HISTORY_GRAPH_XRANGE, padding=0)
		self.graph_hashrate.setMouseEnabled(False, False)
		self.graph_hashrate.hideButtons()
		self.graph_hashrate.setMenuEnabled(False)
		self.graph_hashrate.setYRange(0, 100, padding=0)
		self.graph_hashrate_dataline = self.graph_hashrate.plot([], [], pen=pyqtgraph.mkPen(color=(255, 0, 0), width=2))

		self.setStyleSheet(qdarkstyle.load_stylesheet())

		self.query_miner()
		query_miner_timer = QTimer(self)
		query_miner_timer.timeout.connect(self.query_miner)
		query_miner_timer.start(50)

		self.show()
	
	@pyqtSlot()
	def query_miner(self):
		self.button_start_stop.setText("Stop" if self.miner.running else "Start")

		self.label_rate.setText("Rate: {:.1f} MH/s".format(
			self.miner.last_recorded_hashrate
		))

		self.label_jobs.setText("Jobs: {}".format(
			self.miner.jobs_count
		))

		self.label_temp.setText(
			"Temp: {}C".format(
				self.miner.last_recorded_temperature
			) if self.miner.last_recorded_temperature else
			"Temp: ..."
		)

		self.label_shares.setText("Shares: {}".format(
			self.miner.shares_count
		))

		self.label_diff.setText("Diff: {}G".format(
			int(self.miner.total_difficulty_mined)
		))

		profitability = self.miner.calculate_profitability()
		self.label_profit.setText(
			"Profit: " +
			("{:.4f}/d".format(profitability) if profitability else "...")
		)

		uptime = time.time() - self.start_time
		self.setWindowTitle("[QMTR 2.0] {} {:.1f} MH/s".format(
			datetime.timedelta(seconds=int(uptime)),
			self.miner.last_recorded_hashrate
		))

		self.graph_hashrate_dataline.setData(range(len(self.miner.hashrate_history)), self.miner.hashrate_history)
		self.graph_hashrate.setYRange(0, max(self.miner.hashrate_history or (0,))+10, padding=0)
	
	def rich_presence_loop(self):
		asyncio.set_event_loop(asyncio.new_event_loop())

		def connect_presence():
			presence = Presence(client_id=cfg["rich_presence_id"])
			try:
				presence.connect()
				logging.info("Discord rich presence connected")
			except:
				presence = None
				logging.warning("Discord rich presence failed to connect")
			
			return presence
		
		presence = connect_presence()

		while True:
			try:
				if presence: presence.update(
					pid=os.getpid(),
					details="Mining Ethash",
					state="{:.1f} MH/s | {} Shares".format(
						self.miner.last_recorded_hashrate,
						self.miner.shares_count
					),
					start=self.start_time,
					large_image="eth",
					large_text=cfg["wallet"],
					buttons=[{"label": "Etherscan", "url": f"https://etherscan.io/address/{cfg['wallet']}"}]
				)
			except PyPresenceException as E:
				logging.warning("Problem with Discord rich presence, reconnecting...")
				presence = connect_presence()
			except:
				pass

			time.sleep(15)

	@pyqtSlot()
	def on_button_start_stop(self):
		if self.miner.running:
			self.miner.stop_miner()
		else:
			self.miner.start_miner()
	
	@pyqtSlot()
	def on_button_save_log(self):
		name = QFileDialog.getSaveFileName(self, "Save Log", "qmtr_log.txt")
		text = self.textbox_log.widget.toPlainText()

		with open(name[0], "w") as file:
			file.write(text)


	# Override
	def closeEvent(self, event):
		if self.miner.running:
			self.miner.stop_miner()



import logging
import requests
from subprocess import Popen, PIPE, CREATE_NO_WINDOW, CalledProcessError
import threading
import time

from util import sanitize_line

from const import *

class MinerMonitor():
	def __init__(self, cfg):
		self.pool_host = cfg["pool_host"]
		self.pool_port = cfg["pool_port"]
		self.pool_wallet = cfg["pool_wallet"]
		self.pool_worker = cfg["pool_worker"]

		self.cryptocompare_api_key = cfg["cryptocompare_api_key"]

		self.process = None

		self.running = False

		self.last_recorded_hashrate = 0
		self.last_recorded_temperature = None
		self.jobs_count = 0
		self.shares_count = 0
		self.total_difficulty_mined = 0

		self.hashrate_history = []

		self.eth_net_hashrate = None
		self.eth_last_block_reward = None
		self.eth_last_block_time = None

		self.eth_price = None

		self.problem_zero_hashrate_detected = 0

		self.cryptocompare_thread = threading.Thread(target=self.cryptocompare_api_loop, daemon=True)
		self.cryptocompare_thread.start()

	def cryptocompare_api_loop(self):
		while True:
			try:
				r = requests.get(
					f"https://min-api.cryptocompare.com/data/blockchain/mining/calculator?fsyms=ETH&tsyms=USD",
					headers = {"authorization": f"Apikey {self.cryptocompare_api_key}"}
				)

				data = r.json()["Data"]

				self.eth_net_hashrate = data["ETH"]["CoinInfo"]["NetHashesPerSecond"]
				self.eth_last_block_reward = data["ETH"]["CoinInfo"]["BlockReward"]
				self.eth_last_block_time = data["ETH"]["CoinInfo"]["BlockTime"]

				self.eth_price = data["ETH"]["Price"]["USD"]
			except:
				pass
		
			time.sleep(180)

	def calculate_profitability(self):
		if not (self.eth_net_hashrate or self.eth_last_block_reward or self.eth_last_block_time):
			return None

		return (self.last_recorded_hashrate * 1000000) / (self.eth_net_hashrate) * (self.eth_last_block_reward) * ((24*60*60) / self.eth_last_block_time)

	def construct_miner_command(self):
		return f".\miner\lolMiner.exe --algo ETHASH --pool {self.pool_host}:{self.pool_port} --user {self.pool_wallet}.{self.pool_worker} --watchdog exit --shortstats 1 --longstats 1"
	
	def start_miner(self):
		self.running = True
		self.watcher_thread = threading.Thread(target=self.watcher_loop, daemon=True)
		self.watcher_thread.start()
	
	def stop_miner(self):
		if self.process: self.process.terminate()

		logging.info("Miner process killed")
		
		self.running = False

		self.last_recorded_hashrate = 0
		self.last_recorded_temperature = None
		self.hashrate_history = []

		del self.watcher_thread

	def watcher_loop(self):
		while self.running:
			self.problem_zero_hashrate_detected = 0

			logging.info("Starting miner process...")

			self.process = Popen(
				self.construct_miner_command(),
				stdout=PIPE,
				bufsize=1,
				universal_newlines=True,
				shell=False,
				creationflags=CREATE_NO_WINDOW
			)

			logging.info("Miner process started")

			for line in self.process.stdout:
				print(line, end="")

				clean_line = sanitize_line(line)

				if INFO_ANSI in line:
					logging.info(clean_line)
				elif WARNING_ANSI in line:
					logging.warning(clean_line)

				if clean_line.startswith("Average speed "):
					rate = float(clean_line.split(" ")[3])
					self.last_recorded_hashrate = rate

					self.hashrate_history.append(rate)
					if len(self.hashrate_history) > HASHRATE_HISTORY_GRAPH_XRANGE:
						self.hashrate_history.pop(0)

					if rate < MIN_AVERAGE_SPEED:
						self.problem_zero_hashrate_detected += 1

						if self.problem_zero_hashrate_detected >= LOW_HASHRATE_RESTART:
							logging.warning("Low hashrate detected, restarting process...")
							self.process.terminate()
					
				
				elif clean_line.startswith("New job received: "):
					self.jobs_count += 1
				
				elif clean_line.startswith("Temp (deg C):"):
					val = clean_line.split()[-1]

					if val != "n.a.":
						self.last_recorded_temperature = int(val)
					else:
						self.last_recorded_temperature = None

				elif "Found a share of difficulty" in clean_line:
					diff_str = clean_line.split(" ")[7]
					diff = float(diff_str[:-1]) * METRIC_LEVELS[diff_str[-1]] / METRIC_LEVELS["G"]
					
					self.total_difficulty_mined += diff
					self.shares_count += 1

					logging.info(clean_line)
				
				elif "DAG gen" in clean_line:
					logging.info(clean_line)

				elif clean_line.endswith("will be stopped."):
					logging.error("Mining error detected, restarting process...")
					self.process.terminate()
			
			if self.running:
				logging.error("Miner crashed, restarting process...")
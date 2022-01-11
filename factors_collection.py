import json
from datetime import datetime
import time
import re
import threading
from ssh_manager import SshConnections, RunCmdLocal


class FactorsCollection:
    def __init__(self, remote, collection_interval, remote_config=None):
        self.sessions = []
        self.threads = []
        self.collection_interval = collection_interval
        self.remote_config = remote_config
        self.data_file_name = "data.json"
        self.remote_collection_mode = remote
        self.temp = None
        self.core_voltage = None
        self.freq_arm = None
        self.freq_core = None
        self.throttle_hex = None
        self.cpu_load = None
        self.mem_load = None
        self.power = None
        self.rxkB = None
        self.txkB = None
        self.gateway_ip = None
        self.device_ip = None
        self.device_metric = None
        self.all_space = None
        self.used_space = None
        self.available_space = None
        self.disk_space_usage = None
        self._generate_data_file_if_not_exist()
        self.file_semaphore = threading.Semaphore()

    def start_agents(self):
        self.threads.append(threading.Thread(target=self.temperature_agent, args=()))
        self.threads.append(threading.Thread(target=self.processors_voltage_agent, args=()))
        self.threads.append(threading.Thread(target=self.system_load_agent, args=()))
        self.threads.append(threading.Thread(target=self.processors_parameter_agent, args=()))
        self.threads.append(threading.Thread(target=self.power_monitor_agent, args=()))
        self.threads.append(threading.Thread(target=self.network_ip_statistic_agent, args=()))
        self.threads.append(threading.Thread(target=self.network_throughput_statistic_agent, args=()))
        self.threads.append(threading.Thread(target=self.disk_usage_agent, args=()))
        for thread in self.threads:
            thread.daemon = True
            thread.start()

    def prepare_connection(self):
        if self.remote_collection_mode:
            return SshConnections(self.remote_config["host"], self.remote_config["username"],
                                  self.remote_config["password"])
        else:
            return RunCmdLocal

    def _generate_data_file_if_not_exist(self):
        try:
            open(self.data_file_name, "r")
        except FileNotFoundError:
            with open(self.data_file_name, "a+") as data_file:
                data_file.seek(0)
                json.dump({"temp": [],
                           "processor_voltage": [],
                           "freq_arm": [],
                           "freq_core": [],
                           "cpu_load": [],
                           "memory_load": [],
                           "throttle": [],
                           "rxkB": [],
                           "txkB": [],
                           "gateway_ip": [],
                           "device_ip": [],
                           "device_metric": [],
                           "all_space": [],
                           "used_space": [],
                           "available_space": [],
                           "disk_space_usage": [],
                           "power": []}, data_file)
                data_file.close()

    def save_factors(self, param_name, entry):
        self.file_semaphore.acquire()
        data = json.load(open(self.data_file_name, "r"))
        data[param_name].append(entry)
        self.put_data_in_json(data)
        self.file_semaphore.release()

    def put_data_in_json(self, data):
        with open(self.data_file_name, "w") as file:
            file.seek(0)
            json.dump(data, file)
            file.close()

    def temperature_agent(self):
        con = self.prepare_connection()
        while True:
            self.temp = re.search(r"\d+\.\d+", con.run_cmd("vcgencmd measure_temp")).group(0)
            self.save_factors("temp", {"time": str(datetime.now()), "value": self.temp})
            time.sleep(self.collection_interval)

    def system_load_agent(self):
        con = self.prepare_connection()
        while True:
            self._process_ps_aux_data(con.run_cmd("ps -aux | grep -v COMMAND"))
            self.save_factors("cpu_load", {"time": str(datetime.now()), "value": str(self.cpu_load)})
            self.save_factors("memory_load", {"time": str(datetime.now()), "value": str(self.mem_load)})
            time.sleep(self.collection_interval)

    def _process_ps_aux_data(self, data):
        self.cpu_load = 0
        self.mem_load = 0
        for line in data:
            match = re.search(r"(?P<CPU>\d+\.\d+).*(?P<MEM>\d+\.\d+)", line)
            self.cpu_load += float(match.group("CPU"))
            self.mem_load += float(match.group("MEM"))
        if self.cpu_load > 100:
            self.cpu_load = 100  # average cpu_load from ps_aux issue

    def processors_voltage_agent(self):
        con = self.prepare_connection()
        while True:
            self.core_voltage = re.search(r"\d+\.\d+", con.run_cmd("vcgencmd measure_volts")).group(0)
            self.save_factors("processor_voltage", {"time": str(datetime.now()), "value": self.core_voltage})
            time.sleep(self.collection_interval)

    def network_throughput_statistic_agent(self):
        con = self.prepare_connection()
        while True:
            for line in con.run_cmd("sar -n DEV 1 1"):
                if "wlan0" in line:
                    self.rxkB = re.split(r"\s+", line)[4]
                    self.txkB = re.split(r"\s+", line)[5]
            self.save_factors("rxkB", {"time": str(datetime.now()), "value": self.rxkB})
            self.save_factors("txkB", {"time": str(datetime.now()), "value": self.txkB})
            time.sleep(self.collection_interval)

    def network_ip_statistic_agent(self):
        con = self.prepare_connection()
        while True:
            ip_matched = re.search(r".*\svia\s(?P<GATEWAY>.*)\sdev\swlan0\ssrc\s(?P<IP>.*)\smetric\s(?P<METRIC>\d+)",
                                   con.run_cmd("ip r")[0])
            self.gateway_ip = ip_matched.group("GATEWAY")
            self.device_ip = ip_matched.group("IP")
            self.device_metric = ip_matched.group("METRIC")
            self.save_factors("gateway_ip", {"time": str(datetime.now()), "value": self.gateway_ip})
            self.save_factors("device_ip", {"time": str(datetime.now()), "value": self.device_ip})
            self.save_factors("device_metric", {"time": str(datetime.now()), "value": self.device_metric})
            time.sleep(self.collection_interval)

    def disk_usage_agent(self):
        con = self.prepare_connection()
        while True:
            regex = r"total\s+(?P<ALL_SPACE>\d+)\s+(?P<USED_SPACE_>\d+)\s+(?P<AVL_SPACE>\d+)\s+(?P<DISK_USAGE>\d+)\%"
            disk_space_matched = re.search(regex, con.run_cmd("df --total")[-1])
            self.all_space = disk_space_matched.group("ALL_SPACE")
            self.used_space = disk_space_matched.group("USED_SPACE_")
            self.available_space = disk_space_matched.group("AVL_SPACE")
            self.disk_space_usage = disk_space_matched.group("DISK_USAGE")
            self.save_factors("all_space", {"time": str(datetime.now()), "value": self.all_space})
            self.save_factors("used_space", {"time": str(datetime.now()), "value": self.used_space})
            self.save_factors("available_space", {"time": str(datetime.now()), "value": self.available_space})
            self.save_factors("disk_space_usage", {"time": str(datetime.now()), "value": self.disk_space_usage})
            time.sleep(self.collection_interval)

    def processors_parameter_agent(self):
        con = self.prepare_connection()
        while True:
            self.freq_arm = re.search(r".*=(?P<FREQ>\d+)", con.run_cmd("vcgencmd measure_clock arm")).group("FREQ")
            self.freq_core = re.search(r".*=(?P<FREQ>\d+)", con.run_cmd("vcgencmd measure_clock core")).group("FREQ")
            self.throttle_hex = re.search(r"0[xX][0-9a-fA-F]+", con.run_cmd("vcgencmd get_throttled")).group(0)
            self.save_factors("freq_arm", {"time": str(datetime.now()), "value": self.freq_arm})
            self.save_factors("freq_core", {"time": str(datetime.now()), "value": self.freq_core})
            self.save_factors("throttle", {"time": str(datetime.now()), "value": self.throttle_hex})
            time.sleep(self.collection_interval)

    def power_monitor_agent(self):
        time.sleep(self.collection_interval + 5)
        while True:
            self.power = 0.5 + 1 / 1000 * float(self.temp) + 1.3 / 1000 * float(self.cpu_load) + 0.5 / 1000 * float(
                self.mem_load)
            self.save_factors("power", {"time": str(datetime.now()), "value": str("{:.1f}".format(self.power * 1000))})
            time.sleep(self.collection_interval)

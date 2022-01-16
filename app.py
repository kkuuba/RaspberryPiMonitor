import streamlit as st
import time
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
import os
from factors_collection import FactorsCollection
import threading
from hashlib import sha256


def get_parameter_data_frame(parameter_name, y_label):
    parameter_collector.file_semaphore.acquire()
    with open(parameter_collector.data_file_name) as json_file:
        data = json.load(json_file)
        json_file.close()
    parameter_collector.file_semaphore.release()
    values = []
    time_stamps = []
    for k in data[parameter_name]:
        time_stamps.append(str(k["time"]))
        values.append(float(k["value"]))

    return pd.DataFrame({"Time line": time_stamps, y_label: values})


st.title("RaspberryPi Monitor")
device_address = st.empty()
device_ssh_username = st.empty()
device_ssh_password = st.empty()
connect_button = st.empty()
power_usage = st.empty()
temperature = st.empty()
cpu_usage = st.empty()
ram_usage = st.empty()
disk_space = st.empty()
dl_stats = st.empty()
ul_stats = st.empty()


def refresh_layout():
    power = px.line(get_parameter_data_frame("power", "Power usage [mW]"), x="Time line", y="Power usage [mW]",
                    title="Actual power usage")
    temp = px.line(get_parameter_data_frame("temp", "Temperature [°C]"), x="Time line", y="Temperature [°C]",
                   title="Actual core temperature")
    cpu = px.line(get_parameter_data_frame("cpu_load", "CPU load [%]"), x="Time line", y="CPU load [%]",
                  title="Actual CPU usage")
    ram = px.line(get_parameter_data_frame("memory_load", "RAM load [%]"), x="Time line", y="RAM load [%]",
                  title="Actual RAM usage")
    free_space = get_parameter_data_frame("available_space", "available_space")["available_space"].iloc[-1]
    used_space = get_parameter_data_frame("used_space", "used_space")["used_space"].iloc[-1]
    disk = go.Figure(data=[
        go.Pie(labels=["Used space", "Free space"], values=[used_space, free_space], hole=.3, title="Disk usage")])
    dl = px.line(get_parameter_data_frame("rxkB", "DL [Kbit/sec]"), x="Time line", y="DL [Kbit/sec]",
                 title="Actual downlink usage")
    ul = px.line(get_parameter_data_frame("txkB", "UL [Kbit/sec]"), x="Time line", y="UL [Kbit/sec]",
                 title="Actual uplink usage")

    power_usage.write(power)
    temperature.write(temp)
    cpu_usage.write(cpu)
    ram_usage.write(ram)
    disk_space.write(disk)
    dl_stats.write(dl)
    ul_stats.write(ul)


address = device_address.text_input("Host", "")
ssh_username = device_ssh_username.text_input("Username", "")
ssh_password = device_ssh_password.text_input("Password", "", type="password")

if connect_button.button('Connect', key='start'):
    data_file_name = "{}.json".format(sha256(address.encode('utf-8')).hexdigest())
    file_exist = os.path.isfile(data_file_name)
    authorization = {"host": address,
                     "username": ssh_username,
                     "password": ssh_password}
    parameter_collector = FactorsCollection(True, 10, authorization, file_name=data_file_name)
    factor_collection_thread = threading.Thread(target=parameter_collector.start_agents, name="factor_collection",
                                                args=())
    factor_collection_thread.start()
    connect_button.empty()
    device_address.empty()
    device_ssh_username.empty()
    device_ssh_password.empty()
    if not file_exist:
        with st.spinner("Waiting for data from remote device ..."):
            time.sleep(20)
    if st.button('Disconnect', key='stop'):
        factor_collection_thread.join()
        pass
    while True:
        refresh_layout()
        time.sleep(7)

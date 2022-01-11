import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json
import time
from factors_collection import FactorsCollection
import threading

factor_collection_thread = threading.Thread(target=FactorsCollection(True, 10, {}).start_agents,
                                            name="factor_collection", args=())
factor_collection_thread.start()

st.set_page_config(layout="wide")

with open('data.json') as json_file:
    data = json.load(json_file)
    json_file.close()


def get_factor_values(factor_name):
    values = []
    for k in data[factor_name]:
        values.append(float(k["value"]))

    return values


network_data = pd.DataFrame({"UL [Kbit/sec]": get_factor_values("rxkB"), "DL [Kbit/sec]": get_factor_values("txkB")})

power_usage_values = np.array(get_factor_values("power"))
temperature_values = np.array(get_factor_values("temp"))
cpu_usage_values = np.array(get_factor_values("cpu_load"))
ram_usage_values = np.array(get_factor_values("memory_load"))

available_space = get_factor_values("available_space")[-1] / 1000
used_space = get_factor_values("used_space")[-1] / 1000

source = pd.DataFrame(
    {"category": ["Available space [MB]", "Used space [MB]"], "value": [available_space, used_space]})

disk_usage = alt.Chart(source).mark_arc(innerRadius=50).encode(
    theta=alt.Theta(field="value", type="quantitative"),
    color=alt.Color(field="category", type="nominal"),
)

start_button = st.empty()


def refresh_data():
    header = st.container()
    disk_space_usage, network_stats = st.columns(2)
    power_usage, temperature, cpu_usage, ram_usage = st.columns(4)

    power_usage.metric("Power usage", "{:.2f} mW".format(power_usage_values[-1]),
                       "{:.2f} mW".format(power_usage_values[-1] - power_usage_values.mean()), delta_color="inverse")
    temperature.metric("Temperature", "{:.2f} °C".format(temperature_values[-1]),
                       "{:.2f} °C".format(temperature_values[-1] - temperature_values.mean()), delta_color="inverse")
    cpu_usage.metric("CPU usage", "{:.2f} %".format(cpu_usage_values[-1]),
                     "{:.2f}%".format(cpu_usage_values[-1] - cpu_usage_values.mean()), delta_color="inverse")
    ram_usage.metric("RAM usage", "{:.2f} %".format(ram_usage_values[-1]),
                     "{:.2f}%".format(ram_usage_values[-1] - ram_usage_values.mean()), delta_color="inverse")

    with header:
        st.title("RaspberryPiMonitor")

    with disk_space_usage:
        st.write("Disk space usage")
        st.altair_chart(disk_usage, use_container_width=True)
    with network_stats:
        st.write("Network statistics")
        st.line_chart(network_data, use_container_width=True)


if start_button.button('Start', key='start'):
    start_button.empty()
    if st.button('Stop', key='stop'):
        pass
    while True:
        refresh_data()
        time.sleep(0.5)

import streamlit as st
import random
import time

st.title("🚀 Predictive Last-Mile Transit Synchronizer")

st.subheader("📍 City Overview")

# Stations
stations = {
    "Station A": 2,
    "Station B": 5,
    "Station C": 8
}

# Initialize vehicles
if "vehicles" not in st.session_state:
    st.session_state.vehicles = [
        {"id": i, "pos": random.randint(0, 10)} for i in range(8)
    ]

# Display stations
st.write("### 🚉 Stations")
for name, pos in stations.items():
    st.write(f"{name} → Position {pos}")

# Display vehicles
st.write("### 🚗 Vehicles")
for v in st.session_state.vehicles:
    st.write(f"Vehicle {v['id']} → Position {v['pos']}")

# Button to simulate train arrival
if st.button("🚆 Simulate Train Arrival at Station A"):

    st.warning("🚨 Surge Detected at Station A")

    target = stations["Station A"]

    # Move vehicles step by step
    for step in range(3):
        for v in st.session_state.vehicles:
            if v["pos"] > target:
                v["pos"] -= 1
            elif v["pos"] < target:
                v["pos"] += 1

        time.sleep(0.5)
        st.rerun()
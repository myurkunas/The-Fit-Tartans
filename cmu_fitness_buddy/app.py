import streamlit as st
import pandas as pd

st.title("🏋️ CMU Fitness Buddy")
st.write("Hello! Welcome to your custom fitness buddy!")

# Example data to go
df = pd.DataFrame({
    "Class": ["Yoga", "Spin", "HIIT"],
    "Date": ["2025-09-29", "2025-09-30", "2025-10-01"],
    "Location": ["Studio A", "Studio B", "Gym Floor"]
})

st.subheader("Sample Data")
st.dataframe(df)

# Example user input
name = st.text_input("What’s your name?")
if name:
    st.success(f"Welcome to CMU Fitness Buddy, {name}!")

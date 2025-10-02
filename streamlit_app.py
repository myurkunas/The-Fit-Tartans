import streamlit as st
import pandas as pd
from cmu_scraper import scrape_groupx
from eventbrite_scraper import scrape_eventbrite
from google_calendar import get_calendar_events
from combiner import combine_data

st.set_page_config(page_title="Fit-Tartans Demo", layout="wide")

st.title("📅 Fit-Tartans Fitness Scheduler")

# ------------------------
# CMU GroupX Scraper
# ------------------------
st.header("Scrape CMU GroupX classes")
headless = st.toggle("Run headless browser", value=True)

if st.button("Run GroupX Selenium scraper"):
    with st.spinner("Scraping CMU GroupX classes..."):
        groupx_df = scrape_groupx(headless=headless)
        st.success("GroupX data is ready ✅")
        st.dataframe(groupx_df)

# ------------------------
# Eventbrite Scraper
# ------------------------
st.header("Scrape Eventbrite fitness events")

if st.button("Run Eventbrite scraper now"):
    with st.spinner("Scraping Eventbrite events..."):
        eventbrite_df = scrape_eventbrite()
        st.success("Eventbrite data is ready ✅")
        st.dataframe(eventbrite_df)

# ------------------------
# Google Calendar
# ------------------------
st.header("Your Google Calendar events")

if st.button("Load my Google Calendar"):
    with st.spinner("Fetching your next 14 days of events..."):
        calendar_df = get_calendar_events()
        st.success("Calendar data is ready ✅")
        st.dataframe(calendar_df)

# ------------------------
# Combine All
# ------------------------
st.header("Combine all schedules")

if st.button("Combine my schedule"):
    with st.spinner("Combining data sources..."):
        try:
            groupx_df = scrape_groupx(headless=True)
            eventbrite_df = scrape_eventbrite()
            calendar_df = get_calendar_events()

            final_df = combine_data(groupx_df, eventbrite_df, calendar_df)
            st.success("Combined schedule ready ✅")
            st.dataframe(final_df)

        except Exception as e:
            st.error(f"Error combining schedules: {e}")

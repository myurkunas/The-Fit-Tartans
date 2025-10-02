import streamlit as st
import pandas as pd

# Import Python File Scripts
import google_calendar
import combiner

# Fitness Class Scrapers
try:
    import eventbrite_scraper
except ImportError:
    eventbrite_scraper = None

# CMU GroupX scraper
try:
    import cmu_scraper
except ImportError:
    cmu_scraper = None

st.title("CMU Student Fitness Scheduler")

st.markdown(
    "This app pulls your Google Calendar plus fitness events from Eventbrite and CMU GroupX, "
    "then combines them into one schedule so you can see which classes fit your calendar."
)

# Store DataFrames in session state
if "calendar_df" not in st.session_state:
    st.session_state["calendar_df"] = None
if "eventbrite_df" not in st.session_state:
    st.session_state["eventbrite_df"] = None
if "groupx_df" not in st.session_state:
    st.session_state["groupx_df"] = None

# -------------------------
# Google Calendar
# -------------------------
st.header("Step 1: Fetch Google Calendar Events")
if st.button("Fetch Google Calendar (next 14 days)"):
    try:
        cal_df = google_calendar.get_calendar_events()
        st.session_state["calendar_df"] = cal_df
        st.success("Calendar events loaded")
        st.dataframe(cal_df)
    except Exception as e:
        st.error(f"Error fetching calendar: {e}")

# -------------------------
# Eventbrite Scraper
# -------------------------
st.header("Step 2: Scrape Eventbrite Fitness Events")
if eventbrite_scraper:
    if st.button("Scrape Eventbrite"):
        try:
            eb_df = eventbrite_scraper.get_eventbrite_events()
            st.session_state["eventbrite_df"] = eb_df
            st.success("Eventbrite events scraped")
            st.dataframe(eb_df)
        except Exception as e:
            st.error(f"Error scraping Eventbrite: {e}")
else:
    st.info("Eventbrite scraper not integrated as .py file. Please add eventbrite_scraper.py into your repo root.")

# -------------------------
# GroupX Scraper
# -------------------------
st.header("Step 3: Scrape CMU GroupX Events")
if cmu_scraper:
    if st.button("Scrape GroupX"):
        try:
            gx_df = cmu_scraper.scrape_groupx(headless=True)   # <- fixed function call
            st.session_state["groupx_df"] = gx_df
            st.success("GroupX events scraped")
            st.dataframe(gx_df)
        except Exception as e:
            st.error(f"Error scraping GroupX: {e}")
else:
    st.info("GroupX scraper not integrated as .py file yet.")

# -------------------------
# Combine All
# -------------------------
st.header("Step 4: Combine All Events")
if st.button("Combine"):
    cal_df = st.session_state.get("calendar_df")
    eb_df = st.session_state.get("eventbrite_df")
    gx_df = st.session_state.get("groupx_df")

    if cal_df is not None and eb_df is not None and gx_df is not None:
        try:
            final_df = combiner.standardize_and_combine(cal_df, eb_df, gx_df)
            st.success("Combined schedule created")
            st.dataframe(final_df)

            # Download option
            csv = final_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download Combined CSV",
                csv,
                "combined_schedule.csv",
                "text/csv"
            )
        except Exception as e:
            st.error(f"Error combining data: {e}")
    else:
        st.warning("Please run all three steps first.")


import os
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# ---- Local project imports (use your modules) ----
try:
    from google_calendar import get_google_credentials, get_calendar_events
except Exception as e:
    get_google_credentials = None
    get_calendar_events = None

try:
    from combiner import standardize_and_combine
except Exception as e:
    standardize_and_combine = None

# CMU GroupX Selenium scraper is optional for the demo (falls back to CSV)
CMU_AVAILABLE = True
try:
    # Your class name may differ; import at module level for speed
    from cmu_scraper import CMUGroupXSeleniumScraper
except Exception:
    CMU_AVAILABLE = False


st.set_page_config(page_title="Fit-Tartans Demo", page_icon="🏋️", layout="wide")
st.title("🏋️ The Fit-Tartans – End‑to‑End Demo")

st.write("""This app demonstrates the full pipeline:
1) Pull your next 14 days from Google Calendar,
2) Scrape Eventbrite fitness classes,
3) Scrape CMU GroupX classes,
4) Combine everything and show classes that fit around your schedule.
""")

with st.sidebar:
    st.header("Options")
    use_cached = st.toggle("Use cached CSVs if available (recommended for demo)", value=True)
    show_raw = st.toggle("Show raw dataframes", value=False)
    st.markdown("---")
    st.caption("Tip: For a smooth video, pre-run scrapers and save CSVs.")

# ---------- Helpers ----------

def read_csv_if_exists(path: str):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            return df
        except Exception:
            return None
    return None

def save_csv(df: pd.DataFrame, filename: str):
    try:
        df.to_csv(filename, index=False)
        st.toast(f"Saved {filename}")
    except Exception:
        pass

# ---------- TABS (one step per tab) ----------
tab1, tab2, tab3, tab4 = st.tabs([
    "1) Google Calendar", "2) Eventbrite", "3) GroupX (CMU)", "4) Combine & View"
])

# --- STATE ---
if "google_df" not in st.session_state: st.session_state.google_df = None
if "eventbrite_df" not in st.session_state: st.session_state.eventbrite_df = None
if "cmu_df" not in st.session_state: st.session_state.cmu_df = None
if "final_df" not in st.session_state: st.session_state.final_df = None


# ------------------------
# TAB 1 – Google Calendar
# ------------------------
with tab1:
    st.subheader("Authorize & fetch next 14 days")
    st.caption("OAuth happens in the browser. Redirect URI must match your Google Cloud OAuth app settings.")
    gc_btn = st.button("🔐 Login to Google & Fetch Events", type="primary")
    if gc_btn:
        if get_google_credentials is None or get_calendar_events is None:
            st.error("Couldn't import google_calendar.py. Make sure it's in this folder and exports get_google_credentials() and get_calendar_events().")
        else:
            with st.spinner("Opening OAuth and fetching upcoming events..."):
                creds = get_google_credentials()
                if creds:
                    df = get_calendar_events(creds)
                    if df is not None and not df.empty:
                        st.session_state.google_df = df
                        save_csv(df, "google_calendar_events.csv")
                        st.success(f"Fetched {len(df)} Google Calendar rows")
                    else:
                        st.warning("No events found.")
                else:
                    st.info("Please complete the login flow, then click the button again.")

    # Load cached CSV if requested
    if st.session_state.google_df is None and use_cached:
        cached = read_csv_if_exists("google_calendar_events.csv")
        if cached is not None:
            st.session_state.google_df = cached
            st.info("Loaded cached google_calendar_events.csv")

    if st.session_state.google_df is not None:
        st.success("Google Calendar data is ready ✅")
        if show_raw:
            st.dataframe(st.session_state.google_df, use_container_width=True)


# ------------------------
# TAB 2 – Eventbrite
# ------------------------
with tab2:
    st.subheader("Scrape Eventbrite fitness events")
    st.caption("If you have a separate notebook/script, run it beforehand to produce eventbrite_events.csv for a faster demo.")
    eb_col1, eb_col2 = st.columns([1,1])
    with eb_col1:
        run_eb = st.button("🕸️ Run Eventbrite scraper now", help="Runs your custom scraper if wired in this app.")
    with eb_col2:
        load_eb = st.button("📥 Load eventbrite_events.csv")
    # Placeholder: user notebooks typically save to CSV. We support that flow.
    if run_eb:
        # If you've refactored your notebook into a function, you can import and call it here.
        st.info("Plug your Eventbrite scraping function here. For the demo, use the CSV loader instead.")
    if load_eb:
        df = read_csv_if_exists("eventbrite_events.csv")
        if df is not None:
            st.session_state.eventbrite_df = df
            st.success(f"Loaded {len(df)} Eventbrite rows from eventbrite_events.csv")
        else:
            st.error("eventbrite_events.csv not found in this folder.")
    # Auto-load cached
    if st.session_state.eventbrite_df is None and use_cached:
        cached = read_csv_if_exists("eventbrite_events.csv")
        if cached is not None:
            st.session_state.eventbrite_df = cached
            st.info("Loaded cached eventbrite_events.csv")
    if st.session_state.eventbrite_df is not None:
        st.success("Eventbrite data is ready ✅")
        if show_raw:
            st.dataframe(st.session_state.eventbrite_df, use_container_width=True)


# ------------------------
# TAB 3 – GroupX (CMU)
# ------------------------
with tab3:
    st.subheader("Scrape CMU GroupX classes")
    headless = st.toggle("Run headless browser", value=True)
    gx_col1, gx_col2 = st.columns([1,1])
    with gx_col1:
        run_cmu = st.button("🤖 Run GroupX Selenium scraper")
    with gx_col2:
        load_cmu = st.button("📥 Load cmu_groupx_classes.csv")

    if run_cmu:
        if not CMU_AVAILABLE:
            st.error("Couldn't import cmu_scraper.py or CMUGroupXSeleniumScraper. Use the CSV loader instead.")
        else:
            with st.spinner("Launching Selenium and scraping CMU GroupX..."):
                try:
                    scraper = CMUGroupXSeleniumScraper(headless=headless)
                    data = scraper.scrape_schedule_data()
                    if data:
                        df = pd.DataFrame(data)
                        st.session_state.cmu_df = df
                        save_csv(df, "cmu_groupx_classes.csv")
                        st.success(f"Scraped {len(df)} classes.")
                    else:
                        st.warning("No classes scraped. Try logging in in a non-headless run or use cached CSV.")
                except Exception as e:
                    st.exception(e)

    if load_cmu:
        df = read_csv_if_exists("cmu_groupx_classes.csv")
        if df is not None:
            st.session_state.cmu_df = df
            st.success(f"Loaded {len(df)} GroupX rows from cmu_groupx_classes.csv")
        else:
            st.error("cmu_groupx_classes.csv not found in this folder.")
    # Auto-load cached
    if st.session_state.cmu_df is None and use_cached:
        cached = read_csv_if_exists("cmu_groupx_classes.csv")
        if cached is not None:
            st.session_state.cmu_df = cached
            st.info("Loaded cached cmu_groupx_classes.csv")
    if st.session_state.cmu_df is not None:
        st.success("GroupX data is ready ✅")
        if show_raw:
            st.dataframe(st.session_state.cmu_df, use_container_width=True)


# ------------------------
# TAB 4 – Combine & View
# ------------------------
with tab4:
    st.subheader("Combine into a single view")
    combine_btn = st.button("🔗 Combine DataFrames", type="primary")
    if combine_btn:
        if standardize_and_combine is None:
            st.error("Couldn't import combiner.standardize_and_combine. Ensure combiner.py is present.")
        else:
            with st.spinner("Cleaning, merging and removing overlaps..."):
                google_df = st.session_state.google_df if st.session_state.google_df is not None else pd.DataFrame()
                eb_df = st.session_state.eventbrite_df if st.session_state.eventbrite_df is not None else pd.DataFrame()
                cmu_df = st.session_state.cmu_df if st.session_state.cmu_df is not None else pd.DataFrame()

                final_df = standardize_and_combine(google_df, eb_df, cmu_df)
                st.session_state.final_df = final_df
                if final_df is not None and not final_df.empty:
                    st.success(f"Combined: {len(final_df)} rows")
                    save_csv(final_df, "final_combined_schedule.csv")
                else:
                    st.warning("Final dataframe is empty.")

    # Display + filters
    if st.session_state.final_df is not None and not st.session_state.final_df.empty:
        df = st.session_state.final_df.copy()
        st.markdown("### Filters")
        search = st.text_input("Search text (in event/title/description/location)", "")
        if search:
            s = search.lower()
            mask = (
                df["scraped_event"].fillna("").str.lower().str.contains(s) |
                df["calendar_event"].fillna("").str.lower().str.contains(s) |
                df["description"].fillna("").str.lower().str.contains(s) |
                df["location"].fillna("").str.lower().str.contains(s)
            )
            df = df[mask]

        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download final_combined_schedule.csv",
                           df.to_csv(index=False),
                           "final_combined_schedule.csv")
    else:
        st.info("Run the steps above, then click **Combine DataFrames**.")

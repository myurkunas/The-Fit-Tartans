
import os
import json
import pytz
import time
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date, time as dtime

# ======== Optional Google Calendar imports (only when user connects) ========
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except Exception:
    GOOGLE_LIBS_AVAILABLE = False

# =================== Page & session config ===================
st.set_page_config(page_title="CMU Fitness Buddy", layout="wide")
st.title("🏋️ CMU Fitness Buddy — Streamlit Demo")

st.caption("Find GroupX and Eventbrite classes that don't conflict with your Google Calendar (next 14 days).")

# ================ Helpers & caching ================
EASTERN = pytz.timezone("US/Eastern")
WEEKDAYS = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}

@st.cache_data(show_spinner=False)
def read_groupx_csv(path: str = "cmu_groupx_classes.csv") -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    # Expected columns from your CSV:
    # term_name, term_start_date, term_end_date, registration_url, campus_area, weekday,
    # class_name, time_range_text, start_time_local, end_time_local, studio, class_description
    return df

def _parse_ampm(t: str) -> dtime:
    """Parse '8:00am' style strings into time objects (local)."""
    if pd.isna(t) or not isinstance(t, str) or not t.strip():
        return None
    try:
        return datetime.strptime(t.strip().lower().replace(" ", ""), "%I:%M%p").time()
    except Exception:
        # Try without minutes, e.g., '8am'
        try:
            return datetime.strptime(t.strip().lower().replace(" ", ""), "%I%p").time()
        except Exception:
            return None

def _daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)

def expand_groupx_to_events(df: pd.DataFrame, window_days: int = 14) -> pd.DataFrame:
    """Expand weekly GroupX rows into dated events in the next 'window_days' (bounded by term dates)."""
    if df.empty:
        return df

    today = datetime.now(EASTERN).date()
    end_window = today + timedelta(days=window_days)

    out = []
    for _, row in df.iterrows():
        wd = str(row.get("weekday", "")).strip()[:3]  # 'Mon', 'Tue', ...
        if wd not in WEEKDAYS:
            continue

        # Bound by term
        try:
            term_start = datetime.strptime(str(row.get("term_start_date")), "%Y-%m-%d").date()
            term_end = datetime.strptime(str(row.get("term_end_date")), "%Y-%m-%d").date()
        except Exception:
            # If term dates are missing, just use the 14-day window
            term_start, term_end = today, end_window

        start_date = max(today, term_start)
        end_date = min(end_window, term_end)

        stime = _parse_ampm(row.get("start_time_local"))
        etime = _parse_ampm(row.get("end_time_local"))

        for d in _daterange(start_date, end_date):
            if d.weekday() == WEEKDAYS[wd] and stime and etime:
                start_dt = EASTERN.localize(datetime.combine(d, stime))
                end_dt = EASTERN.localize(datetime.combine(d, etime))
                out.append({
                    "source": "GroupX",
                    "name": row.get("class_name"),
                    "start": start_dt,
                    "end": end_dt,
                    "location": row.get("studio"),
                    "campus_area": row.get("campus_area"),
                    "description": row.get("class_description"),
                    "register_url": row.get("registration_url"),
                })

    if not out:
        return pd.DataFrame()
    events = pd.DataFrame(out).sort_values("start").reset_index(drop=True)
    return events

@st.cache_data(show_spinner=False)
def try_import_groupx_live() -> pd.DataFrame:
    """Optional: try to use live scraper if available in this environment, else return empty."""
    try:
        import cmu_scraper  # your module
        if hasattr(cmu_scraper, "scrape_groupx"):
            df = cmu_scraper.scrape_groupx()
            return df
    except Exception as e:
        st.info("GroupX live scraping not available in this environment; using CSV fallback if present.")
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def try_import_eventbrite_live() -> pd.DataFrame:
    """Optional: call your Eventbrite scraper if available; else return empty."""
    # Expect a function `scrape_eventbrite()` returning a DataFrame with columns:
    # name, start (datetime), end (datetime), location, description, register_url
    try:
        import eventbrite_scraper  # if you refactor your notebook to this module
        if hasattr(eventbrite_scraper, "scrape_eventbrite"):
            return eventbrite_scraper.scrape_eventbrite()
    except Exception:
        st.info("Eventbrite live scraping not available in this environment.")
    return pd.DataFrame()

def _google_client_config_from_secrets():
    """Read Google OAuth client from Streamlit secrets: [google] client_id, client_secret, redirect_uri"""
    if "google" not in st.secrets:
        return None
    cfg = {
        "web": {
            "client_id": st.secrets["google"].get("client_id"),
            "client_secret": st.secrets["google"].get("client_secret"),
            "project_id": st.secrets["google"].get("project_id", "cmu-fitness-buddy"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [st.secrets["google"].get("redirect_uri")],
            "javascript_origins": [st.secrets["google"].get("origin", st.secrets["google"].get("redirect_uri", ""))],
        }
    }
    if not cfg["web"]["client_id"] or not cfg["web"]["client_secret"] or not cfg["web"]["redirect_uris"][0]:
        return None
    return cfg

def _creds_to_dict(creds: Credentials) -> dict:
    return {
        "token": creds.token,
        "refresh_token": getattr(creds, "refresh_token", None),
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }

def ensure_google_login():
    """Render a sign-in link and complete OAuth when Google creds not yet in session."""
    if not GOOGLE_LIBS_AVAILABLE:
        st.error("Google libraries not installed. Add them to requirements.txt: google-auth, google-auth-oauthlib, google-api-python-client")
        return None

    cfg = _google_client_config_from_secrets()
    if not cfg:
        st.warning("Google OAuth secrets not configured. Add [google] client_id, client_secret, redirect_uri to Streamlit secrets.")
        return None

    if "google_creds_dict" in st.session_state:
        try:
            creds = Credentials(**st.session_state["google_creds_dict"])
            return creds
        except Exception:
            st.session_state.pop("google_creds_dict", None)

    flow = Flow.from_client_config(
        cfg,
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        redirect_uri=cfg["web"]["redirect_uris"][0],
    )

    # If this is a redirect back from Google, "code" will be in query params
    params = st.experimental_get_query_params()
    if "code" in params:
        try:
            flow.fetch_token(code=params["code"][0])
            creds = flow.credentials
            st.session_state["google_creds_dict"] = _creds_to_dict(creds)
            st.success("Google Calendar connected!")
            return creds
        except Exception as e:
            st.error(f"OAuth error: {e}")
            return None

    # Otherwise, render login link
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    st.markdown(f"[🔐 Connect Google Calendar]({auth_url})")
    return None

@st.cache_data(show_spinner=False)
def fetch_calendar_events(creds_dict: dict, days: int = 14) -> pd.DataFrame:
    """Fetch next N days from Google Calendar primary as a DataFrame with tz-aware datetimes (Eastern)."""
    if not creds_dict:
        return pd.DataFrame()

    creds = Credentials(**creds_dict)
    service = build("calendar", "v3", credentials=creds)

    now_utc = datetime.utcnow()
    max_utc = now_utc + timedelta(days=days)

    now_iso = now_utc.isoformat() + "Z"
    max_iso = max_utc.isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now_iso,
        timeMax=max_iso,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    items = events_result.get("items", [])
    rows = []
    for ev in items:
        # Google events may have 'dateTime' or all-day 'date'
        start_raw = ev.get("start", {})
        end_raw = ev.get("end", {})
        start_s = start_raw.get("dateTime") or start_raw.get("date")
        end_s = end_raw.get("dateTime") or end_raw.get("date")

        # Parse into timezone-aware datetimes in Eastern for comparison
        def _to_dt(s, is_end=False):
            if not s:
                return None
            # All-day events are in 'YYYY-MM-DD'
            if len(s) == 10 and s.count("-") == 2:
                d = datetime.strptime(s, "%Y-%m-%d").date()
                # treat all-day as 00:00 to 23:59:59
                t = dtime(23, 59, 59) if is_end else dtime(0, 0, 0)
                return EASTERN.localize(datetime.combine(d, t))
            # dateTime with tz
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                return None
            return dt.astimezone(EASTERN)

        start_dt = _to_dt(start_s, is_end=False)
        end_dt = _to_dt(end_s, is_end=True)

        rows.append({
            "name": ev.get("summary", "Busy"),
            "start": start_dt,
            "end": end_dt,
            "location": ev.get("location"),
            "description": ev.get("description"),
        })

    df = pd.DataFrame(rows).dropna(subset=["start", "end"])
    return df

def detect_conflicts(candidate_events: pd.DataFrame, calendar_df: pd.DataFrame) -> pd.DataFrame:
    """Keep only candidate events that do not overlap with any calendar event (simple O(nm) check)."""
    if candidate_events.empty:
        return candidate_events
    if calendar_df.empty:
        # No conflicts to remove
        candidate_events["conflicts"] = False
        return candidate_events

    # For speed, sort both
    cand = candidate_events.sort_values("start").reset_index(drop=True)
    cal = calendar_df.sort_values("start").reset_index(drop=True)

    # Two-pointer sweep
    j = 0
    cal_list = cal.to_dict("records")
    out = []
    for _, ev in cand.iterrows():
        s, e = ev["start"], ev["end"]
        conflict = False
        while j < len(cal_list) and cal_list[j]["end"] < s:
            j += 1
        k = j
        while k < len(cal_list) and cal_list[k]["start"] <= e:
            if (s < cal_list[k]["end"]) and (e > cal_list[k]["start"]):
                conflict = True
                break
            k += 1
        rec = ev.to_dict()
        rec["conflicts"] = conflict
        out.append(rec)

    out_df = pd.DataFrame(out)
    return out_df[out_df["conflicts"] == False].drop(columns=["conflicts"])

def format_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    disp = df.copy()
    disp["date"] = disp["start"].dt.strftime("%a, %b %d")
    disp["start_time"] = disp["start"].dt.strftime("%-I:%M %p")
    disp["end_time"] = disp["end"].dt.strftime("%-I:%M %p")
    cols = ["source", "name", "date", "start_time", "end_time", "location", "register_url"]
    for c in cols:
        if c not in disp.columns:
            disp[c] = ""
    return disp[cols].sort_values(["date", "start_time", "source", "name"])

# =================== Sidebar controls ===================
with st.sidebar:
    st.header("Settings")
    use_live_groupx = st.toggle("Live scrape GroupX (if module available)", value=False)
    use_live_eventbrite = st.toggle("Live scrape Eventbrite (if module available)", value=False)
    st.caption("Tip: Disable both toggles on Streamlit Cloud for a quick demo using the CSV.")

# =================== Load data sources ===================
# 1) GroupX (live or CSV)
groupx_raw = pd.DataFrame()
if use_live_groupx:
    groupx_raw = try_import_groupx_live()
if groupx_raw.empty:
    groupx_raw = read_groupx_csv()
groupx_events = expand_groupx_to_events(groupx_raw)

# 2) Eventbrite (if available)
eventbrite_events = pd.DataFrame()
if use_live_eventbrite:
    eventbrite_events = try_import_eventbrite_live()
    # Ensure same columns as groupx_events where possible
    if not eventbrite_events.empty:
        # Try to coerce column names to expected schema
        rename_map = {
            "event_name": "name",
            "title": "name",
            "start_time": "start",
            "end_time": "end",
            "url": "register_url"
        }
        eventbrite_events = eventbrite_events.rename(columns=rename_map)
        # tz-awareness
        if "start" in eventbrite_events and pd.api.types.is_datetime64_any_dtype(eventbrite_events["start"]) and eventbrite_events["start"].dt.tz is None:
            eventbrite_events["start"] = eventbrite_events["start"].dt.tz_localize(EASTERN)
        if "end" in eventbrite_events and pd.api.types.is_datetime64_any_dtype(eventbrite_events["end"]) and eventbrite_events["end"].dt.tz is None:
            eventbrite_events["end"] = eventbrite_events["end"].dt.tz_localize(EASTERN)
        eventbrite_events["source"] = "Eventbrite"

# Combine candidate events (GroupX + Eventbrite)
candidates = pd.concat([groupx_events, eventbrite_events], ignore_index=True, sort=False)
if "source" not in candidates.columns and not candidates.empty:
    candidates["source"] = "GroupX"

# =================== Google Calendar Connect ===================
st.subheader("1) Connect your Google Calendar")
creds = ensure_google_login()

calendar_df = pd.DataFrame()
if creds:
    calendar_df = fetch_calendar_events(_creds_to_dict(creds), days=14)
    if calendar_df.empty:
        st.info("No upcoming Google Calendar events found in the next 14 days.")
    else:
        with st.expander("Your next 14 days (from Google Calendar)"):
            st.dataframe(calendar_df[["name", "start", "end", "location"]])

# =================== Recommendations ===================
st.subheader("2) Recommended classes that don't conflict")
if candidates.empty:
    st.warning("No candidate events found. Check that you have 'cmu_groupx_classes.csv' in the repo or enable live scraping.")
else:
    if creds is None:
        st.info("Connect Google Calendar above to filter out conflicts. Showing all candidate events for now.")
        display_df = format_for_display(candidates)
    else:
        non_conflicting = detect_conflicts(candidates, calendar_df)
        display_df = format_for_display(non_conflicting)

    # Simple filters
    sources = sorted(display_df["source"].dropna().unique().tolist())
    src_sel = st.multiselect("Source", sources, default=sources)
    display_df = display_df[display_df["source"].isin(src_sel)] if src_sel else display_df

    # Show table
    st.dataframe(display_df, use_container_width=True)

    # Download
    if not display_df.empty:
        csv_bytes = display_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download recommendations (CSV)", data=csv_bytes, file_name="fitness_recommendations.csv", mime="text/csv")

st.caption("Built with ❤️ using Streamlit, Google Calendar API, and CMU GroupX data.")

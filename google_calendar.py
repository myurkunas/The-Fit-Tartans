# GenAI - GPT 5.0 was used to develop this file

import streamlit as st
import pandas as pd
import datetime as dt
import os
import json

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# -------------------
# CONFIG
# -------------------
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = "credentials.json"   # download this from Google Cloud Console
TOKEN_FILE = "token.json"               # will be created after login

# -------------------
# AUTHENTICATION
# -------------------
def get_google_credentials():
    creds = None

    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid creds yet, go through OAuth flow
    if not creds or not creds.valid:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri="http://localhost:8501/"  # must match Google Cloud Console exactly
        )

        auth_url, _ = flow.authorization_url(prompt="consent")
        st.write(f"[🔑 Login with Google]({auth_url})")

        code = st.query_params.get("code")
        if code:
            flow.fetch_token(code=code)
            creds = flow.credentials

            # Save token to file (JSON is safer than pickle)
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

            # Refresh page so "Logged in" state shows immediately
            st.rerun()

    return creds


# -------------------
# FETCH EVENTS
# -------------------
def get_calendar_events(creds):
    service = build("calendar", "v3", credentials=creds)
    now = dt.datetime.utcnow()
    now_iso = now.isoformat() + "Z"
    two_weeks = (now + dt.timedelta(days=14)).isoformat() + "Z"

    # Get all calendars in the account
    calendars_result = service.calendarList().list().execute()
    calendars = calendars_result.get("items", [])

    all_events = []

    for calendar in calendars:
        cal_id = calendar["id"]
        cal_name = calendar.get("summary", "Unnamed Calendar")

        events_result = service.events().list(
            calendarId=cal_id,
            timeMin=now_iso,
            timeMax=two_weeks,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            all_events.append({
                "Calendar": cal_name,
                "Summary": event.get("summary", "No Title"),
                "Start": start,
                "End": end,
                "Location": event.get("location", ""),
                "Description": event.get("description", "")
            })

    if not all_events:
        st.write("No upcoming events found.")
        return pd.DataFrame()

    return pd.DataFrame(all_events)


# -------------------
# STREAMLIT APP
# -------------------
st.title("📅 Google Calendar to DataFrame")

creds = get_google_credentials()

if creds:
    st.success("✅ Logged in with Google!")
    df = get_calendar_events(creds)
    if not df.empty:
        st.dataframe(df)
        st.download_button("⬇️ Download as CSV", df.to_csv(index=False), "calendar.csv")
else:
    st.info("Please log in with Google to continue.")

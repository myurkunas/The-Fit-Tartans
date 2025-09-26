import streamlit as st
import pandas as pd
import datetime as dt

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os
import pickle

# -------------------
# CONFIG
# -------------------
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = "credentials.json"   # download this from Google Cloud Console
TOKEN_FILE = "token.pkl"                # will be created after login

# -------------------
# AUTHENTICATION
# -------------------
def get_google_credentials():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    else:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri="http://localhost:8501"
        )
        auth_url, _ = flow.authorization_url(prompt="consent")
        st.write(f"[Login with Google]({auth_url})")
        code = st.query_params().get("code")
        if code:
            flow.fetch_token(code=code[0])
            creds = flow.credentials
            with open(TOKEN_FILE, "wb") as token:
                pickle.dump(creds, token)
    return creds if "creds" in locals() else None

# -------------------
# FETCH EVENTS
# -------------------
def get_calendar_events(creds):
    service = build("calendar", "v3", credentials=creds)
    now = dt.datetime.utcnow().isoformat() + "Z"  # current time in UTC

    events_result = service.events().list(
        calendarId="primary", timeMin=now,
        maxResults=50, singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    if not events:
        st.write("No upcoming events found.")
        return pd.DataFrame()

    data = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        data.append({
            "Summary": event.get("summary", "No Title"),
            "Start": start,
            "End": end,
            "Location": event.get("location", ""),
            "Description": event.get("description", "")
        })

    return pd.DataFrame(data)

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
        st.download_button("Download as CSV", df.to_csv(index=False), "calendar.csv")
else:
    st.info("Please log in with Google to continue.")

Run: streamlit run google_calendar.py --server.address=localhost

---

**Quick run (for mac terminal) -- assuming you have credentials.json downloaded & in the parent folder**
cd ~/The-Fit-Tartans

source .venv/bin/activate

streamlit run streamlit_app.py


**Running after changes (for mac terminal):**
cd ~/The-Fit-Tartans

git pull origin main

source .venv/bin/activate

pip install -r requirements.txt

ls | grep credentials.json

streamlit run streamlit_app.py





import asyncio
from playwright.async_api import async_playwright
import json
import pandas as pd

async def run():
    url = "https://www.eventbrite.com/d/pa--pittsburgh/fitness-class/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)

        # Get all event links
        event_cards = await page.locator("a[href*='/e/']").all()
        event_links = []
        for card in event_cards:
            link = await card.get_attribute("href")
            title = await card.inner_text()
            if link and title.strip():
                event_links.append({"title": title.strip(), "link": link})

        print(f"Found {len(event_links)} events. Visiting each...")

        results = []
        for event in event_links[:10]:  # test first 10 events
            print(f"Visiting: {event['link']}")
            event_page = await browser.new_page()
            await event_page.goto(event["link"], timeout=60000)

            # Event title
            title = await event_page.locator("h1").first.inner_text()

            # --- Try to get date/time from visible span ---
            date_time = None
            try:
                date_time = await event_page.locator(
                    "#instance-selector .date-info [data-testid='display-date-container'] span.date-info__full-datetime"
                ).inner_text(timeout=5000)
                date_time = date_time.strip()
            except:
                # --- Fallback: Use JSON-LD startDate / endDate ---
                try:
                    json_ld_handle = event_page.locator("script[type='application/ld+json']").first
                    json_ld_text = await json_ld_handle.text_content()
                    data = json.loads(json_ld_text)
                    start = data.get("startDate")
                    end = data.get("endDate")
                    if start:
                        date_time = f"{start} → {end}" if end else start
                except:
                    date_time = None

            # Only keep events with a valid date_time
            if date_time:
                # Extract venue and address from JSON-LD
                try:
                    json_ld_handle = event_page.locator("script[type='application/ld+json']").first
                    json_ld_text = await json_ld_handle.text_content()
                    data = json.loads(json_ld_text)
                    location = data.get("location", {}).get("name")
                    address = data.get("location", {}).get("address", {})
                except:
                    location = None
                    address = None

                results.append({
                    "title": title.strip() if title else None,
                    "link": event["link"],
                    "date_time": date_time,
                    "venue": location,
                    "address": address
                })

            await event_page.close()

        await browser.close()
        return results


if __name__ == "__main__":
    # Run the async function properly in a Python file
    events = asyncio.run(run())

    # Convert to DataFrame
    df = pd.DataFrame(events)
    # Save DataFrame to CSV
    df.to_csv("eventbrite_events.csv", index=False, encoding="utf-8")
    print("✅ CSV file created: eventbrite_events.csv")

    print(df)

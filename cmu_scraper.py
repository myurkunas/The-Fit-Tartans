"""
CMU GroupX Class Scraper
========================
This script scrapes class schedule data from CMU's GroupX recreation portal.

External Resources & Citations:
-------------------------------
1. Selenium WebDriver Documentation - Used for browser automation and hover simulation
   https://www.selenium.dev/documentation/webdriver/
   
2. BeautifulSoup Documentation - Used for HTML parsing
   https://www.crummy.com/software/BeautifulSoup/bs4/doc/
   
3. Pandas Documentation - Used for data structuring and CSV export
   https://pandas.pydata.org/docs/
   
4. ChromeDriver Manager - Used for automatic ChromeDriver setup
   https://github.com/SergeyPirogov/webdriver_manager
   
5. Stack Overflow - Referenced for handling stale element exceptions in Selenium
   https://stackoverflow.com/questions/16166261/selenium-webdriver-how-to-resolve-stale-element-reference-exception
   
6. Selenium ActionChains for hover simulation - Referenced official documentation
   https://www.selenium.dev/documentation/webdriver/actions_api/mouse/

7. Claude AI (Anthropic) - Claude Sonnet 4.5 - Used for code development assistance, 
   debugging support, and implementation guidance for web scraping techniques
   https://claude.ai
"""


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime
import time
import requests

class CMUGroupXSeleniumScraper:
    def __init__(self, headless=False):
        self.setup_driver(headless)
        self.schedule_url = "https://cmu.dserec.com/online/cr/programs/1/program-classes-weekly-view"
        self.descriptions_url = "https://athletics.cmu.edu/recreation/groupxdescriptions"
        
        # Load class descriptions
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.class_descriptions = self.load_class_descriptions()
        
    def setup_driver(self, headless):
        """Setup Chrome WebDriver with automatic driver management"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            # Automatically download and setup ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Chrome WebDriver setup successful!")
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            raise
            
    def load_class_descriptions(self):
        """Load class descriptions from the CMU athletics website"""
        descriptions = {}
        try:
            print("Loading class descriptions...")
            response = self.session.get(self.descriptions_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content = soup.get_text()
            
            # Parse the descriptions using regex patterns
            pattern = r'^([A-Z0-9&\s]+)\n([^A-Z0-9].+?)(?=\n[A-Z0-9&\s]+\n|\nView a video|\n\[|\Z)'
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            
            for match in matches:
                class_name = match[0].strip()
                description = match[1].strip()
                clean_name = self.normalize_class_name(class_name)
                descriptions[clean_name] = description
                
            print(f"Loaded {len(descriptions)} class descriptions")
                
        except Exception as e:
            print(f"Warning: Could not load class descriptions: {e}")
            
        return descriptions
    
    def normalize_class_name(self, name):
        """Normalize class names for matching"""
        normalized = re.sub(r'\s+', ' ', name.lower().strip())
        variations = {
            'indoor cycling': 'cycling',
            'hiit': 'high intensity interval training',
            'kettlebell cardio hiit': 'kettlebells',
        }
        
        for variation, standard in variations.items():
            if variation in normalized:
                normalized = standard
                break
                
        return normalized
    
    def get_class_description(self, class_name):
        """Get description for a class name"""
        normalized = self.normalize_class_name(class_name)
        
        if normalized in self.class_descriptions:
            return self.class_descriptions[normalized]
        
        for desc_name, description in self.class_descriptions.items():
            if normalized in desc_name or desc_name in normalized:
                return description
                
        return "Description not available"
    
    def wait_for_schedule_to_load(self, timeout=30):
        """Wait for the schedule grid to load"""
        try:
            print("Waiting for schedule to load...")
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "dse-event")))
            print("Schedule loaded successfully!")
            return True
        except Exception as e:
            print(f"Schedule did not load within {timeout} seconds: {e}")
            # Take a screenshot for debugging
            self.driver.save_screenshot("debug_screenshot.png")
            print("Debug screenshot saved as 'debug_screenshot.png'")
            return False
    
    def parse_time_range(self, time_text):
        """Parse time range text into start and end times"""
        try:
            time_text = re.sub(r'[–—~-]', '-', time_text)
            time_pattern = r'(\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(\d{1,2}:\d{2}\s*[ap]m)'
            match = re.search(time_pattern, time_text.lower())
            
            if match:
                return match.group(1).strip(), match.group(2).strip()
            else:
                return time_text, ""
                
        except Exception as e:
            print(f"Error parsing time range '{time_text}': {e}")
            return time_text, ""
    
    def determine_campus_area(self, studio_text):
        """Determine campus area based on studio information"""
        studio_lower = studio_text.lower()
        
        if any(tepper_indicator in studio_lower for tepper_indicator in ['tepper', 'tep']):
            return 'Tepper'
        elif any(cuc_indicator in studio_lower for cuc_indicator in ['cuc', 'cohon', 'kenner']):
            return 'CUC'
        else:
            return 'CUC'  # Default assumption
    
    def scrape_schedule_data(self):
        """Main method to scrape schedule data with hover simulation"""
        classes_data = []
        
        try:
            print("Navigating to CMU GroupX schedule page...")
            self.driver.get(self.schedule_url)
            
            # Check if login is required
            current_url = self.driver.current_url
            if 'login' in current_url.lower() or 'auth' in current_url.lower():
                print("Login required! Please log in manually in the browser window.")
                print("After logging in, navigate back to the schedule page.")
                input("Press Enter after you've logged in and can see the schedule...")
            
            # Wait for page to load
            time.sleep(5)
            
            # Try to wait for schedule to load automatically
            if not self.wait_for_schedule_to_load(timeout=15):
                print("Schedule didn't load automatically. Please ensure you're on the schedule page.")
                input("Press Enter when you can see the schedule grid...")
            
            # Find class elements using Selenium
            try:
                # Get all class event elements using Selenium
                event_elements = self.driver.find_elements(By.CLASS_NAME, "dse-event")
                print(f"Found {len(event_elements)} class events with Selenium")
                
                for i in range(min(len(event_elements), 36)):  # Process up to 36 classes
                    try:
                        print(f"\nProcessing class {i+1}...")
                        
                        # Re-find elements to avoid stale references
                        current_elements = self.driver.find_elements(By.CLASS_NAME, "dse-event")
                        if i >= len(current_elements):
                            print(f"Element {i} no longer exists, skipping...")
                            continue
                            
                        element = current_elements[i]
                        
                        # Scroll element into view first
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(0.5)
                        
                        # Simulate hover to trigger any tooltips/popups
                        actions = ActionChains(self.driver)
                        actions.move_to_element(element).perform()
                        time.sleep(2)  # Wait for hover effects
                        
                        # Now get the updated page source
                        page_source = self.driver.page_source
                        soup = BeautifulSoup(page_source, 'html.parser')
                        
                        # Find this specific element in the soup
                        aria_label = element.get_attribute('aria-label')
                        matching_elements = soup.find_all('div', {'aria-label': aria_label})
                        
                        if matching_elements:
                            class_info = self.parse_dse_event_with_hover(matching_elements[0], element)
                            if class_info:
                                classes_data.append(class_info)
                        
                        # Move mouse away to clear hover state
                        actions.move_by_offset(100, 100).perform()
                        time.sleep(0.5)
                        
                    except Exception as e:
                        print(f"Error processing element {i}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error with Selenium approach: {e}")
                # Fallback to original method
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                dse_events = soup.find_all('div', class_='dse-event')
                print(f"Fallback: Found {len(dse_events)} class events with BeautifulSoup")
                
                for event in dse_events:
                    class_info = self.parse_dse_event(event)
                    if class_info:
                        classes_data.append(class_info)
            
        except Exception as e:
            print(f"Error during scraping: {e}")
        
        return classes_data

    def parse_dse_event_with_hover(self, soup_element, selenium_element):
        """Parse DSE event with hover data from Selenium element"""
        try:
            # Get basic info from soup element
            title_element = soup_element.find('span', class_='dse-event-title')
            class_name = title_element.get_text().strip() if title_element else ""
            
            time_element = soup_element.find('span', class_='dse-event-time')
            time_range_text = time_element.get_text().strip() if time_element else ""
            
            # Get additional attributes from Selenium element
            aria_label = selenium_element.get_attribute('aria-label') or ""
            
            # Look for studio information that appears after hover
            studio = ""
            
            try:
                # Wait a bit for popup to appear
                time.sleep(1)
                
                # Look for elements with specific text content
                studio_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Keeler') or contains(text(), 'Kenner') or contains(text(), 'Noll') or contains(text(), 'Studio')]")
                
                for element in studio_elements:
                    if element.is_displayed():
                        element_text = element.text.strip()
                        print(f"Found visible studio element: {element_text}")
                        if not studio and any(word in element_text.lower() for word in ['keeler', 'kenner', 'noll', 'studio']):
                            studio = element_text
                            break
                            
            except Exception as e:
                print(f"Error searching for studio elements: {e}")
            
            # Parse other data same as before
            weekday = ""
            if aria_label:
                date_pattern = r'(\d{1,2}/\d{1,2}/\d{4})'
                date_matches = re.findall(date_pattern, aria_label)
                if date_matches:
                    try:
                        date_obj = datetime.strptime(date_matches[0], '%m/%d/%Y')
                        weekday = date_obj.strftime('%a')
                    except:
                        pass
            
            style = selenium_element.get_attribute('style') or ""
            left_percentage = 0
            left_match = re.search(r'left:\s*(\d+(?:\.\d+)?)%', style)
            if left_match:
                left_percentage = float(left_match.group(1))
            
            day_mapping = {
                0: 'Sun', 14.3: 'Mon', 28.6: 'Tue', 42.9: 'Wed',
                57.1: 'Thu', 71.4: 'Fri', 85.7: 'Sat'
            }
            
            if not weekday and left_percentage is not None:
                closest_percentage = min(day_mapping.keys(), key=lambda x: abs(x - left_percentage))
                weekday = day_mapping[closest_percentage]
            
            start_time, end_time = self.parse_time_range(time_range_text)
            
            print(f"Class: {class_name}, Studio found: '{studio}'")
            
            return {
                'term_name': 'Fall Mini 1 2025',
                'term_start_date': '2025-08-25',
                'term_end_date': '2025-10-11',
                'registration_url': self.schedule_url,
                'campus_area': self.determine_campus_area(studio),
                'weekday': weekday,
                'class_name': class_name,
                'time_range_text': time_range_text,
                'start_time_local': start_time,
                'end_time_local': end_time,
                'studio': studio,
                'class_description': self.get_class_description(class_name)
            }
            
        except Exception as e:
            print(f"Error parsing hover event: {e}")
            return None

    def parse_dse_event(self, event_element):
        """Parse a DSE event element to extract class information (fallback method)"""
        try:
            # Extract class name
            title_element = event_element.find('span', class_='dse-event-title')
            class_name = title_element.get_text().strip() if title_element else ""
            
            # Extract time
            time_element = event_element.find('span', class_='dse-event-time')
            time_range_text = time_element.get_text().strip() if time_element else ""
            
            # Parse aria-label for date info
            aria_label = event_element.get('aria-label', '')
            weekday = ""
            
            if aria_label:
                date_pattern = r'(\d{1,2}/\d{1,2}/\d{4})'
                date_matches = re.findall(date_pattern, aria_label)
                if date_matches:
                    try:
                        date_obj = datetime.strptime(date_matches[0], '%m/%d/%Y')
                        weekday = date_obj.strftime('%a')
                    except:
                        pass
            
            # Extract positioning to determine day column
            style = event_element.get('style', '')
            left_percentage = 0
            left_match = re.search(r'left:\s*(\d+(?:\.\d+)?)%', style)
            if left_match:
                left_percentage = float(left_match.group(1))
            
            day_mapping = {
                0: 'Sun', 14.3: 'Mon', 28.6: 'Tue', 42.9: 'Wed',
                57.1: 'Thu', 71.4: 'Fri', 85.7: 'Sat'
            }
            
            if not weekday and left_percentage is not None:
                closest_percentage = min(day_mapping.keys(), key=lambda x: abs(x - left_percentage))
                weekday = day_mapping[closest_percentage]
            
            start_time, end_time = self.parse_time_range(time_range_text)
            
            return {
                'term_name': 'Fall Mini 1 2025',
                'term_start_date': '2025-08-25',
                'term_end_date': '2025-10-11',
                'registration_url': self.schedule_url,
                'campus_area': 'CUC',
                'weekday': weekday,
                'class_name': class_name,
                'time_range_text': time_range_text,
                'start_time_local': start_time,
                'end_time_local': end_time,
                'studio': '',  # No studio info in fallback method
                'class_description': self.get_class_description(class_name)
            }
            
        except Exception as e:
            print(f"Error parsing event: {e}")
            return None
    
    def close_driver(self):
        """Close the browser driver"""
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    def save_to_csv(self, df, filename="cmu_groupx_classes.csv"):
        """Save DataFrame to CSV"""
        import os
        full_path = os.path.abspath(filename)
        df.to_csv(filename, index=False)
        print(f"Data saved to {full_path}")

def main():
    scraper = None
    try:
        print("Starting CMU GroupX Scraper...")
        print("This will open a Chrome browser window.")
        
        # Initialize scraper (set headless=True if you don't want to see the browser)
        scraper = CMUGroupXSeleniumScraper(headless=False)
        
        # Scrape the data
        classes_data = scraper.scrape_schedule_data()
        
        # Create DataFrame
        if classes_data:
            df = pd.DataFrame(classes_data)
            print(f"\nSuccessfully scraped {len(df)} classes!")
            print("\nFirst few classes:")
            print(df[['weekday', 'class_name', 'time_range_text', 'studio']].head())
            
            # Save to CSV
            scraper.save_to_csv(df)
            
            # Show summary
            print(f"\nSummary:")
            print(f"Total classes: {len(df)}")
            print(f"Unique class types: {df['class_name'].nunique()}")
            print(f"Classes by weekday:")
            print(df['weekday'].value_counts().sort_index())
            
        else:
            print("No class data could be scraped.")
            print("This might be because:")
            print("1. You need to log in manually")
            print("2. The page structure has changed")
            print("3. Network issues")
            
    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Always close the browser
        if scraper:
            print("Closing browser...")
            scraper.close_driver()

if __name__ == "__main__":
    main()
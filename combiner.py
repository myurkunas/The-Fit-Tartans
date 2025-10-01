import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

# ===========================
# HELPER FUNCTIONS
# ===========================

def safe_timezone_convert(dt_series: pd.Series, target_tz: str = 'UTC') -> pd.Series:
    """Safely convert datetime series to target timezone"""
    return dt_series.apply(
        lambda x: x.tz_convert(target_tz) if x is not pd.NaT and x.tz is not None 
        else (x.tz_localize(target_tz) if x is not pd.NaT and x.tz is None else x)
    )

def standardize_columns(df: pd.DataFrame, column_mapping: Dict[str, str]) -> pd.DataFrame:
    """Standardize column names and clean basic fields"""
    df = df.rename(columns=column_mapping)
    
    # Clean string columns
    for col in df.select_dtypes(include=['object']).columns:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str).str.strip()
    
    return df

def parse_datetime_efficiently(date_str: str) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """Optimized datetime parsing with fewer try/except blocks"""
    if pd.isna(date_str) or not date_str:
        return None, None
    
    date_str = str(date_str).strip()
    
    # Try direct pandas parsing first (fastest)
    try:
        single_dt = pd.to_datetime(date_str, errors='coerce', utc=True)
        if pd.notna(single_dt):
            return single_dt, None
    except:
        pass
    
    # Handle specific formats
    if '→' in date_str:
        # ISO format: "2024-01-15T18:00:00Z → 2024-01-15T20:00:00Z"
        parts = date_str.split('→', 1)
        start_dt = pd.to_datetime(parts[0].strip(), errors='coerce', utc=True)
        end_dt = pd.to_datetime(parts[1].strip(), errors='coerce', utc=True)
        return start_dt, end_dt
    
    elif '·' in date_str and '-' in date_str:
        # Natural language: "Saturday, October 4 · 10:15 - 11:15am EDT"
        return parse_natural_language_datetime(date_str)
    
    return None, None

def parse_natural_language_datetime(date_str: str) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """Parse natural language datetime format"""
    try:
        date_part, time_part = date_str.split('·', 1)
        date_part = date_part.strip()
        time_part = time_part.strip()
        
        # Remove timezone suffixes
        timezone_suffixes = ['EDT', 'EST', 'CDT', 'CST', 'MDT', 'MST', 'PDT', 'PST', 'UTC']
        for tz in timezone_suffixes:
            time_part = time_part.replace(tz, '').strip()
        
        if '-' not in time_part:
            return None, None
            
        start_time_str, end_time_str = time_part.split('-', 1)
        start_time_str = start_time_str.strip()
        end_time_str = end_time_str.strip()
        
        # Handle AM/PM inheritance
        if ('am' in end_time_str or 'pm' in end_time_str) and not ('am' in start_time_str or 'pm' in start_time_str):
            am_pm = 'am' if 'am' in end_time_str else 'pm'
            start_time_str += am_pm
        
        # Clean up date part
        date_clean = re.sub(r'^[A-Za-z]+,\s*', '', date_part)
        if str(datetime.now().year) not in date_clean:
            date_clean += f', {datetime.now().year}'
        
        # Parse both datetimes
        start_datetime_str = f"{date_clean} {start_time_str}"
        end_datetime_str = f"{date_clean} {end_time_str}"
        
        start_dt = pd.to_datetime(start_datetime_str, errors='coerce')
        end_dt = pd.to_datetime(end_datetime_str, errors='coerce')
        
        # Convert to UTC
        if pd.notna(start_dt):
            start_dt = start_dt.tz_localize('UTC') if start_dt.tz is None else start_dt.tz_convert('UTC')
        if pd.notna(end_dt):
            end_dt = end_dt.tz_localize('UTC') if end_dt.tz is None else end_dt.tz_convert('UTC')
        
        return start_dt, end_dt
        
    except:
        return None, None

def create_time_range_display(start: pd.Timestamp, end: Optional[pd.Timestamp]) -> str:
    """Create user-friendly time range string in Eastern Time"""
    if pd.isna(start):
        return None
    
    # Convert to Eastern Time for display
    start_et = start.tz_convert('US/Eastern')
    
    if pd.isna(end):
        return f"{start_et.strftime('%Y-%m-%d %H:%M')} ET"
    
    end_et = end.tz_convert('US/Eastern')
    
    # Optimized format based on date equality
    if start_et.date() == end_et.date():
        return f"{start_et.strftime('%Y-%m-%d %H:%M')} - {end_et.strftime('%H:%M')} ET"
    else:
        return f"{start_et.strftime('%Y-%m-%d %H:%M')} - {end_et.strftime('%Y-%m-%d %H:%M')} ET"

# ===========================
# OPTIMIZED CLEANING FUNCTIONS
# ===========================

def clean_google_calendar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Optimized Google Calendar cleaning"""
    if df.empty:
        return pd.DataFrame(columns=['start', 'end', 'calendar_event', 'description', 'location', 'url'])
    
    # Standardize columns
    column_mapping = {
        'Summary': 'calendar_event',
        'Start': 'start',
        'End': 'end',
        'Location': 'location',
        'Description': 'description'
    }
    
    cleaned_df = standardize_columns(df.copy(), column_mapping)
    
    # Filter out date-only events using vectorized operations
    has_time = cleaned_df['start'].str.contains(r'T.*:', na=False) & \
               cleaned_df['start'].str.contains(r'[-+]\d{2}:\d{2}|Z', na=False)
    cleaned_df = cleaned_df[has_time]
    
    # Parse datetime columns
    for col in ['start', 'end']:
        if col in cleaned_df.columns:
            cleaned_df[col] = pd.to_datetime(cleaned_df[col], errors='coerce')
            cleaned_df[col] = safe_timezone_convert(cleaned_df[col], 'UTC')
    
    # Add required columns
    cleaned_df['calendar_event'] = cleaned_df['calendar_event'].replace('', 'Untitled Event')
    cleaned_df['url'] = ''
    
    # Remove invalid rows
    cleaned_df = cleaned_df.dropna(subset=['start'])
    
    return cleaned_df[['start', 'end', 'calendar_event', 'description', 'location', 'url']]

def clean_webscraping_df(df: pd.DataFrame) -> pd.DataFrame:
    """Optimized web scraping cleaning"""
    if df.empty:
        return pd.DataFrame(columns=['start', 'end', 'scraped_event', 'description', 'location', 'url'])
    
    cleaned_df = df.copy()
    
    # Vectorized datetime parsing
    datetime_results = cleaned_df['date_time'].apply(parse_datetime_efficiently)
    cleaned_df['start'] = [x[0] for x in datetime_results]
    cleaned_df['end'] = [x[1] for x in datetime_results]
    
    # Vectorized location formatting
    def format_location_vectorized(row):
        venue = str(row.get('venue', '')) if pd.notna(row.get('venue')) else ''
        address = str(row.get('address', '')) if pd.notna(row.get('address')) else ''
        parts = [part for part in [venue, address] if part.strip()]
        return '- '.join(parts) if parts else ''
    
    cleaned_df['location'] = cleaned_df.apply(format_location_vectorized, axis=1)
    
    # Standardize remaining columns
    cleaned_df['scraped_event'] = cleaned_df['title'].fillna('Untitled Event')
    cleaned_df['description'] = cleaned_df['link'].fillna('')
    cleaned_df['url'] = cleaned_df['link'].fillna('')
    
    # Remove invalid rows
    cleaned_df = cleaned_df.dropna(subset=['start'])
    
    return cleaned_df[['start', 'end', 'scraped_event', 'description', 'location', 'url']]

def clean_cmu_scraper_df(df: pd.DataFrame) -> pd.DataFrame:
    """Optimized CMU scraper cleaning with efficient occurrence generation"""
    if df.empty:
        return pd.DataFrame(columns=['start', 'end', 'scraped_event', 'description', 'location', 'url'])
    
    cleaned_df = df.copy()
    
    # Pre-compute constants
    weekday_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
    current_time = pd.Timestamp.now(tz='UTC')
    
    all_occurrences = []
    
    # Vectorized approach where possible
    for _, row in cleaned_df.iterrows():
        occurrences = generate_class_occurrences_optimized(row, weekday_map, current_time)
        all_occurrences.extend(occurrences)
    
    if not all_occurrences:
        return pd.DataFrame(columns=['start', 'end', 'scraped_event', 'description', 'location', 'url'])
    
    result_df = pd.DataFrame(all_occurrences)
    
    # Vectorized location formatting
    result_df['location'] = result_df.apply(
        lambda row: format_cmu_location_optimized(row.get('studio'), row.get('campus_area')), 
        axis=1
    )
    
    # Set other required columns
    result_df['scraped_event'] = result_df['class_name'].fillna('Untitled Class')
    result_df['description'] = result_df['class_description'].fillna(result_df['registration_url'].fillna(''))
    result_df['url'] = result_df['registration_url'].fillna('')
    
    # Filter future events only
    result_df = result_df[result_df['start'] >= current_time]
    
    return result_df[['start', 'end', 'scraped_event', 'description', 'location', 'url']]

def generate_class_occurrences_optimized(row: pd.Series, weekday_map: Dict[str, int], current_time: pd.Timestamp) -> List[Dict]:
    """Optimized occurrence generation"""
    try:
        # Parse term dates once
        term_start = pd.to_datetime(row['term_start_date'], errors='coerce')
        term_end = pd.to_datetime(row['term_end_date'], errors='coerce')
        
        if pd.isna(term_start) or pd.isna(term_end):
            return []
        
        weekday = row['weekday']
        if weekday not in weekday_map:
            return []
        
        # Calculate first occurrence
        effective_start = term_start.date()
        target_weekday = weekday_map[weekday]
        days_ahead = target_weekday - effective_start.weekday()
        if days_ahead < 0:
            days_ahead += 7
        
        first_class_date = effective_start + timedelta(days=days_ahead)
        
        # Pre-parse time strings
        start_time_str = str(row['start_time_local']).strip()
        end_time_str = str(row['end_time_local']).strip()
        
        # Generate all occurrences using date range
        occurrences = []
        current_date = first_class_date
        
        while current_date <= term_end.date():
            # Create datetime objects
            start_datetime = pd.to_datetime(f"{current_date.strftime('%Y-%m-%d')} {start_time_str}", errors='coerce')
            end_datetime = pd.to_datetime(f"{current_date.strftime('%Y-%m-%d')} {end_time_str}", errors='coerce')
            
            if pd.notna(start_datetime) and pd.notna(end_datetime):
                # Convert to UTC once
                start_datetime = start_datetime.tz_localize('US/Eastern').tz_convert('UTC')
                end_datetime = end_datetime.tz_localize('US/Eastern').tz_convert('UTC')
                
                # Create occurrence dictionary
                occurrence = row.to_dict()
                occurrence.update({
                    'start': start_datetime,
                    'end': end_datetime,
                    'occurrence_date': current_date.strftime('%Y-%m-%d')
                })
                
                occurrences.append(occurrence)
            
            # Move to next week
            current_date += timedelta(days=7)
        
        return occurrences
        
    except Exception:
        return []

def format_cmu_location_optimized(studio: Any, campus_area: Any) -> str:
    """Optimized CMU location formatting"""
    parts = []
    
    if pd.notna(studio) and str(studio).strip():
        parts.append(str(studio).strip())
    
    if pd.notna(campus_area) and str(campus_area).strip():
        parts.append(f"({str(campus_area).strip()})")
    
    return ' '.join(parts) if parts else 'CMU Campus'

# ===========================
# OPTIMIZED COMBINATION FUNCTION
# ===========================

def standardize_and_combine_optimized(google_df: Optional[pd.DataFrame] = None, 
                                     webscrape_df: Optional[pd.DataFrame] = None, 
                                     cmu_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Optimized version of standardize_and_combine with better performance"""
    
    cleaned_dfs = []
    
    # Process each data source
    data_sources = [
        (google_df, clean_google_calendar_df, 'calendar_event'),
        (webscrape_df, clean_webscraping_df, 'scraped_event'),
        (cmu_df, clean_cmu_scraper_df, 'scraped_event')
    ]
    
    for df, clean_func, event_type in data_sources:
        if df is not None and not df.empty:
            cleaned = clean_func(df)
            if not cleaned.empty:
                # Add the appropriate event type column
                if event_type == 'calendar_event':
                    cleaned['scraped_event'] = None
                else:
                    cleaned['calendar_event'] = None
                cleaned_dfs.append(cleaned)
    
    if not cleaned_dfs:
        return pd.DataFrame(columns=['time_range', 'scraped_event', 'calendar_event', 'description', 'location', 'url'])
    
    # Combine all dataframes
    combined_df = pd.concat(cleaned_dfs, ignore_index=True)
    
    # Create time ranges
    combined_df['time_range'] = combined_df.apply(
        lambda row: create_time_range_display(row['start'], row['end']), axis=1
    )
    
    # Remove invalid rows
    combined_df = combined_df.dropna(subset=['time_range'])
    
    # Sort by start time
    combined_df = combined_df.sort_values('start').reset_index(drop=True)
    
    # Optimized overlap detection
    final_df = remove_overlapping_events_optimized(combined_df)
    
    # Return final columns
    return final_df[['time_range', 'scraped_event', 'calendar_event', 'description', 'location', 'url']]

def remove_overlapping_events_optimized(df: pd.DataFrame) -> pd.DataFrame:
    """Optimized overlap detection using vectorized operations where possible"""
    
    # Separate calendar and scraped events
    calendar_events = df[df['calendar_event'].notna()].copy()
    scraped_events = df[df['scraped_event'].notna()].copy()
    
    if calendar_events.empty:
        return df
    
    if scraped_events.empty:
        return calendar_events
    
    # Pre-fill missing end times for vectorized operations
    calendar_events['end_filled'] = calendar_events['end'].fillna(
        calendar_events['start'] + timedelta(hours=1)
    )
    scraped_events['end_filled'] = scraped_events['end'].fillna(
        scraped_events['start'] + timedelta(hours=1)
    )
    
    # Find non-overlapping scraped events
    non_overlapping_scraped = []
    
    for _, scraped in scraped_events.iterrows():
        # Check overlap with all calendar events at once
        overlaps = (
            (calendar_events['start'] < scraped['end_filled']) & 
            (scraped['start'] < calendar_events['end_filled'])
        )
        
        if not overlaps.any():
            non_overlapping_scraped.append(scraped)
    
    # Combine results
    events_to_keep = [calendar_events] + ([pd.DataFrame(non_overlapping_scraped)] if non_overlapping_scraped else [])
    
    if events_to_keep:
        result_df = pd.concat(events_to_keep, ignore_index=True)
        result_df = result_df.sort_values('start').reset_index(drop=True)
        # Remove the temporary column
        if 'end_filled' in result_df.columns:
            result_df = result_df.drop('end_filled', axis=1)
        return result_df
    
    return pd.DataFrame(columns=df.columns)

# ===========================
# MAIN FUNCTION
# ===========================

def standardize_and_combine(google_df=None, webscrape_df=None, cmu_df=None):
    """
    Main function - calls the optimized version for better performance
    """
    return standardize_and_combine_optimized(google_df, webscrape_df, cmu_df)
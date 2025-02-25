# Function to save current scraping progress
def save_progress(status_file, page_count, current_url, next_url, total_bills, total_actions, 
                  current_page_bills=None, processed_bill_ids=None):
    """Save current progress to status file"""
    status = {
        "current_page": page_count,
        "current_url": current_url,
        "next_url": next_url,
        "total_bills": total_bills,
        "total_actions": total_actions,
        "last_update": str(datetime.datetime.now()),
        "processed_bill_ids": processed_bill_ids or [],
        "current_page_bills": current_page_bills or []
    }
    
    with open(status_file, 'w') as f:
        json.dump(status, f, indent=2)
    
    print(f"Progress saved: Page {page_count}, {total_bills} bills, {total_actions} actions")# Function to safely get a page with retries and delay
def safe_get_page(url, max_retries=5, retry_delay=3, description="page"):
    """Get a page safely with retries and random delays"""
    headers = get_random_headers()
    
    for attempt in range(max_retries):
        try:
            # Add a small random delay to simulate human browsing
            time.sleep(random.uniform(0.5, 2.0))
            
            print(f"Fetching {description} (attempt {attempt+1}/{max_retries}): {url}")
            response = session.get(url, headers=headers, timeout=30)
            
            # Handle 403 Forbidden or other client errors
            if response.status_code == 403:
                print(f"Access Forbidden (403). Waiting and trying with different headers...")
                # Longer wait after a 403
                time.sleep(retry_delay * (attempt + 1))
                # Get new headers for next attempt
                headers = get_random_headers()
                continue
                
            # For other client errors, try again
            if response.status_code >= 400 and response.status_code < 500:
                print(f"Client error: {response.status_code}. Retrying...")
                time.sleep(retry_delay)
                continue
                
            # If we got a successful response, return it
            if response.status_code == 200:
                return response
                
            # For server errors, let the retry adapter handle it
            response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            if attempt < max_retries - 1:
                sleep_time = retry_delay * (2 ** attempt)  # exponential backoff
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                print(f"Max retries reached for {url}")
                raise
    
    return None  # If all retries fail
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os
import datetime
import random
from urllib.parse import urljoin
from tqdm import tqdm  # For progress bars
import http.cookiejar  # For cookie handling
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Base URL for the website (congress.gov)
BASE_URL = "https://www.congress.gov"

# Set up a session with retries and cookies
session = requests.Session()
cookie_jar = http.cookiejar.CookieJar()
session.cookies = cookie_jar

# Configure retry strategy
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Define headers to mimic a browser
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/94.0.4606.76 Mobile/15E148 Safari/604.1'
]

# Add explicit User-Agent rotator
class UserAgentRotator:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/118.0.2088.76',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/118.0.5993.69 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/118.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/104.0.0.0',
        ]
        self.desktop_browsers = [
            'Chrome',
            'Firefox',
            'Safari',
            'Edge',
            'Opera'
        ]
        self.operating_systems = [
            'Windows NT 10.0; Win64; x64',
            'Macintosh; Intel Mac OS X 10_15_7',
            'X11; Linux x86_64',
            'Windows NT 10.0; WOW64'
        ]
    
    def get_random_user_agent(self):
        """Return a random user agent from the list"""
        return random.choice(self.user_agents)
    
    def generate_realistic_user_agent(self):
        """Generate a realistic user agent string"""
        browser = random.choice(self.desktop_browsers)
        os_string = random.choice(self.operating_systems)
        
        if browser == 'Chrome':
            chrome_version = f"{random.randint(70, 120)}.0.{random.randint(0, 9999)}.{random.randint(0, 999)}"
            return f"Mozilla/5.0 ({os_string}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
        elif browser == 'Firefox':
            firefox_version = f"{random.randint(60, 120)}.0"
            return f"Mozilla/5.0 ({os_string}; rv:{firefox_version}) Gecko/20100101 Firefox/{firefox_version}"
        elif browser == 'Safari':
            webkit_version = f"605.1.{random.randint(1, 15)}"
            safari_version = f"{random.randint(10, 16)}.{random.randint(0, 7)}"
            return f"Mozilla/5.0 ({os_string}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Version/{safari_version} Safari/{webkit_version}"
        elif browser == 'Edge':
            edge_version = f"{random.randint(80, 120)}.0.{random.randint(0, 9999)}.{random.randint(0, 999)}"
            return f"Mozilla/5.0 ({os_string}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{edge_version} Safari/537.36 Edg/{edge_version}"
        else:  # Opera
            opera_version = f"{random.randint(60, 100)}.0.{random.randint(0, 9999)}.{random.randint(0, 999)}"
            return f"Mozilla/5.0 ({os_string}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{opera_version} Safari/537.36 OPR/{opera_version}"

# Initialize our user agent rotator
ua_rotator = UserAgentRotator()

def get_random_headers():
    """Generate random headers to look more like a real browser"""
    # user_agent = random.choice(user_agents)
    user_agent = ua_rotator.generate_realistic_user_agent()
    
    # Randomize accept language slightly
    languages = ["en-US,en;q=0.9", "en-US,en;q=0.8", "en;q=0.9,en-US;q=0.8", "en-GB,en;q=0.9"]
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': random.choice(languages),
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'DNT': '1',  # Do Not Track
        'Referer': 'https://www.congress.gov/'
    }
    return headers

# Function to scrape bill information from a search results page
def scrape_search_page(url):
    print(f"Scraping search page: {url}")
    start_time = time.time()
    
    response = safe_get_page(url, description="search page")
    if not response:
        print(f"Failed to retrieve search page after multiple attempts")
        return [], None
    
    if response.status_code != 200:
        print(f"Failed to retrieve page: {response.status_code}")
        return [], None
    
    # Debug the response
    content_length = len(response.content)
    print(f"Received response: {response.status_code}, Content length: {content_length} bytes")
    
    # If the content is very small, it might be a redirect or anti-bot page
    if content_length < 1000:
        print("Warning: Received very small response, might be blocked or redirected")
        print("First 500 chars of response:")
        print(response.text[:500])
        return [], None
    
    soup = BeautifulSoup(response.content, 'html.parser')
    bills = []
    
    # Find all bill items (list items with class "expanded")
    bill_items = soup.select('li.expanded')
    print(f"Found {len(bill_items)} bills on this page")
    
    # If no bills found, check if we're being blocked
    if len(bill_items) == 0:
        print("No bills found on the page. Checking for possible blocks...")
        # Check for common block indicators
        if "captcha" in response.text.lower() or "access denied" in response.text.lower():
            print("Possible CAPTCHA or access restriction detected.")
        
        # Try to save the HTML for debugging
        debug_file = "debug_response.html"
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"Saved response to {debug_file} for debugging")
        return [], None
    
    for item in bill_items:
        bill_data = {}
        
        # Extract bill type
        bill_type_elem = item.select_one('span.visualIndicator')
        if bill_type_elem:
            bill_data['bill_type'] = bill_type_elem.text.strip()
        
        # Extract bill number, congress, and URL
        bill_heading = item.select_one('span.result-heading a')
        if bill_heading:
            bill_data['bill_number'] = bill_heading.text.strip()
            bill_data['bill_url'] = urljoin(BASE_URL, bill_heading.get('href', ''))
            # Get all actions URL by modifying the bill URL
            all_actions_url = bill_data['bill_url'] + "/all-actions"
            bill_data['all_actions_url'] = all_actions_url
        
        # Extract congress info
        congress_text = item.select_one('span.result-heading')
        if congress_text and congress_text.contents:
            # Find text after the <a> tag
            for content in congress_text.contents:
                if isinstance(content, str) and "Congress" in content:
                    bill_data['congress'] = content.strip()
        
        # Extract bill title
        bill_title = item.select_one('span.result-title')
        if bill_title:
            bill_data['title'] = bill_title.text.strip()
        
        # Extract sponsor information
        sponsor_info = item.select_one('span.result-item:has(strong:contains("Sponsor:"))')
        if sponsor_info:
            bill_data['sponsor_info'] = sponsor_info.get_text(' ', strip=True)
            
            # Extract sponsor name and party separately
            sponsor_link = sponsor_info.select_one('a')
            if sponsor_link:
                bill_data['sponsor_name'] = sponsor_link.text.strip()
                bill_data['sponsor_url'] = urljoin(BASE_URL, sponsor_link.get('href', ''))
            
            # Extract cosponsors count
            cosponsor_link = sponsor_info.select_one('a[href*="/cosponsors"]')
            if cosponsor_link:
                cosponsor_text = cosponsor_link.text.strip()
                bill_data['cosponsors_count'] = cosponsor_text
                bill_data['cosponsors_url'] = urljoin(BASE_URL, cosponsor_link.get('href', ''))
        
        # Extract committees
        committees_info = item.select_one('span.result-item:has(strong:contains("Committees:"))')
        if committees_info:
            bill_data['committees'] = committees_info.get_text(' ', strip=True).replace('Committees:', '').strip()
        
        # Extract latest action
        latest_action = item.select_one('span.result-item:has(strong:contains("Latest Action:"))')
        if latest_action:
            bill_data['latest_action'] = latest_action.get_text(' ', strip=True).replace('Latest Action:', '').strip()
            
            # Extract action date if available
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', bill_data['latest_action'])
            if date_match:
                bill_data['latest_action_date'] = date_match.group(1)
        
        # Extract bill status
        status_elem = item.select_one('span.result-item.result-tracker')
        if status_elem:
            status_text = status_elem.select_one('p.hide_fromsighted')
            if status_text:
                bill_data['status'] = status_text.text.strip()
        
        # Add to bills list
        bills.append(bill_data)
    
    # Find the next page link
    next_page_link = soup.select_one('a.next')
    next_page_url = urljoin(BASE_URL, next_page_link.get('href')) if next_page_link else None
    
    return bills, next_page_url

# Function to scrape the "All Actions" page for a bill
def scrape_all_actions(url, bill_number):
    print(f"Scraping actions for {bill_number}: {url}")
    
    response = safe_get_page(url, description=f"actions for {bill_number}")
    if not response:
        print(f"Failed to retrieve actions page after multiple attempts")
        return []
    
    if response.status_code != 200:
        print(f"Failed to retrieve actions page: {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    actions = []
    
    # Find the table with all actions
    action_table = soup.select_one('table.expanded-actions')
    if not action_table:
        print(f"No action table found for {bill_number}")
        # Try alternative method - sometimes the compact actions view is used
        compact_actions = soup.select_one('div.compact-actions')
        if compact_actions:
            print(f"Found compact actions view instead for {bill_number}")
            # Process compact actions instead
            actions_text = compact_actions.get_text('\n', strip=True)
            action_blocks = actions_text.split('\n\n')
            for block in action_blocks:
                if block.strip():
                    parts = block.split('\n', 1)
                    if len(parts) >= 1:
                        date_match = re.match(r'(\d{2}/\d{2}/\d{4})', parts[0])
                        if date_match:
                            date = date_match.group(1)
                            action_text = parts[0][len(date):].strip()
                            actions.append({
                                'date': date,
                                'action': action_text,
                                'action_by': '' # No action_by in compact view
                            })
        return actions
    
    # Extract each action row from the table
    action_rows = action_table.select('tbody tr')
    print(f"Found {len(action_rows)} actions for {bill_number}")
    
    for row in action_rows:
        action_data = {}
        
        # Extract date
        date_cell = row.select_one('td.date')
        if date_cell:
            action_data['date'] = date_cell.text.strip()
        
        # Extract action text and "Action By" info
        action_cell = row.select_one('td.actions')
        if action_cell:
            # Get the main action text (first part before the <br>)
            # We need to handle both cases: when there's direct text and when there are nested elements
            action_texts = []
            for content in action_cell.contents:
                if isinstance(content, str) and content.strip():
                    action_texts.append(content.strip())
                elif getattr(content, 'name', None) != 'br' and getattr(content, 'name', None) != 'span':
                    action_texts.append(content.get_text().strip())
                
                # Stop when we hit a <br> tag
                if getattr(content, 'name', None) == 'br':
                    break
            
            action_data['action'] = ' '.join(action_texts).strip()
            
            # Get the "Action By" information
            action_by = action_cell.select_one('span[style*="color:#666"]')
            if action_by:
                action_by_text = action_by.get_text(' ', strip=True)
                # Remove "Action By:" prefix if present
                action_data['action_by'] = action_by_text.replace('Action By:', '').strip()
        
        # Only add if we have meaningful data
        if action_data.get('date') and action_data.get('action'):
            actions.append(action_data)
    
    # Double-check: If we didn't extract any actions but the table exists,
    # there might be a different structure than expected
    if not actions and action_rows:
        print(f"Warning: Found action table but couldn't extract actions for {bill_number}")
        # Save HTML for debugging
        debug_file = f"debug_actions_{bill_number.replace('.', '_')}.html"
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(str(action_table))
        print(f"Saved action table HTML to {debug_file} for debugging")
    
    return actions
    
    # Extract each action row
    action_rows = action_table.select('tbody tr')
    print(f"Found {len(action_rows)} actions")
    
    for row in action_rows:
        action_data = {}
        
        # Extract date
        date_cell = row.select_one('td.date')
        if date_cell:
            action_data['date'] = date_cell.text.strip()
        
        # Extract action text and "Action By" info
        action_cell = row.select_one('td.actions')
        if action_cell:
            # Get the main action text (first part before the <br>)
            action_text = action_cell.contents[0].strip() if action_cell.contents else ""
            action_data['action'] = action_text
            
            # Get the "Action By" information
            action_by = action_cell.select_one('span[style="color:#666;"]')
            if action_by:
                action_data['action_by'] = action_by.text.strip().replace('Action By:', '').strip()
        
        actions.append(action_data)
    
    return actions

# Main function to orchestrate the scraping process
def scrape_legislation():
    # Set up initial variables and directories
    all_bills = []
    page_count = 1
    max_pages = 100  # Safety limit
    total_bills_processed = 0
    total_actions_processed = 0
    start_time = datetime.datetime.now()
    processed_bill_ids = []
    current_page_bills = []
    next_page_url = None
    
    # Create a directory for the JSON files
    os.makedirs('legislation_data', exist_ok=True)
    
    # Create a scrape_status.json to track where we left off
    status_file = 'legislation_data/scrape_status.json'
    
    # Stats file for monitoring progress
    stats_file = 'legislation_data/scraping_stats.txt'
    
    # Check if we're resuming a previous scrape
    current_url = None
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                status_data = json.load(f)
                current_url = status_data.get('current_url')
                next_page_url = status_data.get('next_url')
                page_count = status_data.get('current_page', 1)
                total_bills_processed = status_data.get('total_bills', 0)
                total_actions_processed = status_data.get('total_actions', 0)
                processed_bill_ids = status_data.get('processed_bill_ids', [])
                current_page_bills = status_data.get('current_page_bills', [])
                
                print(f"Resuming scrape from page {page_count}")
                print(f"Already processed {len(processed_bill_ids)} bills")
                
                if current_page_bills:
                    print(f"Resuming with {len(current_page_bills)} bills remaining on current page")
        except Exception as e:
            print(f"Error loading status file: {e}")
    
    # If not resuming or error loading status, start from the beginning
    if not current_url:
        current_url = "https://www.congress.gov/search?pageSort=latestAction%3Adesc&q=%7B%22source%22%3A%22legislation%22%2C%22type%22%3A%22bills%22%7D"
    
    # Load any existing scraped bills
    if os.path.exists('legislation_data/all_bills.json'):
        try:
            with open('legislation_data/all_bills.json', 'r') as f:
                all_bills = json.load(f)
                print(f"Loaded {len(all_bills)} previously scraped bills")
        except Exception as e:
            print(f"Error loading existing bills: {e}")
            all_bills = []
    
    while current_url and page_count <= max_pages:
        page_start_time = time.time()
        print(f"\n[{datetime.datetime.now()}] Processing page {page_count}...")
        
        # Scrape the search results page
        bills, next_page_url = scrape_search_page(current_url)
        
        # For each bill, get its detailed actions
        print(f"Processing {len(bills)} bills from page {page_count}...")
        for i, bill in enumerate(bills):
            bill_start_time = time.time()
            bill_number = bill.get('bill_number', f'Unknown-{i}')
            bill_id = bill.get('bill_url', '')  # Use URL as unique identifier
            
            # Skip if we already processed this bill
            if bill_id in processed_bill_ids:
                print(f"[{i+1}/{len(bills)}] Skipping already processed {bill_number}")
                continue
            
            print(f"[{i+1}/{len(bills)}] Processing {bill_number}")
            
            if 'all_actions_url' in bill:
                bill['actions'] = scrape_all_actions(bill['all_actions_url'], bill_number)
                total_actions_processed += len(bill['actions'])
            
            # Add to our collection
            all_bills.append(bill)
            
            # Save individual bill data
            if 'bill_number' in bill:
                bill_filename = f"legislation_data/{bill['bill_number'].replace('.', '').replace(' ', '_')}.json"
                with open(bill_filename, 'w', encoding='utf-8') as f:
                    json.dump(bill, f, indent=2)
            
            # Mark this bill as processed
            processed_bill_ids.append(bill_id)
            
            # Remove this bill from the current_page_bills list
            if bill in current_page_bills:
                current_page_bills.remove(bill)
            
            # Update progress after each bill
            save_progress(status_file, page_count, current_url, next_page_url, 
                          total_bills_processed + 1, total_actions_processed, 
                          current_page_bills, processed_bill_ids)
            
            bill_end_time = time.time()
            print(f"  Completed in {bill_end_time - bill_start_time:.2f} seconds")
            
            # Be nice to the server - rate limit to less than 20 calls per second
            time.sleep(0.05)  # 50ms sleep = max 20 requests per second
            
            total_bills_processed += 1
        
        # We've finished all bills on this page
        current_page_bills = []
        
        # Save the complete data after each page
        with open('legislation_data/all_bills.json', 'w', encoding='utf-8') as f:
            json.dump(all_bills, f, indent=2)
        
        # Update and save statistics
        current_time = datetime.datetime.now()
        elapsed_time = (current_time - start_time).total_seconds()
        page_time = time.time() - page_start_time
        
        stats = [
            f"Scraping Statistics - Updated: {current_time}",
            f"Pages Processed: {page_count}",
            f"Total Bills Processed: {total_bills_processed}",
            f"Total Actions Processed: {total_actions_processed}",
            f"Elapsed Time: {elapsed_time:.2f} seconds",
            f"Last Page Processing Time: {page_time:.2f} seconds",
            f"Average Time Per Bill: {elapsed_time/max(1, total_bills_processed):.2f} seconds",
            f"Bills Per Second: {total_bills_processed/max(1, elapsed_time):.2f}",
            f"Current Page: {page_count}",
            f"Next URL: {next_page_url}"
        ]
        
        with open(stats_file, 'w') as f:
            f.write('\n'.join(stats))
        
        print(f"Page {page_count} completed in {page_time:.2f} seconds")
        print(f"Progress: {total_bills_processed} bills, {total_actions_processed} actions")
        
        # Move to the next page
        current_url = next_page_url
        page_count += 1
        
        # Be nice to the server between pages, but still stay under 20 calls/second
        time.sleep(0.1)  # 100ms sleep between pages
    
    end_time = datetime.datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print("\n" + "="*80)
    print("SCRAPING COMPLETE")
    print(f"Start time: {start_time}")
    print(f"End time: {end_time}")
    print(f"Total elapsed time: {elapsed:.2f} seconds")
    print(f"Pages processed: {page_count-1}")
    print(f"Bills scraped: {len(all_bills)}")
    print(f"Total actions: {total_actions_processed}")
    print(f"Average time per bill: {elapsed/max(1, len(all_bills)):.2f} seconds")
    print(f"Processing rate: {len(all_bills)/max(1, elapsed):.2f} bills per second")
    print("="*80)
    
    return all_bills

# Run the scraper
if __name__ == "__main__":
    try:
        print("Starting legislation scraper...")
        print("Press Ctrl+C at any time to stop the scraper. Progress will be saved.")
        scrape_legislation()
    except KeyboardInterrupt:
        print("\nScraper stopped by user. Saving final progress...")
        
        # Save final progress - this is a trick to access variables from scrape_legislation()
        # We'll try to get the traceback frame to get the variables
        import sys
        import traceback
        
        try:
            # Get the most recent frame
            frame = sys._current_frames()[list(sys._current_frames().keys())[0]]
            
            # Look for the scrape_legislation frame in the stack
            while frame and frame.f_code.co_name != 'scrape_legislation':
                frame = frame.f_back
            
            if frame:
                # Get the local variables from the frame
                locals_dict = frame.f_locals
                
                # Get the variables we need
                status_file = locals_dict.get('status_file')
                page_count = locals_dict.get('page_count', 1)
                current_url = locals_dict.get('current_url', '')
                next_page_url = locals_dict.get('next_page_url', '')
                total_bills_processed = locals_dict.get('total_bills_processed', 0)
                total_actions_processed = locals_dict.get('total_actions_processed', 0)
                current_page_bills = locals_dict.get('current_page_bills', [])
                processed_bill_ids = locals_dict.get('processed_bill_ids', [])
                
                # Save the final progress
                if status_file:
                    save_progress(status_file, page_count, current_url, next_page_url,
                                 total_bills_processed, total_actions_processed,
                                 current_page_bills, processed_bill_ids)
                    print("Final progress saved successfully.")
                else:
                    print("Could not save final progress: status_file not found")
            else:
                print("Could not locate scrape_legislation frame to save progress")
        except Exception as e:
            print(f"Error saving final progress: {e}")
        
        print("Partial data has been saved. Run the script again to resume from where you left off.")
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()
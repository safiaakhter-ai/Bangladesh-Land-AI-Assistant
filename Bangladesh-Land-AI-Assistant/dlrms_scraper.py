"""
DLRMS (Digital Land Records Management System) Scraper
Selenium-based browser automation for Survey, Namjari, and Mouza Map sections
Requires credentials and respects site's intended usage
"""

import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import sqlite3
import json
import time
import logging
from datetime import datetime
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(__import__('pathlib').Path(__file__).resolve().parent / 'data' / 'dlrms_scraper.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DLRMSScraper:
    def __init__(self, db_path='dlrms_records.db', headless=False):
        self.db_path = db_path
        self.base_url = __import__('os').environ.get('DLRMS_SOURCE_URL', '')
        if not self.base_url.startswith('https://'):
            raise ValueError('Configure an authorized HTTPS DLRMS_SOURCE_URL before using the scraper')
        self.init_database()
        self.driver = None
        self.headless = headless
        self.stop_requested = False
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Survey records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS survey_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mauza TEXT,
                sheet_number TEXT,
                dag_number TEXT,
                area REAL,
                owner_name TEXT,
                record_content TEXT,
                url TEXT UNIQUE,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Namjari (mutation) records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS namjari_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mauza TEXT,
                khatian_number TEXT,
                dag_number TEXT,
                mutation_date TEXT,
                from_name TEXT,
                to_name TEXT,
                record_content TEXT,
                url TEXT UNIQUE,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Mouza Map data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mouza_maps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                district TEXT,
                upazila TEXT,
                mauza TEXT,
                map_url TEXT,
                map_data TEXT,
                map_image_path TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def init_driver(self):
        """Initialize Selenium WebDriver"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("WebDriver initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            return False
    
    def login(self, username, password):
        """Login to DLRMS if required"""
        try:
            self.driver.get(self.base_url)
            time.sleep(2)
            
            # Check if login page exists
            try:
                login_btn = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Login')]")
                login_btn.click()
                time.sleep(2)
                
                # Enter credentials
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                username_field.send_keys(username)
                
                password_field = self.driver.find_element(By.ID, "password")
                password_field.send_keys(password)
                
                submit_btn = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                submit_btn.click()
                
                time.sleep(3)
                logger.info("Login successful")
                return True
            except:
                logger.info("No login required or login page not found")
                return True
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def scrape_survey_section(self):
        """Scrape survey records by iterating columns dynamically with state saving"""
        logger.info("Starting automated list iteration for Survey section (landgov-bd.com)...")
        state = self.load_scraper_state('survey')
        
        try:
            self.driver.get(self.base_url)
            time.sleep(4)
            
            # 1. Division loop
            divisions = self._get_list_column_options("division")
            logger.info(f"Divisions found: {divisions}")
            
            for division in divisions:
                if getattr(self, 'stop_requested', False): break
                
                if state.get('division') and division != state.get('division'):
                    continue
                if state.get('division') == division:
                    state['division'] = None
                    
                logger.info(f"Selecting division: {division}")
                if not self._select_list_column_option("division", division):
                    continue
                time.sleep(2.5)
                
                # 2. District loop
                districts = self._get_list_column_options("district")
                for district in districts:
                    if getattr(self, 'stop_requested', False): break
                    
                    if state.get('district') and district != state.get('district'):
                        continue
                    if state.get('district') == district:
                        state['district'] = None
                        
                    logger.info(f"Selecting district: {district}")
                    if not self._select_list_column_option("district", district):
                        continue
                    time.sleep(2.5)
                    
                    # 3. Upazila loop
                    upazilas = self._get_list_column_options("upazila")
                    for upazila in upazilas:
                        if getattr(self, 'stop_requested', False): break
                        
                        if state.get('upazila') and upazila != state.get('upazila'):
                            continue
                        if state.get('upazila') == upazila:
                            state['upazila'] = None
                            
                        logger.info(f"Selecting upazila: {upazila}")
                        if not self._select_list_column_option("upazila", upazila):
                            continue
                        time.sleep(2.5)
                        
                        # 4. Khatiyan Type loop
                        khatian_types = self._get_list_column_options("khatian_type")
                        for k_type in khatian_types:
                            if getattr(self, 'stop_requested', False): break
                            
                            if state.get('khatian_type') and k_type != state.get('khatian_type'):
                                continue
                            if state.get('khatian_type') == k_type:
                                state['khatian_type'] = None
                                
                            logger.info(f"Selecting Khatiyan Type: {k_type}")
                            if not self._select_list_column_option("khatian_type", k_type):
                                continue
                            time.sleep(2.5)
                            
                            # 5. Mouza loop
                            mouzas = self._get_list_column_options("mauza")
                            for mouza in mouzas:
                                if getattr(self, 'stop_requested', False): break
                                
                                if state.get('mouza') and mouza != state.get('mouza'):
                                    continue
                                if state.get('mouza') == mouza:
                                    state['mouza'] = None
                                    
                                logger.info(f"Selecting Mouza: {mouza}")
                                if not self._select_list_column_option("mauza", mouza):
                                    continue
                                time.sleep(3)
                                
                                # Scrape
                                self._scrape_records_on_page('survey', division, district, upazila, mouza, type_name=k_type)
                                
                                # Update progress state
                                self.save_scraper_state('survey', {
                                    'division': division,
                                    'district': district,
                                    'upazila': upazila,
                                    'khatian_type': k_type,
                                    'mouza': mouza
                                })
                                
            logger.info("Survey section scraping completed")
        except Exception as e:
            logger.error(f"Error in survey scraping: {e}")
    
    def scrape_namjari_section(self):
        """Scrape namjari records by iterating columns dynamically with state saving"""
        logger.info("Starting automated list iteration for Namjari section...")
        state = self.load_scraper_state('namjari')
        
        try:
            self.driver.get(self.base_url)
            time.sleep(4)
            
            # Make sure we click the Namjari tab
            try:
                namjari_tab = self.driver.find_element(By.XPATH, "//*[contains(text(), 'নামজারি খতিয়ান')]")
                namjari_tab.click()
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Could not click Namjari Khatiyan tab: {e}")
                
            # 1. Division loop
            divisions = self._get_list_column_options("division")
            logger.info(f"Divisions found: {divisions}")
            
            for division in divisions:
                if getattr(self, 'stop_requested', False): break
                
                if state.get('division') and division != state.get('division'):
                    continue
                if state.get('division') == division:
                    state['division'] = None
                    
                logger.info(f"Selecting division: {division}")
                if not self._select_list_column_option("division", division):
                    continue
                time.sleep(2.5)
                
                # 2. District loop
                districts = self._get_list_column_options("district")
                for district in districts:
                    if getattr(self, 'stop_requested', False): break
                    
                    if state.get('district') and district != state.get('district'):
                        continue
                    if state.get('district') == district:
                        state['district'] = None
                        
                    logger.info(f"Selecting district: {district}")
                    if not self._select_list_column_option("district", district):
                        continue
                    time.sleep(2.5)
                    
                    # 3. Upazila loop
                    upazilas = self._get_list_column_options("upazila")
                    for upazila in upazilas:
                        if getattr(self, 'stop_requested', False): break
                        
                        if state.get('upazila') and upazila != state.get('upazila'):
                            continue
                        if state.get('upazila') == upazila:
                            state['upazila'] = None
                            
                        logger.info(f"Selecting upazila: {upazila}")
                        if not self._select_list_column_option("upazila", upazila):
                            continue
                        time.sleep(2.5)
                        
                        # 4. Mouza loop
                        mouzas = self._get_list_column_options("mauza")
                        for mouza in mouzas:
                            if getattr(self, 'stop_requested', False): break
                            
                            if state.get('mouza') and mouza != state.get('mouza'):
                                continue
                            if state.get('mouza') == mouza:
                                state['mouza'] = None
                                
                            logger.info(f"Selecting Mouza: {mouza}")
                            if not self._select_list_column_option("mauza", mouza):
                                continue
                            time.sleep(3)
                            
                            # Scrape
                            self._scrape_records_on_page('namjari', division, district, upazila, mouza)
                            
                            # Update progress state
                            self.save_scraper_state('namjari', {
                                'division': division,
                                'district': district,
                                'upazila': upazila,
                                'mouza': mouza
                            })
                            
            logger.info("Namjari section scraping completed")
        except Exception as e:
            logger.error(f"Error in namjari scraping: {e}")
    
    def scrape_mouza_map_section(self):
        """Scrape মৌজা ম্যাপ (Mouza Map) section"""
        logger.info("Starting Mouza Map section scraping...")
        
        try:
            # Navigate to mouza map section
            map_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'মৌজা ম্যাপ')]")
            map_link.click()
            time.sleep(3)
            
            # Handle map selection (district, upazila, mauza dropdowns)
            districts = self._get_dropdown_options("district")
            
            for district in districts[:5]:  # Start with first 5 districts to test
                if getattr(self, 'stop_requested', False):
                    logger.info("Scraping stopped by user request.")
                    break
                logger.info(f"Processing district: {district}")
                
                self._select_dropdown("district", district)
                time.sleep(2)
                
                upazilas = self._get_dropdown_options("upazila")
                
                for upazila in upazilas[:3]:  # First 3 upazilas per district
                    if getattr(self, 'stop_requested', False):
                        break
                    logger.info(f"Processing upazila: {upazila}")
                    
                    self._select_dropdown("upazila", upazila)
                    time.sleep(2)
                    
                    mouzas = self._get_dropdown_options("mauza")
                    
                    for mauza in mouzas[:5]:  # First 5 mouzas per upazila
                        if getattr(self, 'stop_requested', False):
                            break
                        try:
                            self._select_dropdown("mauza", mauza)
                            time.sleep(2)
                            
                            # Extract map
                            map_data = self._extract_map_data()
                            
                            map_record = {
                                'district': district,
                                'upazila': upazila,
                                'mauza': mauza,
                                'map_data': json.dumps(map_data)
                            }
                            
                            self.save_mouza_map(map_record)
                            
                        except Exception as e:
                            logger.warning(f"Error processing mauza {mauza}: {e}")
                            continue
            
            logger.info("Mouza Map section scraping completed")
            
        except Exception as e:
            logger.error(f"Error in mouza map scraping: {e}")
            
    def automate_search_form(self, division=None, district=None, upazila=None, mouza=None, search_type=None, search_query=None):
        """Automate filling and submitting the search form"""
        logger.info(f"Automating search form: Division={division}, District={district}, Upazila={upazila}, Mouza={mouza}, SearchType={search_type}, Query={search_query}")
        
        try:
            # 1. Select division if provided
            if division:
                self._select_dropdown("division", division)
                time.sleep(2)
                
            # 2. Select district
            if district:
                self._select_dropdown("district", district)
                time.sleep(2)
                
            # 3. Select upazila
            if upazila:
                self._select_dropdown("upazila", upazila)
                time.sleep(2)
                
            # 4. Select mouza
            if mouza:
                self._select_dropdown("mauza", mouza)
                time.sleep(2)
                
            # 5. Select search type if provided (e.g. by value or index)
            if search_type:
                try:
                    self._select_dropdown("search_type", search_type)
                except:
                    try:
                        self._select_dropdown("search_by", search_type)
                    except:
                        pass
                time.sleep(1)
                
            # 6. Fill search query
            if search_query:
                query_inputs = ["search_query", "khatian_no", "dag_no", "owner_name", "query", "search-key"]
                input_field = None
                for q_id in query_inputs:
                    try:
                        input_field = self.driver.find_element(By.ID, q_id)
                        break
                    except:
                        try:
                            input_field = self.driver.find_element(By.NAME, q_id)
                            break
                        except:
                            continue
                if not input_field:
                    try:
                        input_field = self.driver.find_element(By.XPATH, "//input[@type='text']")
                    except:
                        pass
                if input_field:
                    input_field.clear()
                    input_field.send_keys(search_query)
                    time.sleep(1)
                    
            # 7. Click search button
            search_buttons = ["search_button", "submit", "btn-search", "search-btn"]
            btn = None
            for b_id in search_buttons:
                try:
                    btn = self.driver.find_element(By.ID, b_id)
                    break
                except:
                    try:
                        btn = self.driver.find_element(By.XPATH, f"//button[contains(text(), 'অনুসন্ধান') or contains(text(), 'Search')]")
                        break
                    except:
                        continue
            if not btn:
                try:
                    btn = self.driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
                except:
                    pass
            if btn:
                btn.click()
                logger.info("Search form submitted")
                time.sleep(3)
            else:
                logger.warning("Search button not found")
                
            return True
        except Exception as e:
            logger.error(f"Error automating search form: {e}")
            return False
    
    def load_scraper_state(self, task_type):
        """Load scraper state from scraper_state.json"""
        import os
        state_file = 'scraper_state.json'
        default_state = {'division': None, 'district': None, 'upazila': None, 'mouza': None}
        if not os.path.exists(state_file):
            return default_state
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(task_type, default_state)
        except Exception as e:
            logger.warning(f"Error loading state file: {e}")
            return default_state

    def save_scraper_state(self, task_type, state_data):
        """Save scraper state to scraper_state.json"""
        import os
        state_file = 'scraper_state.json'
        data = {}
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except:
                pass
        data[task_type] = state_data
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Scraper state saved for {task_type}: {state_data}")
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def _click_search_button(self):
        """Click the search/submit button on the DLRMS form"""
        search_buttons = ["search_button", "submit", "btn-search", "search-btn"]
        btn = None
        for b_id in search_buttons:
            try:
                btn = self.driver.find_element(By.ID, b_id)
                break
            except:
                try:
                    btn = self.driver.find_element(By.XPATH, f"//button[contains(text(), 'অনুসন্ধান') or contains(text(), 'Search')]")
                    break
                except:
                    continue
        if not btn:
            try:
                btn = self.driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
            except:
                pass
        if btn:
            btn.click()
            time.sleep(3)
            return True
        return False

    def _scrape_records_on_page(self, task_type, division, district, upazila, mouza, type_name=None):
        """Scrape all khatian records listed after a mouza is selected on landgov-bd.com.
        A single click opens a summary modal; scraper then clicks 'বিস্তারিত দেখুন' for full details."""
        logger.info(f"Scraping records in Mouza: {mouza}...")
        
        try:
            # Wait for khatian list to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "khatianList"))
            )
            
            ul = self.driver.find_element(By.ID, "khatianList")
            records = ul.find_elements(By.TAG_NAME, "li")
            record_count = len(records)
            logger.info(f"Found {record_count} records in Mouza {mouza}")
            
            for idx in range(record_count):
                if getattr(self, 'stop_requested', False):
                    break
                    
                try:
                    # Re-find the list to prevent StaleElementReferenceException
                    ul = self.driver.find_element(By.ID, "khatianList")
                    items = ul.find_elements(By.TAG_NAME, "li")
                    if idx >= len(items):
                        break
                    item = items[idx]
                    
                    record_label = item.text.strip()
                    logger.info(f"Processing record [{idx+1}/{record_count}]: {record_label}")
                    
                    # Scroll into view
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
                    time.sleep(0.5)
                    
                    # Single click opens the summary modal on landgov-bd.com
                    item.click()
                    time.sleep(2)
                    
                    # Click 'বিস্তারিত দেখুন' (See Details) button in the modal
                    try:
                        details_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//a[contains(text(), 'বিস্তারিত দেখুন')] | "
                                "//button[contains(text(), 'বিস্তারিত দেখুন')] | "
                                "//a[contains(text(), 'Details')]"
                            ))
                        )
                        detail_url_before = self.driver.current_url
                        details_btn.click()
                        time.sleep(3)
                    except Exception as e:
                        logger.warning(f"Could not click 'বিস্তারিত দেখুন': {e}. Scraping modal content only.")
                        # Fall back: scrape modal text directly
                        modal_text = ""
                        try:
                            modal = self.driver.find_element(By.CSS_SELECTOR,
                                "div[class*='modal'], div[class*='popup'], .modal-content")
                            modal_text = modal.text.strip()
                        except:
                            pass
                        self._close_modal()
                        if modal_text and task_type == 'survey':
                            parts = record_label.split('-', 1)
                            self.save_survey_record({
                                'mauza': mouza,
                                'sheet_number': type_name or "",
                                'dag_number': "",
                                'area': "",
                                'owner_name': parts[1].strip() if len(parts) > 1 else "",
                                'record_content': modal_text,
                                'url': self.driver.current_url
                            })
                        continue
                    
                    current_url = self.driver.current_url
                    logger.info(f"Navigated to detail page: {current_url}")
                    
                    # Extract structured fields from the detail page
                    detail_data = self._extract_detail_card()
                    full_text = self.driver.find_element(By.XPATH, "//body").text.strip()
                    
                    # Parse label for fallback values
                    parts = record_label.split('-', 1)
                    khatian_no = detail_data.get('khatian_no') or (parts[0].strip() if parts else "")
                    owner_name = detail_data.get('owner_name') or (parts[1].strip() if len(parts) > 1 else "")
                    
                    if task_type == 'survey':
                        survey_data = {
                            'mauza': detail_data.get('mouza') or mouza,
                            'sheet_number': detail_data.get('survey_type') or type_name or "",
                            'dag_number': detail_data.get('dag_no') or "",
                            'area': detail_data.get('area') or "",
                            'owner_name': owner_name,
                            'record_content': full_text,
                            'url': current_url
                        }
                        self.save_survey_record(survey_data)
                        logger.info(f"Saved survey record: Khatian {khatian_no}, Owner: {owner_name}, Area: {detail_data.get('area')}")
                        
                    elif task_type == 'namjari':
                        namjari_data = {
                            'mauza': detail_data.get('mouza') or mouza,
                            'khatian_number': khatian_no,
                            'dag_number': detail_data.get('dag_no') or "",
                            'mutation_date': "",
                            'from_name': "",
                            'to_name': owner_name,
                            'record_content': full_text,
                            'url': current_url
                        }
                        self.save_namjari_record(namjari_data)
                        logger.info(f"Saved namjari record: Khatian {khatian_no}, Owner: {owner_name}")
                    
                    # Navigate back to the main list page
                    self.driver.back()
                    time.sleep(2)
                    
                    # Close any open modal after returning
                    self._close_modal()
                    
                    # Wait for khatian list to be available again
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "khatianList"))
                    )
                    
                except Exception as e:
                    logger.warning(f"Error scraping record {idx}: {e}")
                    try:
                        if 'khatian-details' in self.driver.current_url:
                            self.driver.back()
                            time.sleep(2)
                        self._close_modal()
                    except:
                        pass
                    continue
                    
        except Exception as e:
            logger.warning(f"Error loading records for Mouza {mouza}: {e}")

    def _close_modal(self):
        """Close any open modal by clicking the × or Close button, or pressing Escape"""
        try:
            close_btn = self.driver.find_element(By.XPATH,
                "//span[text()='×'] | //button[contains(@class,'close')] | "
                "//button[contains(text(),'Close')] | //span[@aria-label='close']"
            )
            if close_btn.is_displayed():
                close_btn.click()
                time.sleep(0.8)
        except:
            try:
                from selenium.webdriver.common.keys import Keys
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(0.5)
            except:
                pass

    def _extract_detail_card(self):
        """Extract structured fields from the khatian detail page on landgov-bd.com.
        Returns a dict with: khatian_no, division, district, upazila, survey_type, mouza, area, owner_name, dag_no"""
        data = {}
        try:
            # Wait for card to appear - landgov-bd.com uses a heading containing 'খতিয়ান'
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.XPATH,
                    "//*[contains(text(), 'খতিয়ান')] | "
                    "//*[contains(@class, 'khatian')] | "
                    "//h1 | //h2 | //h3"
                ))
            )
            
            # Helper: find the sibling/child value element next to a label
            def extract_field(*label_texts):
                for label_text in label_texts:
                    try:
                        # Try: <td>Label</td><td>Value</td>
                        el = self.driver.find_element(
                            By.XPATH,
                            f"//td[contains(normalize-space(.), '{label_text}')]/following-sibling::td[1] | "
                            f"//th[contains(normalize-space(.), '{label_text}')]/following-sibling::td[1] | "
                            f"//li[contains(normalize-space(.), '{label_text}')]//span[2] | "
                            f"//p[contains(normalize-space(.), '{label_text}')]/following-sibling::p[1] | "
                            f"//*[contains(text(), '{label_text}')]/following-sibling::*[1]"
                        )
                        text = el.text.strip().lstrip(':').strip()
                        if text:
                            return text
                    except:
                        pass
                return ""
            
            data['khatian_no']  = extract_field('খতিয়ান নং', 'Khatian No', 'KH No')
            data['division']    = extract_field('বিভাগ', 'Division')
            data['district']    = extract_field('জেলা', 'District')
            data['upazila']     = extract_field('উপজেলা', 'Upazila', 'Thana')
            data['survey_type'] = extract_field('সার্ভে', 'Survey')
            data['mouza']       = extract_field('মৌজা', 'Mouza')
            data['jl_no']       = extract_field('জে এল নং', 'JL No')
            data['area']        = extract_field('জমির পরিমাণ', 'মোট জমি', 'Total Land', 'Land Area')
            data['owner_name']  = extract_field('মালিকের নাম', 'মালিক', 'Owner', 'Owner Name')
            data['dag_no']      = extract_field('দাগ নং', 'Dag No', 'Dag Number')
            
            logger.info(f"Detail card: Khatian={data.get('khatian_no')}, Mouza={data.get('mouza')}, "
                        f"Owner={data.get('owner_name')}, Area={data.get('area')}, Dag={data.get('dag_no')}")
        except Exception as e:
            logger.warning(f"Could not extract detail card fields: {e}")
        return data

    def _get_list_column_options(self, column_type):
        """Get options text from a specific list column using landgov-bd.com IDs"""
        # Map column_type to the element ID used on landgov-bd.com
        id_map = {
            'division':     'divisionList',
            'district':     'districtList',
            'upazila':      'upazilaList',
            'khatian_type': 'surveyList',
            'mauza':        'mouzaList',
            'khatian_list': 'khatianList',
        }
        element_id = id_map.get(column_type)
        if not element_id:
            logger.warning(f"Unknown column_type: {column_type}")
            return []
        try:
            ul = WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.ID, element_id))
            )
            items = ul.find_elements(By.TAG_NAME, "li")
            values = [item.text.strip() for item in items if item.text.strip()]
            logger.debug(f"{column_type} options ({len(values)}): {values[:5]}{'...' if len(values)>5 else ''}")
            return values
        except Exception as e:
            logger.debug(f"Error fetching list options for {column_type} (ID={element_id}): {e}")
            return []

    def _select_list_column_option(self, column_type, value):
        """Click an option in the specific list column by text value on landgov-bd.com"""
        id_map = {
            'division':     'divisionList',
            'district':     'districtList',
            'upazila':      'upazilaList',
            'khatian_type': 'surveyList',
            'mauza':        'mouzaList',
            'khatian_list': 'khatianList',
        }
        element_id = id_map.get(column_type)
        if not element_id:
            return False
        try:
            ul = WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.ID, element_id))
            )
            items = ul.find_elements(By.TAG_NAME, "li")
            for item in items:
                item_text = item.text.strip()
                if item_text == value or value in item_text:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
                    time.sleep(0.3)
                    item.click()
                    logger.debug(f"Selected {column_type}: '{value}'")
                    return True
            logger.warning(f"Value '{value}' not found in {column_type} list")
            return False
        except Exception as e:
            logger.warning(f"Error selecting {column_type} value '{value}': {e}")
            return False

    def _safe_extract(self, element, xpath):
        """Safely extract text from element using xpath"""
        try:
            # Ensure the XPath is relative to the element (not matching from document root)
            if xpath.startswith('/') and not xpath.startswith('./'):
                xpath = '.' + xpath
            found = element.find_element(By.XPATH, xpath)
            return found.text.strip()
        except:
            return None
    
    def _safe_extract_page(self):
        """Safely extract page content"""
        try:
            return self.driver.find_element(By.XPATH, "//body").text
        except:
            return None
    
    def _get_dropdown_options(self, dropdown_name):
        """Get all options from a dropdown"""
        try:
            dropdown = self.driver.find_element(By.ID, dropdown_name)
            options = dropdown.find_elements(By.TAG_NAME, "option")
            return [opt.text for opt in options if opt.text]
        except:
            return []
    
    def _select_dropdown(self, dropdown_id, value):
        """Select option from dropdown"""
        try:
            dropdown = self.driver.find_element(By.ID, dropdown_id)
            options = dropdown.find_elements(By.TAG_NAME, "option")
            for option in options:
                if option.text == value:
                    option.click()
                    break
        except Exception as e:
            logger.warning(f"Error selecting {dropdown_id}: {e}")
    
    def _extract_map_data(self):
        """Extract map data (GeoJSON, coordinates, etc.)"""
        try:
            # Try to get map data from canvas or SVG
            map_container = self.driver.find_element(By.ID, "map-container")
            map_data = map_container.get_attribute("data-geojson") or {}
            return json.loads(map_data) if isinstance(map_data, str) else map_data
        except:
            return {}
    
    def save_survey_record(self, data):
        """Save survey record to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO survey_records 
                (mauza, sheet_number, dag_number, area, owner_name, record_content, url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('mauza'),
                data.get('sheet_number'),
                data.get('dag_number'),
                data.get('area'),
                data.get('owner_name'),
                data.get('record_content'),
                data.get('url')
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved survey record for mauza: {data.get('mauza')}")
        except Exception as e:
            logger.error(f"Error saving survey record: {e}")
    
    def save_namjari_record(self, data):
        """Save namjari record to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO namjari_records 
                (mauza, khatian_number, dag_number, mutation_date, from_name, to_name, record_content, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('mauza'),
                data.get('khatian_number'),
                data.get('dag_number'),
                data.get('mutation_date'),
                data.get('from_name'),
                data.get('to_name'),
                data.get('record_content'),
                data.get('url')
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved namjari record for mauza: {data.get('mauza')}")
        except Exception as e:
            logger.error(f"Error saving namjari record: {e}")
    
    def save_mouza_map(self, data):
        """Save mouza map data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO mouza_maps 
                (district, upazila, mauza, map_data)
                VALUES (?, ?, ?, ?)
            ''', (
                data.get('district'),
                data.get('upazila'),
                data.get('mauza'),
                data.get('map_data')
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved map for: {data.get('district')} - {data.get('mauza')}")
        except Exception as e:
            logger.error(f"Error saving mouza map: {e}")
    
    def export_to_json(self, output_dir='dlrms_export'):
        """Export all collected data to JSON"""
        try:
            import os
            os.makedirs(output_dir, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Export survey records
            cursor.execute('SELECT * FROM survey_records')
            survey_data = [dict(row) for row in cursor.fetchall()]
            with open(f'{output_dir}/survey_records.json', 'w', encoding='utf-8') as f:
                json.dump(survey_data, f, ensure_ascii=False, indent=2, default=str)
            
            # Export namjari records
            cursor.execute('SELECT * FROM namjari_records')
            namjari_data = [dict(row) for row in cursor.fetchall()]
            with open(f'{output_dir}/namjari_records.json', 'w', encoding='utf-8') as f:
                json.dump(namjari_data, f, ensure_ascii=False, indent=2, default=str)
            
            # Export mouza maps
            cursor.execute('SELECT * FROM mouza_maps')
            map_data = [dict(row) for row in cursor.fetchall()]
            with open(f'{output_dir}/mouza_maps.json', 'w', encoding='utf-8') as f:
                json.dump(map_data, f, ensure_ascii=False, indent=2, default=str)
            
            conn.close()
            logger.info(f"Data exported to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
    
    def close(self):
        """Close WebDriver"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")


def main():
    """Main execution"""
    scraper = DLRMSScraper(headless=False)
    
    try:
        # Initialize driver
        if not scraper.init_driver():
            return
        
        # Optional: Login if required
        # scraper.login('username', 'password')
        
        # Scrape all sections
        scraper.scrape_survey_section()
        scraper.scrape_namjari_section()
        scraper.scrape_mouza_map_section()
        
        # Export results
        scraper.export_to_json()
        
    finally:
        scraper.close()


if __name__ == '__main__':
    main()

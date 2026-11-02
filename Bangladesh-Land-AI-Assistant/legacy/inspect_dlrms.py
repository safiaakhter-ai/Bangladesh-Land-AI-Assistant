"""
DLRMS Selector Inspector
Helps identify correct CSS selectors for survey, namjari, and mouza map sections
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import json
import time

class DLRMSInspector:
    def __init__(self):
        self.base_url = 'https://dlrms.land.gov.bd/'
        self.driver = None
        self.selectors_found = {}
    
    def init_driver(self, headless=False):
        """Initialize WebDriver"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        print("✓ WebDriver initialized")
    
    def inspect_survey_section(self):
        """Inspect Survey section structure"""
        print("\n" + "="*60)
        print("INSPECTING SURVEY (সার্ভে) SECTION")
        print("="*60)
        
        try:
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # Try to find survey section
            print("\n1. Looking for Survey section link...")
            survey_links = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'সার্ভে') or contains(text(), 'Survey')]")
            
            if survey_links:
                print(f"   ✓ Found {len(survey_links)} survey-related links")
                for link in survey_links:
                    print(f"     - Text: {link.text}")
                    print(f"     - Tag: {link.tag_name}")
                    print(f"     - XPath: {self._get_xpath(link)}")
            else:
                print("   ✗ No survey links found")
            
            # Click first survey link
            if survey_links:
                survey_links[0].click()
                time.sleep(3)
            
            # Inspect record structure
            print("\n2. Looking for record containers...")
            
            # Try common container selectors
            selectors_to_try = [
                ("class", "record-item"),
                ("class", "record"),
                ("class", "survey-record"),
                ("class", "data-row"),
                ("tag", "tr"),
            ]
            
            for selector_type, selector_value in selectors_to_try:
                if selector_type == "class":
                    elements = self.driver.find_elements(By.CLASS_NAME, selector_value)
                elif selector_type == "tag":
                    elements = self.driver.find_elements(By.TAG_NAME, selector_value)
                
                if elements:
                    print(f"   ✓ Found {len(elements)} elements with {selector_type}='{selector_value}'")
                    self.selectors_found[f"survey_container_{selector_type}_{selector_value}"] = len(elements)
            
            # Inspect field structure
            print("\n3. Inspecting field structure in first record...")
            first_record = self.driver.find_elements(By.CLASS_NAME, "record-item") or \
                          self.driver.find_elements(By.CLASS_NAME, "record") or \
                          self.driver.find_elements(By.TAG_NAME, "tr")
            
            if first_record:
                record = first_record[0]
                print(f"   Record HTML:\n{record.get_attribute('outerHTML')[:500]}...\n")
                
                # Try to find common fields
                fields_to_find = [
                    ("mauza", ["মৌজা", "mauza", "mauza-name"]),
                    ("sheet_number", ["sheet", "শীট", "শীট নং"]),
                    ("dag_number", ["dag", "ড্যাগ", "DAG"]),
                    ("owner_name", ["owner", "মালিক", "নাম"]),
                    ("area", ["area", "এলাকা", "ক্ষেত্রফল"]),
                ]
                
                for field_name, keywords in fields_to_find:
                    print(f"\n   Finding '{field_name}':")
                    all_spans = record.find_elements(By.TAG_NAME, "span")
                    for span in all_spans:
                        text = span.text.lower()
                        if any(kw.lower() in text for kw in keywords):
                            print(f"     ✓ Found: {span.text}")
                            print(f"       Class: {span.get_attribute('class')}")
                            print(f"       XPath: {self._get_xpath(span)}")
                            break
            
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    def inspect_namjari_section(self):
        """Inspect Namjari section structure"""
        print("\n" + "="*60)
        print("INSPECTING NAMJARI (নামজারি) SECTION")
        print("="*60)
        
        try:
            self.driver.get(self.base_url)
            time.sleep(3)
            
            print("\n1. Looking for Namjari section link...")
            namjari_links = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'নামজারি') or contains(text(), 'Namjari') or contains(text(), 'Mutation')]")
            
            if namjari_links:
                print(f"   ✓ Found {len(namjari_links)} namjari-related links")
                for link in namjari_links:
                    print(f"     - Text: {link.text}")
                    print(f"     - XPath: {self._get_xpath(link)}")
            else:
                print("   ✗ No namjari links found")
            
            if namjari_links:
                namjari_links[0].click()
                time.sleep(3)
            
            # Inspect mutation record structure
            print("\n2. Looking for mutation record containers...")
            
            selectors_to_try = [
                ("class", "mutation-record"),
                ("class", "namjari-record"),
                ("class", "transfer-record"),
                ("class", "data-row"),
            ]
            
            for selector_type, selector_value in selectors_to_try:
                elements = self.driver.find_elements(By.CLASS_NAME, selector_value)
                if elements:
                    print(f"   ✓ Found {len(elements)} elements with {selector_type}='{selector_value}'")
            
            # Inspect fields
            print("\n3. Typical namjari fields:")
            fields = [
                "mauza", "khatian_number", "dag_number", 
                "mutation_date", "from_name", "to_name"
            ]
            print("   Look for these in the page HTML:")
            for field in fields:
                print(f"     - {field}")
            
            # Show page source snippet
            body = self.driver.find_element(By.TAG_NAME, "body")
            print(f"\n   Page HTML (first 1000 chars):\n{body.get_attribute('innerHTML')[:1000]}...")
            
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    def inspect_mouza_map_section(self):
        """Inspect Mouza Map section structure"""
        print("\n" + "="*60)
        print("INSPECTING MOUZA MAP (মৌজা ম্যাপ) SECTION")
        print("="*60)
        
        try:
            self.driver.get(self.base_url)
            time.sleep(3)
            
            print("\n1. Looking for Map section link...")
            map_links = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'মৌজা ম্যাপ') or contains(text(), 'Mouza Map') or contains(text(), 'Map')]")
            
            if map_links:
                print(f"   ✓ Found {len(map_links)} map-related links")
                for link in map_links:
                    print(f"     - Text: {link.text}")
            else:
                print("   ✗ No map links found")
            
            if map_links:
                map_links[0].click()
                time.sleep(3)
            
            # Look for dropdowns
            print("\n2. Looking for dropdown selectors...")
            dropdowns = self.driver.find_elements(By.TAG_NAME, "select")
            print(f"   ✓ Found {len(dropdowns)} select elements")
            
            for dropdown in dropdowns:
                dropdown_id = dropdown.get_attribute("id")
                dropdown_name = dropdown.get_attribute("name")
                options = dropdown.find_elements(By.TAG_NAME, "option")
                print(f"\n   Dropdown: id='{dropdown_id}', name='{dropdown_name}'")
                print(f"   Options: {len(options)}")
                for opt in options[:3]:  # Show first 3
                    print(f"     - {opt.text}")
            
            # Look for map container
            print("\n3. Looking for map container...")
            map_containers = self.driver.find_elements(By.ID, "map") or \
                           self.driver.find_elements(By.CLASS_NAME, "map-container") or \
                           self.driver.find_elements(By.ID, "map-container")
            
            if map_containers:
                print(f"   ✓ Found {len(map_containers)} map container(s)")
                for container in map_containers:
                    print(f"     - ID: {container.get_attribute('id')}")
                    print(f"     - Class: {container.get_attribute('class')}")
            
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    def export_findings(self, filename='dlrms_selectors_found.json'):
        """Export all findings"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.selectors_found, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Findings exported to {filename}")
    
    def _get_xpath(self, element):
        """Get XPath for an element"""
        try:
            return self.driver.execute_script("""
                function getElementXPath(element) {
                    if (element.id !== '')
                        return "//*[@id='" + element.id + "']";
                    if (element === document.body)
                        return element.tagName.toLowerCase();
                    var ix = 0;
                    var siblings = element.parentNode.childNodes;
                    for (var i = 0; i < siblings.length; i++) {
                        var sibling = siblings[i];
                        if (sibling === element)
                            return getElementXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        if (sibling.nodeType === 1 && sibling.tagName.toLowerCase() === element.tagName.toLowerCase())
                            ix++;
                    }
                }
                return getElementXPath(arguments[0]);
            """, element)
        except:
            return "N/A"
    
    def close(self):
        """Close WebDriver"""
        if self.driver:
            self.driver.quit()
            print("\n✓ WebDriver closed")


def main():
    """Run inspector"""
    inspector = DLRMSInspector()
    
    try:
        inspector.init_driver(headless=False)
        
        # Run all inspections
        inspector.inspect_survey_section()
        inspector.inspect_namjari_section()
        inspector.inspect_mouza_map_section()
        
        # Export findings
        inspector.export_findings()
        
        print("\n" + "="*60)
        print("INSPECTION COMPLETE")
        print("="*60)
        print("\nNext steps:")
        print("1. Review the output above for correct CSS selectors")
        print("2. Update dlrms_scraper.py with the found selectors")
        print("3. Run: python dlrms_scraper.py")
        
    finally:
        inspector.close()


if __name__ == '__main__':
    main()

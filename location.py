from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time
import random
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.keys import Keys
import subprocess
 
def main(driver,proposal_location):
    url = 'https://www.linkedin.com/service-marketplace/provider/requests/'
    driver.get(url)
    time.sleep(10)  # Wait for the page to load
    processed_requests = set()
    while True:
        try:
            try:
              # Try finding either of the close buttons
              close_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'msg-overlay-bubble-header__control artdeco-button artdeco-button--circle ')]")
 
              if close_buttons:
                  for btn in close_buttons:
                      try:
                          btn.click()
                          time.sleep(random.randint(2, 5))  # Allow time for closing before retrying
                          print("Closed a message overlay.")
                          break  # Stop after closing one
                      except Exception:
                          continue  # If the click fails, try the next button
             
              else:
                  print("No close button found!!")
 
            except Exception as e:
              print(f"Error closing message overlay: {e}")
 
 
            li_elements = driver.find_elements(By.CSS_SELECTOR, 'ul[data-test-service-marketplace-premium-service-requests__list] > li')
           
            if not li_elements:
                print("No more service requests found. Exiting...")
                break
            new_items_found = False
            for index, li in enumerate(li_elements):
                try:
                     # Use request text as a simple unique ID (can change to ID if available)
                    request_id = li.text.strip()
 
                    if request_id in processed_requests:
                        continue  # Skip already processed
 
                    processed_requests.add(request_id)
                    li.click()
                    time.sleep(2)
                    name_element = li.find_element(By.CSS_SELECTOR, 'p[data-test-service-requests-list-item__creator-name] span')
                    name = name_element.text
                   
                    subtitle_element = li.find_element(By.CSS_SELECTOR, 'p[data-test-service-requests-list-item__project-title] span')
                    subtitle = subtitle_element.text
                   
                    location_element = driver.find_element(By.XPATH, './/p[@data-test-service-requests-detail__location]')
                    location = location_element.text
 
                    if any(loc.lower() in location.lower() for loc in proposal_location):
                        new_items_found = True
                        submit_button = li.find_element(By.XPATH, '//button[@class="artdeco-button artdeco-button--2 artdeco-button--primary ember-view service-marketplace-provider-service-requests-detail__metadata-action mr2"]')
                        submit_button.click()
 
                       
                        time.sleep(random.randint(2, 5))
 
                                           
                        message = f"""Hi {name},
We are excited about the opportunity to support your business. Let’s schedule a meeting this week to finalize the plan and initiate the process. Please confirm your availability at your earliest convenience.
For any questions, feel free to reach out.
Thanks,
Christy
Work Email- christy@codework.ai"""
 
                        print(f"Processing Item {index + 1}:")
                        print(f"  Name: {name}")
                        print(f"  Subtitle: {subtitle}")
                        print(f"  Location: {location}")
                       
                        time.sleep(2)
                        try:
                            dialog_box = driver.find_element(By.XPATH, "//div[@class='artdeco-modal artdeco-modal--layer-default ']")
                            proposal_input = dialog_box.find_element(By.XPATH, "//textarea[@class='fb-multiline-text  artdeco-text-input--input artdeco-text-input__textarea artdeco-text-input__textarea--align-top']")
                           
                            for line in message.split('\n'):
                                proposal_input.send_keys(line.strip())
                                time.sleep(random.randint(1, 2))
                                ActionChains(driver).key_down(Keys.SHIFT).key_down(Keys.ENTER).key_up(Keys.SHIFT).key_up(Keys.ENTER).perform()
                                time.sleep(random.randint(1, 2))
                           
                            time.sleep(random.randint(5, 7))
                            submit = dialog_box.find_element(By.XPATH, "//button[@class='artdeco-button artdeco-button--2 artdeco-button--primary ember-view']")
                            submit.click()
                            time.sleep(random.randint(2, 5))
                                   
                            try:
                                close_btn = driver.find_element(By.XPATH, "//div[@class='relative display-flex flex-column flex-grow-1']//button[@class='msg-overlay-bubble-header__control artdeco-button artdeco-button--circle artdeco-button--muted artdeco-button--1 artdeco-button--tertiary ember-view']")

                                if close_btn is None:
                                    close_btn = driver.find_elements(By.XPATH, "//button[contains(@class, 'msg-overlay-bubble-header__control artdeco-button artdeco-button--circle ')]")
                                close_btn.click()
                                time.sleep(random.randint(2, 5))
                            except Exception:
                                print(f"No close button found for: {name}")
                        except Exception:
                            print("Send button not found")
                       
                        time.sleep(5)
                except Exception as e:
                    print(f"Error processing request: {e}")
                    continue
            if not new_items_found:
                print("No new matching requests found. Exiting...")
                break
 
            # Optionally scroll to load more
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)
 
        except Exception as e:
            print(f"An error occurred: {e}")
            break
   
    driver.quit()
 
if __name__ == "__main__":
    try:
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe", "/T"], check=True)
        print("✅ Microsoft Edge closed before script execution.")
    except subprocess.CalledProcessError:
        print("⚠️ No Edge process found or already closed.")
    try:
        profile_path = r"C:\\Users\\TCARE\\AppData\\Local\\Microsoft\\Edge\\User Data"
        options = Options()
        options.add_argument(f"--user-data-dir={profile_path}")  # Specify user data directory
        options.add_argument("--profile-directory=Profile 4")  # Use specific profile
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
       
        driver = webdriver.Edge(options=options)
        proposal_location = ["Dubai", "UK", "London", "United Kingdom", "UAE", "Manama, Capital Governorate"]
        main(driver,proposal_location)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if driver:
            driver.quit()
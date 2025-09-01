from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.keys import Keys
import subprocess
import time
import random
import os

router = APIRouter(prefix="/linkedin", tags=["LinkedIn Automation"])

class ProposalRequest(BaseModel):
    proposal_location: list[str]

def setup_optimized_driver():
    """Setup Edge driver with error suppression options."""
    options = EdgeOptions()
    
    # Basic options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    
    # GPU and rendering options to suppress WebGL errors
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-accelerated-2d-canvas")
    options.add_argument("--disable-accelerated-jpeg-decoding")
    options.add_argument("--disable-accelerated-mjpeg-decode")
    options.add_argument("--disable-accelerated-video-decode")
    
    # SSL and security options
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-certificate-errors-spki-list")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-web-security")
    
    # WebRTC options to suppress STUN errors
    options.add_argument("--disable-webrtc")
    options.add_argument("--disable-webrtc-multiple-routes")
    options.add_argument("--disable-webrtc-hw-decoding")
    options.add_argument("--disable-webrtc-hw-encoding")
    
    # Logging options to suppress console errors
    options.add_argument("--log-level=3")  # Only fatal errors
    options.add_argument("--silent")
    options.add_argument("--disable-logging")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Performance options
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    
    # Content settings to suppress pattern warnings
    options.add_argument("--disable-features=MediaRouter")
    options.add_argument("--disable-component-extensions-with-background-pages")
    
    # Profile directory
    profile_path = "C:/Users/Administrator/AppData/Local/Microsoft/Edge/User Data"
    if os.path.exists(profile_path):
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--profile-directory=Profile 4")
    
    service = EdgeService()
    driver = webdriver.Edge(service=service, options=options)
    return driver

def process_requests(driver, proposal_location: list[str]):
    url = 'https://www.linkedin.com/service-marketplace/provider/requests/'
    driver.get(url)
    time.sleep(10)

    processed_requests = set()
    results = []

    while True:
        try:
            close_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(@class, 'msg-overlay-bubble-header__control artdeco-button artdeco-button--circle ')]"
            )
            for btn in close_buttons:
                try:
                    btn.click()
                    time.sleep(random.randint(2, 5))
                    break
                except Exception:
                    continue

            li_elements = driver.find_elements(
                By.CSS_SELECTOR,
                'ul[data-test-service-marketplace-premium-service-requests__list] > li'
            )

            if not li_elements:
                break

            new_items_found = False
            for index, li in enumerate(li_elements):
                try:
                    request_id = li.text.strip()
                    if request_id in processed_requests:
                        continue

                    processed_requests.add(request_id)
                    li.click()
                    time.sleep(2)

                    name = li.find_element(By.CSS_SELECTOR,
                        'p[data-test-service-requests-list-item__creator-name] span').text
                    subtitle = li.find_element(By.CSS_SELECTOR,
                        'p[data-test-service-requests-list-item__project-title] span').text
                    location = driver.find_element(By.XPATH,
                        './/p[@data-test-service-requests-detail__location]').text

                    if any(loc.lower() in location.lower() for loc in proposal_location):
                        new_items_found = True
                        message = f"""Hi {name},
We are excited about the opportunity to support your business. Let’s schedule a meeting this week to finalize the plan and initiate the process. Please confirm your availability at your earliest convenience.
For any questions, feel free to reach out.
Thanks,
Christy
Work Email- christy@codework.ai"""

                        try:
                            dialog_box = driver.find_element(By.XPATH,
                                "//div[@class='artdeco-modal artdeco-modal--layer-default ']")
                            proposal_input = dialog_box.find_element(By.XPATH,
                                "//textarea[@class='fb-multiline-text  artdeco-text-input--input artdeco-text-input__textarea artdeco-text-input__textarea--align-top']")

                            for line in message.split('\n'):
                                proposal_input.send_keys(line.strip())
                                time.sleep(random.randint(1, 2))
                                ActionChains(driver).key_down(Keys.SHIFT).key_down(Keys.ENTER).key_up(Keys.SHIFT).key_up(Keys.ENTER).perform()

                            time.sleep(random.randint(5, 7))
                            dialog_box.find_element(By.XPATH,
                                "//button[@class='artdeco-button artdeco-button--2 artdeco-button--primary ember-view']").click()
                            time.sleep(random.randint(2, 5))

                            results.append({
                                "name": name,
                                "subtitle": subtitle,
                                "location": location,
                                "status": "Proposal Sent"
                            })
                        except Exception:
                            results.append({
                                "name": name,
                                "subtitle": subtitle,
                                "location": location,
                                "status": "Failed to Send"
                            })
                except Exception:
                    continue

            if not new_items_found:
                break

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)

        except Exception:
            break

    return results


@router.post("/send-proposals")
def send_proposals(request: ProposalRequest = Body(...)):
    try:
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe", "/T"], check=False, capture_output=True)

        # Use the optimized driver setup
        driver = setup_optimized_driver()
        results = process_requests(driver, request.proposal_location)
        return {"processed": len(results), "details": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        try:
            driver.quit()
        except Exception:
            pass

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.keys import Keys
import time
import random
import subprocess
import uuid
import os
from typing import Dict, Any

router = APIRouter(prefix="/profile-requests", tags=["LinkedIn Profile Requests"])

# Store for tracking background tasks
profile_tasks_store: Dict[str, Dict[str, Any]] = {}

class ProfileRequestResponse(BaseModel):
    task_id: str
    status: str
    message: str

def scroll_to_bottom(driver, scroll_pause=2):
    """Scroll to the bottom of the page to load all profile views."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Wait to load page
        time.sleep(scroll_pause)
        
        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def setup_driver():
    """Setup Edge driver with optimized options to suppress errors."""
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

def run_profile_request_automation(task_id: str):
    """Run the LinkedIn profile request automation."""
    try:
        profile_tasks_store[task_id] = {
            "status": "running",
            "message": "Starting automation...",
            "successful_connections": 0,
            "failed_connections": 0
        }
        
        # Close existing Edge processes
        try:
            subprocess.run(["taskkill", "/F", "/IM", "msedge.exe", "/T"], check=False, capture_output=True)
            print("✅ Microsoft Edge closed before script execution.")
        except subprocess.CalledProcessError:
            print("⚠️ No Edge process found or already closed.")
        
        # Use the optimized driver setup
        driver = setup_driver()
        
        # Navigate to profile views page
        url = 'https://www.linkedin.com/analytics/profile-views/'
        driver.get(url)
        time.sleep(10)  # Allow time for initial load
        
        profile_tasks_store[task_id]["message"] = "Scrolling through profile views..."
        print("⏳ Scrolling through the profile views list...")
        scroll_to_bottom(driver)
        
        profile_tasks_store[task_id]["message"] = "Looking for connect buttons..."
        print("🔍 Looking for 'Connect' buttons...")
        
        # Find all buttons with 'aria-label' ending in 'to connect'
        connect_buttons = driver.find_elements(By.XPATH, "//button[substring(@aria-label, string-length(@aria-label) - string-length('to connect') + 1) = 'to connect']")
        
        print(f"🔘 Found {len(connect_buttons)} connect button(s).")
        profile_tasks_store[task_id]["message"] = f"Found {len(connect_buttons)} connect buttons. Sending requests..."
        
        successful_connections = 0
        failed_connections = 0
        
        for i, btn in enumerate(connect_buttons):
            try:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                time.sleep(random.uniform(0.5, 1))  # Small pause for visibility
                btn.click()
                print(f"✅ Clicked connect button {i+1}/{len(connect_buttons)}.")
                successful_connections += 1
                time.sleep(random.uniform(2, 4))  # Delay between actions to avoid being flagged
            except Exception as e:
                print(f"⚠️ Could not click button {i+1}: {e}")
                failed_connections += 1
                continue
        
        # Update final status
        profile_tasks_store[task_id] = {
            "status": "completed",
            "message": f"Automation completed. {successful_connections} successful, {failed_connections} failed.",
            "successful_connections": successful_connections,
            "failed_connections": failed_connections
        }
        
        print(f"🎉 Automation completed! {successful_connections} successful connections, {failed_connections} failed.")
        
    except Exception as e:
        profile_tasks_store[task_id] = {
            "status": "failed",
            "message": f"Error: {str(e)}",
            "successful_connections": 0,
            "failed_connections": 0
        }
        print(f"❌ Automation failed: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

@router.post("/start", response_model=ProfileRequestResponse)
def start_profile_requests(background_tasks: BackgroundTasks):
    """Start LinkedIn profile request automation in the background."""
    task_id = str(uuid.uuid4())
    
    background_tasks.add_task(run_profile_request_automation, task_id)
    
    return {
        "task_id": task_id,
        "status": "started",
        "message": "Profile request automation started in background"
    }

@router.get("/status/{task_id}")
def get_profile_request_status(task_id: str):
    """Get the status of a profile request automation task."""
    if task_id not in profile_tasks_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return profile_tasks_store[task_id]

@router.get("/tasks")
def list_profile_request_tasks():
    """List all profile request automation tasks."""
    return {
        "tasks": profile_tasks_store
    }
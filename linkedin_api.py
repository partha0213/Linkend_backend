from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import os
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid
import tempfile
import random
from link_location import router as location_router

app = FastAPI(title="LinkedIn Automation API", version="1.0.0")

# Remove this line to avoid duplicate router inclusion:
# app.include_router(location_router)

# Store for tracking background tasks
tasks_store = {}

def human_like_delay(min_delay=1, max_delay=3):
    """Simulate a human-like random delay between actions."""
    time.sleep(random.uniform(min_delay, max_delay))

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

def run_linkedin_automation(task_id: str, excel_file_path: str):
    """Run the LinkedIn automation in a separate thread"""
    try:
        # Update task status
        tasks_store[task_id]["status"] = "running"
        
        # Read URLs from Excel file
        df = pd.read_excel(excel_file_path)
        urls = []
        
        for _, row in df.iterrows():
            url = row.get('URL', '').strip()
            if url:
                urls.append(url)
        
        if not urls:
            tasks_store[task_id].update({
                "status": "failed",
                "error": "No valid URLs found in Excel file"
            })
            return
        
        # Close existing Edge processes
        try:
            subprocess.run(["taskkill", "/F", "/IM", "msedge.exe", "/T"], check=True)
            print("✅ Microsoft Edge closed before script execution.")
        except subprocess.CalledProcessError:
            print("⚠️ No Edge process found or already closed.")
        
        # Setup Edge options
        # profile_path = r"C:\\Users\\TCARE\\AppData\\Local\\Microsoft\\Edge\\User Data"
        # Around line 58, change:
        # profile_path = r"C:/Users/Administrator/AppData/Local/Microsoft/Edge/User Data"
        # To:
        profile_path = "C:/Users/Administrator/AppData/Local/Microsoft/Edge/User Data"
        options = Options()
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--profile-directory=Profile 4")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        
        driver = webdriver.Edge(options=options)
        
        # Run the automation
        success_profiles = []
        failed_profiles = []
        
        for search_string in urls:
            print(f"Searching for: {search_string}")
            url = f'{search_string}'

            driver.get(url)  
            time.sleep(5)  

            try:
                name_element = driver.find_element(By.XPATH, "//div[@class='mt2 relative']//a[@aria-label]")
                name = name_element.get_attribute("aria-label")
            except:
                name = "Unknown"
                
            message = f"""Hi {name},
I came across your profile and thought it would be good to connect.
I look forward to being part of your network!
Many thanks,
saran"""

            try:
                connect_button = None
                try:
                    more_button = driver.find_element(By.XPATH, "//div[@class='ph5 pb5']//div[@class='artdeco-dropdown artdeco-dropdown--placement-bottom artdeco-dropdown--justification-left ember-view']//button")
                    ActionChains(driver).move_to_element(more_button).click().perform()
                    time.sleep(2)
                    print("Clicked 'More' button successfully.")
                    
                    connect_button = more_button.find_element(By.XPATH, "//div[@class='ph5 pb5']//span[text()='Connect']")
                    if connect_button is None:
                        print("Searching for 'Connect' button on the entire page within ph5 pb5 div.")
                        connect_button = driver.find_element(By.XPATH, "//div[@class='ph5 ']//span[text()='Connect']")

                    if connect_button is not None:
                        print('connect button found!!!')
                        print('clicking connect button!!')
                        ActionChains(driver).move_to_element(connect_button).click().perform()
                        print("Clicked 'Connect' button successfully.")
                        time.sleep(random.randint(2, 4))
                        
                        add_a_note_button = None
                        send_without_note_button = None
                        # try:
                            # First, try to find the regular "Add a note" button
                        modal_buttons = driver.execute_script("return document.querySelectorAll('.artdeco-modal__actionbar button')")
                        
                        for button in modal_buttons:
                            if button.text == 'Add a note':
                                add_a_note_button = button
                                break
                            elif button.text == 'Send without a note':
                                send_without_note_button = button
                                break
                            
                            # If "Add a note" button not found, try to find "Add a free note" button
                            # if add_a_note_button is None:
                            #     try:
                            #         # Try first XPath selector
                            #         add_a_note_button = driver.find_element(By.XPATH, "/html/body/div[4]/div/div/div[3]/button[1]")
                            #         print("Found 'Add a free note' button using first XPath")
                            #     except:
                            #         try:
                            #             # Try second XPath selector
                            #             add_a_note_button = driver.find_element(By.XPATH, "//*[@id='ember355']")
                            #             print("Found 'Add a free note' button using ID selector")
                            #         except:
                            #             try:
                            #                 # Try aria-label selector as fallback
                            #                 add_a_note_button = driver.find_element(By.XPATH, "//button[@aria-label='Add a free note']")
                            #                 print("Found 'Add a free note' button using aria-label")
                            #             except:
                            #                 print("No 'Add a note' or 'Add a free note' button found")
                            #                 add_a_note_button = None
                            
                            # # If no add note buttons found, try to find "Send without a note" button with XPath
                            # if add_a_note_button is None and send_without_note_button is None:
                            #     try:
                            #         # Try first XPath selector for "Send without a note"
                            #         send_without_note_button = driver.find_element(By.XPATH, "//*[@id='ember374']")
                            #         print("Found 'Send without a note' button using ID selector")
                            #     except:
                            #         try:
                            #             # Try second XPath selector
                            #             send_without_note_button = driver.find_element(By.XPATH, "/html/body/div[4]/div/div/div[3]/button[2]")
                            #             print("Found 'Send without a note' button using full XPath")
                            #         except:
                            #             try:
                            #                 # Try aria-label selector as fallback
                            #                 send_without_note_button = driver.find_element(By.XPATH, "//button[@aria-label='Send without a note']")
                            #                 print("Found 'Send without a note' button using aria-label")
                            #             except:
                            #                 print("No 'Send without a note' button found")
                            #                 send_without_note_button = None
                        # except:
                        #     failed_profiles.append({
                        #         'search_for': search_string,
                        #         'profile_found': name,
                        #         'profile_url': url,
                        #         'reason': 'Failed to open the modal'
                        #     })
                        #     continue
                        
                        # # Check if this is a premium account first
                        # premium_offer = driver.find_elements(By.XPATH, "//*[contains(text(),'Try Premium for')]")
                        
                        # # For non-premium accounts, prioritize "Send without a note"
                        # if not premium_offer and send_without_note_button is not None:
                        #     try:
                        #         print("Non-premium account detected, sending connection without note...")
                        #         send_without_note_button.click()
                                
                        #         # Wait for and check for success message
                        #         try:
                        #             # Wait for the success notification to appear
                        #             success_message = WebDriverWait(driver, 10).until(
                        #                 EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Your invitation to connect was sent')]"))
                        #             )
                        #             print("Success message detected: Connection invitation sent!")
                                    
                        #             # Optional: Close the success notification
                        #             try:
                        #                 close_button = driver.find_element(By.XPATH, "//button[@aria-label='Dismiss']")
                        #                 close_button.click()
                        #             except:
                        #                 pass  # Notification might auto-dismiss
                                    
                        #         except TimeoutException:
                        #             print("Success message not found within timeout, but connection likely sent")
                                
                        #         print("Connection sent without note successfully")
                        #         success_profiles.append({
                        #             'search_for': search_string,
                        #             'profile_found': name,
                        #             'profile_url': url,
                        #             'reason': "Connection sent without note (non-premium)"
                        #         })
                        #         time.sleep(random.randint(2, 4))
                        #         continue
                        #     except Exception as e:
                        #         print(f"Error while sending connection without note: {e}")
                        #         # Fall back to trying to add a note if send without note fails
                        #         pass
                        
                        # For premium accounts or when send without note fails, try adding a note
                        if add_a_note_button is not None:
                            try:
                                if premium_offer:
                                    print("Premium offer detected, trying 'Send without a note' instead...")
                                    driver.find_element(By.XPATH, "//button[@aria-label='Dismiss']").click()
                                    time.sleep(random.randint(1, 3))
                                    
                                    # Try to find and click "Send without a note" button as fallback
                                    send_without_note_fallback = None
                                    try:
                                        send_without_note_fallback = driver.find_element(By.XPATH, "//*[@id='ember326']")
                                        print("Found 'Send without a note' button using ID selector (fallback)")
                                    except:
                                        try:
                                            send_without_note_fallback = driver.find_element(By.XPATH, "/html/body/div[4]/div/div/div[3]/button[2]")
                                            print("Found 'Send without a note' button using full XPath (fallback)")
                                        except:
                                            try:
                                                send_without_note_fallback = driver.find_element(By.XPATH, "//button[@aria-label='Send without a note']")
                                                print("Found 'Send without a note' button using aria-label (fallback)")
                                            except:
                                                print("No 'Send without a note' button found after premium offer")
                                                send_without_note_fallback = None
                                    
                                    if send_without_note_fallback is not None:
                                        print("Clicking 'Send without a note' button (premium fallback)")
                                        send_without_note_fallback.click()
                                        print("Connection sent without note successfully (premium fallback)")
                                        success_profiles.append({
                                            'search_for': search_string,
                                            'profile_found': name,
                                            'profile_url': url,
                                            'reason': "Connection sent without note (premium fallback)"
                                        })
                                        time.sleep(random.randint(2, 4))
                                        continue
                                    else:
                                        failed_profiles.append({
                                            'search_for': search_string,
                                            'profile_found': name,
                                            'profile_url': url,
                                            'reason': 'Premium offer detected and no send without note button found'
                                        })
                                        continue
                                
                                # Only try to add a note for premium accounts or as fallback
                                print("Attempting to add a note...")
                                add_a_note_button.click()
                                time.sleep(random.randint(1, 5))

                                elem = driver.find_element(By.CLASS_NAME, 'connect-button-send-invite__custom-message')
                                for line in message.split('\n'):
                                    elem.send_keys(line.strip())
                                    time.sleep(random.randint(1, 2))
                                    ActionChains(driver).key_down(Keys.SHIFT).key_down(Keys.ENTER).key_up(Keys.SHIFT).key_up(Keys.ENTER).perform()

                                send_button = driver.find_element(By.XPATH, "//button[span[text()='Send']]")

                                if send_button.is_enabled():
                                    send_button.click()
                                    print("Note sent successfully")
                                    success_profiles.append({
                                        'search_for': search_string,
                                        'profile_found': name,
                                        'profile_url': url,
                                        'reason': "Note added"
                                    })
                                    time.sleep(random.randint(2, 4))
                                else:
                                    print(f"Send button disabled for: {search_string}")
                                    driver.find_element(By.XPATH, "//button[@aria-label='Dismiss']").click()
                                    failed_profiles.append({
                                        'search_for': search_string,
                                        'profile_found': name,
                                        'profile_url': url,
                                        'reason': 'Send button disabled while sending the note'
                                    })
                                    time.sleep(random.randint(1, 3))
                                    continue
                                    
                                time.sleep(random.randint(1, 5))
                            except Exception as e:
                                print(f"Error while adding note: {e}")
                                # Try "Send without a note" as fallback when note adding fails
                                try:
                                    send_without_note_fallback = None
                                    try:
                                        send_without_note_fallback = driver.find_element(By.XPATH, "//*[@id='ember326']")
                                    except:
                                        try:
                                            send_without_note_fallback = driver.find_element(By.XPATH, "/html/body/div[4]/div/div/div[3]/button[2]")
                                        except:
                                            try:
                                                send_without_note_fallback = driver.find_element(By.XPATH, "//button[@aria-label='Send without a note']")
                                            except:
                                                send_without_note_fallback = None
                                    
                                    if send_without_note_fallback is not None:
                                        print("Trying 'Send without a note' as fallback after note error")
                                        send_without_note_fallback.click()
                                        print("Connection sent without note successfully (error fallback)")
                                        success_profiles.append({
                                            'search_for': search_string,
                                            'profile_found': name,
                                            'profile_url': url,
                                            'reason': "Connection sent without note (error fallback)"
                                        })
                                        time.sleep(random.randint(2, 4))
                                    else:
                                        failed_profiles.append({
                                            'search_for': search_string,
                                            'profile_found': name,
                                            'profile_url': url,
                                            'reason': f'Error while adding note and no send without note fallback: {str(e)}'
                                        })
                                except Exception as fallback_error:
                                    failed_profiles.append({
                                        'search_for': search_string,
                                        'profile_found': name,
                                        'profile_url': url,
                                        'reason': f'Error while adding note: {str(e)}'
                                    })
                        elif send_without_note_button is not None:
                            print('send_without_note_button is not None')
                            try:
                                # premium_offer = driver.find_elements(By.XPATH, "//*[contains(text(),'Try Premium for')]")
                                # if premium_offer:
                                #     print("Premium offer detected, dismissing and continuing with send without note...")
                                #     driver.find_element(By.XPATH, "//button[@aria-label='Dismiss']").click()
                                #     time.sleep(random.randint(1, 3))
                                
                                # print("Clicking 'Send without a note' button")
                                send_without_note_button.click()
                                print("Connection sent without note successfully")
                                success_profiles.append({
                                    'search_for': search_string,
                                    'profile_found': name,
                                    'profile_url': url,
                                    'reason': "Connection sent without note"
                                })
                                time.sleep(random.randint(2, 4))
                            except Exception as e:
                                print(f"Error while sending connection without note: {e}")
                                failed_profiles.append({
                                    'search_for': search_string,
                                    'profile_found': name,
                                    'profile_url': url,
                                    'reason': f'Error while sending connection without note: {str(e)}'
                                })
                        else:
                            # Check for pending button
                            try:
                                pending_button = driver.find_element(By.XPATH, "//div[@class='ph5 pb5']//span[text()='Pending']")
                                if pending_button is not None:
                                    print('pending button found!!!')
                                    success_profiles.append({
                                        'search_for': search_string,
                                        'profile_found': name,
                                        'profile_url': url,
                                        'reason': 'Connection already pending'
                                    })
                            except:
                                failed_profiles.append({
                                    'search_for': search_string,
                                    'profile_found': name,
                                    'profile_url': url,
                                    'reason': 'No connect or pending button found'
                                })
                except Exception as e:
                    print(f"No 'Connect' button in dropdown: {e}")
                    failed_profiles.append({
                        'search_for': search_string,
                        'profile_found': name,
                        'profile_url': url,
                        'reason': f'No connect button found: {str(e)}'
                    })
            except Exception as e:
                print(f"An error occurred: {e}")
                failed_profiles.append({
                    'search_for': search_string,
                    'profile_found': name,
                    'profile_url': url,
                    'reason': f'General error: {str(e)}'
                })

            print(f'Profile processed for {search_string}')
            print(f'Message: {message}')
            
            # Add stalking behavior
            time.sleep(20)
            human_like_delay(1, 3)
        
        # Save results to Excel files
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        success_df = pd.DataFrame(success_profiles)
        failed_df = pd.DataFrame(failed_profiles)
        success_file = f"success_profiles_{timestamp}.xlsx"
        failed_file = f"failed_profiles_{timestamp}.xlsx"
        success_df.to_excel(success_file, index=False)
        failed_df.to_excel(failed_file, index=False)
        
        # Update task with results
        tasks_store[task_id].update({
            "status": "completed",
            "success_profiles": success_profiles,
            "failed_profiles": failed_profiles,
            "success_file": success_file,
            "failed_file": failed_file,
            "total_processed": len(urls),
            "successful_count": len(success_profiles),
            "failed_count": len(failed_profiles)
        })
        
        driver.quit()
        
        # Clean up temporary file
        if os.path.exists(excel_file_path):
            os.remove(excel_file_path)
        
    except Exception as e:
        tasks_store[task_id].update({
            "status": "failed",
            "error": str(e)
        })
        if 'driver' in locals():
            driver.quit()
        # Clean up temporary file
        if os.path.exists(excel_file_path):
            os.remove(excel_file_path)

@app.post("/upload-and-run")
async def upload_excel_and_run(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload Excel file and immediately start LinkedIn automation"""
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Validate Excel file has URL column
        try:
            df = pd.read_excel(temp_file_path)
            if 'URL' not in df.columns:
                os.remove(temp_file_path)
                raise HTTPException(status_code=400, detail="Excel file must contain a 'URL' column")
            
            url_count = len([url for url in df['URL'].dropna() if str(url).strip()])
            if url_count == 0:
                os.remove(temp_file_path)
                raise HTTPException(status_code=400, detail="No valid URLs found in the Excel file")
                
        except Exception as e:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(status_code=400, detail=f"Error reading Excel file: {str(e)}")
        
        # Initialize task in store
        tasks_store[task_id] = {
            "status": "pending",
            "created_at": time.time(),
            "filename": file.filename,
            "url_count": url_count
        }
        
        # Start background task
        background_tasks.add_task(run_linkedin_automation, task_id, temp_file_path)
        
        return {
            "task_id": task_id,
            "status": "started",
            "message": f"LinkedIn automation started for {url_count} URLs from {file.filename}",
            "filename": file.filename,
            "url_count": url_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a LinkedIn automation task"""
    
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = tasks_store[task_id]
    
    response = {
        "task_id": task_id,
        "status": task_data["status"],
        "created_at": task_data["created_at"],
        "filename": task_data.get("filename"),
        "url_count": task_data.get("url_count")
    }
    
    if task_data["status"] == "completed":
        response.update({
            "success_profiles": task_data.get("success_profiles", []),
            "failed_profiles": task_data.get("failed_profiles", []),
            "success_file": task_data.get("success_file"),
            "failed_file": task_data.get("failed_file"),
            "total_processed": task_data.get("total_processed", 0),
            "successful_count": task_data.get("successful_count", 0),
            "failed_count": task_data.get("failed_count", 0)
        })
    elif task_data["status"] == "failed":
        response["error"] = task_data.get("error")
    
    return response

@app.get("/tasks")
async def list_all_tasks():
    """List all automation tasks"""
    return {
        "tasks": [
            {
                "task_id": task_id,
                "status": task_data["status"],
                "created_at": task_data["created_at"],
                "filename": task_data.get("filename"),
                "url_count": task_data.get("url_count")
            }
            for task_id, task_data in tasks_store.items()
        ]
    }

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task from the store"""
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del tasks_store[task_id]
    return {"message": "Task deleted successfully"}

@app.get("/")
async def root():
    return {
        "message": "LinkedIn Automation API",
        "version": "1.0.0",
        "endpoints": {
            "POST /upload-and-run": "Upload Excel file and start automation immediately",
            "GET /status/{task_id}": "Check task status",
            "GET /tasks": "List all tasks",
            "DELETE /tasks/{task_id}": "Delete a task"
        },
        "usage": "Upload an Excel file with a 'URL' column containing LinkedIn profile URLs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)

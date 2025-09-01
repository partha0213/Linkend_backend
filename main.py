from fastapi import FastAPI
import uvicorn
from linkedin_api import app as linkedin_app
from link_location import router as location_router
from profile_request_api import router as profile_request_router

# Create the main FastAPI app
app = FastAPI(
    title="LinkedIn Automation Suite",
    description="Complete LinkedIn automation API with connection requests, location-based proposals, and profile request automation",
    version="1.0.0"
)

# Include routers in the correct order
app.include_router(location_router)
app.include_router(profile_request_router)

# Include routes from linkedin_api.py (excluding the location router)
for route in linkedin_app.routes:
    # Skip routes that are already included via location_router
    if not any(route.path.startswith(prefix) for prefix in ["/linkedin"]):
        app.routes.append(route)

# Add a health check endpoint
@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "message": "LinkedIn Automation Suite API is running",
        "available_endpoints": [
            "/docs - API documentation",
            "/linkedin/send-proposals - Send location-based proposals",
            "/upload-excel - Upload Excel file for connection automation",
            "/start-automation - Start LinkedIn connection automation",
            "/task-status/{task_id} - Check automation task status",
            "/profile-requests/start - Start profile request automation",
            "/profile-requests/status/{task_id} - Check profile request status",
            "/profile-requests/tasks - List all profile request tasks"
        ]
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
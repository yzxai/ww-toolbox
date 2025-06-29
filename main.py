from toolbox.utils.generic import check_privilege
from toolbox.utils.ocr import setup_ocr

check_privilege()
setup_ocr()

from toolbox.core.profile import EchoProfile, EntryCoef, DiscardScheduler, coef_data
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import toolbox.core.api as api
from toolbox.tasks import EchoFilter
import signal
import os

from toolbox.utils.logger import logger

# Global state to handle task cancellation
WORK_STATE = {
    "cancel_requested": False
}

def handle_sigint(sig, frame):
    """
    Handles the SIGINT signal (Ctrl+C) to forcefully exit the application.
    This is a workaround for hanging threads in the threadpool that are stuck
    in blocking C-extension calls from pywin32.
    """
    logger.warning("Ctrl+C detected. Forcing application exit.")
    os._exit(0)

signal.signal(signal.SIGINT, handle_sigint)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/stop_work")
async def stop_work_endpoint():
    """
    Sets a global flag to signal the current long-running task to stop.
    """
    logger.info("Received stop signal. Attempting to stop current work.")
    WORK_STATE["cancel_requested"] = True
    return {"message": "Stop signal received."}

@app.post("/api/apply_filter")
async def apply_filter_endpoint(filter_data: dict):
    # The 'name' field in EchoFilter corresponds to 'echo' in the frontend.
    filter_data['name'] = filter_data.pop('echo', '')
    
    # Ensure 'main_entry' is not '不指定主属性'
    if filter_data.get('main_entry') == '不指定主属性':
        filter_data['main_entry'] = ''
        
    echo_filter = EchoFilter(**filter_data)

    logger.info(f"Applying filter: {echo_filter}")
    success = await api.apply_filter(echo_filter)
    logger.info(f"Filter applied: {success}")
    return {"success": success}

@app.get("/api/scan_echo")
async def scan_echo_endpoint():
    profiles = await api.scan_echo()
    return profiles

@app.get("/api/get_entry_coef/{character_name}")
async def get_entry_coef(character_name: str):
    return coef_data.get(character_name, {})

@app.post("/api/get_brief_analysis")
async def get_brief_analysis_endpoint(data: dict):
    coef_data = data.get("coef", {})
    score_thres = data.get("score_thres", 0.0)

    coef = EntryCoef()
    for key, value in coef_data.items():
        if hasattr(coef, key):
            setattr(coef, key, value)
    
    profile = EchoProfile(level=0)
    
    result = await api.get_brief_analysis(profile, coef, score_thres)
    return result

@app.post("/api/get_full_analysis")
async def get_full_analysis_endpoint(data: dict):
    coef_data_dict = data.get("coef", {})
    score_thres = data.get("score_thres", 0.0)
    scheduler_thresholds = data.get("scheduler", [])
    profile_data = data.get("profile", None)

    coef = EntryCoef()
    for key, value in coef_data_dict.items():
        if hasattr(coef, key):
            setattr(coef, key, value)
    
    if profile_data:
        profile = EchoProfile().from_dict(profile_data)
    else:
        profile = EchoProfile(level=0)
    
    # Create DiscardScheduler from the list of thresholds
    scheduler = DiscardScheduler()
    if len(scheduler_thresholds) == 4:
        scheduler.level_5_9 = scheduler_thresholds[0]
        scheduler.level_10_14 = scheduler_thresholds[1]
        scheduler.level_15_19 = scheduler_thresholds[2]
        scheduler.level_20_24 = scheduler_thresholds[3]

    result = await api.get_analysis(profile, coef, score_thres, scheduler)

    if result.expected_total_wasted_exp == float('inf'):
        result.expected_total_wasted_exp = -1

    return result

@app.post("/api/upgrade_echo")
async def upgrade_echo_endpoint(profile_data: dict):
    # Reset cancellation flag at the start of a new task
    WORK_STATE["cancel_requested"] = False

    profile = EchoProfile(level=0)
    if profile_data and profile_data.get('level', 0) > 0:
        profile = EchoProfile().from_dict(profile_data)
    
    # --- IMPORTANT ---
    # The core api.upgrade_echo function must be modified to accept
    # the WORK_STATE and periodically check WORK_STATE["cancel_requested"].
    new_profile = await api.upgrade_echo(profile, WORK_STATE)
    return new_profile

@app.post("/api/get_echo_search_result")
async def get_echo_search_result_endpoint(data: dict):
    result = await api.get_echo_search_result(data)
    return {"message": "Echo search finished"}

if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)

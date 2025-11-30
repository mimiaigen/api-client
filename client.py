import requests
import base64
import argparse
import json
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Constants
API_URL = "https://mimiaigen--physical-data-agent-api.modal.run"
DEFAULT_PROMPT = """
Generate {TARGET} in different styles, make realistic variations,
no ground, no tool, not toy, only realistic {TARGET}
"""

# ANSI color codes
CYAN = '\033[96m'
BOLD = '\033[1m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
DIM = '\033[2m'
RESET = '\033[0m'

def get_api_key(args_key: Optional[str]) -> str:
    """
    Retrieve API key from arguments or environment variable.
    """
    api_key = args_key or os.getenv("MIMIAI_API_KEY")
    if not api_key:
        # If we are just reconnecting, we might not need it immediately, 
        # but for starting jobs it is required.
        # The main logic handles the requirement check.
        return ""
    return api_key

def start_job(api_key: str, args: argparse.Namespace) -> Optional[str]:
    """
    Start a new asset generation job.
    Returns the job_id if successful, None otherwise.
    """
    # Build payload
    payload = {
        "prompt": args.prompt,
        "target": args.target,
        "batch_size": args.batch_size,
    }
    
    # Encode image if provided
    if args.image and args.image.lower() != "none":
        image_path = Path(args.image)
        if image_path.exists():
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            payload["image_base64"] = image_b64
            print(f"Using image: {args.image}")
        else:
            print(f"Warning: Image not found at {image_path}, proceeding without image")
    else:
        print("No image provided, using text-only generation")
    
    # Set up authorization headers
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    endpoint = f"{API_URL.rstrip('/')}/v1/end2end-asset-gen"
    print(f"Sending request to {endpoint}...")
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        
        job_data = response.json()
        job_id = job_data.get("job_id")
        credits_remaining = job_data.get("credits_remaining", "unknown")
        batch_size = job_data.get("batch_size", 1)
        
        # Create a prominent box with the reconnection info
        reconnect_cmd = f"python client.py --job_id {job_id}"
        box_width = len(reconnect_cmd) + 4
        
        print(f"\n{GREEN}{'=' * box_width}")
        print(f"  Job started! ID: {CYAN}{BOLD}{job_id}{RESET}{GREEN}")
        print(f"  Credits remaining: {YELLOW}{BOLD}{credits_remaining}{RESET}{GREEN}")
        print(f"  ({batch_size} credit(s) will be deducted upon completion)")
        print(f"{'=' * box_width}{RESET}")
        print(f"\n{BOLD}To reconnect later, run:{RESET}")
        print(f"{CYAN}┌{'─' * (box_width - 2)}┐")
        print(f"│ {BOLD}{reconnect_cmd}{RESET}{CYAN} │")
        print(f"└{'─' * (box_width - 2)}┘{RESET}\n")
        
        return job_id
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to start job: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Server response: {e.response.text}")
        return None

def stream_logs(job_id: str):
    """
    Stream logs for a given job ID.
    """
    stream_url = f"{API_URL.rstrip('/')}/job/{job_id}/stream"
    print(f"Streaming logs from {stream_url}...\n")
    
    try:
        response = requests.get(stream_url, stream=True)
        response.raise_for_status()
        
        print("--- Real-time Progress ---")
        
        seen_stages = set()  # Track which stages we've already announced
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    status = data.get("status")
                    
                    if status == "progress":
                        message = data.get('message')
                        client_status = data.get("client_status")
                        
                        # Display stage completion messages with duration
                        if message and message.startswith("[STAGE_COMPLETE]"):
                            completion_msg = message.replace("[STAGE_COMPLETE] ", "")
                            print(f"   ✓ {completion_msg}")
                        
                        # Display stage start messages (only once per stage)
                        elif client_status and client_status not in seen_stages:
                            seen_stages.add(client_status)
                            print(f"[SERVER] {client_status}...")
                        
                        # Print other log messages dimmed to show progress
                        elif message:
                             print(f"{DIM}   {message}{RESET}")
                        
                    elif status == "success":
                        print("\n--- Generation Complete ---")
                        if "total_duration" in data:
                            print(f"Total Time: {data['total_duration']:.1f}s")
                            
                        result = data.get("result", {})
                        print(f"Message: {result.get('message', 'Success')}")
                        print("Download links:")
                        for link in result.get("download_links", []):
                            print(f"- {link}")
                            
                    elif status == "error":
                        print(f"\n[ERROR] {data.get('message')}")
                    else:
                        print(f"Unknown message: {data}")
                        
                except json.JSONDecodeError:
                    print(f"Raw output: {line}")
                    
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Server response: {e.response.text}")

def main():
    parser = argparse.ArgumentParser(description="MimiAI Asset Generation Client")
    
    # Authentication
    parser.add_argument("--api-key", help="Your API key (required for new jobs). Defaults to MIMIAI_API_KEY env var.")
    
    # Job Configuration
    parser.add_argument("--target", help="Target object name to replace {TARGET} in prompt (e.g., 'apple', 'tree')")
    parser.add_argument("--image", help="Path to input image (optional)")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Custom prompt for generation")
    parser.add_argument("--batch-size", type=int, default=1, help="Number of variations to generate (default: 1)")
    
    # Job Management
    parser.add_argument("--job_id", help="Reconnect to an existing job ID")
    
    args = parser.parse_args()
    
    api_key = get_api_key(args.api_key)
    
    # Logic Flow
    job_id = args.job_id
    
    if not job_id:
        if not api_key:
             parser.error("--api-key is required when starting a new job. Set MIMIAI_API_KEY env var or pass --api-key.")
        
        # Start new job
        job_id = start_job(api_key, args)
        if not job_id:
            return # Exit if job start failed

    # Stream logs (for both new and existing jobs)
    if job_id:
        if args.job_id:
            print(f"Reconnecting to existing job: {job_id}")
        stream_logs(job_id)

if __name__ == "__main__":
    main()

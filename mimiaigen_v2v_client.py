import requests
import argparse
import json
import sys
import os
import time
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

# Constants
API_URL = "https://mimiaigen--v2v-app-api.modal.run"
DEFAULT_PROMPT = """
Sunset. Yellow dirt. Farm like background.
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
        return ""
    return api_key

def start_job(api_key: str, args: argparse.Namespace) -> Optional[str]:
    """
    Start a new V2V generation job.
    Returns the job_id if successful, None otherwise.
    """
    # Validate input
    if not os.path.exists(args.input_media):
        print(f"{YELLOW}Error: Input media not found: {args.input_media}{RESET}")
        return None
        
    input_format = "frames_dir" if os.path.isdir(args.input_media) else "video"
    upload_file_path = args.input_media
    clean_upload = False
    
    if input_format == "frames_dir":
        print(f"Zipping frames directory: {args.input_media}...")
        temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_zip.close()
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(args.input_media):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, args.input_media)
                    zipf.write(file_path, arcname)
        
        upload_file_path = temp_zip.name
        clean_upload = True
    
    # Set up authorization headers
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    files = {
        'input_media': (os.path.basename(upload_file_path), open(upload_file_path, 'rb'), 
                        'application/zip' if input_format == 'frames_dir' else 'video/mp4')
    }
    
    config_data = {
        'prompt': args.prompt,
        'input_fps': args.input_fps,
        'output_fps': args.output_fps,
        'output_format': args.output_format,
        'output_size': args.output_size,
    }
    
    endpoint = f"{API_URL.rstrip('/')}/v1/video2video-gen"
    print(f"Sending request...")
    
    try:
        response = requests.post(endpoint, data=config_data, files=files, headers=headers)
        response.raise_for_status()
        
        job_data = response.json()
        job_id = job_data.get("job_id")
        credits_remaining = job_data.get("credits_remaining", "unknown")
        batch_size = job_data.get("batch_size", 1)
        
        # Create a prominent box with the reconnection info
        reconnect_cmd = f"python mimiaigen_v2v_client.py --job_id {job_id}"
        box_width = len(reconnect_cmd) + 4
        
        print(f"\n{GREEN}{'=' * box_width}")
        print(f"  Job started! ID: {CYAN}{BOLD}{job_id}{RESET}{GREEN}")
        print(f"  Credits remaining: {YELLOW}{BOLD}{credits_remaining}{RESET}{GREEN}")
        print(f"  (Cost will be exactly calculated per decoded video seconds upon completion)")
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
    finally:
        if clean_upload and os.path.exists(upload_file_path):
            os.remove(upload_file_path)

def stream_logs(job_id: str):
    """
    Stream logs for a given job ID.
    """
    stream_url = f"{API_URL.rstrip('/')}/job/{job_id}/stream"
    print(f"Streaming logs...\n")
    
    def show_reconnect_info():
        """Display reconnection command in a prominent box."""
        reconnect_cmd = f"python mimiaigen_v2v_client.py --job_id {job_id}"
        box_width = len(reconnect_cmd) + 4
        print(f"\n{BOLD}To reconnect and check status, run:{RESET}")
        print(f"{CYAN}┌{'─' * (box_width - 2)}┐")
        print(f"│ {BOLD}{reconnect_cmd}{RESET}{CYAN} │")
        print(f"└{'─' * (box_width - 2)}┘{RESET}\n")
    
    try:
        response = requests.get(stream_url, stream=True)
        response.raise_for_status()
        
        print("--- Real-time Progress ---")
        
        seen_stages = set()
        last_line_active = False
        buffer = b""
        
        for chunk in response.iter_content(chunk_size=1):
            if chunk:
                buffer += chunk
                if chunk == b"\n":
                    line = buffer.decode('utf-8').strip()
                    buffer = b""
                    if not line:
                        continue
                        
                    try:
                        data = json.loads(line)
                        status = data.get("status")
                        
                        if status == "progress":
                            message = data.get('message')
                            client_status = data.get("client_status")
                            
                            # Handle the main Category Header
                            if client_status and client_status not in seen_stages:
                                if last_line_active: 
                                    print("", flush=True)
                                seen_stages.add(client_status)
                                print(f"[{CYAN}{BOLD}{client_status}{RESET}]", flush=True)
                                last_line_active = False
                            
                            # Display stage completion messages with duration
                            if message and message.startswith("[STAGE_COMPLETE]"):
                                completion_msg = message.replace("[STAGE_COMPLETE] ", "")
                                if last_line_active:
                                    # Overwrite the "..." line
                                    print(f"\r   ✓ {completion_msg}", flush=True)
                                else:
                                    print(f"   ✓ {completion_msg}", flush=True)
                                last_line_active = False
                            
                            # Display stage start messages ending with "..."
                            elif message and message.endswith("..."):
                                if last_line_active: 
                                    print("", flush=True)
                                print(f"   {message}", end="", flush=True)
                                last_line_active = True
                            
                            # Print other log messages dimmed
                            elif message:
                                if last_line_active: 
                                    print("", flush=True)
                                print(f"{DIM}   {message}{RESET}", flush=True)
                                last_line_active = False
                                
                        elif status == "success":
                            if last_line_active: print("", flush=True)
                            print("\n--- Generation Complete ---", flush=True)
                            if "total_duration" in data:
                                print(f"Total Time: {data['total_duration']:.1f}s", flush=True)
                                
                            result = data.get("result", {})
                            print(f"Message: {result.get('message', 'Success')}", flush=True)
                            
                            download_links = result.get("download_links", [])
                            if download_links:
                                print("Download links:", flush=True)
                                for link in download_links:
                                    print(f"- {link}", flush=True)
                                    
                                # Automatically download and extract the first link
                                first_link = download_links[0]
                                print(f"\nDownloading artifacts from {first_link}...", flush=True)
                                try:
                                    dl_response = requests.get(first_link, stream=True)
                                    dl_response.raise_for_status()
                                    
                                    import time
                                    timestamp = int(time.time())
                                    output_zip = f"{job_id}_{timestamp}.zip"
                                    
                                    with open(output_zip, 'wb') as f:
                                        for dl_chunk in dl_response.iter_content(chunk_size=8192):
                                            f.write(dl_chunk)
                                            
                                    print(f"Extracting {output_zip}...", flush=True)
                                    output_dir = f"{job_id}_{timestamp}"
                                    os.makedirs(output_dir, exist_ok=True)
                                    
                                    try:
                                        with zipfile.ZipFile(output_zip, 'r') as zf:
                                            zf.extractall(output_dir)
                                        print(f"Extracted artifacts to {output_dir}/", flush=True)
                                        os.remove(output_zip)
                                    except zipfile.BadZipFile:
                                        print("Error: Received invalid ZIP file.", flush=True)
                                except Exception as dl_err:
                                    print(f"Error downloading artifacts: {dl_err}", flush=True)
                            else:
                                print("No download links found in the response.", flush=True)
                                break # End of job if success but no links? Or just break anyway
                            break

                        elif status == "error":
                            if last_line_active: print("", flush=True)
                            print(f"\n[ERROR] {data.get('message')}", flush=True)
                            show_reconnect_info()
                            break
                            
                    except json.JSONDecodeError:
                        # Heartbeat or malformed lines
                        pass
                    except Exception as e:
                        print(f"Error processing stream: {e}", flush=True)
                        break
                        
    except requests.exceptions.ChunkedEncodingError:
        print(f"\n{DIM}[Connection closed by server]{RESET}", flush=True)
        show_reconnect_info()
    except requests.exceptions.ConnectionError as e:
        error_str = str(e)
        if "Connection broken" in error_str or "InvalidChunkLength" in error_str:
            print(f"\n{DIM}[Stream ended - connection closed]{RESET}", flush=True)
            show_reconnect_info()
        else:
            print(f"\n{YELLOW}Connection issue: Unable to reach server.{RESET}", flush=True)
            show_reconnect_info()
    except Exception as e:
        print(f"\n{YELLOW}Request failed: {e}{RESET}", flush=True)
        show_reconnect_info()

def main():
    parser = argparse.ArgumentParser(description="MIMIAIGEN V2V Generation Client")
    
    # Authentication
    parser.add_argument("--api-key", help="Your API key (required for new jobs). Defaults to MIMIAI_API_KEY env var.")
    
    # -------------------------------------------------------------
    # Constraint Information
    # -------------------------------------------------------------
    # - max duration: 60 seconds
    # - max frames: 1500
    # - max output_size (long side): 1280 (Accepts: 720-1280)
    # - output_fps: 15 (Accepts: 15 ONLY)
    # -------------------------------------------------------------
    
    # Job Configuration
    parser.add_argument("--input-media", help="Path to input video (.mp4) or directory of frames")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Custom prompt for generation")
    parser.add_argument("--output-fps", type=float, default=15.0, help="Target output frame rate. Must be exactly 15.0.")
    parser.add_argument("--output-format", choices=["video", "frames", "both"], default="both", help="Requested output format")
    parser.add_argument("--output-size", type=int, default=1280, help="Output resolution constraint in pixels. Must be between 720 and 1280.")
    parser.add_argument("--input-fps", type=float, default=15.0, help="Input frame rate. Useful for frames directory input. Default is 15.0.")
    
    
    # Job Management
    parser.add_argument("--job_id", help="Reconnect to an existing job ID")
    
    args = parser.parse_args()
    
    api_key = get_api_key(args.api_key)
    
    # Logic Flow
    job_id = args.job_id
    
    if not job_id:
        if not api_key:
             parser.error("--api-key is required when starting a new job. Set MIMIAI_API_KEY env var or pass --api-key.")
        
        if not args.input_media:
             parser.error("--input-media is required when starting a new job.")

        # Start new job
        job_id = start_job(api_key, args)
        if not job_id:
            return

    # Stream logs
    if job_id:
        if args.job_id:
            print(f"Reconnecting to existing job: {job_id}")
        stream_logs(job_id)

if __name__ == "__main__":
    main()
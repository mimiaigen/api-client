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
        'w_da2': args.weight,
        'w_video_conditioning': args.strength,
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
        print("--- Real-time Progress ---")

        seen_stages = set()
        seen_events = set()
        last_line_active = False
        stream_connected_seen = False

        def process_payload(payload: str) -> bool:
            """Return True when stream should terminate."""
            nonlocal last_line_active, stream_connected_seen
            try:
                data = json.loads(payload)
                status = data.get("status")

                if status == "progress":
                    message = data.get("message")
                    client_status = data.get("client_status")

                    if message == "Connected to stream...":
                        if stream_connected_seen:
                            return False
                        stream_connected_seen = True
                    event_key = (
                        status,
                        message,
                        client_status,
                        data.get("timestamp"),
                        data.get("time"),
                    )
                    if event_key in seen_events:
                        return False
                    seen_events.add(event_key)

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
                        print(f"   ✓ {completion_msg}", flush=True)
                        last_line_active = False

                    # Display stage start messages ending with "..."
                    elif message and message.endswith("..."):
                        print(f"   {message}", flush=True)
                        last_line_active = False

                    # Print other log messages dimmed
                    elif message:
                        if last_line_active:
                            print("", flush=True)
                        print(f"{DIM}   {message}{RESET}", flush=True)
                        last_line_active = False

                elif status == "success":
                    event_key = (status, data.get("total_duration"), json.dumps(data.get("result", {}), sort_keys=True))
                    if event_key in seen_events:
                        return False
                    seen_events.add(event_key)
                    if last_line_active:
                        print("", flush=True)
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
                        output_zip = None
                        try:
                            dl_response = requests.get(first_link, stream=True)
                            dl_response.raise_for_status()

                            import time
                            timestamp = int(time.time())
                            timestamp_ms = int(time.time() * 1000)
                            output_zip = f"{job_id}_{timestamp_ms}.zip"

                            with open(output_zip, "wb") as f:
                                for dl_chunk in dl_response.iter_content(chunk_size=8192):
                                    if dl_chunk:
                                        f.write(dl_chunk)

                            print(f"Extracting {output_zip}...", flush=True)
                            output_dir = f"{job_id}_{timestamp}"
                            os.makedirs(output_dir, exist_ok=True)

                            with zipfile.ZipFile(output_zip, "r") as zf:
                                zf.extractall(output_dir)
                            print(f"Extracted artifacts to {output_dir}/", flush=True)
                        except zipfile.BadZipFile:
                            print("Error: Received invalid ZIP file.", flush=True)
                        except Exception as dl_err:
                            print(f"Error downloading artifacts: {dl_err}", flush=True)
                        finally:
                            if output_zip and os.path.exists(output_zip):
                                try:
                                    os.remove(output_zip)
                                except OSError as cleanup_err:
                                    print(f"{DIM}Warning: could not remove temp zip ({cleanup_err}){RESET}", flush=True)
                    else:
                        print("No download links found in the response.", flush=True)
                    return True

                elif status == "error":
                    event_key = (status, data.get("message"))
                    if event_key in seen_events:
                        return False
                    seen_events.add(event_key)
                    if last_line_active:
                        print("", flush=True)
                    print(f"\n[ERROR] {data.get('message')}", flush=True)
                    show_reconnect_info()
                    return True

            except json.JSONDecodeError:
                # Heartbeat or non-JSON event line
                pass
            except Exception as e:
                print(f"Error processing stream: {e}", flush=True)
                return True
            return False

        done = False
        reconnect_attempt = 0

        # Keep reconnecting so transient idle/hung sockets do not look like a frozen client.
        while not done:
            try:
                response = requests.get(
                    stream_url,
                    stream=True,
                    headers={
                        "Accept": "application/x-ndjson, text/event-stream",
                        "Cache-Control": "no-cache",
                        "Accept-Encoding": "identity",
                    },
                    # Force periodic reconnect when no bytes arrive for a while.
                    timeout=(10, 30),
                )
                response.raise_for_status()
                reconnect_attempt = 0

                # `chunk_size=1` reduces buffering so updates render in near real-time.
                sse_data_lines = []
                response.encoding = response.encoding or "utf-8"
                for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                    if line is None:
                        continue

                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")

                    # Blank line = end of SSE event.
                    if line == "":
                        if sse_data_lines:
                            payload = "\n".join(sse_data_lines).strip()
                            sse_data_lines = []
                            if payload and payload != "[DONE]" and process_payload(payload):
                                done = True
                                break
                        continue

                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue

                    if line.startswith("data:"):
                        sse_data_lines.append(line[5:].lstrip())
                        continue

                    # Fallback for NDJSON streams that are not SSE-framed.
                    if process_payload(line):
                        done = True
                        break

                if not done:
                    if last_line_active:
                        print("", flush=True)
                        last_line_active = False
                    print(f"{DIM}[Stream disconnected, reconnecting...]{RESET}", flush=True)
                    time.sleep(1)

            except requests.exceptions.ReadTimeout:
                if last_line_active:
                    print("", flush=True)
                    last_line_active = False
                print(f"{DIM}[No updates for 30s, reconnecting stream...]{RESET}", flush=True)
                continue
            except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError):
                reconnect_attempt += 1
                delay = min(2 * reconnect_attempt, 10)
                if last_line_active:
                    print("", flush=True)
                    last_line_active = False
                print(f"{DIM}[Connection interrupted, retrying in {delay}s...]{RESET}", flush=True)
                time.sleep(delay)
                continue
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
    parser.add_argument("--weight", type=float, default=1.0, help="Depth weight (Default 0.5, acceptable range 0.5-1.0)")
    parser.add_argument("--strength", type=float, default=1.5, help="Video conditioning strength (Default 1.0, acceptable range 1.0-1.5)")
    
    
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
import argparse
import json
import os
import tempfile
import time
import zipfile
from typing import Optional

import requests
from tqdm import tqdm

try:
    from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
except ImportError:
    MultipartEncoder = None
    MultipartEncoderMonitor = None

API_URL = "https://mimiaigen--v2v-app-api.modal.run"
DEFAULT_PROMPT = "Sunset. Yellow dirt. Farm like background."

# ANSI color codes
CYAN = '\033[96m'
BOLD = '\033[1m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
DIM = '\033[2m'
RESET = '\033[0m'


def get_api_key(args_key: Optional[str]) -> str:
    return args_key or os.getenv("MIMIAI_API_KEY", "")


def print_reconnect_box(job_id: str, heading: str) -> None:
    reconnect_cmd = f"python mimiaigen_v2v_client.py --job_id {job_id}"
    print(f"\n{BOLD}{heading}{RESET} {CYAN}{reconnect_cmd}{RESET}\n")


def zip_frames_directory(input_dir: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(input_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, input_dir)
                zipf.write(file_path, arcname)
    return path


def _request_headers(api_key: str, content_type: Optional[str] = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _config_from_args(args: argparse.Namespace) -> dict:
    return {
        'prompt': args.prompt,
        'input_fps': args.input_fps,
        'output_fps': args.output_fps,
        'output_format': args.output_format,
        'output_size': args.output_size,
        'w_da2': args.weight,
        'w_video_conditioning': args.strength,
    }


def _post_start_job(endpoint: str, api_key: str, config_data: dict, upload_path: str, mime_type: str) -> requests.Response:
    with open(upload_path, 'rb') as media_file:
        if MultipartEncoder and MultipartEncoderMonitor:
            fields = {
                "input_media": (os.path.basename(upload_path), media_file, mime_type),
                **{k: str(v) for k, v in config_data.items()},
            }
            encoder = MultipartEncoder(fields=fields)
            with tqdm(
                total=encoder.len,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="Uploading",
                dynamic_ncols=True,
            ) as pbar:
                last_bytes_read = 0

                def on_upload_progress(monitor):
                    nonlocal last_bytes_read
                    delta = monitor.bytes_read - last_bytes_read
                    if delta > 0:
                        pbar.update(delta)
                        last_bytes_read = monitor.bytes_read

                monitor = MultipartEncoderMonitor(encoder, on_upload_progress)
                return requests.post(
                    endpoint,
                    data=monitor,
                    headers=_request_headers(api_key, content_type=monitor.content_type),
                )

        print(f"{DIM}Upload progress unavailable (install requests-toolbelt for upload tqdm).{RESET}")
        files = {'input_media': (os.path.basename(upload_path), media_file, mime_type)}
        return requests.post(endpoint, data=config_data, files=files, headers=_request_headers(api_key))


def download_and_extract_artifacts(download_url: str, job_id: str) -> None:
    print(f"\nDownloading artifacts from {download_url}", flush=True)
    output_zip = None
    try:
        dl_response = requests.get(download_url, stream=True)
        dl_response.raise_for_status()

        timestamp = int(time.time())
        timestamp_ms = int(time.time() * 1000)
        output_zip = f"{job_id}_{timestamp_ms}.zip"

        total_bytes = int(dl_response.headers.get("Content-Length", "0") or 0)
        with open(output_zip, "wb") as f:
            with tqdm(
                total=total_bytes or None,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="Downloading",
                dynamic_ncols=True,
            ) as pbar:
                for dl_chunk in dl_response.iter_content(chunk_size=8192):
                    if dl_chunk:
                        f.write(dl_chunk)
                        pbar.update(len(dl_chunk))

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


def start_job(api_key: str, args: argparse.Namespace) -> Optional[str]:
    if not os.path.exists(args.input_media):
        print(f"{YELLOW}Error: Input media not found: {args.input_media}{RESET}")
        return None

    input_format = "frames_dir" if os.path.isdir(args.input_media) else "video"
    upload_file_path = args.input_media
    should_cleanup_upload = False
    if input_format == "frames_dir":
        print(f"Zipping frames directory: {args.input_media}...")
        upload_file_path = zip_frames_directory(args.input_media)
        should_cleanup_upload = True

    config_data = _config_from_args(args)
    endpoint = f"{API_URL.rstrip('/')}/v1/video2video-gen"
    print("Sending request...")

    try:
        mime_type = 'application/zip' if input_format == 'frames_dir' else 'video/mp4'
        response = _post_start_job(endpoint, api_key, config_data, upload_file_path, mime_type)
        response.raise_for_status()

        job_data = response.json()
        job_id = job_data.get("job_id")
        credits_remaining = job_data.get("credits_remaining", "unknown")

        print(f"\n{GREEN}Job started: {CYAN}{BOLD}{job_id}{RESET}")
        print(f"{GREEN}Credits remaining: {YELLOW}{BOLD}{credits_remaining}{RESET}")
        print_reconnect_box(job_id, "To reconnect later, run:")
        return job_id

    except requests.exceptions.RequestException as e:
        print(f"Failed to start job: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Server response: {e.response.text}")
        return None
    finally:
        if should_cleanup_upload and os.path.exists(upload_file_path):
            os.remove(upload_file_path)


def _iter_stream_payloads(response: requests.Response):
    sse_data_lines = []
    response.encoding = response.encoding or "utf-8"
    for line in response.iter_lines(chunk_size=1, decode_unicode=True):
        if line is None:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        if line == "":
            if sse_data_lines:
                payload = "\n".join(sse_data_lines).strip()
                sse_data_lines = []
                if payload:
                    yield payload
            continue
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            sse_data_lines.append(line[5:].lstrip())
            continue
        yield line


def stream_logs(job_id: str):
    stream_url = f"{API_URL.rstrip('/')}/job/{job_id}/stream"
    print("Streaming logs...\n")

    def show_reconnect_info():
        print_reconnect_box(job_id, "To reconnect and check status, run:")

    try:
        print("--- Real-time Progress ---")
        seen_stages = set()
        seen_events = set()
        stream_connected_seen = False

        def process_payload(payload: str) -> bool:
            nonlocal stream_connected_seen
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

                    if client_status and client_status not in seen_stages:
                        seen_stages.add(client_status)
                        print(f"[{CYAN}{BOLD}{client_status}{RESET}]", flush=True)

                    if message and message.startswith("[STAGE_COMPLETE]"):
                        completion_msg = message.replace("[STAGE_COMPLETE] ", "")
                        print(f"   ✓ {completion_msg}", flush=True)
                    elif message and message.endswith("..."):
                        print(f"   {message}", flush=True)
                    elif message:
                        print(f"{DIM}   {message}{RESET}", flush=True)

                elif status == "success":
                    result = data.get("result", {})
                    event_key = (status, data.get("total_duration"), json.dumps(result, sort_keys=True))
                    if event_key in seen_events:
                        return False
                    seen_events.add(event_key)
                    print("\n--- Generation Complete ---", flush=True)
                    if "total_duration" in data:
                        print(f"Total Time: {data['total_duration']:.1f}s", flush=True)
                    print(f"Message: {result.get('message', 'Success')}", flush=True)
                    download_links = result.get("download_links", [])
                    if download_links:
                        print("Download links:", flush=True)
                        for link in download_links:
                            print(f"- {link}", flush=True)
                        download_and_extract_artifacts(download_links[0], job_id)
                    else:
                        print("No download links found in the response.", flush=True)
                    return True
                elif status == "error":
                    event_key = (status, data.get("message"))
                    if event_key in seen_events:
                        return False
                    seen_events.add(event_key)
                    print(f"\n[ERROR] {data.get('message')}", flush=True)
                    show_reconnect_info()
                    return True
            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"Error processing stream: {e}", flush=True)
                return True
            return False

        done = False
        reconnect_attempt = 0

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
                for payload in _iter_stream_payloads(response):
                    if payload != "[DONE]" and process_payload(payload):
                        done = True
                        break
                if not done:
                    print(f"{DIM}[Stream disconnected, reconnecting...]{RESET}", flush=True)
                    time.sleep(1)
            except requests.exceptions.ReadTimeout:
                print(f"{DIM}[No updates for 30s, reconnecting stream...]{RESET}", flush=True)
                continue
            except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError):
                reconnect_attempt += 1
                delay = min(2 * reconnect_attempt, 10)
                print(f"{DIM}[Connection interrupted, retrying in {delay}s...]{RESET}", flush=True)
                time.sleep(delay)
                continue
    except Exception as e:
        print(f"\n{YELLOW}Request failed: {e}{RESET}", flush=True)
        show_reconnect_info()


def main():
    parser = argparse.ArgumentParser(description="MIMIAIGEN V2V Generation Client")
    parser.add_argument("--api-key", help="Your API key (required for new jobs). Defaults to MIMIAI_API_KEY env var.")
    parser.add_argument("--input-media", help="Path to input video (.mp4) or directory of frames")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Custom prompt for generation")
    parser.add_argument("--output-fps", type=float, default=15.0, help="Target output frame rate. Must be exactly 15.0.")
    parser.add_argument("--output-format", choices=["video", "frames", "both"], default="both", help="Requested output format")
    parser.add_argument("--output-size", type=int, default=1280, help="Output resolution constraint in pixels. Must be between 720 and 1280.")
    parser.add_argument("--input-fps", type=float, default=15.0, help="Input frame rate. Useful for frames directory input. Default is 15.0.")
    parser.add_argument("--weight", type=float, default=1.0, help="Depth weight (Default 0.5, acceptable range 0.5-1.0)")
    parser.add_argument("--strength", type=float, default=1.0, help="Video conditioning strength (Default 1.0, acceptable range 1.0-1.5)")
    parser.add_argument("--job_id", help="Reconnect to an existing job ID")
    args = parser.parse_args()
    api_key = get_api_key(args.api_key)
    job_id = args.job_id
    if not job_id:
        if not api_key:
            parser.error("--api-key is required when starting a new job. Set MIMIAI_API_KEY env var or pass --api-key.")
        if not args.input_media:
            parser.error("--input-media is required when starting a new job.")
        job_id = start_job(api_key, args)
        if not job_id:
            return

    if job_id:
        if args.job_id:
            print(f"Reconnecting to existing job: {job_id}")
        stream_logs(job_id)


if __name__ == "__main__":
    main()
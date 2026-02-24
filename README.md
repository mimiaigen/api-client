# api-client
This is the api client for MIMIAIGEN V2V (Video-to-Video) Generation.

![Inference Time Comparison](./inference_slow_to_fast.gif)

### Step.1 Create acccount

[mimiaigen.com](https://mimiaigen.com/api)


### Step.2 Create api key

Go to [api page](https://mimiaigen.com/api)

Choose your api-key name, press create and copy the api key.
Alternatively, you can set the `MIMIAI_API_KEY` environment variable.


### API Limitations & Constraints

Please note the following system constraints for V2V jobs:
- **Duration:** 3 - 60 seconds
- **Max frames:** 1500
- **Max output size (long side):** 1280 pixels (Accepts: 720-1280)
- **Aspect Ratio:** The original video/frame aspect ratio is preserved during generation. For best performance, use an aspect ratio close to `1280x720` (16:9). Extremely thin rectangular videos may cause degraded results.
- **Output Format:** You can request the output to be `video`, `frames`, or `both` (Default: `video`).
- **Output FPS:** 15 FPS (Accepts: 15 ONLY)
- **Input FPS (Frames ONLY):** When providing a directory of frames instead of a video file, it is **required** to provide the `--input-fps` to correctly calculate the duration and cost.


### Step.3 Calling the V2V client

We provide two convenience scripts for testing the API. Open them to specify your `--input-media`, `--prompt`, and your `--api-key`. 

**Option A: Using an input video file**
Edit `run_video.sh` with your file path and prompt, then run:
```bash
bash run_video.sh
```

**Option B: Using a directory of frames**
Edit `run_frames.sh` with your directory path and prompt, then run:
```bash
bash run_frames.sh
```
*Note: When using a directory of frames, the `--input-fps` argument is required within the script to calculate duration correctly.*


### Step.4 Reconnecting to a running job

If your connection drops or you want to check the status later, you can reconnect to an existing job using its ID without re-uploading the media:

```bash
python mimiaigen_v2v_client.py --job_id <your_job_id>
```

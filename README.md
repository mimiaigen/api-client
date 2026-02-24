# api-client
This is physical-data-agent api client for MIMIAIGEN V2V (Video-to-Video) Generation.


### Step.1 Create acccount

[mimiaigen.com](https://mimiaigen.com/api)


### Step.2 Create api key

Go to [api page](https://mimiaigen.com/api)

Choose your api-key name, press create and copy the api key.
Alternatively, you can set the `MIMIAI_API_KEY` environment variable.


### API Limitations & Constraints

Please note the following system constraints for V2V jobs:
- **Max duration:** 60 seconds
- **Max frames:** 1500
- **Max output size (long side):** 1280 pixels (Accepts: 720-1280)
- **Output FPS:** 15 FPS (Accepts: 15 ONLY)
- **Input FPS (Frames ONLY):** When providing a directory of frames instead of a video file, it is **required** to provide the `--input-fps` to correctly calculate the duration and cost.


### Step.3 Calling the V2V client

You can provide an input video (`.mp4`) or a directory containing frames.

```bash
# Using an input video file
python mimiaigen_v2v_client.py \
--input-media './examples/input_video.mp4' \
--prompt 'Sunset. Yellow dirt. Farm like background.' \
--api-key <your_api_key>

# Using a directory of frames with additional options
python mimiaigen_v2v_client.py \
--input-media './examples/frames_dir/' \
--prompt 'Make it look like a snowy winter day.' \
--output-size 1280 \
--input-fps 15.0 \
--output-fps 15.0 \
--output-format both \
--api-key <your_api_key>
```


### Step.4 Reconnecting to a running job

If your connection drops or you want to check the status later, you can reconnect to an existing job using its ID without re-uploading the media:

```bash
python mimiaigen_v2v_client.py --job_id <your_job_id>
```

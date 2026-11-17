# RunpodComfy — photo → short video (WAN 2.2)

Give it one photo and a sentence describing the motion. It returns a ~5 second MP4.
WAN 2.2 does the work on a rented RunPod GPU; you never have to open ComfyUI.

## Make a video (from this PC)

```
python pod.py start                                   # start the GPU (~1-3 min)
python make_video.py photo.jpg "slow camera push-in on the new deck, sunny afternoon"
python pod.py stop                                    # STOP BILLING when you're done
```

The video lands in `Videos\WAN`. Each run prints a **seed**. Add `--seed N` to repeat a result you liked.

| Option | What it does |
|---|---|
| `--quality full` | 20 steps instead of 4. Sometimes cleaner, about 5× slower |
| `--hd` | 720p instead of 480p, about 2–3× slower |
| `--seconds 3` | shorter clip (WAN tops out around 5 s) |

**Prompt tips:** describe *motion and camera*, not the picture. The photo already
shows what's in the scene. Good: "camera slowly orbits left", "steam rises from the
coffee", "leaves sway in a light breeze". Keep it to one or two motions.

## One-time / after big changes: install models on the pod

SSH in (`python pod.py ssh` prints the command), then:

```bash
curl -fsSL https://raw.githubusercontent.com/beardsservices-png/RunpodComfy/main/setup.sh | bash
```

It only downloads what's missing:

| File | Job | Size |
|---|---|---|
| `wan2.2_i2v_high_noise_14B_*` | pass 1: plans the motion | 14–29 GB |
| `wan2.2_i2v_low_noise_14B_*` | pass 2: fills in detail | 14–29 GB |
| `wan2.2_i2v_lightx2v_4steps_lora_*` (×2) | speed add-on: 4 steps instead of 20 | 1.2 GB each |
| `umt5_xxl_fp8_e4m3fn_scaled` | reads your prompt | 6.7 GB |
| `wan_2.1_vae` / `Wan2_1_VAE_bf16` | turns the result into frames | 0.25 GB |

## Why the old workflow looked bad

WAN 2.2 is **two models that take turns**: the high-noise model handles the first half of
the steps and the low-noise model finishes the rest. The original workflow
(`wan22_i2v_unrestricted.json`, now removed but still in git history) loaded only the
high-noise model for all 25 steps, so the output was blurry. `wan22_i2v_api.json` follows ComfyUI's official WAN 2.2 template.

## Files

| File | |
|---|---|
| `make_video.py` | the photo → video tool (uses `wan22_i2v_api.json`) |
| `pod.py` | status / start / stop / ssh. Needs a RunPod API key in `~/.runpod/config.toml` |
| `setup.sh` | installs missing models on the pod |
| `wan22_i2v_api.json` | the workflow, in ComfyUI API format |

To click around in ComfyUI yourself, open ComfyUI's **Templates** and pick
**"Wan 2.2 14B Image to Video"**. That's the official version of the same workflow.

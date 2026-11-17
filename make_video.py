#!/usr/bin/env python3
"""Turn one photo into a short video with WAN 2.2 running on your RunPod pod.

    python make_video.py photo.jpg "the camera slowly pushes in on the new deck"

You never have to open ComfyUI. The script uploads the photo, runs the job,
and saves the MP4 to  Videos\\WAN  on this PC.

Options
  --seconds 5        clip length (WAN is trained for up to 5 s)
  --quality fast     fast = 4-step speed LoRA (about 1-2 min).  full = 20 steps (about 5x slower)
  --hd               720p instead of 480p (about 2-3x slower)
  --seed N           repeat an earlier result exactly (the seed is printed every run)
  --pod ID / --url   which pod to use (default: the one saved by pod.py start)
"""
import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "wan22_i2v_api.json"
POD_FILE = Path.home() / ".runpod" / "pod_id"
UA = {"User-Agent": "Mozilla/5.0 (make_video.py)"}
FPS = 16


# ---------------------------------------------------------------- HTTP helpers
def http(url, data=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(base, path, timeout=60):
    return json.loads(http(base + path, timeout=timeout))


def post_json(base, path, obj):
    body = json.dumps(obj).encode()
    try:
        return json.loads(http(base + path, body, {"Content-Type": "application/json"}))
    except urllib.error.HTTPError as e:
        sys.exit(f"\nComfyUI rejected the job (HTTP {e.code}):\n{e.read().decode(errors='replace')[:3000]}")


def upload_image(base, path):
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'.encode(),
        (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
         f"Content-Type: application/octet-stream\r\n\r\n").encode(),
        path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    res = json.loads(http(base + "/upload/image", b"".join(parts),
                          {"Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=300))
    return f"{res['subfolder']}/{res['name']}" if res.get("subfolder") else res["name"]


# ------------------------------------------------------------- model discovery
def combo_options(base, node, field):
    info = get_json(base, f"/object_info/{node}")[node]["input"]
    spec = info.get("required", {}).get(field) or info.get("optional", {}).get(field)
    if isinstance(spec[0], list):
        return spec[0]
    if spec[0] == "COMBO":
        return spec[1].get("options", [])
    return []


def pick(names, must, prefer=(), avoid=()):
    low = {n: n.lower().replace("-", "_") for n in names}
    hits = [n for n in names if all(m in low[n] for m in must) and not any(a in low[n] for a in avoid)]
    for p in prefer:
        for n in hits:
            if p in low[n]:
                return n
    return hits[0] if hits else None


def discover(base):
    unets = combo_options(base, "UNETLoader", "unet_name")
    loras = combo_options(base, "LoraLoaderModelOnly", "lora_name")
    vaes = combo_options(base, "VAELoader", "vae_name")
    clips = combo_options(base, "CLIPLoader", "clip_name")
    m = {
        "high": pick(unets, ["i2v", "high"], ["fp8_scaled", "fp8", "fp16"]),
        "low": pick(unets, ["i2v", "low"], ["fp8_scaled", "fp8", "fp16"]),
        "lora_high": pick(loras, ["i2v", "high"], ["lightx2v", "lightning"]) if any(
            k in n.lower() for n in loras for k in ("lightx2v", "lightning")) else None,
        "lora_low": pick(loras, ["i2v", "low"], ["lightx2v", "lightning"]) if any(
            k in n.lower() for n in loras for k in ("lightx2v", "lightning")) else None,
        "vae": pick(vaes, ["wan"], ["2.1", "2_1"], avoid=["2.2", "2_2"]),
        "clip": pick(clips, ["umt5"], ["fp8"]),
    }
    missing = [k for k in ("high", "low", "vae", "clip") if not m[k]]
    if missing:
        sys.exit("The pod is missing model files: " + ", ".join(missing) +
                 "\nRun setup.sh on the pod first (see README).")
    return m


# ------------------------------------------------------------------- the graph
def frame_size(image_path, hd):
    try:
        from PIL import Image, ImageOps
        with Image.open(image_path) as im:
            w, h = ImageOps.exif_transpose(im).size
    except Exception:
        w, h = 4, 5  # assume portrait if we cannot read it
    r = w / h
    if r > 1.15:
        return (1280, 720) if hd else (832, 480)
    if r < 0.87:
        return (720, 1280) if hd else (480, 832)
    return (960, 960) if hd else (640, 640)


def build_graph(models, image_name, prompt, width, height, frames, seed, quality):
    g = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    g["1"]["inputs"]["unet_name"] = models["high"]
    g["2"]["inputs"]["unet_name"] = models["low"]
    g["7"]["inputs"]["clip_name"] = models["clip"]
    g["10"]["inputs"]["vae_name"] = models["vae"]
    g["8"]["inputs"]["text"] = prompt
    g["11"]["inputs"]["image"] = image_name
    g["12"]["inputs"].update(width=width, height=height, length=frames)
    g["13"]["inputs"]["noise_seed"] = seed

    if quality == "fast" and models["lora_high"] and models["lora_low"]:
        g["3"]["inputs"]["lora_name"] = models["lora_high"]
        g["4"]["inputs"]["lora_name"] = models["lora_low"]
        steps, cfg, split = 4, 1.0, 2
    else:
        # Full quality: skip the speed LoRAs, use the official 20-step settings.
        g["5"]["inputs"]["model"] = ["1", 0]
        g["6"]["inputs"]["model"] = ["2", 0]
        del g["3"], g["4"]
        steps, cfg, split = 20, 3.5, 10
    for n in ("13", "14"):
        g[n]["inputs"].update(steps=steps, cfg=cfg)
    g["13"]["inputs"]["end_at_step"] = split
    g["14"]["inputs"]["start_at_step"] = split
    return g, steps


# ------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("prompt", help="describe the motion / camera move you want")
    ap.add_argument("--seconds", type=float, default=5)
    ap.add_argument("--quality", choices=["fast", "full"], default="fast")
    ap.add_argument("--hd", action="store_true")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--pod")
    ap.add_argument("--url")
    ap.add_argument("--out", type=Path, default=Path.home() / "Videos" / "WAN")
    a = ap.parse_args()

    if not a.image.is_file():
        sys.exit(f"Can't find the photo: {a.image}")
    pod = a.pod or (POD_FILE.read_text().strip() if POD_FILE.exists() else None)
    if not (a.url or pod):
        sys.exit("No pod given. Run  python pod.py start  first, or pass --pod ID.")
    base = (a.url or f"https://{pod}-8188.proxy.runpod.net").rstrip("/")

    try:
        stats = get_json(base, "/system_stats", timeout=20)
    except Exception as e:
        sys.exit(f"ComfyUI isn't answering at {base}\n({e})\nIs the pod running?  python pod.py status")
    gpu = (stats.get("devices") or [{}])[0].get("name", "?")
    print(f"Connected: ComfyUI {stats.get('system', {}).get('comfyui_version', '?')} on {gpu}")

    models = discover(base)
    if a.quality == "fast" and not models["lora_high"]:
        print("  (speed LoRA not installed on the pod - using full quality, this will be slower)")
    print(f"  models: {models['high']}  +  {models['low']}")

    w, h = frame_size(a.image, a.hd)
    frames = max(17, min(121, int(round(a.seconds * FPS)) // 4 * 4 + 1))
    seed = a.seed if a.seed is not None else random.randint(1, 2**48)

    print(f"Uploading {a.image.name} ...")
    img_name = upload_image(base, a.image)
    graph, steps = build_graph(models, img_name, a.prompt, w, h, frames, seed, a.quality)

    res = post_json(base, "/prompt", {"prompt": graph, "client_id": uuid.uuid4().hex})
    if res.get("node_errors"):
        sys.exit(f"ComfyUI found problems with the job:\n{json.dumps(res['node_errors'], indent=2)}")
    pid = res["prompt_id"]
    print(f"Queued: {w}x{h}, {frames} frames ({frames / FPS:.1f}s), {steps} steps, seed {seed}")

    t0 = time.time()
    while True:
        time.sleep(5)
        try:
            hist = get_json(base, f"/history/{pid}")
        except Exception:
            hist = {}  # proxy hiccup - keep waiting
        job = hist.get(pid)
        if job:
            status = job.get("status", {})
            if status.get("status_str") == "error":
                for kind, data in status.get("messages", []):
                    if kind == "execution_error":
                        sys.exit(f"\nFailed in {data.get('node_type')}: {data.get('exception_message')}")
                sys.exit("\nThe job failed - check the ComfyUI log on the pod.")
            if status.get("completed") or job.get("outputs"):
                break
        print(f"\r  working... {int(time.time() - t0)}s ", end="", flush=True)
    print(f"\r  done in {int(time.time() - t0)}s          ")

    files = [f for out in job["outputs"].values() for v in out.values() if isinstance(v, list)
             for f in v if isinstance(f, dict) and "filename" in f]
    if not files:
        sys.exit("Job finished but produced no video file.")
    a.out.mkdir(parents=True, exist_ok=True)
    for f in files:
        q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""),
                                    "type": f.get("type", "output")})
        dest = a.out / f"{a.image.stem}_{time.strftime('%Y%m%d_%H%M%S')}{Path(f['filename']).suffix}"
        dest.write_bytes(http(f"{base}/view?{q}", timeout=600))
        print(f"Saved: {dest}")


if __name__ == "__main__":
    main()

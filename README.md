# RunpodComfy — WAN 2.2 Image-to-Video

Turn a single image into a short video using the WAN 2.2 AI model running on a RunPod GPU.

---

## What's in this repo

| File | What it does |
|---|---|
| `wan22_i2v_unrestricted.json` | The ComfyUI workflow (14 nodes, ready to use) |
| `setup.sh` | Restores the workflow after a pod restart |

---

## Prerequisites

- A RunPod account with a pod running the **ComfyUI** template
- An SSH key added to RunPod (already done — key is at `~/.ssh/id_ed25519`)
- The WAN 2.2 models already on your network volume (already there)

---

## Every time your pod restarts

The workflow file is stored in `/tmp` which gets wiped on restart. Run this **one command** after each restart to restore everything:

### Step 1 — Connect via SSH

In your RunPod dashboard, click your pod → **Connect** → copy the SSH command. It looks like:

```
ssh abc123xyz-6441171a@ssh.runpod.io -i ~/.ssh/id_ed25519
```

Paste it into a terminal (PowerShell or Terminal on Mac/Linux).

### Step 2 — Run the setup script

Once connected, paste this:

```bash
curl -fsSL https://raw.githubusercontent.com/beardsservices-png/RunpodComfy/main/setup.sh | bash
```

It will:
- Pull the latest workflow from this GitHub repo
- Install it where ComfyUI can find it
- Confirm ComfyUI is running

You'll see output ending with **"Setup complete!"**

### Step 3 — Open ComfyUI

In RunPod dashboard: pod → **Connect** → **HTTP Service** → Port **8188**

---

## How to generate a video

1. **Open ComfyUI** (port 8188 proxy link from RunPod)

2. **Load the workflow**
   - Click **Workflows** (top menu) → **Browse**
   - Select `wan22_i2v_unrestricted`

3. **Upload your source image**
   - Find the **"Load Image (Upload Here)"** node (light blue box)
   - Click **Upload** and pick any image from your computer
   - Best results: portrait orientation, clear subject, minimal motion blur

4. **Write your prompt**
   - Find the **"Positive Prompt"** node (the text box that's empty)
   - Describe the motion you want, e.g.:
     - *"a woman slowly turns her head and smiles"*
     - *"leaves gently swaying in the breeze"*
     - *"camera slowly zooms in"*

5. **Queue it**
   - Click the orange **Queue** button (top right)
   - Wait **2–5 minutes** — the L40s GPU is fast but the model is large
   - Progress bar appears at the top of the screen

6. **Download your video**
   - When done, a video preview appears in the bottom-right output node
   - Right-click the video → Save

---

## Workflow settings (what everything means)

You generally only need to touch the **Positive Prompt** and **Load Image** nodes. But here's what the others do:

| Node | Setting | Default | What it does |
|---|---|---|---|
| KSampler | `steps` | 25 | More steps = better quality but slower. Range: 15–40 |
| KSampler | `cfg` | 5.5 | How strictly it follows your prompt. Higher = more literal |
| KSampler | `seed` | 421337 | Change this number for different variations |
| WanImageToVideo | `length` | 33 | Number of frames (~2 sec at 16fps). Max ~81 |
| WanImageToVideo | `width/height` | 480×832 | Output resolution (portrait). Swap for landscape |
| CreateVideo | `fps` | 16 | Frames per second. 16 looks natural for AI video |

---

## Storage situation

Your network volume (`/workspace`) is full — all 75GB is used by the AI models. This means:

- **Workflow file**: Stored in `/tmp` via a symlink (that's why setup.sh is needed after restarts)
- **Generated videos**: ComfyUI saves them to `/workspace/ComfyUI/output/` — this **may fail** if the quota blocks it

**Fix**: In RunPod, go to your pod → **Edit** → increase the **Network Volume** size (e.g. from 80GB to 100GB). This costs a small extra amount per hour but permanently solves the quota issue and means you won't need the setup script anymore.

---

## Models on your pod

These are already downloaded and ready:

| Model | Purpose | Size |
|---|---|---|
| `wan2.2_i2v_high_noise_14B_fp16.safetensors` | Main video generation model | ~54GB |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | Understands your text prompt | 19GB |
| `clip_vision_h.safetensors` | Understands your input image | 1.2GB |
| `Wan2_1_VAE_bf16.safetensors` | Converts model output to video | 244MB |

---

## Troubleshooting

**"Workflow not found" in ComfyUI browser**
→ Run the setup script again (see above)

**ComfyUI shows red error nodes**
→ The model filename in node 1 must match exactly what's in `/workspace/ComfyUI/models/unet/`. SSH in and run `ls /workspace/ComfyUI/models/unet/` to check.

**Video saves fail / disk quota errors**
→ Expand your network volume in RunPod (see Storage section above)

**ComfyUI not loading in browser**
→ SSH in and run: `curl -s http://localhost:8188/system_stats`
→ If no response, start it manually:
```bash
nohup python3 /ComfyUI/main.py --listen --enable-cors-header '*' --use-sage-attention --extra-model-paths-config /ComfyUI/extra_model_paths.yaml > /workspace/comfyui.log 2>&1 &
```

**Pod not responding to SSH**
→ The pod may have stopped. Go to RunPod dashboard and click **Start**.

---

## SSH quick reference

Your SSH key is at `C:\Users\bbria\.ssh\id_ed25519`

The SSH command format (get the exact one from RunPod dashboard each time):
```
ssh <pod-id>-<hash>@ssh.runpod.io -i ~/.ssh/id_ed25519
```

Note: RunPod requires `-tt` flag if you're piping commands:
```
echo "ls /workspace" | ssh -tt <pod-id>-<hash>@ssh.runpod.io -i ~/.ssh/id_ed25519
```

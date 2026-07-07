#!/bin/bash
# RunpodComfy — Post-restart setup script
# Run this on the pod every time it restarts:
#   curl -fsSL https://raw.githubusercontent.com/beardsservices-png/RunpodComfy/main/setup.sh | bash

set -e

REPO_URL="https://github.com/beardsservices-png/RunpodComfy.git"
REPO_DIR="/tmp/RunpodComfy"
WORKFLOW="wan22_i2v_unrestricted.json"
WORKFLOWS_DIR="/workspace/ComfyUI/user/default/workflows"

echo ""
echo "================================================"
echo "  RunpodComfy Setup"
echo "================================================"
echo ""

# Step 1: Pull workflow files from GitHub
echo "[1/3] Fetching workflow from GitHub..."
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull --quiet
    echo "      Updated from GitHub."
else
    git clone --quiet "$REPO_URL" "$REPO_DIR"
    echo "      Cloned from GitHub."
fi

# Step 2: Copy workflow directly to /workspace (persistent across restarts)
echo "[2/3] Installing workflow..."
mkdir -p "$WORKFLOWS_DIR"
rm -f "$WORKFLOWS_DIR/$WORKFLOW"
cp "$REPO_DIR/$WORKFLOW" "$WORKFLOWS_DIR/$WORKFLOW"
# Verify it's readable and correct
python3 -c "
import json
with open('$WORKFLOWS_DIR/$WORKFLOW') as f:
    d = json.load(f)
print(f'      Installed: $WORKFLOW ({len(d)} nodes) — saved to /workspace (persistent)')
"

# Step 3: Check ComfyUI is running
echo "[3/3] Checking ComfyUI..."
COMFY_UP=false
for i in $(seq 1 12); do
    STATS=$(curl -sf http://localhost:8188/system_stats 2>/dev/null || true)
    if [ -n "$STATS" ]; then
        VER=$(echo "$STATS" | python3 -c "import json,sys; print(json.load(sys.stdin)['comfyui_version'])" 2>/dev/null || echo "unknown")
        echo "      ComfyUI v$VER is running."
        COMFY_UP=true
        break
    fi
    echo "      Waiting for ComfyUI... ($i/12)"
    sleep 5
done

if [ "$COMFY_UP" = false ]; then
    echo ""
    echo "  WARNING: ComfyUI is not responding. Starting it now..."
    nohup python3 /ComfyUI/main.py \
        --listen \
        --enable-cors-header '*' \
        --use-sage-attention \
        --extra-model-paths-config /ComfyUI/extra_model_paths.yaml \
        > /workspace/comfyui_startup.log 2>&1 &
    echo "  ComfyUI starting in background. Check /workspace/comfyui_startup.log"
    echo "  Wait ~30 seconds then refresh your browser."
fi

echo ""
echo "================================================"
echo "  Setup complete!"
echo ""
echo "  1. Go to RunPod dashboard"
echo "  2. Click your pod > Connect > HTTP Service (port 8188)"
echo "  3. In ComfyUI: Workflows > Browse > wan22_i2v_unrestricted"
echo "  4. Upload your image, type a prompt, click Queue"
echo "================================================"
echo ""

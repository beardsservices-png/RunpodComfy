#!/bin/bash
# RunpodComfy - make sure the pod has every model WAN 2.2 image-to-video needs.
# Safe to run any number of times: it only downloads what is missing.
#   curl -fsSL https://raw.githubusercontent.com/beardsservices-png/RunpodComfy/main/setup.sh | bash

HF22=https://huggingface.co/Comfy-Org/Wan-2.2/resolve/main/split_files
HF21=https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files

echo "== RunpodComfy setup =="

# 1. Find the models folder ComfyUI is already using (where the WAN files live).
existing=$(find /workspace /ComfyUI -maxdepth 6 \( -name 'umt5_xxl*' -o -name 'wan2.2_i2v*' \) 2>/dev/null | head -1)
if [ -n "$existing" ]; then
    M=$(dirname "$(dirname "$existing")")
else
    for d in /workspace/ComfyUI/models /workspace/models /ComfyUI/models; do
        [ -d "$d" ] && M=$d && break
    done
fi
[ -z "$M" ] && { echo "Could not find a ComfyUI models folder."; exit 1; }
echo "Models folder: $M"

# Diffusion models may live in models/unet (old name) or models/diffusion_models.
f=$(find "$M" -maxdepth 2 -name 'wan2.2_i2v_*_noise_14B*' ! -name '*.part' 2>/dev/null | head -1)
if [ -n "$f" ]; then DM=$(dirname "$f"); else DM="$M/diffusion_models"; fi
f=$(find "$M" -maxdepth 2 -name 'umt5_xxl*' 2>/dev/null | head -1)
if [ -n "$f" ]; then TE=$(dirname "$f"); else TE="$M/text_encoders"; fi
mkdir -p "$DM" "$TE" "$M/vae" "$M/loras"

have() { find "$M" -maxdepth 2 -iname "$1" ! -name '*.part' 2>/dev/null | grep -q .; }

get() {  # get <folder> <filename> <url> <size_gb>
    local dir=$1 name=$2 url=$3 gb=$4
    local free_gb=$(df -BG --output=avail "$dir" | tail -1 | tr -dc 0-9)
    if [ "$free_gb" -lt $((gb + 2)) ]; then
        echo "  NOT ENOUGH SPACE for $name (${gb} GB needed, ${free_gb} GB free) - grow the volume in RunPod."
        return 1
    fi
    echo "  downloading $name (${gb} GB)..."
    if curl -sS -L --fail -C - -o "$dir/$name.part" "$url"; then
        mv "$dir/$name.part" "$dir/$name"
        echo "  done: $name"
    else
        echo "  FAILED: $name (run setup again to resume)"
        return 1
    fi
}

echo "Checking models..."
have 'wan2.2_i2v_high_noise*' || get "$DM" wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors \
    "$HF22/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" 15
have 'wan2.2_i2v_low_noise*' || get "$DM" wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors \
    "$HF22/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" 15
have 'umt5_xxl*' || get "$TE" umt5_xxl_fp8_e4m3fn_scaled.safetensors \
    "$HF21/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" 7
have 'wan_2.1_vae*' || have 'Wan2_1_VAE*' || get "$M/vae" wan_2.1_vae.safetensors \
    "$HF22/vae/wan_2.1_vae.safetensors" 1
have 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise*' || get "$M/loras" \
    wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors \
    "$HF22/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" 2
have 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise*' || get "$M/loras" \
    wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors \
    "$HF22/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors" 2

echo "On the volume now:"
find "$M" -maxdepth 2 \( -iname 'wan*' -o -iname 'umt5*' \) -name '*.safetensors' -printf '%f %s\n' 2>/dev/null \
    | awk '{ printf "  %-62s %6.1f GB\n", $1, $2/1e9 }'
df -h "$M" | tail -1 | awk '{print "Space left: " $4}'

# 2. Make sure ComfyUI is running.
if curl -sf http://localhost:8188/system_stats >/dev/null; then
    echo "ComfyUI is running."
else
    echo "ComfyUI is not answering on port 8188 - restart the pod from the RunPod dashboard."
fi
echo "== Setup complete =="

#!/usr/bin/env python3
"""Check, start and stop your RunPod pod from this PC.

    python pod.py status          balance, pods, storage
    python pod.py start [POD_ID]  start the pod and wait until ComfyUI is ready
    python pod.py stop  [POD_ID]  stop it (stops GPU billing; files on the volume are kept)
    python pod.py ssh   [POD_ID]  print the SSH command

Needs a RunPod API key, read from the RUNPOD_API_KEY environment variable or
from ~/.runpod/config.toml  (a line like:  apikey = "rpa_...").
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CFG = Path.home() / ".runpod" / "config.toml"
POD_FILE = Path.home() / ".runpod" / "pod_id"
UA = {"User-Agent": "Mozilla/5.0 (pod.py)", "Content-Type": "application/json"}


def api_key():
    k = os.environ.get("RUNPOD_API_KEY")
    if not k and CFG.exists():
        m = re.search(r'apikey\s*=\s*"([^"]+)"', CFG.read_text(), re.I)
        k = m and m.group(1)
    if not k:
        sys.exit(f"No RunPod API key. Put it in {CFG} as:  apikey = \"rpa_...\"")
    return k


def gql(query):
    req = urllib.request.Request(f"https://api.runpod.io/graphql?api_key={api_key()}",
                                 json.dumps({"query": query}).encode(), UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"RunPod API error {e.code}: {e.read().decode(errors='replace')[:1000]}")
    if res.get("errors"):
        sys.exit("RunPod API error: " + "; ".join(e.get("message", "?") for e in res["errors"]))
    return res["data"]


def pods():
    return gql("""query { myself { pods {
        id name desiredStatus podHostId costPerHr gpuCount
        machine { gpuDisplayName } networkVolume { id name size }
        runtime { uptimeInSeconds } } } }""")["myself"]["pods"]


def pick_pod(arg):
    if arg:
        return arg
    if POD_FILE.exists():
        return POD_FILE.read_text().strip()
    ps = pods()
    if len(ps) == 1:
        return ps[0]["id"]
    sys.exit("Which pod? Run  python pod.py status  and pass the ID.")


def comfy_up(pod_id):
    try:
        req = urllib.request.Request(f"https://{pod_id}-8188.proxy.runpod.net/system_stats", headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


def status():
    me = gql("query { myself { clientBalance currentSpendPerHr "
             "networkVolumes { id name size dataCenterId } } }")["myself"]
    print(f"Balance: ${me['clientBalance']:.2f}    spending now: ${me.get('currentSpendPerHr') or 0:.2f}/hr")
    vols = me.get("networkVolumes") or []
    print(f"Network volumes: {len(vols)}")
    for v in vols:
        print(f"  {v['id']}  {v['name']}  {v['size']} GB  ({v['dataCenterId']})")
    ps = pods()
    print(f"Pods: {len(ps)}")
    for p in ps:
        gpu = (p.get("machine") or {}).get("gpuDisplayName") or "?"
        up = "RUNNING" if p.get("runtime") else p["desiredStatus"]
        print(f"  {p['id']}  {p['name']}  {gpu}  ${p.get('costPerHr') or 0}/hr  {up}")


def start(pod_id):
    gql(f'mutation {{ podResume(input: {{ podId: "{pod_id}", gpuCount: 1 }}) {{ id desiredStatus }} }}')
    POD_FILE.parent.mkdir(exist_ok=True)
    POD_FILE.write_text(pod_id)
    print(f"Starting {pod_id} - waiting for ComfyUI (usually 1-3 minutes)...")
    t0 = time.time()
    while time.time() - t0 < 900:
        if comfy_up(pod_id):
            print(f"Ready after {int(time.time() - t0)}s:  https://{pod_id}-8188.proxy.runpod.net")
            return
        time.sleep(10)
    sys.exit("Pod started but ComfyUI hasn't answered after 15 min - check the RunPod dashboard logs.")


def stop(pod_id):
    gql(f'mutation {{ podStop(input: {{ podId: "{pod_id}" }}) {{ id desiredStatus }} }}')
    print(f"Stopped {pod_id}. GPU billing has stopped; files on the volume are kept.")


def ssh(pod_id):
    host = next((p["podHostId"] for p in pods() if p["id"] == pod_id), None)
    if not host:
        sys.exit(f"Pod {pod_id} not found.")
    print(f"ssh -tt {host}@ssh.runpod.io -i ~/.ssh/id_ed25519")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == "status":
        status()
    elif cmd in ("start", "stop", "ssh"):
        {"start": start, "stop": stop, "ssh": ssh}[cmd](pick_pod(arg))
    else:
        sys.exit(__doc__)

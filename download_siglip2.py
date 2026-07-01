"""Download SigLIP2 model files from hf-mirror.com to local cache."""
import os
import requests
from tqdm import tqdm

MIRROR = "https://hf-mirror.com"
REPO = "google/siglip2-base-patch16-224"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub", "models--google--siglip2-base-patch16-224")

FILES = [
    "config.json",
    "model.safetensors",
    "preprocessor_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
]

def download_file(filename):
    url = f"{MIRROR}/{REPO}/resolve/main/{filename}"
    snap_dir = os.path.join(CACHE_DIR, "snapshots", "main")
    os.makedirs(snap_dir, exist_ok=True)
    dest = os.path.join(snap_dir, filename)

    if os.path.exists(dest):
        print(f"  [skip] {filename} already exists")
        return

    print(f"  Downloading {filename}...")
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))

    with open(dest, "wb") as f:
        with tqdm(total=total, unit="B", unit_scale=True, desc=filename) as pbar:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(chunk)
                pbar.update(len(chunk))

def write_refs():
    refs_dir = os.path.join(CACHE_DIR, "refs")
    os.makedirs(refs_dir, exist_ok=True)
    with open(os.path.join(refs_dir, "main"), "w") as f:
        f.write("main")

def main():
    print(f"Downloading {REPO} to {CACHE_DIR}")
    write_refs()
    for fn in FILES:
        download_file(fn)
    print("Done!")

if __name__ == "__main__":
    main()

"""Gemini API client + image2 generation client for pose and action analysis."""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Gemini ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

MODEL_FLASH = "gemini-3.5-flash"  # 最新 Flash，强推理多模态
MODEL_FLASH_LITE = "gemini-3.1-flash-lite-preview"  # 轻量，低延迟

# ── Gateway (OpenAI-compatible) ────────────────────────────────────────────
GATEWAY_API_KEY = os.getenv("API_KEY")
GATEWAY_BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
GATEWAY_TIMEOUT_MS = int(os.getenv("API_TIMEOUT_MS", "600000"))

# ── image2 ──────────────────────────────────────────────────────────────────
IMAGE2_HOST          = os.environ.get("IMAGE2_HOST",  "http://image2.reltydynamic.com:8787")
IMAGE2_TOKEN         = os.environ.get("IMAGE2_TOKEN", "78f0d77eda6b4bbb8927b513d37f51e61ca8e953780a7431")
IMAGE2_OUTDIR        = os.environ.get("IMAGE2_OUTDIR", os.path.join(os.path.expanduser("~"), "Desktop", "image2-output"))
IMAGE2_POLL_INTERVAL = int(os.environ.get("IMAGE2_POLL_INTERVAL", "5"))

# 模型映射表（-m 参数的合法值）
MODEL_GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"
MODEL_GEMINI_3_1_FLASH_LITE_PREVIEW = "gemini-3.1-flash-lite-preview"
MODEL_CLAUDE_SONNET_4_5 = "claude-sonnet-4-5"

MODELS = {
    "flash": MODEL_FLASH,  # Gemini 3.5 Flash — 强推理、多模态
    "lite": MODEL_FLASH_LITE,  # Gemini 3.1 Flash Lite Preview — 轻量低延迟
    "gemini-3-flash-preview": MODEL_GEMINI_3_FLASH_PREVIEW,
    "gemini-3.1-flash-lite-preview": MODEL_GEMINI_3_1_FLASH_LITE_PREVIEW,
    "claude-sonnet-4-5": MODEL_CLAUDE_SONNET_4_5,
    "image2": None,  # image2 生图服务
}

GATEWAY_MODELS = {
    MODEL_GEMINI_3_FLASH_PREVIEW,
    MODEL_GEMINI_3_1_FLASH_LITE_PREVIEW,
    MODEL_CLAUDE_SONNET_4_5,
}


# ═══════════════════════════════════════════════════════════════════════════
# Gemini helpers
# ═══════════════════════════════════════════════════════════════════════════

def _gemini_headers() -> dict:
    return {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }


def _gateway_headers() -> dict:
    return {
        "Authorization": f"Bearer {GATEWAY_API_KEY}",
        "Content-Type": "application/json",
    }


def _gateway_timeout_seconds() -> float:
    return max(GATEWAY_TIMEOUT_MS / 1000.0, 1.0)


def generate_content(prompt: str, model: str = MODEL_FLASH) -> dict:
    """Send a text prompt to Gemini and return the parsed response."""
    url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    }
    resp = requests.post(url, headers=_gemini_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def generate_content_with_image(
    prompt: str,
    image_path: str | Path,
    model: str = MODEL_FLASH,
) -> dict:
    """Send a prompt + image to Gemini for vision-based analysis."""
    image_path = Path(image_path)
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(image_path.suffix.lower(), "image/jpeg")

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                ],
            }
        ]
    }
    resp = requests.post(url, headers=_gemini_headers(), json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def gateway_generate_content(prompt: str, model: str) -> dict:
    """Send a text prompt via OpenAI-compatible gateway and return the response."""
    if not GATEWAY_BASE_URL or not GATEWAY_API_KEY:
        raise RuntimeError("Missing BASE_URL or API_KEY for gateway models")

    url = f"{GATEWAY_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ],
    }
    resp = requests.post(url, headers=_gateway_headers(), json=payload, timeout=_gateway_timeout_seconds())
    resp.raise_for_status()
    return resp.json()


def gateway_generate_content_with_image(
    prompt: str,
    image_path: str | Path,
    model: str,
) -> dict:
    """Send a prompt + image via OpenAI-compatible gateway and return the response."""
    if not GATEWAY_BASE_URL or not GATEWAY_API_KEY:
        raise RuntimeError("Missing BASE_URL or API_KEY for gateway models")

    image_path = Path(image_path)
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(image_path.suffix.lower(), "image/jpeg")

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    url = f"{GATEWAY_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}"
                        },
                    },
                ],
            }
        ],
    }
    resp = requests.post(url, headers=_gateway_headers(), json=payload, timeout=_gateway_timeout_seconds())
    resp.raise_for_status()
    return resp.json()


def extract_text(response: dict) -> str:
    """Pull the text content out of a Gemini response."""
    try:
        return response["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return ""


def extract_gateway_text(response: dict) -> str:
    """Pull the text content out of an OpenAI-compatible response."""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""


def _is_gateway_model(model: str) -> bool:
    return model in GATEWAY_MODELS


def analyze_pose_from_image(image_path: str | Path, model: str = MODEL_FLASH) -> dict:
    """Use Gemini vision to analyze exercise pose from an image frame."""
    prompt = (
        "You are a professional fitness coach and biomechanics expert. "
        "Analyze the exercise pose in this image and return a JSON object with:\n"
        "- exercise: the detected exercise name\n"
        "- key_joints: list of visible key joints and their positions (left/right, angle if estimable)\n"
        "- form_score: 1-10 rating of form quality\n"
        "- form_issues: list of form problems detected\n"
        "- suggestions: list of improvement tips\n"
        "Return only valid JSON, no markdown."
    )
    if _is_gateway_model(model):
        raw = gateway_generate_content_with_image(prompt, image_path, model=model)
        text = extract_gateway_text(raw)
    else:
        raw = generate_content_with_image(prompt, image_path, model=model)
        text = extract_text(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def analyze_exercise_description(description: str, model: str = MODEL_FLASH) -> dict:
    """Classify and analyze an exercise from a text description."""
    prompt = (
        "You are a fitness AI. Given the exercise description below, return a JSON object with:\n"
        "- exercise: canonical exercise name\n"
        "- muscle_groups: primary and secondary muscles\n"
        "- difficulty: beginner/intermediate/advanced\n"
        "- tips: list of coaching cues\n"
        "Description: " + description + "\n"
        "Return only valid JSON, no markdown."
    )
    if _is_gateway_model(model):
        raw = gateway_generate_content(prompt, model=model)
        text = extract_gateway_text(raw)
    else:
        raw = generate_content(prompt, model=model)
        text = extract_text(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


# ═══════════════════════════════════════════════════════════════════════════
# image2 helpers
# ═══════════════════════════════════════════════════════════════════════════

def _image2_session() -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {IMAGE2_TOKEN}"
    s.trust_env = False  # 禁用系统代理，对应 curl --noproxy '*'
    return s


def _image2_submit(session: requests.Session, prompt: str, images: list[str], n: int) -> str:
    print(">>> [1/3] 提交任务...")
    print(f"      prompt: {prompt}")
    if images:
        print(f"      参考图: {' '.join(images)}")

    data = {"prompt": prompt, "n": str(n)}
    files = [("images", (os.path.basename(p), open(p, "rb"))) for p in images]

    try:
        resp = session.post(f"{IMAGE2_HOST}/jobs", data=data, files=files or None)
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        print(f"错误: 提交任务失败 — {e}")
        sys.exit(1)
    finally:
        for _, (_, f) in files:
            f.close()

    print(f"      响应: {body}")
    job_id = body.get("job_id")
    if not job_id:
        print(f"错误: 无法解析 job_id, 原始响应: {body}")
        sys.exit(1)

    print(f"      job_id: {job_id}")
    return job_id


def _image2_poll(session: requests.Session, job_id: str, interval: int) -> dict:
    print(f">>> [2/3] 轮询状态 (每 {interval}s 一次)...")
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = session.get(f"{IMAGE2_HOST}/jobs/{job_id}")
            resp.raise_for_status()
            body = resp.json()
        except Exception as e:
            print(f"\n错误: 轮询失败 — {e}")
            sys.exit(1)

        state = body.get("state", "unknown")
        print(f"      [{attempt:02d}] state={state:<10}", end="\r", flush=True)

        if state == "done":
            print()
            print("      完成!")
            return body
        elif state == "failed":
            print()
            print(f"错误: 任务失败 — {body.get('error', 'unknown')}")
            sys.exit(1)
        elif state == "cancelled":
            print()
            print("错误: 任务被取消")
            sys.exit(1)

        time.sleep(interval)


def _image2_download(session: requests.Session, body: dict, outdir: str):
    print(">>> [3/3] 下载结果...")
    images = body.get("images", [])
    total = len(images)
    print(f"      共 {total} 张图")

    os.makedirs(outdir, exist_ok=True)

    for idx, img in enumerate(images, start=1):
        filename = img["filename"]
        url = img["url"]
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "png"
        outfile = os.path.join(outdir, f"{idx:02d}.{ext}")
        print(f"      [{idx}/{total}] {filename} -> {outfile}")

        try:
            r = session.get(f"{IMAGE2_HOST}{url}", stream=True)
            r.raise_for_status()
            with open(outfile, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"            {os.path.getsize(outfile)} bytes")
        except Exception as e:
            print(f"错误: 下载失败 — {e}")
            sys.exit(1)

    print(f"\n完成! 图片已保存到 {outdir}")
    for f in sorted(os.listdir(outdir)):
        fp = os.path.join(outdir, f)
        if os.path.isfile(fp):
            print(f"  {os.path.getsize(fp):>10} B  {f}")


def image2_generate(prompt: str, images: list[str] = None, n: int = 1, outdir: str = IMAGE2_OUTDIR):
    """High-level wrapper: submit → poll → download via image2 service."""
    session = _image2_session()
    job_id = _image2_submit(session, prompt, images or [], n)
    body = _image2_poll(session, job_id, IMAGE2_POLL_INTERVAL)
    _image2_download(session, body, outdir)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def _parse_args():
    parser = argparse.ArgumentParser(
        description="多模型推理 / 生图工具",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "模型说明:\n"
            "  flash   → Gemini 3.5 Flash                 (强推理, 多模态, 默认)\n"
            "  lite    → Gemini 3.1 Flash Lite Preview    (轻量, 低延迟)\n"
            "  gemini-3-flash-preview       → Gemini 3 Flash Preview (Gateway)\n"
            "  gemini-3.1-flash-lite-preview → Gemini 3.1 Flash Lite Preview (Gateway)\n"
            "  claude-sonnet-4-5            → Claude Sonnet 4.5 (Gateway)\n"
            "  image2  → image2 生图服务             (文生图 / 图生图)\n\n"
            "示例:\n"
            "  # Gemini 文本分析 (默认 flash)\n"
            "  python gemini_client.py -p '深蹲膝盖内扣的原因'\n\n"
            "  # 切换到 lite 模型\n"
            "  python gemini_client.py -m lite -p '硬拉动作要点'\n\n"
            "  # Gateway: Gemini 3 Flash Preview\n"
            "  python gemini_client.py -m gemini-3-flash-preview -p '动作改进建议'\n\n"
            "  # Gateway: Claude Sonnet 4.5\n"
            "  python gemini_client.py -m claude-sonnet-4-5 -p '训练计划摘要'\n\n"
            "  # Gemini vision 姿态分析\n"
            "  python gemini_client.py -m flash -p '分析运动姿态' -i squat.jpg\n\n"
            "  # image2 文生图\n"
            "  python gemini_client.py -m image2 -p '穿宇航服的橘猫漂浮在土星环上'\n\n"
            "  # image2 图生图, 生成 2 张\n"
            "  python gemini_client.py -m image2 -p '风格迁移' -i ref1.jpg -i ref2.jpg -n 2\n\n"
            "环境变量 (image2):\n"
            "  IMAGE2_HOST          服务地址\n"
            "  IMAGE2_TOKEN         认证 token\n"
            "  IMAGE2_OUTDIR        输出目录\n"
            "  IMAGE2_POLL_INTERVAL 轮询间隔(秒), 默认 5\n\n"
            "环境变量 (Gateway / OpenAI兼容):\n"
            "  API_KEY         网关 API key\n"
            "  BASE_URL        网关 base url, 例如 https://api.zchat.tech/v1\n"
            "  API_TIMEOUT_MS  超时(毫秒), 默认 600000"
        ),
    )
    parser.add_argument(
        "-m", "--model",
        default="flash",
        choices=list(MODELS),
        metavar="{flash|lite|image2}",
        help="选择模型/服务 (默认: flash)",
    )
    parser.add_argument("-p", "--prompt", required=True, help="提示词 (必填)")
    parser.add_argument(
        "-i", "--image",
        action="append", default=[], metavar="IMAGE",
        help="图片路径, 可多次指定; Gemini 仅取第一张, image2 最多 8 张",
    )
    parser.add_argument(
        "-n", "--num",
        type=int, default=1, choices=range(1, 9), metavar="{1..8}",
        help="image2 生成数量 (默认 1, 仅 -m image2 有效)",
    )
    parser.add_argument(
        "-o", "--outdir",
        default=IMAGE2_OUTDIR,
        help="image2 输出目录 (仅 -m image2 有效)",
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    if args.model == "image2":
        image2_generate(args.prompt, args.image, args.num, args.outdir)
    else:
        gemini_model = MODELS[args.model]
        if args.image:
            result = analyze_pose_from_image(args.image[0], model=gemini_model)
        else:
            result = analyze_exercise_description(args.prompt, model=gemini_model)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

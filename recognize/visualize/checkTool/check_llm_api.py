"""
check_llm_api.py
----------------
检测 recognize_video.py 中 LLM API 连接是否正常。
检测项目：
  1. 环境变量是否配置（GEMINI_API_KEY, GEMINI_BASE_URL）
  2. API 端点是否可达
  3. 模型是否可用（发送简单请求测试）
  4. 响应格式是否正确

用法:
  python check_llm_api.py
  python check_llm_api.py --model gemini-3-flash-preview
  python check_llm_api.py --base-url https://xxx/v1 --api-key sk-xxx
"""

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://nextrouter.cc/v1"
DEFAULT_MODEL = "gemini-3-flash-preview"

# 备选模型列表（当主模型不可用时建议切换）
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gpt-4o-mini",
    "gpt-4o",
    "claude-sonnet-4-20250514",
]


def check_env_vars(api_key: str | None, base_url: str | None) -> dict:
    result = {"pass": True, "details": []}

    if not api_key:
        result["pass"] = False
        result["details"].append("[FAIL] GEMINI_API_KEY 未设置。请在 .env 文件或环境变量中配置。")
    else:
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        result["details"].append(f"[OK] GEMINI_API_KEY = {masked}")

    if not base_url:
        result["details"].append(f"[INFO] GEMINI_BASE_URL 未设置，将使用默认值: {DEFAULT_BASE_URL}")
    else:
        result["details"].append(f"[OK] GEMINI_BASE_URL = {base_url}")

    return result


def check_endpoint_reachable(base_url: str, api_key: str) -> dict:
    result = {"pass": False, "details": [], "models": []}

    models_url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        start = time.time()
        resp = requests.get(models_url, headers=headers, timeout=15)
        elapsed = time.time() - start

        if resp.status_code == 200:
            result["pass"] = True
            result["details"].append(f"[OK] API 端点可达 ({elapsed:.2f}s)")
            try:
                data = resp.json()
                models = data.get("data", [])
                result["models"] = [m.get("id", "") for m in models if m.get("id")]
                result["details"].append(f"[OK] 可用模型数: {len(result['models'])}")
            except Exception:
                result["details"].append("[WARN] 模型列表解析失败，但端点可达")
        elif resp.status_code == 401:
            result["details"].append("[FAIL] API 认证失败 (401)。请检查 GEMINI_API_KEY 是否正确。")
        elif resp.status_code == 403:
            result["details"].append("[FAIL] API 无权限 (403)。API Key 可能已过期或被禁用。")
        else:
            result["details"].append(f"[WARN] /models 返回 HTTP {resp.status_code}，尝试直接发送请求...")
            result["pass"] = True  # 有些代理不支持 /models 但支持 /chat/completions
    except requests.ConnectionError:
        result["details"].append(f"[FAIL] 无法连接到 {base_url}。请检查网络或 URL 是否正确。")
    except requests.Timeout:
        result["details"].append(f"[FAIL] 连接超时 (15s)。请检查网络连接。")
    except Exception as e:
        result["details"].append(f"[FAIL] 连接异常: {e}")

    return result


def check_model_available(base_url: str, api_key: str, model: str, available_models: list) -> dict:
    result = {"pass": False, "details": []}

    if available_models:
        if model in available_models:
            result["details"].append(f"[OK] 模型 '{model}' 在可用列表中")
        else:
            result["details"].append(f"[WARN] 模型 '{model}' 不在 /models 列表中（可能仍可使用）")
            similar = [m for m in available_models if "gemini" in m.lower() or "flash" in m.lower()]
            if similar:
                result["details"].append(f"[INFO] 类似模型: {', '.join(similar[:5])}")

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "请回复数字 42，不要其他内容。"}
        ],
        "temperature": 0.0,
        "max_tokens": 16,
    }

    try:
        start = time.time()
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            result["pass"] = True
            result["details"].append(f"[OK] 模型 '{model}' 请求成功 ({elapsed:.2f}s)")
            result["details"].append(f"[OK] 响应内容: {content.strip()[:50]}")

            usage = data.get("usage", {})
            if usage:
                result["details"].append(
                    f"[INFO] Token 使用: prompt={usage.get('prompt_tokens', '?')}, "
                    f"completion={usage.get('completion_tokens', '?')}"
                )
        elif resp.status_code == 429:
            result["details"].append("[FAIL] 请求被限流 (429)。API 配额可能已用尽或频率太高。")
            try:
                err = resp.json()
                result["details"].append(f"[INFO] 错误信息: {err.get('error', {}).get('message', resp.text[:200])}")
            except Exception:
                pass
        elif resp.status_code == 404:
            result["details"].append(f"[FAIL] 模型 '{model}' 不存在 (404)。需要更换模型。")
        elif resp.status_code == 401:
            result["details"].append("[FAIL] API Key 无效 (401)。")
        elif resp.status_code == 402:
            result["details"].append("[FAIL] 余额不足 (402)。请充值或更换 API Key。")
        else:
            result["details"].append(f"[FAIL] 请求失败 HTTP {resp.status_code}")
            try:
                result["details"].append(f"[INFO] 响应: {resp.text[:300]}")
            except Exception:
                pass
    except requests.Timeout:
        result["details"].append(f"[FAIL] 模型请求超时 (30s)。模型可能不可用。")
    except Exception as e:
        result["details"].append(f"[FAIL] 请求异常: {e}")

    return result


def check_vision_capability(base_url: str, api_key: str, model: str) -> dict:
    """测试模型是否支持图片输入（recognize_video.py 依赖此能力）"""
    result = {"pass": False, "details": []}

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # 1x1 白色像素的 base64 JPEG
    tiny_img = (
        "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgK"
        "DBQNDQ0MDBkSGRUUFhUUEhYWGB0eJR4cGyAkIicmJyksMC0sMjIyHCk4ODs7OzszMzP/2wBDAQkJ"
        "CQwLDBYNDRYzIRwhMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMz"
        "MzMzMzP/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAA"
        "AAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQ"
        "ACEQMRAD8AKwA="
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这张图片是什么颜色？请用一个词回答。"},
                    {"type": "image_url", "image_url": {"url": tiny_img}},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 16,
    }

    try:
        start = time.time()
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            result["pass"] = True
            result["details"].append(f"[OK] 视觉能力正常 ({elapsed:.2f}s), 响应: {content.strip()[:30]}")
        elif resp.status_code == 400:
            err_msg = ""
            try:
                err_msg = resp.json().get("error", {}).get("message", "")
            except Exception:
                err_msg = resp.text[:200]
            if "image" in err_msg.lower() or "vision" in err_msg.lower() or "multimodal" in err_msg.lower():
                result["details"].append(f"[FAIL] 模型 '{model}' 不支持图片输入。recognize_video.py 需要视觉模型。")
            else:
                result["details"].append(f"[FAIL] 请求格式错误: {err_msg}")
        else:
            result["details"].append(f"[WARN] 视觉测试返回 HTTP {resp.status_code}")
    except requests.Timeout:
        result["details"].append("[WARN] 视觉测试超时")
    except Exception as e:
        result["details"].append(f"[WARN] 视觉测试异常: {e}")

    return result


def suggest_alternatives(base_url: str, api_key: str, current_model: str) -> list[str]:
    """当主模型不可用时，测试备选模型"""
    suggestions = []
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for model in FALLBACK_MODELS:
        if model == current_model:
            continue
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 4,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                suggestions.append(model)
        except Exception:
            pass

    return suggestions


def main():
    parser = argparse.ArgumentParser(description="检测 LLM API 连接状态")
    parser.add_argument("--api-key", default=None, help="API Key（默认读取 GEMINI_API_KEY 环境变量）")
    parser.add_argument("--base-url", default=None, help="API Base URL（默认读取 GEMINI_BASE_URL 环境变量）")
    parser.add_argument("--model", default=None, help=f"模型名称（默认 {DEFAULT_MODEL}）")
    parser.add_argument("--test-fallbacks", action="store_true", help="当主模型失败时测试备选模型")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    base_url = args.base_url or os.getenv("GEMINI_BASE_URL", DEFAULT_BASE_URL)
    model = args.model or DEFAULT_MODEL

    print("=" * 60)
    print("LLM API 检测工具 (for recognize_video.py)")
    print("=" * 60)
    print(f"  Base URL: {base_url}")
    print(f"  Model:    {model}")
    print("=" * 60)

    all_pass = True

    # Step 1: 环境变量
    print("\n[Step 1] 检查环境变量配置...")
    env_result = check_env_vars(api_key, base_url)
    for line in env_result["details"]:
        print(f"  {line}")
    if not env_result["pass"]:
        all_pass = False
        print("\n结论: 环境变量未正确配置，请先设置 GEMINI_API_KEY。")
        sys.exit(1)

    # Step 2: 端点可达性
    print("\n[Step 2] 检查 API 端点可达性...")
    endpoint_result = check_endpoint_reachable(base_url, api_key)
    for line in endpoint_result["details"]:
        print(f"  {line}")
    if not endpoint_result["pass"]:
        all_pass = False
        print("\n结论: API 端点不可达。建议：")
        print("  1. 检查网络连接和代理设置")
        print("  2. 确认 GEMINI_BASE_URL 是否正确")
        print("  3. 考虑更换 API 服务商")
        sys.exit(1)

    # Step 3: 模型可用性
    print("\n[Step 3] 测试模型请求...")
    model_result = check_model_available(base_url, api_key, model, endpoint_result.get("models", []))
    for line in model_result["details"]:
        print(f"  {line}")
    if not model_result["pass"]:
        all_pass = False

    # Step 4: 视觉能力
    if model_result["pass"]:
        print("\n[Step 4] 测试视觉（图片输入）能力...")
        vision_result = check_vision_capability(base_url, api_key, model)
        for line in vision_result["details"]:
            print(f"  {line}")
        if not vision_result["pass"]:
            all_pass = False

    # 备选模型
    if not all_pass and args.test_fallbacks:
        print("\n[额外] 测试备选模型...")
        alternatives = suggest_alternatives(base_url, api_key, model)
        if alternatives:
            print(f"  可用的备选模型: {', '.join(alternatives)}")
            print(f"\n  建议: 在 recognize_video.py 中将 MODEL 修改为: {alternatives[0]}")
            print(f"  或设置环境变量后运行:")
            print(f"    set MODEL={alternatives[0]}")
        else:
            print("  未找到可用的备选模型。建议更换 API Key 或服务商。")

    # 总结
    print("\n" + "=" * 60)
    if all_pass:
        print("检测结果: ALL PASS ✓")
        print("LLM API 配置正常，recognize_video.py 可以正常运行。")
    else:
        print("检测结果: FAILED ✗")
        print("\n建议操作:")
        if not model_result["pass"]:
            print(f"  → 模型 '{model}' 不可用，需要更换模型或 API Key")
            if not args.test_fallbacks:
                print(f"  → 运行 python check_llm_api.py --test-fallbacks 查看可用备选模型")
        print(f"  → 检查 API Key 余额和有效期")
        print(f"  → 考虑更换 API 代理服务 (当前: {base_url})")
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()

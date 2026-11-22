#!/usr/bin/env python3
"""
通用模型下载工具（适用于 Colab / 本地 ComfyUI）
支持：
1. HuggingFace / 普通直链（使用 aria2c 多线程下载）
2. Civitai 模型页面链接（自动解析最新版本，支持 civitai.com / civitai.red）
3. Civitai 模型版本直链（https://civitai.com/api/download/models/<version_id>）
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def resolve_civitai_url(url: str, token: str = "") -> tuple[str, str | None]:
    """将 Civitai 页面链接或下载链接规范化为实际下载地址，并尝试提取文件名。"""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    if "civitai." not in host:
        return url, None

    # 统一走 civitai.com API（civitai.red 与 civitai.com 共享模型 ID）
    api_host = "civitai.com"

    # 情况 A：已经是 /api/download/models/<version_id>
    if "/api/download/models/" in parsed.path:
        qs = urllib.parse.parse_qs(parsed.query)
        if token and "token" not in qs:
            qs["token"] = [token]
        new_query = urllib.parse.urlencode(qs, doseq=True)
        final_url = urllib.parse.urlunparse(
            ("https", api_host, parsed.path, "", new_query, "")
        )
        return final_url, None

    # 情况 B：模型详情页 /models/<model_id>/...
    m = re.search(r"/models/(\d+)", parsed.path)
    if not m:
        return url, None

    model_id = m.group(1)
    qs = urllib.parse.parse_qs(parsed.query)
    wanted_vid = qs.get("modelVersionId", [None])[0]

    api_url = f"https://{api_host}/api/v1/models/{model_id}"
    req = urllib.request.Request(api_url, headers={"User-Agent": UA})
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    versions = data.get("modelVersions", [])
    if not versions:
        raise RuntimeError(f"Civitai 模型 {model_id} 没有可用版本")

    target_ver = versions[0]
    if wanted_vid:
        for v in versions:
            if str(v.get("id")) == str(wanted_vid):
                target_ver = v
                break

    version_id = target_ver["id"]
    files = target_ver.get("files", [])
    primary = next((f for f in files if f.get("primary")), files[0] if files else None)
    filename = primary.get("name") if primary else f"civitai_{model_id}_{version_id}.safetensors"

    dl_url = f"https://{api_host}/api/download/models/{version_id}"
    if token:
        dl_url += f"?token={urllib.parse.quote(token)}"
    print(f"[Civitai] 解析成功: {data.get('name')} | 版本: {target_ver.get('name')} | 底模: {target_ver.get('baseModel')}")
    if target_ver.get("trainedWords"):
        print(f"[Civitai] 触发词: {', '.join(target_ver['trainedWords'])}")
    return dl_url, filename


def download_file(url: str, target_dir: Path, filename: str | None = None, civitai_token: str = "", hf_token: str = "") -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    url = url.strip()
    if not url:
        raise ValueError("下载链接为空")

    resolved_url, detected_name = resolve_civitai_url(url, token=civitai_token)
    out_name = filename or detected_name
    if not out_name:
        path_name = Path(urllib.parse.urlparse(resolved_url).path).name
        if path_name and "." in path_name:
            out_name = urllib.parse.unquote(path_name)

    if out_name and (target_dir / out_name).exists() and (target_dir / out_name).stat().st_size > 1024 * 1024:
        print(f"[Skip] 已存在: {target_dir / out_name}")
        return target_dir / out_name

    headers = []
    if hf_token and "huggingface.co" in resolved_url:
        headers.append(f"Authorization: Bearer {hf_token}")

    is_civitai = "civitai." in urllib.parse.urlparse(resolved_url).netloc.lower()
    if is_civitai or not shutil.which("aria2c"):
        cmd = ["curl", "-fL", "--retry", "3", "-C", "-", "-A", UA]
        for h in headers:
            cmd += ["-H", h]
        if out_name:
            cmd += ["-o", str(target_dir / out_name)]
        else:
            cmd += ["-J", "-O", "--output-dir", str(target_dir)]
        cmd.append(resolved_url)
        print(f"[Download via curl] -> {target_dir / (out_name or '(auto)')}")
        subprocess.run(cmd, check=True)
        return target_dir / (out_name or "")

    cmd = [
        "aria2c",
        "--console-log-level=warn",
        "-c",
        "-x", "8",
        "-s", "8",
        "-k", "1M",
        "-U", UA,
        "--auto-file-renaming=false",
        "--content-disposition-default-utf8=true",
        "-d", str(target_dir),
    ]
    for h in headers:
        cmd += ["--header", h]
    if out_name:
        cmd += ["-o", out_name]
    cmd.append(resolved_url)

    print(f"[Download via aria2c] -> {target_dir / (out_name or '(auto)')}")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("[Warn] aria2c 下载失败，自动回退到 curl...")
        curl_cmd = ["curl", "-fL", "--retry", "3", "-C", "-", "-A", UA]
        for h in headers:
            curl_cmd += ["-H", h]
        curl_cmd += ["-o", str(target_dir / out_name)] if out_name else ["-J", "-O", "--output-dir", str(target_dir)]
        curl_cmd.append(resolved_url)
        subprocess.run(curl_cmd, check=True)
    return target_dir / (out_name or "")


Z_IMAGE_PRESETS = {
    "gguf_q4": {
        "desc": "Z-Image-Turbo GGUF Q4_K_M + Qwen3-4B Q4_K_M + VAE（适合 Colab 免费 T4 16GB）",
        "files": [
            ("unet", "https://huggingface.co/jayn7/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_K_M.gguf", "z_image_turbo-Q4_K_M.gguf"),
            ("text_encoders", "https://huggingface.co/unsloth/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf", "Qwen3-4B-Q4_K_M.gguf"),
            ("vae", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors", "ae.safetensors"),
        ],
    },
    "gguf_q6": {
        "desc": "Z-Image-Turbo GGUF Q6_K + Qwen3-4B Q6_K + VAE（画质与显存均衡，推荐 16GB+）",
        "files": [
            ("unet", "https://huggingface.co/jayn7/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q6_K.gguf", "z_image_turbo-Q6_K.gguf"),
            ("text_encoders", "https://huggingface.co/unsloth/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q6_K.gguf", "Qwen3-4B-Q6_K.gguf"),
            ("vae", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors", "ae.safetensors"),
        ],
    },
    "fp8": {
        "desc": "Z-Image-Turbo FP8 + Qwen3-4B FP8 + VAE（适合 L4 / 12-16GB 新架构显卡）",
        "files": [
            ("diffusion_models", "https://huggingface.co/drbaph/Z-Image-Turbo-FP8/resolve/main/z_image_turbo_fp8_e4m3fn.safetensors", "z_image_turbo_fp8_e4m3fn.safetensors"),
            ("text_encoders", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors", "qwen_3_4b_fp8_mixed.safetensors"),
            ("vae", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors", "ae.safetensors"),
        ],
    },
    "bf16": {
        "desc": "Z-Image-Turbo 原版 BF16 + Qwen3-4B BF16 + VAE（推荐 Colab L4 24GB / A100）",
        "files": [
            ("diffusion_models", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors", "z_image_turbo_bf16.safetensors"),
            ("text_encoders", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors", "qwen_3_4b.safetensors"),
            ("vae", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors", "ae.safetensors"),
        ],
    },
}


def main():
    parser = argparse.ArgumentParser(description="ComfyUI 模型下载脚本")
    parser.add_argument("--comfy-dir", default="/content/ComfyUI", help="ComfyUI 根目录")
    parser.add_argument("--preset", choices=list(Z_IMAGE_PRESETS.keys()), help="下载预置底模组合")
    parser.add_argument("--url", help="自定义下载链接（支持 HuggingFace / Civitai 页面或直链）")
    parser.add_argument(
        "--type",
        default="loras",
        choices=["checkpoints", "diffusion_models", "unet", "text_encoders", "vae", "loras", "embeddings"],
        help="目标模型目录类型",
    )
    parser.add_argument("--filename", default=None, help="可选：指定保存文件名")
    parser.add_argument("--civitai-token", default=os.environ.get("CIVITAI_API_TOKEN", ""), help="可选：Civitai API Token")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""), help="可选：HuggingFace Token")
    args = parser.parse_args()

    models_root = Path(args.comfy_dir) / "models"

    if args.preset:
        spec = Z_IMAGE_PRESETS[args.preset]
        print(f"=== 下载预置: {args.preset} | {spec['desc']} ===")
        for subdir, url, fname in spec["files"]:
            download_file(url, models_root / subdir, fname, civitai_token=args.civitai_token, hf_token=args.hf_token)

    if args.url:
        download_file(
            args.url,
            models_root / args.type,
            filename=args.filename,
            civitai_token=args.civitai_token,
            hf_token=args.hf_token,
        )

    if not args.preset and not args.url:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

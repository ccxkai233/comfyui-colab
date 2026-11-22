# ComfyUI Colab 多底模 + LoRA 生图工具包

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ccxkai233/comfyui-colab/blob/main/ComfyUI_Colab.ipynb)

面向 Google Colab（兼容免费 **T4 16GB** 与付费 **L4 24GB / A100**）的 ComfyUI 网页版一键启动脚本、模型下载工具与常用工作流模板。

## 目录结构

```text
comfyui-colab/
├── ComfyUI_Colab.ipynb                   # Google Colab 一键启动 Notebook（带表单配置）
├── scripts/
│   └── download_models.py                # 通用模型下载脚本（支持 HuggingFace / Civitai 自动解析）
└── workflows/
    ├── z_image_turbo_gguf_lora.json      # Z-Image-Turbo GGUF + LoRA 工作流（T4 16GB 推荐）
    ├── z_image_turbo_bf16_lora.json      # Z-Image-Turbo BF16/FP8 + LoRA 工作流（L4 24GB+ 推荐）
    └── sd15_lora.json                    # SD 1.5 + LoRA 工作流（含 Clip Skip 2）
```

## 快速开始（一键在 Colab 打开）

1. 点击上方 **Open In Colab** 徽章，或直接访问：
   ```text
   https://colab.research.google.com/github/ccxkai233/comfyui-colab/blob/main/ComfyUI_Colab.ipynb
   ```
2. 在 Colab 菜单栏切换 GPU：**代码执行程序 → 更改运行时类型 → T4 或 L4 GPU**。
3. 按顺序运行第 1–5 步单元格（第 2 步已默认配置本仓库地址，会自动将 `workflows/` 导入 ComfyUI 网页版）。
4. 等待第 5 步打印出 `https://xxxx.trycloudflare.com` 后，点击进入 ComfyUI 网页版。

## 显卡与底模预置选择

| Colab 显卡 | 可用显存 / 内存 | Z-Image-Turbo 推荐预置 | 对应工作流 |
| :--- | :--- | :--- | :--- |
| **T4（免费）** | ~15 GB VRAM / ~12.7 GB RAM | `gguf_q4`（自动 `--force-fp16`） | `z_image_turbo_gguf_lora.json` |
| **L4（Pro）** | ~22.5 GB VRAM / ~53 GB RAM | `bf16` 或 `fp8` | `z_image_turbo_bf16_lora.json` |
| **SD 1.5 任意卡** | 8 GB+ 均流畅 | `Z_IMAGE_PRESET = none`，在 `CUSTOM_CHECKPOINT_URL` 填 SD 1.5 大模型链接 | `sd15_lora.json` |

## 常用底模提示词与参数速查

| 底模 | 提示词写法 | 负向提示词 | Steps | CFG | 采样器 / 调度器 | 推荐分辨率 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Z-Image-Turbo** | 自然语言句子 + 触发词 | `CFG=1` 时留空即可 | `8`（6–10） | `1.0` | `euler` / `simple` | `768×1344`（T4） / `1088×1920`（L4） |
| **SD 1.5** | 英文短词 Tag（逗号分隔）+ 触发词 | 必填（防崩手/低画质） | `28`（20–32） | `7.0` | `dpmpp_2m` / `karras` | `512×768` |
| **SDXL / Pony / Illustrious** | Tag 风格（Pony 需加 `score_9...`） | 必填 | `25`（20–30） | `5–7` | `euler_ancestral` / `dpmpp_2m` | `832×1216` / `1024×1024` |

## 注意事项

- **Civitai Token**：部分 NSFW 或需要登录下载的模型，建议在 Civitai 账号设置中生成 API Token 填到第 3 步的 `CIVITAI_API_TOKEN`（**切勿把 Token 提交到公开 GitHub 仓库**）。
- **下载新模型后刷新**：运行第 4 步补充下载 LoRA 后，不需要重启 ComfyUI，在网页界面按键盘 **`R`** 刷新节点列表即可选到新文件。

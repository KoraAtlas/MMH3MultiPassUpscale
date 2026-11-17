# ComfyUI MMH3 Multi-Pass Upscale

Multi-pass, optionally tiled latent upscaling for **MiniMax H3** text/reference-to-video in ComfyUI.

Render a fast, low-resolution H3 video, then climb to a high final resolution in several controlled steps instead of one big jump. Each pass resizes the latent and re-samples it with its own size, denoise, step count and tile grid, so detail is added gradually while motion, composition and the soundtrack from your base render are kept.

## Why

Upscaling a video latent in one large step usually means a trade-off: low denoise leaves the result soft, and high denoise drifts away from the base render. Splitting the climb into smaller passes lets each pass add detail at a gentle denoise. Tiling the large passes keeps VRAM in check on consumer GPUs.

## Goals

- **One node, drop-in.** Replaces SamplerCustomAdvanced and uses the same `noise`, `guider`, `sampler`, `sigmas` and `latent_image` connections, so it fits existing H3 workflows and any guider.
- **Target-driven.** Set a final size in megapixels; the node works out every pass's resolution at the source aspect ratio.
- **Per-pass control.** Each pass has its own size (auto, scale factor or megapixels), denoise, steps, tile grid and optional manual sigmas.
- **Lower memory.** Tile any pass (2x2, 3x3 and up to 8x8) to cap peak VRAM. Tiles share one noise field and blend across overlaps to hide seams.
- **Keep the audio.** H3 renders audio and video together. Audio from the base render is passed through untouched on every pass.
- **Easy troubleshooting.** Toggle passes on and off without losing their settings, and save any pass's latent to find where a bad denoise or tiling issue starts.

## Features

- Pass list editor on the node: **+ Add Pass**, an on/off toggle per pass, **✕** to remove (up to 8 passes).
- Disabled passes keep their values and are skipped.
- Optional `pass_N` latent output for each pass, plus a switch to run saves for all passes or only the final one.
- Denoise as a true starting noise level, independent of the scheduler node's denoise setting.
- Latent resize by interpolation or an H3 3D latent upscale model.
- `plan` output listing each pass's resolution, scale, tiles and sigmas.

## Requirements

- A ComfyUI version with native MiniMax H3 support.
- MiniMax H3 model files (diffusion model, Qwen3-VL text encoder, video VAE, audio VAE), from [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3).
- Optional: a turbo LoRA for fast base renders, and an H3 3D latent upscale model (`.safetensors`) in `models/latent_upscale_models`.
- No extra Python packages.
- (Optional, but highly recommended) a H3 latent upscale model, such as https://huggingface.co/LBH-123-AI/Minimax_h3_latent_Upscaler

## Install

Copy this folder into `ComfyUI/custom_nodes/` and restart ComfyUI. Remove the folder to uninstall. It does not need Comfyui-MMH3-UltimateUpscale.

## Quick start

Open `example_workflows/minimal_h3_multipass_upscale.json`, or find it in ComfyUI's template browser under this node pack. It is a bare-minimum text-to-video graph:

| Stage | Settings |
|---|---|
| Prompt | "A red fox trots through fresh snow in a pine forest at golden hour. Snowflakes drift through shafts of warm light, its breath fogs in the cold air, and the camera tracks alongside at ground level. Soft crunch of paws in snow, wind moving through the branches." |
| Base render | 864x480 (0.4 MP), 124 frames (5 s at 24 fps), 6 steps, Euler, simple scheduler, 6-step turbo LoRA |
| Pass 1 | auto size → 1184x672 (0.8 MP), denoise 0.45, 4 steps, 1x1 tiles |
| Pass 2 | target → 1632x928 (1.5 MP), denoise 0.35, 4 steps, 1x1 tiles |
| Output | VAE Decode + VAE Decode Audio → Create Video (24 fps) → Save Video |

Select your own files in the five loaders. The turbo LoRA name is a placeholder. The workflow uses the H3 Reference to Video node with no references, which works as text-to-video.

The base render must come from a regular sampler, because this node keeps the input latent's audio as it is.

## Wiring

Same connections as SamplerCustomAdvanced: `noise`, `guider`, `sampler`, `sigmas`, `latent_image`. The `output` and `denoised_output` slots also match. Extra outputs: `plan` and one `pass_N` latent per pass. A `noise_mask` on the input latent is ignored.

Send `output` to VAE Decode. For very large targets, use a tiled VAE decode.

## Global settings

| Input | Meaning |
|---|---|
| `target_megapixels` | Final resolution at the source aspect ratio, snapped to 32 px. The last enabled pass always renders here. |
| `upscaler` | Interpolation, or an H3 3D upscale model from `models/latent_upscale_models` (`.safetensors` only). The model upscales the full frame, so if it runs out of memory on large passes, use interpolation. |
| `denoise_mode` | See below. |
| `tile_overlap`, `seam_fade` | Seam settings for tiled passes, in pixels. |
| `pass_outputs` | `final_pass_only` activates only the last enabled pass's `pass_N` output. `all_passes` activates every enabled pass, for troubleshooting. Nodes connected to an inactive output, and anything after them, do not run. Changing this re-runs the whole node, because it is one of its inputs. |

## Pass list

Passes are rows on the node, edited like rgthree's Power Lora Loader:

- **+ Add Pass** adds a row (up to 8), copying the previous row's denoise, steps and tiles.
- The **toggle** enables or disables a pass. A disabled pass is skipped but keeps all its values.
- **✕** removes the pass.
- Click the ◀ ▶ arrows to nudge a number, or click its value to type one. Click the size mode, tiles or σ box to change them.

Each row has:

| Field | Meaning |
|---|---|
| size mode + size | `scale` multiplies the previous enabled pass's width and height (`1.5` is 2.25x the pixels). `megapixels` sets it directly. `auto` takes even steps toward the next set size or the target. The last enabled pass shows `target`, because it always renders at `target_megapixels`; its own size value is kept for when it stops being last. Sizes above the target are capped. |
| denoise | Where this pass starts. `0` resizes without sampling. |
| steps | Steps, per tile when tiled. The curve is resampled to this count. `0` keeps the connected schedule's own points, which can leave very few steps at low denoise. |
| tiles | Grid as `COLUMNSxROWS`. `1x1` renders the frame whole. |
| σ | Optional schedule such as `0.6, 0.4, 0.2, 0`. Replaces denoise, steps and the `sigmas` input for that pass; denoise and steps are greyed out while it is set. |

To run your exact connected schedule on a pass, set denoise to its first sigma and steps to `0`, or enter it in σ.

The rows are stored as JSON in a hidden `pass_config` input, which is what the server reads. If the node's script fails to load, that input shows as a text box and can be edited directly.

The pass list is drawn on the classic canvas view. If the rows do not appear in the newer node view, switch back to the canvas view.

## Outputs

`output` stays at the top and is always the final, fully upscaled latent; `denoised_output` and `plan` follow. Below them the node shows one optional `pass_N` latent output per pass in the list, added and removed with the rows. Connect one only if you want to save that pass. A disabled pass's output is labelled `(off)`.

Pass N always uses seed + N − 1 and the `pass_N` output, whether or not other passes are enabled, so toggling a pass does not change the others. Removing a pass renumbers the passes after it; their output connections move with them, and the removed pass's connections are dropped.

## Troubleshooting passes

Connect a VAE Decode and a save node to each `pass_N` output you want to inspect. Leave `pass_outputs` on `final_pass_only` for normal renders, and switch to `all_passes` with a fixed seed to see where a problem starts. Outputs for disabled or missing passes stay inactive, so the same wiring works for any pass list.

## Denoise modes

- `noise_level` (default): denoise is the starting sigma. `0.5` starts at sigma 0.5, whatever denoise is set on the scheduler node. A sigma list only holds what the scheduler kept, so leave the scheduler's denoise at 1.0 to keep the full curve shape. If a pass starts above the list, the curve is extended upward in a straight line.
- `comfy_steps`: denoise keeps that fraction of the connected list's steps, like BasicScheduler, so it stacks on top of the scheduler's denoise. On a shifted H3 schedule, `0.5` can start near sigma 0.92, which replaces most of the image.

## Tiling notes

Tiles render one at a time, so peak VRAM follows one tile plus any reference latents. Each tile sees the whole prompt but only part of the frame, and at high denoise it can invent content that does not belong there. Keep denoise low on tiled passes, and do any high-denoise work on early passes, while the frame still fits without tiles.

## Status

Early release. The node logic and the pass list editor have been tested outside ComfyUI, but not yet in a full H3 run. Please report issues with the `plan` output and console log attached.

## Credits

Based on [Comfyui-MMH3-UltimateUpscale](https://github.com/bbaudio-2025/Comfyui-MMH3-UltimateUpscale) (MIT). `nodes/h3_latent_upscaler.py` is copied from it, and the H3 upscaler code there comes from [Comfyui_Minimax_h3_latent_Upscaler](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler). This package does not include that project's GPL-licensed tiled diffusion code.

License: MIT.

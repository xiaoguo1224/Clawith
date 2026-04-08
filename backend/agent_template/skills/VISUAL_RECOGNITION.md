---
name: Visual Recognition (Native Vision)
description: Use the agent's primary LLM vision capability to understand images in chat—no MCP, no separate vision APIs, no OCR tools.
---

# Visual Recognition (Native Vision)

## What this skill is for

Use when the user wants **object/scene understanding, OCR, diagram reading, UI screenshots, chart interpretation**, or any task where **seeing the image** matters.

The **same model** you run as the agent (e.g. **Kimi K2.5**, GPT-4o, Claude with vision, Gemini, etc.) already receives the image through the platform **if** that model is **vision-capable** and the image is attached in this conversation.

## How images reach you (Clawith)

- The user **uploads or pastes** an image in chat.
- The client embeds markers like  
  `[image_data:data:image/jpeg;base64,...]`  
  in the user message.
- When the configured **primary model supports vision**, the runtime turns these into **native multimodal** input for the API. **You are not calling a separate “vision service”.** You simply **reason over what the model sees**.

If there is **no** such marker (or no image part in the message), you **do not** have pixels—do not hallucinate content.

## Operating protocol

1. **Check the question** — What should you extract? (labels, text, layout, counts, errors on screen, trend in a chart, etc.)
2. **Use direct visual analysis** — Answer from the image(s) in the current turn. Be specific: locations, colors, text quotes, approximate counts, uncertainty when blurry or partial.
3. **Multiple images** — Address each if the user referred to several; state which image you mean if needed.
4. **No image in context** — Ask the user to **attach the image in this chat** (or re-upload). A **file path alone** does not give you pixels unless the system has already injected vision content for that upload in this thread.

## Explicit non-goals (unless the user insists otherwise)

- **Do not** use **MCP** or third-party tools marketed as “image recognition” for normal in-chat images—the primary model’s vision is the default path.
- **Do not** use **`web_search`** to infer what is inside a **private** image.
- **Do not** use **`read_document`** (or similar text-only file tools) to “open” **raster** images (jpg/png/webp/gif, etc.)—they are not reliable for pixel content; vision input is.

## If vision is unavailable

If the user’s **primary model is not vision-capable** (or images were stripped), say so clearly: they should switch to a **vision model** in agent settings, or describe the image in text.

## Output style

- Lead with a **short answer**, then **detail** (bullet lists for many items).
- For OCR, **quote visible text**; note language if relevant.
- State **limitations** (blur, crop, watermark, low resolution) when they affect accuracy.

**Keywords:** 图像识别, 看图, OCR, 截图, 视觉理解, image understanding, screenshot, chart, diagram, native vision, multimodal

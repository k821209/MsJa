---
name: nanobanana-pro
description: Generate images using Google Nano Banana Pro (Gemini 3 Pro Image) API. Use when user wants to create AI images, generate illustrations, or create visual content.
argument-hint: [prompt or @file.md] [--aspect 16:9] [--size 2K] [--output filename.png] [--lang ko]
context: fork
agent: general-purpose
allowed-tools: Bash, Read
---

# Nano Banana Pro Image Generator

Generate professional-quality images using Google's Nano Banana Pro API (Gemini 3 Pro Image Preview).

## Usage

```bash
source ~/.zshrc && python3 .claude/skills/nanobanana-pro/scripts/generate.py "YOUR_PROMPT" --aspect RATIO --size SIZE --output FILENAME
```

Or use the --api-key flag directly:

```bash
python3 .claude/skills/nanobanana-pro/scripts/generate.py "YOUR_PROMPT" --api-key "YOUR_API_KEY"
```

### Arguments

| Argument | Default | Options | Description |
|----------|---------|---------|-------------|
| prompt | (required) | - | Image description |
| --aspect | 16:9 | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 | Aspect ratio |
| --size | 2K | 1K, 2K, 4K | Image resolution |
| --output | generated_image.png | any filename | Output file path |
| --lang | (none) | ko, ja, zh | Force text labels in target language |

## Language Detection (CRITICAL)

| User says | Action |
|-----------|--------|
| "한글로", "한국어로", "Korean" | Add `--lang ko` and use Korean prompt |
| "日本語で", "Japanese" | Add `--lang ja` |
| "中文", "Chinese" | Add `--lang zh` |
| (default) | Don't add `--lang` |

## Output Filename Rules

**When an input file is provided:**
1. Extract the base filename without extension
2. Use `.png` extension for output
3. Save to the same directory as the input file

**When no input file:**
- Use a descriptive name based on the prompt
- Save to current working directory

## Examples

### Basic
```bash
python3 .claude/skills/nanobanana-pro/scripts/generate.py "a cute robot reading a book"
```

### Korean Text
```bash
python3 .claude/skills/nanobanana-pro/scripts/generate.py "귀여운 로봇이 책을 읽고 있는 그림" --lang ko --output robot.png
```

### High Resolution
```bash
python3 .claude/skills/nanobanana-pro/scripts/generate.py "modern minimalist logo design" --aspect 1:1 --size 4K --output logo.png
```

## Model Capabilities

- **4K Resolution**: Up to 4K output for print-quality images
- **Text Rendering**: Accurate text in generated images
- **Thinking Mode**: Advanced reasoning for complex prompts
- **SynthID Watermark**: All outputs include invisible watermark

## Persona Image Rules (IMPORTANT)

1. **Avatar = Reference**: Check `get_persona_state` → `avatar` field. If an avatar exists, use nanobanana-edit with it as input for consistent appearance. If no avatar is set (default), generate from scratch with nanobanana-pro.
2. **Auto-register**: After successful generation, call `add_persona_image` MCP tool with the output path, a label, and image_type to register in the web dashboard Images page.

## Error Handling

- If `GEMINI_API_KEY` not set: Script will prompt to set it
- If API error: Error message will be displayed
- If rate limited: Wait and retry

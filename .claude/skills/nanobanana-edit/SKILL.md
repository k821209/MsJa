---
name: nanobanana-edit
description: Edit existing images using Google Nano Banana Pro (Gemini 3 Pro Image) API. Use when user wants to modify, refine, or transform an existing image.
argument-hint: --input image.png "editing instruction" [--aspect 16:9] [--size 2K] [--output edited.png]
context: fork
agent: general-purpose
allowed-tools: Bash, Read
---

# Nano Banana Pro Image Editor

Edit and transform existing images using Google's Nano Banana Pro API (Gemini 3 Pro Image Preview).

## Usage

```bash
source ~/.zshrc && python3 .claude/skills/nanobanana-edit/scripts/edit.py --input INPUT_IMAGE "EDITING_INSTRUCTION" --output OUTPUT_FILE
```

### Arguments

| Argument | Default | Options | Description |
|----------|---------|---------|-------------|
| --input | (required) | any image file | Source image to edit (PNG, JPG, WEBP) |
| prompt | (required) | - | Editing instruction |
| --aspect | (preserve) | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 | Output aspect ratio |
| --size | 4K | 1K, 2K, 4K | Output resolution |
| --output | edited_image.png | any filename | Output file path |

## Editing Capabilities

### Element Modification
```bash
python3 .claude/skills/nanobanana-edit/scripts/edit.py \
  --input photo.png "Remove the background and replace with white" --output clean.png
```

### Inpainting (Partial Edit)
```bash
python3 .claude/skills/nanobanana-edit/scripts/edit.py \
  --input portrait.png "Change only the hair color to blonde. Keep everything else exactly the same" --output blonde.png
```

### Style Transfer
```bash
python3 .claude/skills/nanobanana-edit/scripts/edit.py \
  --input photo.png "Transform into watercolor painting style" --output watercolor.png
```

### Sketch Refinement
```bash
python3 .claude/skills/nanobanana-edit/scripts/edit.py \
  --input sketch.png "Transform this rough sketch into a professional diagram with clean lines" --output diagram.png
```

## Tips

1. **Be specific**: "Change the sky to sunset orange" > "make it prettier"
2. **Preserve context**: Add "Keep everything else exactly the same" for targeted edits
3. **Iterative editing**: Make small changes step by step for complex edits

## Persona Image Rules (IMPORTANT)

1. **Avatar = Reference**: Check `get_persona_state` → `avatar` field. If an avatar exists, use it as input. If no avatar is set (default), use nanobanana-pro to generate from scratch instead.
2. **Auto-register**: After successful edit, call `add_persona_image` MCP tool with the output path, a label, and image_type to register in the web dashboard Images page.

## Error Handling

- If `GEMINI_API_KEY` not set: Script will prompt to set it
- If API error: Error message will be displayed

---
name: nanobanana-edit
description: Edit existing images using Google Nano Banana Pro (Gemini 3 Pro Image) API. Use when user wants to modify, refine, or transform an existing image.
argument-hint: --input image.png "editing instruction" [--aspect 16:9] [--size 2K] [--output edited.png]
context: fork
agent: general-purpose
allowed-tools: Bash, Read, mcp__persona__add_persona_image, mcp__persona__set_persona_avatar, mcp__persona__get_avatar_reference
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

## Output Path (IMPORTANT)

Always save images to `persona/avatar/` with a descriptive filename:
```
--output persona/avatar/{descriptive_name}.png
```
Example: `--output persona/avatar/casual_edit.png`

## Post-Edit (MANDATORY — DO NOT SKIP)

After every successful image edit, you MUST execute these steps:

1. Call `mcp__persona__add_persona_image` with:
   - `file_path`: the output image path (must start with `persona/avatar/`)
   - `label`: short description of the image
   - `image_type`: "avatar" or "scene"
   - `description`: detailed description of what was generated
2. Report the registration result to the user

This is NOT optional. Every generated image MUST be registered. Failure to register is a bug.

## Pre-Edit (MANDATORY — DO FIRST)

Before editing, you MUST follow these steps:

1. Call `mcp__persona__get_avatar_reference` to get the current reference image path
2. If `--input` was NOT specified by the user, use the reference image as input
3. If no reference image is set, inform the user and suggest using nanobanana-pro to generate one first
4. **Read the reference image** to determine its visual style (photorealistic, anime, illustration, etc). Match the output style exactly — do not override with a different style unless explicitly requested

This ensures all edits are based on the user's chosen reference image for visual consistency.

## Error Handling

- If `GEMINI_API_KEY` not set: Script will prompt to set it
- If API error: Error message will be displayed

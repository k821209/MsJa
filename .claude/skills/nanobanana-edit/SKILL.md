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

## ⚠️ STEP 1: GET REFERENCE IMAGE (DO THIS FIRST — MANDATORY)

**You MUST do this BEFORE anything else. No exceptions.**

1. Call `mcp__persona__get_avatar_reference` to get the reference image path
2. Use the returned `reference_path` as `--input` (UNLESS the user explicitly provided a different `--input`)
3. If `reference_path` is null/empty → STOP and tell the user: "No reference image set. Please set one in the Images page, or use /nanobanana-pro to generate one first."
4. **Read the reference image** to check its visual style (photorealistic, anime, illustration, etc). Your output MUST match this style exactly.

**DO NOT skip this step. DO NOT guess the input path. DO NOT use a hardcoded path.**

## STEP 2: EDIT

```bash
source ~/.zshrc && python3 .claude/skills/nanobanana-edit/scripts/edit.py \
  --input {reference_path} "EDITING_INSTRUCTION" \
  --output persona/avatar/{descriptive_name}.png
```

### Arguments

| Argument | Default | Options | Description |
|----------|---------|---------|-------------|
| --input | (from reference) | any image file | Source image to edit (PNG, JPG, WEBP) |
| prompt | (required) | - | Editing instruction |
| --aspect | (preserve) | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 | Output aspect ratio |
| --size | 4K | 1K, 2K, 4K | Output resolution |
| --output | persona/avatar/ | must be under persona/avatar/ | Output file path |

## STEP 3: REGISTER (MANDATORY — DO NOT SKIP)

After every successful edit, you MUST:

1. Call `mcp__persona__add_persona_image` with:
   - `file_path`: the output path (must start with `persona/avatar/`)
   - `label`: short description
   - `image_type`: "avatar" or "scene"
   - `description`: what was edited
2. Report the result to the user

Failure to register is a bug.

## Editing Capabilities

### Element Modification
```bash
--input ref.png "Remove the background and replace with white" --output persona/avatar/clean.png
```

### Inpainting (Partial Edit)
```bash
--input ref.png "Change only the hair color to blonde. Keep everything else exactly the same" --output persona/avatar/blonde.png
```

### Style Transfer
```bash
--input ref.png "Transform into watercolor painting style" --output persona/avatar/watercolor.png
```

## Tips

1. **Be specific**: "Change the sky to sunset orange" > "make it prettier"
2. **Preserve context**: Add "Keep everything else exactly the same" for targeted edits
3. **Iterative editing**: Make small changes step by step for complex edits

## Error Handling

- If `GEMINI_API_KEY` not set: Script will prompt to set it
- If API error: Error message will be displayed

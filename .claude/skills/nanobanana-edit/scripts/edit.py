#!/usr/bin/env python3
"""Edit images using Google Nano Banana Pro API (Gemini 3 Pro Image Preview)."""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent"


def _load_key_from_dotenv() -> str | None:
    """Try to load GEMINI_API_KEY from project .env file."""
    for env_path in [Path.cwd() / ".env", Path(__file__).parent.parent.parent.parent.parent / ".env"]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return None

ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
IMAGE_SIZES = ["1K", "2K", "4K"]
SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def get_mime_type(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }
    return mime_types.get(ext, "image/png")


def load_image_as_base64(file_path: Path) -> tuple[str, str]:
    if not file_path.exists():
        raise FileNotFoundError(f"Image file not found: {file_path}")
    if file_path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format. Use: {', '.join(SUPPORTED_FORMATS)}")
    mime_type = get_mime_type(file_path)
    image_data = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return image_data, mime_type


def edit_image(input_path: str, prompt: str, aspect_ratio: str = None,
               image_size: str = "4K", output_path: str = "edited_image.png",
               api_key: str = None) -> bool:
    api_key = api_key or os.environ.get("GEMINI_API_KEY") or _load_key_from_dotenv()
    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        print("Set it via: Web Dashboard > Settings, or export GEMINI_API_KEY='your-key'")
        return False

    if aspect_ratio and aspect_ratio not in ASPECT_RATIOS:
        print(f"Error: Invalid aspect ratio. Choose from: {', '.join(ASPECT_RATIOS)}")
        return False

    if image_size not in IMAGE_SIZES:
        print(f"Error: Invalid image size. Choose from: {', '.join(IMAGE_SIZES)}")
        return False

    input_file = Path(input_path)
    try:
        image_data, mime_type = load_image_as_base64(input_file)
        print(f"Loaded image: {input_file.name} ({mime_type})")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return False

    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_data
                    }
                }
            ]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"]
        }
    }

    if aspect_ratio:
        payload["generationConfig"]["imageConfig"] = {
            "aspectRatio": aspect_ratio
        }

    print(f"Editing with instruction: {prompt[:80]}...")

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()

        if "candidates" in data:
            candidate = data["candidates"][0]
            if "content" not in candidate or "parts" not in candidate.get("content", {}):
                print(f"Candidate has no content/parts. Candidate keys: {list(candidate.keys())}")
                if "finishReason" in candidate:
                    print(f"Finish reason: {candidate['finishReason']}")
                print(json.dumps(candidate, indent=2)[:500])
                return False
            for part in candidate["content"]["parts"]:
                if "inlineData" in part:
                    img_data = base64.b64decode(part["inlineData"]["data"])
                    output_file = Path(output_path)
                    output_file.write_bytes(img_data)
                    print(f"Edited image saved to: {output_file.absolute()}")
                    print(f"File size: {len(img_data) / 1024:.1f} KB")
                    return True
                elif "text" in part:
                    print(f"Model response: {part['text'][:200]}")
            print("No image data in response.")
            return False
        elif "error" in data:
            print(f"API Error: {data['error']['message']}")
            return False
        else:
            print("Unexpected response format:")
            print(json.dumps(data, indent=2)[:500])
            return False

    except requests.exceptions.Timeout:
        print("Error: Request timed out. Try again.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Edit images using Google Nano Banana Pro API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("prompt", help="Editing instruction")
    parser.add_argument("--input", "-i", required=True,
                        help="Input image file (PNG, JPG, WEBP)")
    parser.add_argument("--aspect", default=None, choices=ASPECT_RATIOS,
                        help="Output aspect ratio (default: preserve original)")
    parser.add_argument("--size", default="4K", choices=IMAGE_SIZES,
                        help="Image size (default: 4K)")
    parser.add_argument("--output", "-o", default="edited_image.png",
                        help="Output filename (default: edited_image.png)")
    parser.add_argument("--api-key", help="Gemini API key (or set GEMINI_API_KEY env var)")

    args = parser.parse_args()

    success = edit_image(
        input_path=args.input,
        prompt=args.prompt,
        aspect_ratio=args.aspect,
        image_size=args.size,
        output_path=args.output,
        api_key=args.api_key
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

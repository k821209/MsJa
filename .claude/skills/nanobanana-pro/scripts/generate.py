#!/usr/bin/env python3
"""Generate images using Google Nano Banana Pro API (Gemini 3 Pro Image Preview)."""

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

LANG_PREFIXES = {
    "ko": (
        "CRITICAL: ALL text labels, headers, titles, and descriptions in this image "
        "MUST be written in Korean (한국어/한글). Do NOT use English for any labels or headers. "
        "Only proper nouns and technical acronyms (e.g., DNA, RNA, KEGG, API) may remain in English. "
        "Every other visible text element MUST use Korean characters.\n\n"
    ),
    "ja": (
        "CRITICAL: ALL text labels, headers, titles, and descriptions in this image "
        "MUST be written in Japanese (日本語). Do NOT use English for any labels or headers. "
        "Only proper nouns and technical acronyms may remain in English. "
        "Every other visible text element MUST use Japanese characters.\n\n"
    ),
    "zh": (
        "CRITICAL: ALL text labels, headers, titles, and descriptions in this image "
        "MUST be written in Chinese (中文). Do NOT use English for any labels or headers. "
        "Only proper nouns and technical acronyms may remain in English. "
        "Every other visible text element MUST use Chinese characters.\n\n"
    ),
}


def generate_image(prompt: str, aspect_ratio: str = "16:9", image_size: str = "2K",
                   output_path: str = "generated_image.png", api_key: str = None,
                   lang: str = None) -> bool:
    """Generate an image using Nano Banana Pro API."""

    if lang and lang in LANG_PREFIXES:
        prompt = LANG_PREFIXES[lang] + prompt
        print(f"Language override: {lang} — non-English text enforcement enabled")

    api_key = api_key or os.environ.get("GEMINI_API_KEY") or _load_key_from_dotenv()
    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        print("Set it via: Web Dashboard > Settings, or export GEMINI_API_KEY='your-key'")
        return False

    if aspect_ratio not in ASPECT_RATIOS:
        print(f"Error: Invalid aspect ratio. Choose from: {', '.join(ASPECT_RATIOS)}")
        return False

    if image_size not in IMAGE_SIZES:
        print(f"Error: Invalid image size. Choose from: {', '.join(IMAGE_SIZES)}")
        return False

    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size
            }
        }
    }

    print(f"Generating image with prompt: {prompt[:50]}...")
    print(f"Settings: {aspect_ratio} aspect ratio, {image_size} resolution")

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        if "candidates" in data:
            for part in data["candidates"][0]["content"]["parts"]:
                if "inlineData" in part:
                    img_data = base64.b64decode(part["inlineData"]["data"])
                    output_file = Path(output_path)
                    output_file.write_bytes(img_data)
                    print(f"Image saved to: {output_file.absolute()}")
                    print(f"File size: {len(img_data) / 1024:.1f} KB")
                    return True
            print("No image data in response")
            return False
        elif "error" in data:
            print(f"API Error: {data['error']['message']}")
            return False
        else:
            print("Unexpected response format:")
            print(json.dumps(data, indent=2))
            return False

    except requests.exceptions.Timeout:
        print("Error: Request timed out. Try again.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using Google Nano Banana Pro API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "a cute robot reading a book"
  %(prog)s "scientific diagram of DNA" --aspect 3:4 --size 4K
  %(prog)s "modern logo design" --output logo.png
        """
    )
    parser.add_argument("prompt", help="Image generation prompt")
    parser.add_argument("--aspect", default="16:9", choices=ASPECT_RATIOS,
                        help="Aspect ratio (default: 16:9)")
    parser.add_argument("--size", default="2K", choices=IMAGE_SIZES,
                        help="Image size (default: 2K)")
    parser.add_argument("--output", "-o", default="generated_image.png",
                        help="Output filename (default: generated_image.png)")
    parser.add_argument("--api-key", help="Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--lang", choices=list(LANG_PREFIXES.keys()),
                        help="Force text labels in this language (ko, ja, zh)")

    args = parser.parse_args()

    success = generate_image(
        prompt=args.prompt,
        aspect_ratio=args.aspect,
        image_size=args.size,
        output_path=args.output,
        api_key=args.api_key,
        lang=args.lang
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

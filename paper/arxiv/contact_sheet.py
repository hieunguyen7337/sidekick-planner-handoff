#!/usr/bin/env python3
"""
contact_sheet.py - Generate contact sheets from preview images.

Usage:
    contact_sheet.py [--per-sheet 8] [--cols 4] [--label|--no-label] --out PREFIX IMG [IMG ...]
"""

import argparse
import math
import os
import re
import sys
from PIL import Image, ImageDraw


def parse_page_number(path: str) -> int:
    """Extract trailing page number from filename for natural sorting."""
    base = os.path.basename(path)
    # Match trailing number after - or _ before extension
    m = re.search(r'[-_](\d+)(?:\.[a-zA-Z0-9]+)?$', base)
    if m:
        return int(m.group(1))
    # Match any trailing digits before extension
    m = re.search(r'(\d+)(?:\.[a-zA-Z0-9]+)?$', base)
    if m:
        return int(m.group(1))
    return 0


def natural_sort_key(path: str):
    """Sort key using trailing page number, falling back to full path."""
    return (parse_page_number(path), path)


def get_resample_filter():
    """Get LANCZOS resampling filter compatible with multiple Pillow versions."""
    resampling = getattr(Image, 'Resampling', Image)
    return getattr(resampling, 'LANCZOS', getattr(Image, 'ANTIALIAS', Image.BICUBIC))


def get_text_dimensions(draw: ImageDraw.ImageDraw, text: str):
    """Get width and height of text across Pillow versions."""
    if hasattr(draw, 'textbbox'):
        bbox = draw.textbbox((0, 0), text)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    if hasattr(draw, 'textsize'):
        return draw.textsize(text)
    return (len(text) * 6, 11)


def main():
    parser = argparse.ArgumentParser(description="Create contact sheets from page images.")
    parser.add_argument('--per-sheet', type=int, default=8, help='Pages per sheet (default: 8)')
    parser.add_argument('--cols', type=int, default=4, help='Columns per sheet grid (default: 4)')
    parser.add_argument('--label', dest='label', action='store_true', default=True, help='Draw page number label (default)')
    parser.add_argument('--no-label', dest='label', action='store_false', help='Disable page number label')
    parser.add_argument('--out', type=str, required=True, help='Output prefix (e.g., /path/to/sheet)')
    parser.add_argument('images', nargs='*', help='Input image file paths')

    args = parser.parse_args()

    if not args.images:
        print("ERROR: No input images provided.", file=sys.stderr)
        sys.exit(2)

    if args.per_sheet < 1:
        print("ERROR: --per-sheet must be >= 1", file=sys.stderr)
        sys.exit(2)

    if args.cols < 1:
        print("ERROR: --cols must be >= 1", file=sys.stderr)
        sys.exit(2)

    # Sort images naturally by trailing page number
    sorted_image_paths = sorted(args.images, key=natural_sort_key)

    gutter = 8
    resample = get_resample_filter()

    # Load first image to determine target width
    try:
        first_img = Image.open(sorted_image_paths[0])
        target_width = first_img.width
        first_img.close()
    except Exception as e:
        print(f"ERROR: Failed to open first image '{sorted_image_paths[0]}': {e}", file=sys.stderr)
        sys.exit(2)

    # Chunk into sheets
    num_sheets = math.ceil(len(sorted_image_paths) / args.per_sheet)

    for sheet_idx in range(num_sheets):
        sheet_num = sheet_idx + 1
        chunk_paths = sorted_image_paths[sheet_idx * args.per_sheet : (sheet_idx + 1) * args.per_sheet]

        # Load and resize images for this sheet
        sheet_items = []  # list of (Image, page_num)
        for p in chunk_paths:
            try:
                im = Image.open(p)
                im = im.convert('RGB')
                if im.width != target_width:
                    scale = target_width / float(im.width)
                    new_height = int(round(im.height * scale))
                    im_resized = im.resize((target_width, new_height), resample=resample)
                    im.close()
                    im = im_resized
                page_num = parse_page_number(p)
                sheet_items.append((im, page_num))
            except Exception as e:
                print(f"ERROR: Failed to process image '{p}': {e}", file=sys.stderr)
                sys.exit(2)

        # Calculate grid layout
        num_items = len(sheet_items)
        cols = min(args.cols, len(sheet_items))
        num_rows = math.ceil(num_items / cols)

        # Calculate row heights
        row_heights = []
        for r in range(num_rows):
            row_items = sheet_items[r * cols : (r + 1) * cols]
            max_h = max(item[0].height for item in row_items)
            row_heights.append(max_h)

        sheet_width = cols * target_width + (cols + 1) * gutter
        sheet_height = sum(row_heights) + (num_rows + 1) * gutter

        sheet_img = Image.new("RGB", (sheet_width, sheet_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(sheet_img)

        # Place tiles
        for idx, (im, page_num) in enumerate(sheet_items):
            r = idx // cols
            c = idx % cols

            x = gutter + c * (target_width + gutter)
            y = gutter + sum(row_heights[:r]) + r * gutter

            sheet_img.paste(im, (x, y))

            if args.label:
                label_text = f"p.{page_num}" if page_num > 0 else f"#{idx + 1}"
                tw, th = get_text_dimensions(draw, label_text)
                pad_x, pad_y = 3, 2
                box = [
                    x + 2,
                    y + 2,
                    x + 2 + tw + 2 * pad_x,
                    y + 2 + th + 2 * pad_y
                ]
                draw.rectangle(box, fill=(255, 255, 255), outline=(0, 0, 0))
                draw.text((x + 2 + pad_x, y + 2 + pad_y), label_text, fill=(0, 0, 0))

            im.close()

        out_path = f"{args.out}_{sheet_num:02d}.png"
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        sheet_img.save(out_path, format="PNG")
        sheet_img.close()

        page_numbers = [item[1] for item in sheet_items]
        if len(page_numbers) == 1:
            page_range_str = f"page {page_numbers[0]}"
        else:
            page_range_str = f"pages {page_numbers[0]}-{page_numbers[-1]}"

        print(f"Wrote {out_path} ({page_range_str})")


if __name__ == '__main__':
    main()

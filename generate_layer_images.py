#!/usr/bin/env python3
"""Render Vial (.vil) keyboard layouts as beautiful Corne-style images."""

import argparse
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


MOD_LABELS = {
    "LALT": "⌥",
    "RALT": "⌥",
    "LGUI": "⌘",
    "RGUI": "⌘",
    "LCTL": "⌃",
    "RCTL": "⌃",
    "LSFT": "⇧",
    "RSFT": "⇧",
}

# Layer colors - distinct colors for each layer
LAYER_COLORS = {
    0: (100, 120, 140),    # Base layer - slate blue-gray
    1: (76, 175, 80),      # Layer 1 - green
    2: (33, 150, 243),     # Layer 2 - blue
    3: (255, 152, 0),      # Layer 3 - orange
    4: (156, 39, 176),     # Layer 4 - purple
    5: (244, 67, 54),      # Layer 5 - red
    6: (0, 188, 212),      # Layer 6 - cyan
    7: (255, 193, 7),      # Layer 7 - amber
}

# Corne column stagger offsets (in fraction of key height)
CORNE_STAGGER = [0.5, 0.25, 0, 0.125, 0.25, 0.25]


def load_font(size):
    for name in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "DejaVuSans.ttf",
        "Arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def unwrap_mods(key):
    """Extract modifier wrappers like LALT(LGUI(KC_X)) -> ([⌥, ⌘], KC_X)"""
    mods = []
    inner = key
    while True:
        match = re.match(r"^([A-Z0-9_]+)\((.+)\)$", inner)
        if not match:
            break
        mod = match.group(1)
        if mod in MOD_LABELS:
            mods.append(MOD_LABELS[mod])
            inner = match.group(2)
            continue
        break
    return mods, inner


KEY_LABELS = {
    "GESC": "~\nEsc",
    "ESC": "Esc",
    "ESCAPE": "Esc",
    "TAB": "Tab",
    "SPACE": "Space",
    "ENTER": "Enter",
    "RETURN": "Enter",
    "BSPACE": "Bksp",
    "BSPC": "Bksp",
    "DELETE": "Del",
    "DEL": "Del",
    "LSHIFT": "LShift",
    "RSHIFT": "RShift",
    "LSFT": "LShift",
    "RSFT": "RShift",
    "LCTRL": "LCtrl",
    "RCTRL": "RCtrl",
    "LCTL": "LCtrl",
    "RCTL": "RCtrl",
    "LGUI": "LGui",
    "RGUI": "RGui",
    "LALT": "LAlt",
    "RALT": "RAlt",
    "SCOLON": ":\n;",
    "SCLN": ":\n;",
    "QUOTE": "\"\n'",
    "QUOT": "\"\n'",
    "COMMA": "<\n,",
    "COMM": "<\n,",
    "DOT": ">\n.",
    "SLASH": "?\n/",
    "SLSH": "?\n/",
    "BSLASH": "|\n\\",
    "BSLS": "|\n\\",
    "MINUS": "_\n-",
    "MINS": "_\n-",
    "EQUAL": "+\n=",
    "EQL": "+\n=",
    "LBRACKET": "{\n[",
    "LBRC": "{\n[",
    "RBRACKET": "}\n]",
    "RBRC": "}\n]",
    "GRAVE": "~\n`",
    "GRV": "~\n`",
    "LEFT": "←",
    "RIGHT": "→",
    "UP": "↑",
    "DOWN": "↓",
    "PGUP": "PgUp",
    "PGDOWN": "PgDn",
    "PGDN": "PgDn",
    "HOME": "Home",
    "END": "End",
    "TRNS": "▽",
    "TRANS": "▽",
    "NO": "",
    "BTN1": "🖱L",
    "BTN2": "🖱R",
    "BTN3": "🖱M",
    "BTN4": "🖱4",
    "BTN5": "🖱5",
    "MS_L": "🖱←",
    "MS_R": "🖱→",
    "MS_U": "🖱↑",
    "MS_D": "🖱↓",
    "WH_U": "⚙↑",
    "WH_D": "⚙↓",
    "WH_L": "⚙←",
    "WH_R": "⚙→",
    "ACL0": "Acl0",
    "ACL1": "Acl1",
    "ACL2": "Acl2",
    "KP_PLUS": "+",
    "KP_MINUS": "-",
    "KP_ASTERISK": "*",
    "KP_SLASH": "/",
    "KP_EQUAL": "=",
    "UNDO": "Undo",
    "CUT": "Cut",
    "COPY": "Copy",
    "PSTE": "Paste",
    "AGIN": "Again",
}

SHIFT_SYMBOLS = {
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "MINUS": "_",
    "EQUAL": "+",
    "LBRACKET": "{",
    "RBRACKET": "}",
    "SCOLON": ":",
    "QUOTE": '"',
    "COMMA": "<",
    "DOT": ">",
    "SLASH": "?",
    "BSLASH": "|",
    "GRAVE": "~",
}


def get_layer_from_key(key):
    """Extract layer number from layer-switching keys like MO(1), LT2(...), etc."""
    if not isinstance(key, str):
        return None
    
    # MO(x) - momentary layer
    mo_match = re.match(r"^MO\((\d+)\)$", key)
    if mo_match:
        return int(mo_match.group(1))
    
    # LTx(...) - layer tap
    lt_match = re.match(r"^LT(\d+)\(.+\)$", key)
    if lt_match:
        return int(lt_match.group(1))
    
    # DF(x) - default layer
    df_match = re.match(r"^DF\((\d+)\)$", key)
    if df_match:
        return int(df_match.group(1))
    
    # TG(x) - toggle layer
    tg_match = re.match(r"^TG\((\d+)\)$", key)
    if tg_match:
        return int(tg_match.group(1))
    
    return None


def normalize_key_label(key):
    if key == -1 or key is None:
        return ""
    if not isinstance(key, str):
        return str(key)

    mods, inner = unwrap_mods(key)

    # Handle LT and MO layer keys
    lt_match = re.match(r"^LT(\d+)\((.+)\)$", inner)
    if lt_match:
        layer_num = lt_match.group(1)
        held_key = lt_match.group(2)
        tap_label = normalize_key_label(held_key)
        return f"LT {layer_num}\n{tap_label}"

    mo_match = re.match(r"^MO\((\d+)\)$", inner)
    if mo_match:
        return f"MO({mo_match.group(1)})"

    df_match = re.match(r"^DF\((\d+)\)$", inner)
    if df_match:
        return f"DF({df_match.group(1)})"

    tg_match = re.match(r"^TG\((\d+)\)$", inner)
    if tg_match:
        return f"TG({tg_match.group(1)})"

    # Handle shifted keys with proper symbols
    shift_match = re.match(r"^LSFT\(KC_(.+)\)$", inner) or re.match(r"^RSFT\(KC_(.+)\)$", inner)
    if shift_match:
        base = shift_match.group(1)
        if base in SHIFT_SYMBOLS:
            symbol = SHIFT_SYMBOLS[base]
            if mods:
                return "".join(mods) + symbol
            return symbol

    # Strip KC_ prefix
    if inner.startswith("KC_"):
        inner = inner[3:]

    # Check for known labels
    if inner in KEY_LABELS:
        label = KEY_LABELS[inner]
        if mods:
            return "".join(mods) + "\n" + label
        return label

    # Single letters/numbers
    if len(inner) == 1:
        if mods:
            return "".join(mods) + inner
        return inner

    # F-keys
    if re.match(r"^F\d+$", inner):
        if mods:
            return "".join(mods) + inner
        return inner

    # Fallback
    label = inner.replace("_", " ")
    if mods:
        return "".join(mods) + "\n" + label
    return label


def draw_rotated_key(cx, cy, w, h, label, font, key_color, border_color, text_color, rotation):
    """Draw a rotated key and return as an image with position."""
    padding = 30
    key_img = Image.new("RGBA", (int(w) + padding * 2, int(h) + padding * 2), (0, 0, 0, 0))
    key_draw = ImageDraw.Draw(key_img)
    
    kx, ky = padding, padding
    rect = (kx, ky, kx + w, ky + h)
    
    # Draw key background
    key_draw.rounded_rectangle(rect, radius=6, fill=key_color, outline=border_color, width=2)
    
    # Draw label
    if label:
        lines = label.split("\n")
        line_height = font.size + 2
        total_h = len(lines) * line_height
        start_y = ky + (h - total_h) / 2
        
        for line in lines:
            bbox = key_draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            tx = kx + (w - text_w) / 2
            key_draw.text((tx, start_y), line, font=font, fill=text_color)
            start_y += line_height
    
    # Rotate
    key_img = key_img.rotate(rotation, expand=True, resample=Image.BICUBIC)
    
    pos = (int(cx - key_img.width / 2), int(cy - key_img.height / 2))
    return key_img, pos


def draw_key(draw, cx, cy, w, h, label, font, key_color, border_color, text_color):
    """Draw a single key centered at (cx, cy)."""
    half_w, half_h = w / 2, h / 2
    rect = (cx - half_w, cy - half_h, cx + half_w, cy + half_h)
    
    draw.rounded_rectangle(rect, radius=6, fill=key_color, outline=border_color, width=2)
    
    if label:
        lines = label.split("\n")
        line_height = font.size + 2
        total_h = len(lines) * line_height
        start_y = cy - half_h + (h - total_h) / 2
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            tx = cx - text_w / 2
            draw.text((tx, start_y), line, font=font, fill=text_color)
            start_y += line_height


def render_corne_layer(layer, layer_idx, cell_w=70, cell_h=62, gap=8):
    """Render a single layer as a Corne-style split keyboard on white background."""
    # Colors
    bg_color = (255, 255, 255, 0)  # Transparent for layer, white for final
    default_key_color = (75, 80, 90)
    border_color = (55, 60, 70)
    text_color = (255, 255, 255)
    
    half_cols = 6
    split_gap = cell_w * 2.0
    
    stagger_px = [s * cell_h for s in CORNE_STAGGER]
    max_stagger = max(stagger_px)
    
    # Thumb key spacing - wider to prevent overlap
    thumb_gap = cell_w + gap + 12  # Extra spacing between thumb keys
    
    # Canvas dimensions - extra space for thumb cluster
    layer_w = int(half_cols * (cell_w + gap) * 2 + split_gap + 140)
    layer_h = int(max_stagger + 3 * (cell_h + gap) + cell_h * 2.5 + 80)
    
    img = Image.new("RGBA", (layer_w, layer_h), bg_color)
    draw = ImageDraw.Draw(img)
    font = load_font(14)
    
    ox_left = 60
    ox_right = ox_left + half_cols * (cell_w + gap) + split_gap
    oy = 20 + max_stagger
    
    rotated_keys = []
    
    # Build override map from row 3 (thumb row)
    # Positions 0,1,9,10,11 override keys in main rows (0-2)
    override_map = {}  # (row, col) -> key
    if len(layer) > 3:
        thumb_row = layer[3]
        # Position 0: KC_LBRACKET -> row 1, col 6 (first right key of middle row)
        if len(thumb_row) > 0 and thumb_row[0] != -1:
            override_map[(1, 6)] = thumb_row[0]
        # Position 1: KC_LCTRL -> row 2, col 6 (first right key of bottom row, filling gap)
        if len(thumb_row) > 1 and thumb_row[1] != -1:
            override_map[(2, 6)] = thumb_row[1]
        # Position 9: KC_RCTRL -> row 0, col 11 (last right key of top row)
        if len(thumb_row) > 9 and thumb_row[9] != -1:
            override_map[(0, 11)] = thumb_row[9]
        # Position 10: KC_QUOTE -> row 1, col 11 (last right key of middle row)
        # This shows " ' at the end of middle row
        if len(thumb_row) > 10 and thumb_row[10] != -1:
            override_map[(1, 11)] = thumb_row[10]
        # Position 11: KC_RSHIFT -> row 2, col 11 (last right key of bottom row)
        if len(thumb_row) > 11 and thumb_row[11] != -1:
            override_map[(2, 11)] = thumb_row[11]
    
    # Draw alpha rows (0-2)
    for r in range(min(len(layer), 3)):
        row_data = layer[r] if r < len(layer) else []
        
        # Left half: columns 0-5
        for c in range(min(half_cols, len(row_data))):
            # Check for override from row 3
            key = override_map.get((r, c), row_data[c])
            if key == -1:
                continue
            label = normalize_key_label(key)
            stagger = stagger_px[c] if c < len(stagger_px) else 0
            cx = ox_left + c * (cell_w + gap) + cell_w / 2
            cy = oy + r * (cell_h + gap) + cell_h / 2 + stagger
            
            # Check if this is a layer key
            target_layer = get_layer_from_key(key)
            if target_layer is not None:
                key_color = LAYER_COLORS.get(target_layer, default_key_color)
            else:
                key_color = default_key_color
            
            draw_key(draw, cx, cy, cell_w, cell_h, label, font, key_color, border_color, text_color)
        
        # Right half: columns 6-11 (mirrored stagger)
        right_col_idx = 0
        for c in range(half_cols, min(len(row_data), 12)):
            # Determine which key to use: override takes precedence over original
            if (r, c) in override_map:
                # Use override key
                key = override_map[(r, c)]
            elif c < len(row_data) and row_data[c] != -1:
                # Use original key (not a gap)
                key = row_data[c]
            else:
                # Gap (-1) with no override, skip this column
                continue
            
            # Normalize and draw the key
            label = normalize_key_label(key)
            if label:  # Only draw if label is not empty
                rc = right_col_idx
                stagger = stagger_px[half_cols - 1 - rc] if (half_cols - 1 - rc) < len(stagger_px) and rc < half_cols else 0
                cx = ox_right + rc * (cell_w + gap) + cell_w / 2
                cy = oy + r * (cell_h + gap) + cell_h / 2 + stagger
                
                target_layer = get_layer_from_key(key)
                if target_layer is not None:
                    key_color = LAYER_COLORS.get(target_layer, default_key_color)
                else:
                    key_color = default_key_color
                
                draw_key(draw, cx, cy, cell_w, cell_h, label, font, key_color, border_color, text_color)
            
            # Always increment right_col_idx after processing a column
            right_col_idx += 1
    
    # Draw thumb cluster (row 3) - handle all 12 positions
    if len(layer) > 3:
        thumb_row_data = layer[3]
        thumb_y_base = oy + 3 * (cell_h + gap) + cell_h * 0.5
        
        # Extract thumb keys - based on reference: left has positions 3,4,5 and right has 6,7,8
        # But we also need to handle positions 0,1,9,10,11 which might be in main rows or thumb
        
        # Left thumb keys: positions 3, 4, 5 (MO(5), Bksp, Del)
        left_thumb_keys = []
        if len(thumb_row_data) > 5:
            left_thumb_keys = [thumb_row_data[3], thumb_row_data[4], thumb_row_data[5]]
        left_thumb_keys = [k for k in left_thumb_keys if k != -1]
        
        # Position left thumb keys
        thumb_start_x = ox_left + 3.0 * (cell_w + gap)
        thumb_positions_left = [
            (thumb_start_x, thumb_y_base, 0),                           # MO(5) - inner
            (thumb_start_x + thumb_gap, thumb_y_base + cell_h * 0.3, 12),  # Bksp - middle
            (thumb_start_x + thumb_gap * 2, thumb_y_base + cell_h * 0.7, 20),  # Del - outer
        ]
        
        for i, key in enumerate(left_thumb_keys[:3]):
            if i >= len(thumb_positions_left):
                break
            label = normalize_key_label(key)
            tx, ty, rot = thumb_positions_left[i]
            
            target_layer = get_layer_from_key(key)
            if target_layer is not None:
                key_color = LAYER_COLORS.get(target_layer, default_key_color)
            else:
                key_color = default_key_color
            
            if rot != 0:
                rot_img, pos = draw_rotated_key(tx, ty, cell_w, cell_h, label, font, 
                                                key_color, border_color, text_color, rot)
                rotated_keys.append((rot_img, pos))
            else:
                draw_key(draw, tx, ty, cell_w, cell_h, label, font, key_color, border_color, text_color)
        
        # Right thumb keys: positions 6, 7, 8 (Enter, LT 2 Space, MO(3))
        right_thumb_keys = []
        if len(thumb_row_data) > 8:
            right_thumb_keys = [thumb_row_data[6], thumb_row_data[7], thumb_row_data[8]]
        right_thumb_keys = [k for k in right_thumb_keys if k != -1]
        
        # Position right thumb keys
        thumb_start_x_r = ox_right
        thumb_positions_right = [
            (thumb_start_x_r, thumb_y_base, 0),                          # Enter - inner
            (thumb_start_x_r + thumb_gap, thumb_y_base + cell_h * 0.3, -12),  # LT 2 Space - middle
            (thumb_start_x_r + thumb_gap * 2, thumb_y_base + cell_h * 0.7, -20),  # MO(3) - outer
        ]
        
        for i, key in enumerate(right_thumb_keys[:3]):
            if i >= len(thumb_positions_right):
                break
            label = normalize_key_label(key)
            tx, ty, rot = thumb_positions_right[i]
            
            target_layer = get_layer_from_key(key)
            if target_layer is not None:
                key_color = LAYER_COLORS.get(target_layer, default_key_color)
            else:
                key_color = default_key_color
            
            if rot != 0:
                rot_img, pos = draw_rotated_key(tx, ty, cell_w, cell_h, label, font,
                                                key_color, border_color, text_color, rot)
                rotated_keys.append((rot_img, pos))
            else:
                draw_key(draw, tx, ty, cell_w, cell_h, label, font, key_color, border_color, text_color)
        
    
    # Composite rotated keys
    for rot_img, pos in rotated_keys:
        img.paste(rot_img, pos, rot_img)
    
    return img


def render_all_layers(layout, title):
    """Render all layers in a grid layout with white background."""
    # Filter active layers
    active_layers = []
    for idx, layer in enumerate(layout):
        has_content = False
        for row in layer:
            for key in row:
                if key != -1 and key != "KC_TRNS" and key != "KC_NO":
                    has_content = True
                    break
            if has_content:
                break
        if has_content:
            active_layers.append((idx, layer))
    
    if not active_layers:
        active_layers = [(i, l) for i, l in enumerate(layout)]
    
    # Render each layer
    layer_imgs = []
    for idx, layer in active_layers:
        layer_img = render_corne_layer(layer, idx)
        layer_imgs.append((idx, layer_img))
    
    if not layer_imgs:
        raise SystemExit("No layers to render")
    
    # Grid layout
    n_layers = len(layer_imgs)
    grid_cols = 2 if n_layers > 2 else 1
    grid_rows = math.ceil(n_layers / grid_cols)
    
    sample_w, sample_h = layer_imgs[0][1].size
    header_h = 44
    border_width = 3
    frame_padding = 12
    padding = 40
    layer_gap = 35
    
    # Total frame size for each keyboard
    frame_w = sample_w + frame_padding * 2
    frame_h = sample_h + header_h + frame_padding + border_width
    
    img_w = padding * 2 + grid_cols * frame_w + (grid_cols - 1) * layer_gap
    img_h = padding * 2 + grid_rows * frame_h + (grid_rows - 1) * layer_gap
    
    # White background
    final_img = Image.new("RGB", (img_w, img_h), (255, 255, 255))
    draw = ImageDraw.Draw(final_img)
    font_title = load_font(20)
    
    for i, (layer_idx, layer_img) in enumerate(layer_imgs):
        col = i % grid_cols
        row = i // grid_cols
        
        # Frame position
        fx = padding + col * (frame_w + layer_gap)
        fy = padding + row * (frame_h + layer_gap)
        
        layer_color = LAYER_COLORS.get(layer_idx, (100, 100, 100))
        
        # Draw frame border (rounded rectangle)
        frame_rect = (fx, fy, fx + frame_w, fy + frame_h)
        draw.rounded_rectangle(frame_rect, radius=12, fill=(245, 247, 250), outline=(200, 205, 215), width=border_width)
        
        # Draw colored header bar
        header_rect = (fx + border_width, fy + border_width, fx + frame_w - border_width, fy + header_h)
        draw.rounded_rectangle(header_rect, radius=9, fill=layer_color)
        # Fill bottom corners of header to make it flat at bottom
        draw.rectangle((fx + border_width, fy + header_h - 10, fx + frame_w - border_width, fy + header_h), fill=layer_color)
        
        # Draw layer title in white on colored header
        layer_title = f"Layer {layer_idx}"
        bbox = draw.textbbox((0, 0), layer_title, font=font_title)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        tx = fx + (frame_w - text_w) / 2
        ty = fy + (header_h - text_h) / 2
        draw.text((tx, ty), layer_title, font=font_title, fill=(255, 255, 255))
        
        # Paste keyboard image inside frame
        kx = fx + frame_padding
        ky = fy + header_h + frame_padding // 2
        final_img.paste(layer_img, (kx, ky), layer_img)
    
    return final_img


def main():
    parser = argparse.ArgumentParser(description="Render Vial layout as Corne-style keyboard images.")
    parser.add_argument("vial_file", help="Path to the .vil file")
    parser.add_argument("--out-dir", default="layers images", help="Output directory")
    args = parser.parse_args()
    
    vial_path = Path(args.vial_file)
    data = json.loads(vial_path.read_text())
    layout = data.get("layout", [])
    if not layout:
        raise SystemExit(f"No layout found in {vial_path}")
    
    title = vial_path.stem
    img = render_all_layers(layout, title)
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{title}.png"
    img.save(out_path, "PNG")
    print(out_path)


if __name__ == "__main__":
    main()

"""Add temporary debug logging to add_clip to trace thumbnail flow."""
lines = open('aivideostudio/gui/panels/timeline_panel.py', encoding='utf-8').readlines()

# Find add_clip and add debug log after line 586
new_lines = []
for i, l in enumerate(lines):
    new_lines.append(l)
    # After "if track["type"] == "video" and clip_data.get("path"):" line
    if i == 585:  # line 586 (0-indexed: 585)
        indent = '            '
        new_lines.append(f'{indent}logger.info(f"DEBUG add_clip: track_type={{track[\'type\']}} path={{clip_data.get(\'path\',\'NONE\')}} ffmpeg={{self._ffmpeg_path}}")\n')

with open('aivideostudio/gui/panels/timeline_panel.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Done: added debug log. Lines: {len(new_lines)}")

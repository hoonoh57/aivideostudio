lines = open('aivideostudio/gui/main_window.py', encoding='utf-8').readlines()
for rng in [(55,75), (115,130), (455,475), (610,625)]:
    print(f"=== lines {rng[0]+1}-{rng[1]} ===")
    for i in range(rng[0], min(rng[1], len(lines))):
        print(f'{i+1}: {lines[i]}', end='')
    print()
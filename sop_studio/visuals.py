"""Deterministic text-driven educational illustrations and motion graphics.

These are editable/reviewable schematics, not simulations or verified procedures.
No model, cloud service, fabricated AI output or GPU dependency is used.
"""
from __future__ import annotations
import math
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw
from .composition import font, wrap
from .diagnostics import ffmpeg
from .schema import digest, file_hash
from .storage import atomic_json
from .process import check_cancel, run

VERSION = 'schematic-1.2'
W, H = 960, 540
INK, MUTED, GREEN, BLUE, GOLD = '#173c35', '#687b78', '#2b9975', '#54aeda', '#e4b45b'
TEMPLATES = ['Automatic', 'Soap application', 'Hand rubbing', 'Hand wetting', 'Hand rinsing', 'Hand drying',
             'Gowning / PPE', 'Fluid bed dryer', 'Equipment schematic', 'Surface cleaning',
             'Documentation', 'Material transfer', 'Safety warning', 'Source process card']

def choose_template(row: dict) -> str:
    text = (row.get('narration', '') + ' ' + row.get('visual_description', '')).lower()
    if any(word in text for word in ('do not', 'must not', 'never ', 'prohibited', 'danger', 'warning')):
        return 'Safety warning'
    if any(word in text for word in ('fluid bed', 'fluidized bed', 'fluidisation', 'fluidization', 'fbd')):
        return 'Fluid bed dryer'
    if any(word in text for word in ('wet both', 'wet hands')):
        return 'Hand wetting'
    if any(word in text for word in ('rinse', 'rinsing')):
        return 'Hand rinsing'
    if any(word in text for word in ('dry hands', 'drying method', 'dry both', 'dry your')):
        return 'Hand drying'
    if 'soap' in text and any(word in text for word in ('apply', 'dispense', 'application')):
        return 'Soap application'
    if any(word in text for word in ('rub', 'palms', 'handwash', 'wash hands', 'hand hygiene')):
        return 'Hand rubbing'
    topic = row.get('visual', '')
    return {'Gowning':'Gowning / PPE', 'Equipment':'Equipment schematic', 'Disinfection':'Surface cleaning',
            'Documentation':'Documentation', 'Material handling':'Material transfer', 'Safety':'Safety warning'}.get(topic, 'Source process card')

def arrow(draw, start, end, color=BLUE, width=5):
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1]-start[1], end[0]-start[0])
    draw.polygon([end, (end[0]-15*math.cos(angle-.45), end[1]-15*math.sin(angle-.45)),
                  (end[0]-15*math.cos(angle+.45), end[1]-15*math.sin(angle+.45))], fill=color)

def label(draw, xy, text, color=INK, size=17):
    draw.text(xy, text, font=font(size), fill=color)

def hand(draw, x, y, flip=False, shift=0):
    # Deliberately schematic: no claim to anatomically exact procedural movements.
    fill = '#e9b68c'
    draw.rounded_rectangle((x, y+shift, x+91, y+85+shift), 28, fill=fill, outline='#bd8b67', width=2)
    for i, length in enumerate((55, 73, 79, 64)):
        xx = x+5+i*21
        draw.rounded_rectangle((xx, y-length+shift, xx+18, y+29+shift), 9, fill=fill, outline='#bd8b67', width=2)
    tx = x-27 if not flip else x+76
    draw.rounded_rectangle((tx, y+15+shift, tx+41, y+70+shift), 14, fill=fill, outline='#bd8b67', width=2)
    draw.rounded_rectangle((x+19, y+66+shift, x+72, y+128+shift), 12, fill=fill)

def frame(row: dict, template: str, phase: float = 0) -> Image.Image:
    image = Image.new('RGB', (W, H), '#f2f5ed')
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((20, 16, W-20, H-16), 22, fill='white', outline='#dbe5d8', width=2)
    label(d, (44, 30), 'SOP STUDIO  /  GENERATED EXPLANATORY VISUAL', GREEN, 14)
    label(d, (44, 62), template, INK, 28)
    # Dedicated drawing area; source caption never overlaps the illustration.
    d.rounded_rectangle((40, 111, 920, 382), 18, fill='#eaf2ed')
    t = phase * math.tau
    if template in ('Soap application', 'Hand rubbing', 'Hand wetting', 'Hand rinsing', 'Hand drying'):
        motion = math.sin(t)*10 if template == 'Hand rubbing' else 0
        hand(d, 367+motion, 225, shift=0)
        hand(d, 510-motion, 225, flip=True, shift=math.cos(t)*6 if template == 'Hand rubbing' else 0)
        if template == 'Soap application':
            d.rounded_rectangle((238, 167, 292, 262), 8, fill='#83b9aa', outline=GREEN, width=3)
            d.line((260, 167, 260, 147, 311, 147), fill=INK, width=6)
            label(d, (242, 198), 'SOAP', 'white', 13)
            for i in range(4):
                yy = 171+((phase+i/4)%1)*82
                d.ellipse((307, yy, 315, yy+12), fill=BLUE)
            arrow(d, (319, 262), (356, 262), GREEN)
        elif template == 'Hand rubbing':
            for xx, yy in ((448, 185), (474, 213), (452, 246), (493, 164)):
                radius = 6+2*math.sin(t+xx)
                d.ellipse((xx-radius, yy-radius, xx+radius, yy+radius), outline='#63aa9a', width=2)
            arrow(d, (400, 140), (470, 140), GREEN)
            arrow(d, (565, 353), (495, 353), GREEN)
        elif template in ('Hand wetting', 'Hand rinsing'):
            d.line((270, 145, 270, 122, 473, 122, 473, 148), fill='#8caaa7', width=14)
            for i in range(18):
                xx = 430+(i%6)*17
                yy = 154+((phase+i/18)%1)*185
                d.line((xx, yy, xx-3, yy+12), fill=BLUE, width=3)
        else:
            d.rounded_rectangle((635, 177, 748, 299), 8, fill='#fff7dc', outline=GOLD, width=3)
            for yy in range(195, 290, 17):
                d.line((652, yy, 733, yy), fill='#e1cd94', width=2)
            arrow(d, (615, 242), (640, 242), GOLD)
        label(d, (66, 359), 'Hand hygiene concept — confirm exact technique against the source.', MUTED, 15)
    elif template == 'Fluid bed dryer':
        d.polygon([(382, 153), (578, 153), (559, 295), (514, 345), (447, 345), (403, 295)], fill='#d2e4df', outline=INK, width=3)
        d.rounded_rectangle((389, 134, 571, 169), 7, fill='#9dbeb2', outline=INK, width=2)
        for xx in range(404, 564, 20):
            d.line((xx, 140, xx, 161), fill='white', width=4)
        for i in range(30):
            xx = 421+(i*37)%116
            yy = 220+(i*23)%82+math.sin(t+i)*13
            d.ellipse((xx, yy, xx+7, yy+7), fill=GOLD)
        for xx in (442, 480, 518):
            arrow(d, (xx, 329), (xx, 184), BLUE, 3)
        arrow(d, (280, 335), (420, 335), BLUE)
        arrow(d, (575, 150), (704, 150), BLUE)
        label(d, (222, 299), 'Inlet airflow', BLUE)
        label(d, (638, 120), 'Exhaust', BLUE)
        label(d, (600, 221), 'Particle movement', INK)
        label(d, (600, 248), 'Conceptual only', MUTED, 15)
        label(d, (66, 359), 'Generic fluidization diagram — not a site equipment model or operating recipe.', MUTED, 15)
    elif template == 'Gowning / PPE':
        d.ellipse((433, 129, 515, 207), fill='#e9b68c', outline='#bd8b67', width=2)
        d.polygon([(428, 208), (518, 208), (572, 265), (541, 285), (522, 258), (522, 354), (423, 354), (423, 258), (402, 285), (372, 265)], fill='#fafcff', outline='#83a7a0', width=3)
        d.line((473, 214, 473, 353), fill='#83a7a0', width=3)
        d.rounded_rectangle((437, 169, 511, 194), 7, fill='#a9d4df')
        d.arc((426, 120, 521, 182), 180, 360, fill=GREEN, width=12)
        d.ellipse((644, 192, 665, 213), fill=GOLD)
        arrow(d, (640, 202), (530, 224), GOLD)
        label(d, (666, 190), 'PPE schematic', INK)
        label(d, (66, 359), 'No donning order inferred. Verify the required PPE and sequence.', MUTED, 15)
    elif template == 'Surface cleaning':
        d.polygon([(245, 254), (600, 254), (730, 322), (334, 322)], fill='#b5c9c0', outline=INK, width=3)
        x = 332+phase*220
        d.polygon([(x, 236), (x+66, 236), (x+98, 265), (x+23, 265)], fill='#fff8dd', outline=GOLD, width=2)
        for i in range(10):
            xx = 350+i*25
            d.ellipse((xx, 278, xx+5, 283), fill=GREEN if xx<x else '#ba8b82')
        arrow(d, (339, 192), (564, 192), GREEN)
        label(d, (66, 359), 'Wiping concept — no chemical, contact time or cleanliness limit is invented.', MUTED, 15)
    elif template == 'Documentation':
        d.rounded_rectangle((329, 127, 624, 364), 12, fill='white', outline='#87a49a', width=3)
        label(d, (353, 145), 'TRAINING RECORD', INK, 18)
        for i in range(5):
            yy = 189+i*31
            d.line((353, yy, 601, yy), fill='#dce7df', width=2)
        yy = 183+int(phase*4)*31
        d.rounded_rectangle((347, yy, 604, yy+25), 4, outline=GREEN, width=3)
        label(d, (66, 359), 'Record illustration — enter only source-authorized information.', MUTED, 15)
    elif template == 'Material transfer':
        for x in (240, 620):
            d.rounded_rectangle((x, 199, x+111, 330), 12, fill='#cee2da', outline=INK, width=3)
            d.rounded_rectangle((x-5, 185, x+116, 209), 6, fill='#8eafa2', outline=INK, width=2)
        arrow(d, (365, 250), (607, 250), GREEN)
        for i in range(8):
            xx = 371+((phase+i/8)%1)*223
            d.ellipse((xx, 232, xx+9, 241), fill=GOLD)
        label(d, (66, 359), 'Transfer concept — verify containment, direction and actual equipment.', MUTED, 15)
    elif template == 'Safety warning':
        d.polygon([(465, 137), (578, 331), (353, 331)], fill='#fff0c9', outline='#bb7c2e', width=5)
        label(d, (452, 196), '!', '#a45e19', 76)
        label(d, (621, 211), 'CHECK SOURCE', '#a45e19', 19)
        label(d, (621, 242), 'Prohibitions stay visible.', MUTED, 16)
        label(d, (66, 359), 'Warning illustration — prohibited actions are not animated as instructions.', MUTED, 15)
    elif template == 'Equipment schematic':
        d.rounded_rectangle((365, 153, 580, 306), 15, fill='#b8d3c8', outline=INK, width=3)
        d.rounded_rectangle((385, 175, 478, 237), 8, fill='#f3f7ed', outline=GREEN, width=2)
        for i in range(3):
            d.ellipse((510, 176+i*34, 528, 194+i*34), fill=GREEN if i==int(phase*3)%3 else '#dce6de')
        d.line((390, 307, 390, 344), fill=INK, width=9)
        d.line((555, 307, 555, 344), fill=INK, width=9)
        label(d, (66, 359), 'Generic equipment concept — geometry and controls are not site-specific.', MUTED, 15)
    else:
        # Unknown topics keep their actual source as the content, without invented actions.
        for i in range(3):
            x = 177+i*230
            d.rounded_rectangle((x, 192, x+166, 290), 14, fill='#d5e8dd' if i==int(phase*3)%3 else 'white', outline='#9ab7a6', width=2)
            label(d, (x+22, 225), ('SOURCE', 'REVIEW', 'TRAINING')[i], INK, 20)
            if i<2:
                arrow(d, (x+176, 240), (x+215, 240), GREEN, 3)
        label(d, (66, 359), 'Source process card — no unsupported procedural demonstration inferred.', MUTED, 15)
    source = row.get('narration', '')
    lines = wrap(d, source, font(20), 860)
    for i, line in enumerate(lines[:3]):
        if i == 2 and len(lines)>3:
            line = line[:max(0, len(line)-3)]+'…'
        label(d, (46, 397+i*25), line, INK, 20)
    label(d, (46, 490), 'SCHEMATIC • NOT TO SCALE • TECHNICAL REVIEW REQUIRED', '#8c6334', 14)
    return image

def generate(row: dict, media_root: Path, mode='Animation', template='Automatic', cancel_file=None) -> dict:
    if mode not in ('Animation', 'Illustration') or template not in TEMPLATES:
        raise ValueError('Unknown generated visual mode or template.')
    if not row.get('narration', '').strip():
        raise ValueError('Narration is required to generate a contextual visual.')
    chosen = choose_template(row) if template == 'Automatic' else template
    # Never animate a prohibited action even when a user chooses another template.
    if choose_template(row) == 'Safety warning':
        chosen = 'Safety warning'
    key = digest({'narration':row['narration'], 'visual_description':row.get('visual_description',''), 'reference':row.get('reference',''),
                  'template':chosen, 'mode':mode, 'version':VERSION})
    dest = Path(media_root) / 'generated'
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f'{key}.{ "mp4" if mode == "Animation" else "png"}'
    sidecar = dest / f'{key}.generation.json'
    check_cancel(cancel_file)
    if not (path.exists() and sidecar.exists()):
        with tempfile.TemporaryDirectory(dir=dest) as temporary:
            temp = Path(temporary)
            if mode == 'Illustration':
                frame(row, chosen, .35).save(temp/'output.png')
            else:
                executable = ffmpeg()
                if not executable:
                    raise RuntimeError('FFmpeg is required for animation; choose Illustration or run the installer.')
                # Fixed-size short loops keep RAM and storage bounded; no GPU allocation.
                for i in range(36):
                    check_cancel(cancel_file)
                    frame(row, chosen, i/36).save(temp/f'{i:04}.png')
                run([executable, '-y', '-loglevel', 'error', '-framerate', '12', '-i', temp/'%04d.png',
                     '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', temp/'output.mp4'], cancel_file, timeout=120)
            (temp/('output'+path.suffix)).replace(path)
        atomic_json(sidecar, {'generator':VERSION, 'template':chosen, 'mode':mode, 'source_narration':row['narration'],
                              'source_reference':row.get('reference',''), 'sha256':file_hash(path),
                              'limitations':'Conceptual schematic; not anatomically exact, not to scale, not a validated procedural demonstration.'})
    else:
        import json
        if file_hash(path) != json.loads(sidecar.read_text(encoding='utf-8'))['sha256']:
            raise ValueError('Cached generated visual changed. Remove the damaged generated file before retrying.')
    return {'path':str(path.resolve()), 'template':chosen, 'generator':VERSION, 'mode':mode,
            'generation_manifest':str(sidecar.resolve()), 'source_narration_hash':digest(row['narration'])}

"""Mobile-safe 3D presenter slides: no extra dependencies beyond Pillow."""
import re
from PIL import Image, ImageDraw


def split_voiceover(text, max_words=9, max_chars=74):
    """Make short, readable caption scenes without discarding narration words."""
    chunks, current = [], []
    for word in text.split():
        candidate = ' '.join(current + [word])
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            chunks.append(' '.join(current))
            current = []
        current.append(word)
        if len(current) >= 5 and re.search(r'[.!?;]$', word):
            chunks.append(' '.join(current))
            current = []
    if current:
        chunks.append(' '.join(current))
    return chunks


def _wrap(draw, text, f, max_width):
    lines = []
    line = ''
    for word in text.split():
        test = (line + ' ' + word).strip()
        if draw.textbbox((0, 0), test, font=f)[2] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fitted(draw, text, max_width, max_height, font_fn, sizes):
    for size in sizes:
        f = font_fn(size, True)
        lines = _wrap(draw, text, f, max_width)
        lh = round(size * 1.36)
        if lines and len(lines)*lh <= max_height and all(draw.textbbox((0,0),t,font=f)[2] <= max_width for t in lines):
            return f, lines, lh
    # Never silently crop the caption: split source narration into shorter phrases.
    raise ValueError('Caption does not fit scene; split it into shorter phrases')


def render_slide_v3(path, headline, copy, brand, idx, total, topic,
                    atlas_path, pick_theme, font_fn, width=540, height=960):
    theme, (base, mid, accent) = pick_theme(topic or headline, idx)
    im = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(im)
    for y in range(height):
        fraction = y / height
        rgb = tuple(int(base[k]*(1-fraction) + mid[k]*(fraction*0.8)) for k in range(3))
        draw.line((0,y,width,y), fill=rgb+(255,))
    draw.ellipse((292,-83,663,305),outline=accent+(255,),width=4)
    draw.ellipse((-220,540,190,1070),outline=tuple(min(255,x+34) for x in base)+(255,),width=4)

    # Branding: one clean line and no overlapping text.
    draw.rounded_rectangle((21,23,519,88),radius=17,fill=(9,24,49,248),outline=accent,width=2)
    brand_font, brand_lines, brand_height = _fitted(draw,brand.upper(),460,38,font_fn,[20,19,18,17,16,15])
    draw.text((40,44),brand_lines[0],font=brand_font,fill='white')

    # Show the topic on every frame instead of a huge POINT X OF Y banner.
    draw.rounded_rectangle((20,109,520,266),radius=22,fill=(8,19,44,239),outline=accent,width=3)
    label = (topic if topic else headline).strip().upper()
    title_f, title_lines, title_lh = _fitted(draw,label,451,128,font_fn,
                                               [35,33,31,29,27,25,23,21,19,17])
    title_height = len(title_lines)*title_lh
    ty = 109+(157-title_height)//2
    for line in title_lines:
        draw.text((43,ty),line,font=title_f,fill=(255,251,244))
        ty += title_lh

    # Presenter stage + large static 3D pose: explicitly upscale source atlas sprites.
    draw.ellipse((9,822,224,857),fill=(12,36,56,205),outline=accent,width=2)
    with Image.open(atlas_path) as atlas_source:
        atlas = atlas_source.convert('RGBA')
    cw, ch = atlas.width//3,atlas.height//2
    pose = [1,2,3,0,4,5][idx%6]
    sprite = atlas.crop(((pose%3)*cw,(pose//3)*ch,((pose%3)+1)*cw,((pose//3)+1)*ch))
    bbox = sprite.getchannel('A').getbbox()
    if bbox:
        sprite = sprite.crop(bbox)
        ratio = min(218/sprite.width,490/sprite.height)
        sprite = sprite.resize((max(1,int(sprite.width*ratio)),max(1,int(sprite.height*ratio))),Image.Resampling.LANCZOS)
        sx = max(0,(218-sprite.width)//2)
        sy = 837-sprite.height
        im.alpha_composite(sprite,(sx,sy))

    # Dedicated readable card. Fit every caption before drawing; keep footer clear.
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((212,287,519,819),radius=23,fill=(247,252,255,255),outline=accent,width=4)
    draw.rounded_rectangle((230,307,501,361),radius=12,fill=mid+(255,))
    if idx == 0:
        badge="TODAY'S IDEA"
    elif idx == total-1:
        badge='TAKEAWAY'
    else:
        found = re.search(r'POINT\s+(\d+)\s+OF\s+(\d+)',headline,re.I)
        badge = f'IDEA {found.group(1)} / {found.group(2)}' if found else 'EXPLAINED'
    badge_f, badge_lines, _ = _fitted(draw,badge,244,38,font_fn,[21,20,19,18,17])
    draw.text((246,323),badge_lines[0],font=badge_f,fill='white')
    draw.line((234,381,496,381),fill=mid,width=3)
    statement = ' '.join(copy.split())
    caption_f, caption_lines, caption_lh = _fitted(draw,statement,256,327,font_fn,
        [31,29,27,25,23,21,19,18,17,16])
    content_top, content_bottom = 398,733
    cy = content_top + max(0, (content_bottom-content_top-len(caption_lines)*caption_lh)//2)
    for line in caption_lines:
        draw.text((235,cy),line,font=caption_f,fill=(24,42,68))
        cy += caption_lh
    draw.rounded_rectangle((230,752,501,799),radius=12,fill=mid+(255,))
    footer_f = font_fn(15,True)
    draw.text((244,767),'LEARN  •  BUILD  •  GROW',font=footer_f,fill='white')

    draw.rounded_rectangle((38,875,502,883),radius=4,fill=(10,34,53))
    draw.rounded_rectangle((38,875,38+int(464*(idx+1)/max(1,total)),883),radius=4,fill=accent)
    draw.text((38,910),'AI  •  EXPLAINED SIMPLY',font=font_fn(16,True),fill='white')
    im.convert('RGB').save(path)

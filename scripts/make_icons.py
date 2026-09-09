"""Render the existing four-line Skill-Desk mark at application icon resolution."""
from pathlib import Path
from PIL import Image, ImageDraw
root = Path(__file__).resolve().parent.parent
im = Image.new('RGBA', (1024,1024))
d = ImageDraw.Draw(im)
d.rounded_rectangle((24,24,1000,1000), radius=210, fill='#272c28')
for y, end in [(280,768),(440,608),(600,768),(760,608)]:
    d.line((256,y,end,y), fill='#f8f7f2', width=48)
im.save(root/'assets/skilldesk.png')
im.resize((128,128)).save(root/'desktop/logo.png')
(root/'assets/skilldesk.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><rect x="24" y="24" width="976" height="976" rx="210" fill="#272c28"/><path d="M256 280h512M256 440h352M256 600h512M256 760h352" fill="none" stroke="#f8f7f2" stroke-width="48"/></svg>')

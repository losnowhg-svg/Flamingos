"""📲 Condividi: the phone's share sheet (Instagram, WhatsApp, Foto...) for a PNG or MP4.

Uses the Web Share API from a tiny HTML component. Where the browser cannot
share files (most desktop browsers, old phones) the button does not appear and
the normal download stays the way.
"""
from __future__ import annotations

import base64
import json

LIMIT = 30_000_000        # bytes: beyond this a page with the file inside gets too heavy for a phone


def button(data, filename: str = '', mime: str = '', label: str = '📲 Condividi (Instagram, WhatsApp...)', key: str = ''):
    """data: bytes (with filename and mime) or a list of (bytes, filename, mime) for a carousel."""
    files = data if isinstance(data, list) else [(data, filename, mime)]
    files = [f for f in files if f[0]]
    if not files or sum(len(f[0]) for f in files) > LIMIT:
        return
    import streamlit.components.v1 as components
    payload = json.dumps([{'name': name, 'type': kind, 'data': base64.b64encode(blob).decode()} for blob, name, kind in files])
    html = f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;background:transparent;font:600 15px system-ui,-apple-system,sans-serif}}
button{{width:100%;min-height:44px;border-radius:8px;border:1px solid #e95396;background:#2a1830;color:#ffd2e6;
font:inherit;cursor:pointer}}#msg{{color:#bca9c5;font-size:12px;text-align:center;margin-top:4px}}</style></head>
<body><button id="b" style="display:none">{label}</button><div id="msg"></div><script>
const items={payload};
function toFile(it){{const bin=atob(it.data);const arr=new Uint8Array(bin.length);
for(let i=0;i<bin.length;i++)arr[i]=bin.charCodeAt(i);return new File([arr],it.name,{{type:it.type}});}}
let files=[];try{{files=items.map(toFile);}}catch(e){{}}
const b=document.getElementById('b'), msg=document.getElementById('msg');
if(files.length&&navigator.canShare&&navigator.canShare({{files}})){{b.style.display='block';
b.onclick=async()=>{{try{{await navigator.share({{files}});}}catch(e){{if(e.name!=='AbortError')msg.textContent='Condivisione non riuscita: usa Scarica.';}}}};}}
else{{document.body.style.display='none';}}
</script></body></html>"""
    components.html(html, height=58)


def from_zip(blob):
    """The images of a carousel ZIP, in order, for button()."""
    import io
    import zipfile
    out = []
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for name in sorted(archive.namelist()):
            if name.lower().endswith('.png'):
                out.append((archive.read(name), name.rsplit('/', 1)[-1], 'image/png'))
    return out

"""Optional component smoke test (Chromium + playwright required).

Runs custom component protocols in a local iframe harness, not a complete
Streamlit server. No uploaded fonts, user backups or browser profiles are retained.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import renderer as r
from studio_state import defaults, validate_library
from playwright.sync_api import sync_playwright

logo = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
editor_args = r.editor_data(r.scene(defaults('Starting 7'),logo))


class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        if urlparse(self.path).path=='/harness':
            editor = 'editor' in self.path
            path = '/frontend/index.html' if editor else '/library_frontend/index.html'
            args = editor_args if editor else {'command':None}
            script = '''
window.values=[];window.args=ARGS;
window.render=()=>document.querySelector('iframe').contentWindow.postMessage({type:'streamlit:render',args:window.args},'*');
window.addEventListener('message',e=>{
 const m=e.data;if(!m||!m.isStreamlitMessage)return;
 if(m.type==='streamlit:componentReady')window.render();
 if(m.type==='streamlit:setComponentValue'){
  window.values.push(m.value);
  if(m.value.positions)window.args.positions=m.value.positions;
  if(m.value.command_id)window.args.command=null;
  window.render();
 }
 if(m.type==='streamlit:setFrameHeight')document.querySelector('iframe').height=m.height;
});
'''.replace('ARGS',json.dumps(args))
            html = '<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:#19131f"><script>'+script+'</script><iframe title="component" style="border:0;width:570px" src="'+path+'"></iframe></body></html>'
            data = html.encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        else:
            super().do_GET()


def wait_snapshot(page,count=1):
    page.wait_for_function('(n)=>window.values.length>=n',arg=count)
    return page.evaluate('window.values[window.values.length-1]')


def main():
    binary = shutil.which('chromium') or shutil.which('google-chrome')
    if not binary:
        raise SystemExit('Chromium not found. Install it or use a Playwright-managed executable.')
    server = ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/harness'
    checks = []
    font_path = next((Path(p) for p in r.FONT_FALLBACK if Path(p).exists()),None)
    with tempfile.TemporaryDirectory() as temp, sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(str(Path(temp)/'profile'),executable_path=binary,headless=True,args=['--no-sandbox'],viewport={'width':700,'height':1100},device_scale_factor=2)
        page = context.new_page()
        errors = []
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(url+'?library')
        snapshot = wait_snapshot(page)
        assert snapshot['storage_ok'] is True,snapshot
        assert not snapshot['library']['assets']
        frame = page.frame_locator('iframe')
        if font_path:
            frame.locator('#fonts').set_input_files(str(font_path))
            snapshot = wait_snapshot(page,2)
            assert len(snapshot['library']['assets'])==1
            valid,messages = validate_library(snapshot['library'])
            assert not messages,messages
            assert valid['preferred_font']
            checks.append('Font upload, server validation and preferred font')
            frame.locator('#fonts').set_input_files(str(font_path))
            snapshot = wait_snapshot(page,3)
            assert len(snapshot['library']['assets'])==1
            checks.append('Content-addressed font deduplication')
        count = page.evaluate('window.values.length')
        frame.locator('#logos').set_input_files(str(ROOT/'assets'/'flamingos_logo.jpg'))
        snapshot = wait_snapshot(page,count+1)
        assert any(x['kind']=='logo' for x in snapshot['library']['assets'].values())
        checks.append('Persistent logo upload')
        command = {'id':'qa-save-project','type':'save_project','project_id':'qa-project',
                   'project':{'name':'QA Starting 7','template':'Starting 7','config':defaults('Starting 7')}}
        count = page.evaluate('window.values.length')
        page.evaluate('(cmd)=>{window.args.command=cmd;window.render()}',command)
        snapshot = wait_snapshot(page,count+1)
        assert snapshot['command_id']=='qa-save-project'
        assert 'qa-project' in snapshot['library']['projects']
        checks.append('Project command acknowledged only after transaction completion')
        initial_asset_count = len(snapshot['library']['assets'])
        page.reload();snapshot=wait_snapshot(page)
        assert len(snapshot['library']['assets'])==initial_asset_count
        assert 'qa-project' in snapshot['library']['projects']
        checks.append('Full-page reload restores fonts, logo and project')
        with page.expect_download() as download_info:
            frame.locator('#backup').click()
        backup = Path(temp)/'backup.json'
        download_info.value.save_as(str(backup))
        backup_data = json.loads(backup.read_text())
        assert len(backup_data['assets'])==initial_asset_count
        assert 'qa-project' in backup_data['projects']
        checks.append('Portable backup includes exact asset bytes and projects')
        context.close()
        context = playwright.chromium.launch_persistent_context(str(Path(temp)/'profile'),executable_path=binary,headless=True,args=['--no-sandbox'],viewport={'width':700,'height':1100})
        page = context.new_page();page.goto(url+'?library');snapshot=wait_snapshot(page)
        assert len(snapshot['library']['assets'])==initial_asset_count
        checks.append('Closing and reopening Chromium preserves the library')
        frame = page.frame_locator('iframe')
        page.on('dialog',lambda dialog:dialog.accept())
        frame.locator('#assets button').first.click()
        snapshot = wait_snapshot(page,2)
        assert len(snapshot['library']['assets'])==initial_asset_count-1
        page.reload();snapshot=wait_snapshot(page)
        assert len(snapshot['library']['assets'])==initial_asset_count-1
        checks.append('Deletion is committed and survives reload')
        frame.locator('#restore').set_input_files(str(backup))
        snapshot=wait_snapshot(page,2)
        assert len(snapshot['library']['assets'])==initial_asset_count
        checks.append('Backup restore merges into the existing library')
        frame.locator('#fonts').set_input_files({'name':'invalid.ttf','mimeType':'font/ttf','buffer':b'not a font'})
        frame.locator('#message').filter(has_text='Errore').wait_for()
        assert len(page.evaluate('window.values[window.values.length-1].library.assets'))==initial_asset_count
        checks.append('Malformed font rejected before persistent storage')
        # Editor protocol with a native-1080 source and logical layout positions.
        page.goto(url+'?editor')
        frame = page.frame_locator('iframe')
        target = frame.locator('[data-id="player_6"]')
        target.wait_for()
        target.focus();page.keyboard.press('ArrowRight')
        changed=wait_snapshot(page)
        assert changed['positions']['player_6']==[271,284]
        page.keyboard.press('Shift+ArrowDown')
        changed=wait_snapshot(page,2)
        assert changed['positions']['player_6']==[271,294]
        frame.locator('#undo').click();changed=wait_snapshot(page,3)
        assert changed['positions']['player_6']==[271,284]
        frame.locator('#redo').click();changed=wait_snapshot(page,4)
        assert changed['positions']['player_6']==[271,294]
        checks.append('Keyboard steps, Shift steps, undo and redo survive server echoes')
        box=target.bounding_box();assert box
        page.mouse.move(box['x']+box['width']/2,box['y']+15)
        page.mouse.down();page.mouse.move(box['x']+box['width']/2+50,box['y']+45,steps=5);page.mouse.up()
        changed=wait_snapshot(page,5)
        assert changed['positions']['player_6'][0]>300,changed
        checks.append('Pointer drag persists logical positions, independent of preview scale')
        page.evaluate('()=>{window.args.crop=[0,210,540,750];window.render()}')
        assert frame.locator('#crop').is_visible()
        frame.locator('#guides').uncheck()
        assert not frame.locator('#crop').is_visible()
        frame.locator('#zoom').select_option('810')
        assert frame.locator('#stage').evaluate('(e)=>e.getBoundingClientRect().width')==810
        checks.append('Crop guides, guide visibility and zoom')
        context.close()
        # Private / restricted browser behavior: no false saved confirmation.
        context=playwright.chromium.launch_persistent_context(str(Path(temp)/'blocked'),executable_path=binary,headless=True,args=['--no-sandbox'])
        context.add_init_script("Object.defineProperty(window,'indexedDB',{value:{open(){throw Error('Storage blocked for test')}}});")
        page=context.new_page();page.goto(url+'?library');snapshot=wait_snapshot(page)
        assert snapshot['storage_ok'] is False
        assert 'Solo sessione' in page.frame_locator('iframe').locator('#status').inner_text()
        checks.append('Blocked browser storage is reported as session-only')
        context.close()
        assert not errors,errors
    server.shutdown()
    for check in checks:
        print('PASS:',check)
    print(f'{len(checks)} browser component checks passed. Full Streamlit integration not covered by this harness.')


if __name__=='__main__':
    main()

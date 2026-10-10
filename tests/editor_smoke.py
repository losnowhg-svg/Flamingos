"""No-network Chromium test for the editor and unavailable-storage fallback.

The complete persistent-storage test is in browser_smoke.py and requires
an environment that permits navigation to a local HTTP server.
"""
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import renderer as r
from studio_state import defaults
from playwright.sync_api import sync_playwright


def mount(page,source,args):
    script = '''window.values=[];window.args=ARGS;
    window.render=()=>document.querySelector('iframe').contentWindow.postMessage({type:'streamlit:render',args:window.args},'*');
    window.addEventListener('message',e=>{
      const m=e.data;if(!m||!m.isStreamlitMessage)return;
      if(m.type==='streamlit:componentReady')window.render();
      if(m.type==='streamlit:setComponentValue'){
        window.values.push(m.value);
        if(m.value.positions)window.args.positions=m.value.positions;
      if(m.value.locked_layers)window.args.locked_layers=m.value.locked_layers;
        if(m.value.command_id)window.args.command=null;
        window.render();
      }
      if(m.type==='streamlit:setFrameHeight')document.querySelector('iframe').height=m.height;
    });'''.replace('ARGS',json.dumps(args))
    page.set_content('<html><head><meta charset="utf-8"></head><body style="margin:0;background:#19131f"><script>'+script+'</script><iframe title="component" style="border:0;width:570px" srcdoc="'+html.escape(source,quote=True)+'"></iframe></body></html>')


def wait(page,count):
    page.wait_for_function('(n)=>window.values.length>=n',arg=count)
    return page.evaluate('window.values[window.values.length-1]')


def main():
    results=[]
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
        page=b.new_page(viewport={'width':700,'height':1200},device_scale_factor=2)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        logo=(ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
        args=r.editor_data(r.scene(defaults('Starting 7'),logo))
        mount(page,(ROOT/'frontend'/'index.html').read_text(),args)
        frame=page.frame_locator('iframe');target=frame.locator('[data-id="player_6"]');target.wait_for()
        target.focus();page.keyboard.press('ArrowRight');changed=wait(page,1)
        assert changed['positions']['player_6']==[271,284]
        page.keyboard.press('Shift+ArrowDown');changed=wait(page,2)
        assert changed['positions']['player_6']==[271,294]
        results.append('Keyboard and Shift movement in logical coordinates')
        frame.locator('#undo').click();changed=wait(page,3)
        assert changed['positions']['player_6']==[271,284]
        frame.locator('#redo').click();changed=wait(page,4)
        assert changed['positions']['player_6']==[271,294]
        results.append('Undo/redo and selection survive simulated server rerenders')
        box=target.bounding_box()
        page.mouse.move(box['x']+box['width']/2,box['y']+15);page.mouse.down()
        page.mouse.move(box['x']+box['width']/2+50,box['y']+45,steps=5);page.mouse.up()
        changed=wait(page,5)
        assert changed['positions']['player_6'][0]>300
        results.append('Pointer drag updates positions at preview scale')
        page.evaluate('()=>{window.args.crop=[0,210,540,750];window.render()}')
        frame.locator('#crop').wait_for(state='visible')
        frame.locator('#guides').uncheck()
        assert not frame.locator('#crop').is_visible()
        frame.locator('#zoom').select_option('810')
        assert frame.locator('#stage').evaluate('(e)=>e.getBoundingClientRect().width')==810
        results.append('Square crop guides, visibility and zoom')
        mount(page,(ROOT/'library_frontend'/'index.html').read_text(),{'command':None})
        changed=wait(page,1)
        assert changed['storage_ok'] is False
        frame=page.frame_locator('iframe')
        assert 'Solo sessione' in frame.locator('#status').inner_text()
        results.append('Restricted origin reports unavailable storage without hanging')
        frame.locator('#fonts').set_input_files({'name':'invalid.ttf','mimeType':'font/ttf','buffer':b'not a font'})
        frame.locator('#message').filter(has_text='Errore').wait_for()
        assert not page.evaluate('window.values[window.values.length-1].library.assets')
        results.append('Invalid font upload rejected by the browser')
        assert not errors,errors
        b.close()
    for item in results:print('PASS:',item)
    print(f'{len(results)} no-network browser checks passed.')


if __name__=='__main__':main()

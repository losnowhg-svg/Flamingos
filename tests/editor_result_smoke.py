"""Offline Chromium checks for result editing and the version-1 project protocol.
Uses srcdoc: persistent storage is deliberately unavailable, never simulated as saved.
"""
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import renderer as r
import match_result_renderer as mr
from studio_state import defaults,validate_library,empty_library
from studio_tools import switch_result_format
from editor_smoke import mount,wait
from playwright.sync_api import sync_playwright


def main():
    results=[]
    logo=(ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':760,'height':1250},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        for fmt,height in mr.FORMATS.items():
            conf=switch_result_format(defaults('Match Result'),fmt)
            args=r.editor_data(mr.scene(conf,logo,render_scale=1))
            args['locked_layers']=[]
            mount(page,(ROOT/'frontend'/'index.html').read_text(),args)
            frame=page.frame_locator('iframe')
            score=frame.locator('[data-id="score"]');score.wait_for()
            dimensions=frame.locator('#stage').evaluate('(e)=>[e.getBoundingClientRect().width,e.getBoundingClientRect().height]')
            assert abs(dimensions[1]/dimensions[0]-height/540)<.01
            frame.locator('#layer-select').select_option('score')
            page.keyboard.press('ArrowRight')
            changed=wait(page,1)
            assert changed['positions']['score'][0]==271
            frame.locator('#lock').click();changed=wait(page,2)
            assert changed['locked_layers']==['score']
            score.focus();page.keyboard.press('Shift+ArrowRight')
            page.wait_for_timeout(100)
            assert page.evaluate('window.values.length')==2
            assert 'BLOCCATO' in frame.locator('#status').inner_text()
            assert frame.locator('#center').is_disabled()
            box=score.bounding_box()
            page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
            page.mouse.down();page.mouse.move(box['x']+box['width']/2+25,box['y']+box['height']/2+10);page.mouse.up()
            assert page.evaluate('window.values.length')==2
            frame.locator('#lock').click();changed=wait(page,3)
            assert changed['locked_layers']==[]
            frame.locator('#center').click();changed=wait(page,4)
            assert changed['positions']['score'][0]==270
            frame.locator('#undo').click();changed=wait(page,5)
            assert changed['positions']['score'][0]==271
            frame.locator('#redo').click();changed=wait(page,6)
            assert changed['positions']['score'][0]==270
            results.append(fmt+': canvas ratio, layer selection, keyboard, lock, drag lock, centering, undo/redo')
        # A smaller viewport does not change the logical coordinate system.
        page.set_viewport_size({'width':390,'height':950})
        page.locator('iframe').evaluate('(e)=>e.style.width="370px"')
        dimensions=frame.locator('#stage').evaluate('(e)=>[e.getBoundingClientRect().width,e.getBoundingClientRect().height]')
        assert dimensions[0]<=370
        assert abs(dimensions[1]-dimensions[0])<1
        score.focus();page.keyboard.press('ArrowRight');changed=wait(page,7)
        assert changed['positions']['score'][0]==271
        results.append('Narrow editor remains responsive without changing logical movement')
        # Exercise the new result project through the actual browser JS validator.
        mount(page,(ROOT/'library_frontend'/'index.html').read_text(),{'command':None})
        snapshot=wait(page,1)
        assert snapshot['storage_ok'] is False
        result=defaults('Match Result');result['home_score']=3;result['locked_layers']=['score']
        result=switch_result_format(result,'Post 4:5')
        cmd={'id':'result-save-qa','type':'save_project','project_id':'qa-result',
             'project':{'name':'Risultato QA','template':'Match Result','config':result}}
        page.evaluate('(cmd)=>{window.args.command=cmd;window.render()}',cmd)
        snapshot=wait(page,2)
        assert snapshot['command_id']=='result-save-qa'
        assert snapshot['error'] is None
        decoded,messages=validate_library(snapshot['library'])
        assert not messages,messages
        stored=decoded['projects']['qa-result']['config']
        assert stored['home_score']==3 and stored['locked_layers']==['score']
        assert stored['export_format']=='Post 4:5'
        assert snapshot['storage_ok'] is False
        results.append('Match Result save command round-trip, layouts and locks; no false persistent-save claim')
        frame=page.frame_locator('iframe')
        page.on('dialog',lambda dialog:dialog.accept())
        old=empty_library();old['projects']['legacy']={'name':'Progetto 1.4','template':'Starting 7','config':defaults('Starting 7')}
        frame.locator('#restore').set_input_files({'name':'legacy.json','mimeType':'application/json','buffer':json.dumps(old).encode()})
        snapshot=wait(page,3)
        assert set(snapshot['library']['projects'])=={'qa-result','legacy'}
        decoded,messages=validate_library(snapshot['library']);assert not messages
        results.append('Legacy backup merges with a new Match Result project')
        frame.locator('#restore').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{"schema":999}'})
        frame.locator('#message').filter(has_text='Errore').wait_for()
        assert page.evaluate('window.values.length')==3
        results.append('Unsupported backup rejected without replacing existing session data')
        assert not errors,errors
        browser.close()
    for result in results:print('PASS:',result)
    print(f'{len(results)} result-editor browser scenarios passed.')


if __name__=='__main__':main()

"""No-network Chromium checks for new editor events and vault message protocol.

This validates in-session projects and backup round trips, NOT IndexedDB
persistence or full Streamlit integration. See browser_smoke.py for persistence.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from editor_smoke import mount,wait
import renderer as r
from studio_state import MODULES,defaults,validate_library
from crt_presets import CROPS


def main():
    checks=[]
    logo=(ROOT/'assets/flamingos_logo.jpg').read_bytes()
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':700,'height':1200},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        for template,element in (('Full Time','score'),('Convocati','player_17')):
            config=defaults(template)
            if template=='Convocati':config['roster_count']=18
            args=r.editor_data(MODULES[template].scene(config,logo))
            args['crop']=CROPS['Post 4:5']
            mount(page,(ROOT/'frontend/index.html').read_text(),args)
            frame=page.frame_locator('iframe')
            target=frame.locator('[data-id="'+element+'"]');target.wait_for()
            target.focus();page.keyboard.press('Shift+ArrowRight')
            changed=wait(page,1)
            expected=config['positions'][element].copy();expected[0]+=10
            assert changed['positions'][element]==expected
            frame.locator('#undo').click();changed=wait(page,2)
            assert changed['positions'][element]==config['positions'][element]
            frame.locator('#crop').wait_for(state='visible')
            assert frame.locator('#crop').evaluate('(e)=>e.style.height')=='70.3125%'
            checks.append(template+': draggable layer protocol, undo and 4:5 guides')
        mount(page,(ROOT/'library_frontend/index.html').read_text(),{'command':None})
        wait(page,1)
        for index,template in enumerate(('Full Time','Convocati'),2):
            config=defaults(template)
            config.update(preset_id='cassette',font_choice='CRT Scoreboard',season_round=9)
            if template=='Full Time':config.update(home_score=7,away_score=6,home_scorers='ROSSI 12\'')
            cmd=dict(id='cmd-'+str(index),type='save_project',project_id=template,
                     project=dict(name='Test '+template,template=template,config=config))
            page.evaluate('(command)=>{window.args.command=command;window.render()}',cmd)
            snapshot=wait(page,index)
            assert not snapshot['error'],snapshot
            saved=snapshot['library']['projects'][template]
            assert saved['config']['font_choice']=='CRT Scoreboard'
            assert saved['config']['preset_id']=='cassette'
            clean,messages=validate_library(snapshot['library'])
            assert not messages,messages
            checks.append(template+': vault accepts project, pixel font and preset')
        frame=page.frame_locator('iframe')
        with page.expect_download() as info:frame.locator('#backup').click()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'backup.json';info.value.save_as(path)
            backup=json.loads(path.read_text())
            assert set(backup['projects'])=={'Full Time','Convocati'}
            page.on('dialog',lambda d:d.accept())
            frame.locator('#restore').set_input_files(str(path))
            snapshot=wait(page,4)
            assert len(snapshot['library']['projects'])==2
        checks.append('Export/import JSON retains both new project types in session')
        assert not errors,errors
        browser.close()
    for check in checks:print('PASS:',check)
    print(str(len(checks))+' new no-network browser checks passed.')


if __name__=='__main__':main()

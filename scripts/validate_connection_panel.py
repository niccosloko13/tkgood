"""60s real-browser UI audit. Private test profile; only loopback GETs permitted.

Never attaches to the authenticated Chrome or navigates a TikTok/CDN URL.
"""
import base64
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.chrome_launcher import find_chrome
from scripts.process_runtime import hidden_kwargs
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/connection-panel-fix'


class CDP:
    def __init__(self,ws):self.ws=ws;self.seq=0;self.blocked=[];self.errors=[]
    def send(self,method,params=None):
        self.seq+=1;key=self.seq;self.ws.send(json.dumps({'id':key,'method':method,'params':params or {}}));return key
    def call(self,method,params=None):
        key=self.send(method,params)
        while True:
            event=json.loads(self.ws.recv(timeout=15))
            self.handle(event)
            if event.get('id')==key:
                if 'error' in event:raise RuntimeError(event['error'])
                return event.get('result',{})
    def handle(self,event):
        if event.get('method')=='Fetch.requestPaused':
            p=event['params'];url=p['request']['url'];allowed=url.startswith('http://127.0.0.1:8000/') and p['request']['method']=='GET'
            if not allowed:self.blocked.append({'url':url,'method':p['request']['method']})
            self.send('Fetch.continueRequest' if allowed else 'Fetch.failRequest',{'requestId':p['requestId'],**({} if allowed else {'errorReason':'BlockedByClient'})})
        if event.get('method')=='Runtime.exceptionThrown':self.errors.append(event['params'])
    def pump(self,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try:self.handle(json.loads(self.ws.recv(timeout=min(.2,max(.001,deadline-time.monotonic())))))
            except TimeoutError:pass
    def evaluate(self,code):
        result=self.call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')
    def screenshot(self,name):
        data=self.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data']
        (OUT/name).write_bytes(base64.b64decode(data))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    profile=(ROOT/'.runtime'/('dashboard-ui-test-'+uuid.uuid4().hex)).resolve()
    assert profile.is_relative_to((ROOT/'.runtime').resolve())
    profile.mkdir();chrome=find_chrome()
    if not chrome:raise RuntimeError('Chrome test executable unavailable')
    args=[str(chrome),'--headless=new','--remote-debugging-port=0',f'--user-data-dir={profile}',
        '--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-extensions',
        '--window-size=1280,720','about:blank']
    with (OUT/'browser.log').open('ab') as logfile:
        process=subprocess.Popen(args,stdout=logfile,stderr=logfile,**hidden_kwargs())
        ws=None
        try:
            deadline=time.monotonic()+15
            portfile=profile/'DevToolsActivePort'
            while not portfile.exists() and time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('Test browser exited')
                time.sleep(.1)
            port=int(portfile.read_text().splitlines()[0])
            with urlopen(f'http://127.0.0.1:{port}/json/list',timeout=5) as response:targets=json.load(response)
            target=next(t for t in targets if t['type']=='page')
            ws=connect(target['webSocketDebuggerUrl'],max_size=16*1024*1024);cdp=CDP(ws)
            cdp.call('Page.enable');cdp.call('Runtime.enable');cdp.call('Fetch.enable',{'patterns':[{'urlPattern':'*'}]})
            cdp.call('Page.addScriptToEvaluateOnNewDocument',{'source':'''(()=>{const nativeSet=window.setTimeout,nativeClear=window.clearTimeout;window.__connectionTimers=new Set();window.setTimeout=function(fn,ms,...args){let id;const ours=String(fn).includes('uiPollTimer');id=nativeSet.call(this,()=>{window.__connectionTimers.delete(id);fn(...args);},ms);if(ours)window.__connectionTimers.add(id);return id;};window.clearTimeout=function(id){window.__connectionTimers.delete(id);return nativeClear.call(this,id);};let active=0;window.__sessionRequests=0;window.__maxSessionFlight=0;const nativeFetch=window.fetch;window.fetch=async function(url,...args){const ours=url==='/api/session/state';if(ours){active++;window.__sessionRequests++;window.__maxSessionFlight=Math.max(active,window.__maxSessionFlight);}try{return await nativeFetch.call(this,url,...args);}finally{if(ours)active--;}};})();'''})
            cdp.call('Page.navigate',{'url':'http://127.0.0.1:8000/'})
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if cdp.evaluate("typeof BabiConnectionPanel==='object'"):break
                time.sleep(.1)
            cdp.evaluate("showSection('connection'); BabiConnectionPanel.poll()")
            cdp.evaluate('''window.__buttons=['openTikTokButton','renewSession','verifySession','refreshConnectionButton'].map(id=>document.getElementById(id));window.__removedElements=0;window.__panelObserver=new MutationObserver(rs=>{for(const r of rs)window.__removedElements += [...r.removedNodes].filter(n=>n.nodeType===1).length;});window.__panelObserver.observe(document.querySelector('[data-section="connection"]'),{childList:true,subtree:true});document.getElementById('verifySession').focus({preventScroll:true});window.scrollTo(0,150);''')
            def sample():return cdp.evaluate('''({time:Date.now(),timerCount:__connectionTimers.size,inFlight:BabiConnectionPanel.stats().inFlight,log:[...document.querySelectorAll('#sessionMiniLog li')].map(n=>n.textContent),heartbeat:document.querySelector('[data-connection-state="LAST HEARTBEAT"] .value').textContent,session:document.getElementById('sessionStatus').textContent,focus:document.activeElement.id,scroll:window.scrollY,buttonsStable:__buttons.every(n=>n===document.getElementById(n.id)),buttonsEnabled:__buttons.every(n=>!n.disabled),removedElements:__removedElements,requests:__sessionRequests,maxFlight:__maxSessionFlight})''')
            samples=[sample()];cdp.screenshot('before.png');start=time.monotonic()
            while time.monotonic()-start<60:
                cdp.pump(min(5,max(.001,60-(time.monotonic()-start))));samples.append(sample())
            cdp.screenshot('after.png')
            result={'duration_seconds':time.monotonic()-start,'samples':samples,'blocked_requests':cdp.blocked,'javascript_errors':cdp.errors,
                'isolation':'Headless test profile; loopback GET only; authenticated Chrome untouched'}
            (OUT/'browser-60s.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            assert all(s['timerCount']<=1 and s['buttonsStable'] and s['buttonsEnabled'] and s['focus']=='verifySession' and s['scroll']==samples[0]['scroll'] and s['removedElements']==0 and s['maxFlight']==1 for s in samples)
            assert samples[-1]['requests']-samples[0]['requests']>=15
            assert samples[-1]['heartbeat']!=samples[0]['heartbeat']
            assert all(s['log']==samples[0]['log'] for s in samples)
            assert not cdp.errors
            result['passed']=True
            (OUT/'browser-60s.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'passed':True,'seconds':result['duration_seconds'],'polls':samples[-1]['requests']-samples[0]['requests'],'log_lines':len(samples[-1]['log']),'focus_preserved':True,'scroll_preserved':True,'blocked_requests':len(cdp.blocked)}))
        finally:
            if ws:
                try:ws.send(json.dumps({'id':99999,'method':'Browser.close'}))
                except Exception:pass
                ws.close()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()

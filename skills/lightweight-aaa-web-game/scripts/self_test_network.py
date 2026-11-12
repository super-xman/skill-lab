"""Browser regressions: intentionally bad fixtures must fail the zero-request gate."""
import argparse
import json
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from network_audit import NetworkAudit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root/'index.html').write_text('<!doctype html><link rel="icon" href="data:,"><button id="go">go</button><canvas></canvas>')
        server = ThreadingHTTPServer(('127.0.0.1',0), partial(Quiet,directory=directory))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/index.html'
        cases = [
            ('inline_and_data_blob', "async()=>{await fetch('data:text/plain,local');const u=URL.createObjectURL(new Blob(['local']));await fetch(u);URL.revokeObjectURL(u);}", 'passed'),
            ('fetch_after_input', "()=>{go.onclick=()=>fetch('/hidden.json').catch(()=>{});go.click();}", 'failed'),
            ('same_entry_fetch', "()=>fetch(location.href).catch(()=>{})", 'failed'),
            ('same_entry_iframe', "()=>{const f=document.createElement('iframe');f.src=location.href;document.body.append(f);}", 'failed'),
            ('beacon_ignored', "()=>{navigator.sendBeacon('/telemetry','x')}", 'failed'),
            ('worker_nested_fetch', "()=>{const w=new Worker(URL.createObjectURL(new Blob([`fetch('${location.origin}/worker-data').catch(()=>{})`],{type:'text/javascript'})));window.worker=w;}", 'failed'),
            ('service_worker_blocked', "()=>navigator.serviceWorker.register('/sw.js').catch(()=>{})", 'failed'),
            ('websocket_blocked', "()=>{const w=new WebSocket(location.origin.replace('http:','ws:')+'/socket');w.onerror=()=>{};}", 'failed'),
            ('dynamic_css', "()=>{const s=document.createElement('style');s.textContent='body{background:url(/texture.png)}';document.head.append(s);}", 'failed'),
            ('dynamic_preconnect', "()=>{const l=document.createElement('link');l.rel='preconnect';l.href=location.origin+'/other';document.head.append(l);}", 'failed'),
            ('csp_blocked_fetch', "()=>{const m=document.createElement('meta');m.httpEquiv='Content-Security-Policy';m.content=\"connect-src 'none'\";document.head.append(m);fetch('/blocked-by-csp').catch(()=>{});}", 'failed'),
        ]
        results=[]
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=args.browser,args=['--no-sandbox'])
                for name, script, expected in cases:
                    context=browser.new_context(service_workers='block')
                    page=context.new_page();audit=NetworkAudit(context,page,url)
                    page.goto(url);page.evaluate(script);page.wait_for_timeout(500)
                    result=audit.result()
                    results.append({'case':name,'expected':expected,'actual':result['status'],
                                    'passed':result['status']==expected,'evidence':result['evidence']})
                    print(name,result['status'],'OK' if results[-1]['passed'] else 'MISMATCH',flush=True)
                    context.close()
                browser.close()
        finally:
            server.shutdown();server.server_close()
        report={'purpose':'Validator regression fixtures, not a game acceptance result',
                'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results),'cases':results}
        if args.out:
            args.out.parent.mkdir(parents=True,exist_ok=True)
            args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        return 0 if not report['failed'] else 2


if __name__ == '__main__': raise SystemExit(main())

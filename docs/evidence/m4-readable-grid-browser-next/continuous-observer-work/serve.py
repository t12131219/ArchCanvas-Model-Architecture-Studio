"""Read-only measurement routes over independently stored formal Studio.

No model executes; the operator alone edits via the ordinary formal UI.
"""
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import hashlib
import json
from archcanvas_cli.server import ArchCanvasServer, Handler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = ROOT / 'docs/evidence/m4-viewport-resize-current/checks-final-attempt-2'
ROUTES = {
    '/__continuous/': ('harness.html','text/html; charset=utf-8'),
    '/__continuous/harness.mjs': ('harness.mjs','text/javascript; charset=utf-8'),
    '/__continuous/observer.mjs': ('observer.mjs','text/javascript; charset=utf-8'),
}

def bound(path):
    raw=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def context():
    receipt=json.loads((STAGE/'receipt.json').read_text())
    assets=[]
    for row in receipt['build']:
        path=ROOT/row['snapshot'];fingerprint=bound(path)
        if fingerprint['bytes']!=row['bytes'] or fingerprint['sha256']!=row['sha256']:
            raise ValueError('Frozen Studio asset binding is stale')
        assets.append(fingerprint)
    return {'schema':'archcanvas-responsive-continuous-context/1','productionAssets':assets,
            'probeSources':[bound(HERE/name) for name in ['serve.py','harness.html','harness.mjs','observer.mjs']],
            'formalStudioUnmodified':True,'dist':str(STAGE/'build'),
            'limits':['Responsive same-origin iframe is a separately recorded environment',
                      'Full input ledger completeness excludes unsupported event types and unformed native timing',
                      'DOM change and rAF are proxies, never presented FPS or continuous paint certification']}

class MeasurementHandler(Handler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if not path.startswith('/__continuous/'):
            return super().do_GET()
        if not self.guard():return
        if path=='/__continuous/context.json':return self.send_json(200,context())
        route=ROUTES.get(path)
        if route is None:return self.send_json(404,{'error':'Unknown measurement route'})
        name,mime=route;raw=(HERE/name).read_bytes()
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self'; frame-ancestors 'self'")
        self.end_headers();self.wfile.write(raw)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=42940)
    parser.add_argument('--data-dir',type=Path,required=True);args=parser.parse_args()
    context()  # Verify the exact frozen dist before startup.
    with ArchCanvasServer(('127.0.0.1',args.port),data_dir=args.data_dir,studio_dir=STAGE/'build') as server:
        server.RequestHandlerClass=MeasurementHandler
        print(f'Responsive measurement: http://127.0.0.1:{server.server_address[1]}/__continuous/',flush=True)
        server.serve_forever()

if __name__=='__main__':main()

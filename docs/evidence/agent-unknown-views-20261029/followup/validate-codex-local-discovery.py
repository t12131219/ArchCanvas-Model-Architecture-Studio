import json,subprocess,selectors,time
from pathlib import Path
workspace=Path('/home/fzg/PycharmProjects/ArchCanvas/Releases/20261029-agent-completion/final-codex-workspace')
output=Path('/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/agent-unknown-views-20261029/followup')
with (output/'codex-discovery.stderr.log').open('w') as error:
    process=subprocess.Popen(['/usr/lib/chatgpt/resources/codex','--no-daemon','app-server','--stdio'],cwd=workspace,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=error,text=True,bufsize=1)
    def send(value):
        process.stdin.write(json.dumps(value)+'\n');process.stdin.flush()
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    def response(identifier):
        end=time.monotonic()+25
        while time.monotonic()<end:
            if selector.select(max(0,end-time.monotonic())):
                line=process.stdout.readline()
                if not line: raise RuntimeError('Host client exited before discovery response')
                value=json.loads(line)
                if value.get('id')==identifier:return value
        raise TimeoutError('Codex client discovery response timed out')
    try:
        send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'clientInfo':{'name':'archcanvas-host-verification','version':'1.0'},'capabilities':{'experimentalApi':True}}})
        initial=response(1)
        if 'error' in initial: raise RuntimeError(str(initial['error']))
        send({'jsonrpc':'2.0','method':'initialized'})
        send({'jsonrpc':'2.0','id':2,'method':'skills/list','params':{'cwds':[str(workspace)],'forceReload':True}})
        result=response(2)
        if 'error' in result: raise RuntimeError(str(result['error']))
        data=result['result']['data']
        found=[s for row in data for s in row['skills'] if s['name']=='archcanvas']
        expected=str(workspace/'.agents/skills/archcanvas/SKILL.md')
        assert any(s['path']==expected and s['enabled'] for s in found),found
        report={'schema':'archcanvas-codex-real-discovery/1','status':'passed','workspace':str(workspace),'skills':found,'scope':'real-client-discovery-only','authenticatedAgentInvocation':'blocked-not-logged-in'}
        (output/'codex-final-real-discovery.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()

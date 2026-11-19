"""Decode the owned World FSM with its Japanese strings preserved, then list edges."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[3]
PROJECT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/ls_world_retarget/mhw_fsm'

def many(value):return value if isinstance(value,list) else [value] if isinstance(value,dict) and value.get('CLASS_ID')!=65534 else []
def main():
    source=Path('D:/MHW_extract/MHW_LS_LOGIC/hm/wp/wp03/wp03_action.fsm')
    out=ROOT/'.cache/mhw_ls_combat/fsm_source.fsm';shutil.copy2(source,out)
    sys.path.insert(0,str(CACHE/'deps'));sys.argv=[str(CACHE/'fsm_handling.py'),str(out)]
    script=(CACHE/'fsm_handling.py').read_text(encoding='utf8')
    script=script.replace("return obj.decode(self.encoding,'ignore')", "try:return obj.decode('utf8','strict')\n    except UnicodeDecodeError:return obj.decode('cp932','strict')")
    exec(compile(script,str(CACHE/'fsm_handling.py'),'exec'),{'__name__':'__main__'})
    parsed=json.loads(Path(str(out)+'.json').read_text(encoding='utf8'));root=parsed['root']
    nodes=root['mpRootCluster']['mpNodeList'];conditions=root['mpConditionTree']['mpTreeList']
    def action(n):
        for p in many(n['mpProcessList']):
            v=p.get('mpParameter',{}).get('ActionNo',{}).get('EnumValue')
            if v is not None:return v
    def properties(obj):
        found=[]
        if isinstance(obj,dict):
            if 'mPropertyName' in obj and obj['mPropertyName']:found.append(obj['mPropertyName'])
            for v in obj.values():found+=properties(v)
        elif isinstance(obj,list):
            for v in obj:found+=properties(v)
        return found
    cond={c['mName']['mId']:c for c in conditions}
    rows=[]
    for n in nodes:
        links=[]
        for e in many(n['mpLinkList']):
            target=next(v for v in nodes if v['mId']==e['mDestinationNodeId'])
            links.append({'node':target['mId'],'name':target['mName'],'action':action(target),
                'condition':e['mConditionId'],'properties':properties(cond.get(e['mConditionId'],{}))})
        rows.append({'node':n['mId'],'name':n['mName'],'action':action(n),'links':links})
    report={'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'string_encoding':'UTF8 with strict CP932 fallback','nodes':rows,'conditions':conditions}
    (PROJECT/'research/world_fsm_source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for n in rows:
        if n['action'] in (86,87,89,90,91,92,98,101,102,1013):print(json.dumps(n,ensure_ascii=False))

if __name__=='__main__':main()

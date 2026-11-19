"""Exhaustively compare generated C branches with source JSON condition trees.

Enumerates all relevant property combinations for each retained node, including
overlapping commands. This verifies priorities/AND/OR/helper preservation, not
the runtime bindings that produce those properties.
"""
from pathlib import Path
import ctypes as C
import itertools
import json
import shutil
import subprocess
from compile_world_ground_fsm import ROOT,PROJECT,AIR,EXTERNAL,rows

def variables(tree):
    if tree['CLASS_ID']==25:return {tree['mVariable']['mPropertyName']}
    if tree['CLASS_ID']==65534:return set()
    return set().union(*(variables(v)for v in rows(tree['mpChildList'])))

def source_eval(tree,enabled):
    kind=tree['CLASS_ID']
    if kind==65534:return None
    if kind==25:return tree['mVariable']['mPropertyName'] in enabled
    children=[source_eval(c,enabled)for c in rows(tree['mpChildList'])]
    children=[c for c in children if c is not None]
    if not children:return None
    op=tree['mOperator']
    if op==0:
        if len(children)!=1:raise ValueError('Source identity has multiple active operands')
        return children[0]
    if op==16:return all(children)
    if op==17:return any(children)
    raise ValueError(op)

def main():
    source=json.loads((ROOT/'.cache/mhw_ls_combat/fsm_source.fsm.json').read_text(encoding='utf8'))['root']
    contract=json.loads((PROJECT/'research/world_ground_contract.json').read_text(encoding='utf8'))
    bits={p:i for i,p in enumerate(contract['properties'])}
    trees={t['mName']['mId']:t['mpRootNode']for t in source['mpConditionTree']['mpTreeList']}
    out=ROOT/'.cache/mhw_ls_ground_rebuild';out.mkdir(parents=True,exist_ok=True)
    dll=out/'world_ground_vm.dll'
    subprocess.run([shutil.which('gcc'),'-std=c11','-O2','-shared',str(PROJECT/'tests/world_ground_vm_bridge.c'),'-o',str(dll)],check=True)
    portable=C.CDLL(str(dll));portable.ground_select.argtypes=[C.c_uint,C.c_uint64]
    portable.ground_select.restype=C.c_int
    cases=0;selected=set();per_node=[]
    for n in source['mpRootCluster']['mpNodeList']:
        node=n['mId']
        if node in AIR|EXTERNAL:continue
        links=[l for l in rows(n['mpLinkList'])if l['mDestinationNodeId']not in AIR|EXTERNAL]
        names=sorted(set().union(*(variables(trees[l['mConditionId']])for l in links if l['mExistCondition'])))
        before=cases
        for values in itertools.product((False,True),repeat=len(names)):
            enabled={k for k,v in zip(names,values)if v};expected=-1
            for edge in links:
                result=source_eval(trees[edge['mConditionId']],enabled)if edge['mExistCondition']else True
                if result is None:result=True
                if result:expected=edge['mDestinationNodeId'];break
            mask=sum(1<<bits[p]for p in enabled)
            actual=portable.ground_select(node,mask)
            if actual!=expected:raise AssertionError((node,sorted(enabled),expected,actual))
            if actual>=0:selected.add((node,actual))
            cases+=1
        per_node.append({'node':node,'combinations':cases-before})
    report={'status':'PASS_SOURCE_GRAPH_COMPILATION','combinations':cases,'nodes':len(per_node),
        'selectable_node_pairs':len(selected),'per_node':per_node,
        'limits':'Condition values supplied exhaustively; native input/cost/action bindings and actual playback remain pending.'}
    (PROJECT/'research/world_ground_graph_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k!='per_node'}))

if __name__=='__main__':main()

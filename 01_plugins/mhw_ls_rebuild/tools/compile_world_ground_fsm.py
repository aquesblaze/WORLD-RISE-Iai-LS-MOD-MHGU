"""Compile the owned W03 ground graph without flattening LinkMotion nodes.

Only the user's exclusions are removed. Original edge order and complete
AND/OR condition trees are retained. This is a source contract, not a claim
that the runtime adapter has executed every edge.
"""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[3]
PROJECT=Path(__file__).resolve().parents[1]
SOURCE=Path(r'D:\MHW_extract\MHW_LS_LOGIC\hm\wp\wp03\wp03_action.fsm')
AIR={17,18,19,20,21,22,24,25,26,27,43,44,46,47,48,49,50,51,59}
EXTERNAL={63,*range(66,75),*range(84,90)}

def rows(value):
    return value if isinstance(value,list) else [value] if value else []

def expression(value):
    if value['CLASS_ID']==65534:
        if value['content'] is not None:raise ValueError('Unexpected non-null expression')
        return {'constant':True}
    if value['CLASS_ID']==25:
        return {'property':value['mVariable']['mPropertyName'],
                'owner':value['mVariable']['mOwnerName']}
    children=[expression(v)for v in rows(value['mpChildList']) if v['CLASS_ID']!=65534]
    op=value['mOperator']
    if op==0:
        if not children:return {'constant':True}
        # The editor serializes an empty second operand for identity nodes.
        children=[c for c in children if c!={'constant':True}] or [{'constant':True}]
        if len(children)!=1:raise ValueError(('identity arity',children))
        return children[0]
    if op not in (16,17):raise ValueError(('Unknown source operator',op))
    return {'all' if op==16 else 'any':children}

def evaluate(tree,values):
    if 'constant'in tree:return tree['constant']
    if 'property'in tree:return values.get(tree['property'],False)
    if 'all'in tree:return all(evaluate(t,values)for t in tree['all'])
    return any(evaluate(t,values)for t in tree['any'])

def properties(tree):
    if 'property'in tree:return {tree['property']}
    return set().union(*(properties(t)for key in ('all','any')for t in tree.get(key,[])))

def compile_contract():
    root=json.loads((ROOT/'.cache/mhw_ls_combat/fsm_source.fsm.json').read_text(encoding='utf8'))['root']
    trees={v['mName']['mId']:expression(v['mpRootNode'])for v in root['mpConditionTree']['mpTreeList']}
    nodes=[];excluded=[];used=set()
    for n in root['mpRootCluster']['mpNodeList']:
        node=n['mId']
        if node in AIR|EXTERNAL:
            excluded.append({'node':node,'name':n['mName'],
                'reason':'standalone aerial/slope/climb' if node in AIR else 'slinger/clutch claw'})
            continue
        processes=[]
        for p in rows(n['mpProcessList']):
            param=p['mpParameter'];kind=p['mContainerName']
            if kind=='Action_W03':processes.append({'kind':'action','id':param['ActionNo']['EnumValue']})
            elif kind=='LinkMotion_W03':processes.append({'kind':'link_motion',
                'motion':param['MotionNo'],'phase1_motion':param['MotionNo_Phase1']})
            else:raise ValueError(('Unhandled source process',node,p))
        edges=[];dropped=[]
        for priority,link in enumerate(rows(n['mpLinkList'])):
            target=link['mDestinationNodeId']
            row=dict(priority=priority,target=target,condition=link['mConditionId'],
                     expression=trees[link['mConditionId']] if link['mExistCondition'] else {'constant':True})
            if target in AIR|EXTERNAL:dropped.append(row)
            else:
                edges.append(row);used|=properties(row['expression'])
        nodes.append({'node':node,'name':n['mName'],'processes':processes,'edges':edges,
                      'excluded_edges':dropped,'global_condition':
                      trees[n['mConditionTrainsitionFromAllId']] if n['mExistConditionTrainsitionFromAll'] else None,
                      'setting':n['mSetting'],'user_attribute':n['mUserAttribute']})
    return {'source':str(SOURCE),'sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'scope':'LS weapon ground branches; includes ground-initiated Helm chain; excludes slinger/clutch claw',
        'nodes':nodes,'excluded_nodes':excluded,'properties':sorted(used),
        'native_link_motion_contract':{'init_rva':'17845e0','update_rva':'1787950','main_entry_rva':'17896e0',
            'rule':'History/motion override first, then configured preparation and main motion; preserve both clocks.'},
        'runtime_acceptance':'PENDING: graph generation does not prove runtime integration or World parity'}

def write_header(contract):
    props=contract['properties'];pmap={p:i for i,p in enumerate(props)}
    instructions=[];edges=[];nodes=[]
    def emit(tree):
        if 'constant'in tree:instructions.append((0,1))
        elif 'property'in tree:instructions.append((1,pmap[tree['property']]))
        else:
            key='all' if 'all'in tree else 'any'
            for child in tree[key]:emit(child)
            instructions.append((2 if key=='all' else 3,len(tree[key])))
    for n in contract['nodes']:
        offset=len(edges)
        for edge in n['edges']:
            start=len(instructions);emit(edge['expression'])
            edges.append((edge['target'],start,len(instructions)-start,edge['condition']))
        p=n['processes']
        if len(p)!=1:raise ValueError(('source process count',n))
        proc=p[0];kind=proc['kind']=='action'
        nodes.append((n['node'],1 if kind else 2,proc['id'] if kind else proc['motion'],
                      -1 if kind else proc['phase1_motion'],offset,len(edges)-offset))
    s='/* Generated by compile_world_ground_fsm.py; native edge order retained. */\n#pragma once\n'
    s+='typedef struct {unsigned op,value;} WGroundTerm;\n'
    s+='typedef struct {unsigned target,offset,count,source_condition;} WGroundEdge;\n'
    s+='typedef struct {unsigned id,kind,value;int phase1;unsigned offset,count;} WGroundNode;\n'
    for typ,name,data in [('WGroundTerm','world_ground_terms',instructions),('WGroundEdge','world_ground_edges',edges),('WGroundNode','world_ground_nodes',nodes)]:
        s+=f'static const {typ} {name}[]={{\n'+''.join('    {'+','.join(map(str,row))+'},\n'for row in data)+'};\n'
    # Names allow native property bindings to be generated, not inferred from GU action IDs.
    s+='static const char *const world_ground_properties[]={\n'+''.join('    '+json.dumps(p,ensure_ascii=True)+',\n'for p in props)+'};\n'
    (PROJECT/'c/world_ground_graph.h').write_text(s,encoding='utf8')

def main():
    report=compile_contract();write_header(report)
    (PROJECT/'research/world_ground_contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'nodes':len(report['nodes']),'edges':sum(len(n['edges'])for n in report['nodes']),
                      'properties':report['properties'],'excluded_nodes':len(report['excluded_nodes'])},ensure_ascii=True))

if __name__=='__main__':main()

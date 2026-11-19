"""Check native one-shot visuals for every genuine delayed damage dispatch."""
import json,re,sys
from pc_fixture import Fixture
from animation_port import PROJECT,sha

def main():
    f=Fixture();report={'status':'FAIL','run':str(f.run),
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')}
    try:
        text=(f.run/'log.txt').read_text(errors='replace');events=[]
        if 'presentation=world-layers-v102' in text:
            name=sys.argv[1] if len(sys.argv)>1 else 'encounter_probe_auto.json'
            encounter=json.loads((f.run/name).read_text())
            with (f.run/'log.txt').open('rb') as stream:
                stream.seek(encounter['log_start'])
                text=stream.read(encounter['log_end']-encounter['log_start']).decode(errors='replace')
            pattern=r'ML_REBUILD: (world_simple_fx_emit|world_helm_fx_contact) (\w+) (\w+) (\w+) (\w+)'
            emitted=[(m[1],*[int(x,16) for x in m.groups()[1:]]) for m in re.finditer(pattern,text)]
            touches=[]
            for i,(tag,actor,shell,target,request) in enumerate(emitted):
                if tag!='world_helm_fx_contact':continue
                assert i and emitted[i-1][:3]==('world_simple_fx_emit',actor,0x3fc0) and emitted[i-1][4]==1
                assert target==encounter['target']
                touches.append(shell)
            damage=json.loads((f.run/(name[:-5]+'_seven_hit_report.json')).read_text())
            assert damage['plugin_sha256']==report['plugin_sha256'] and sorted(touches)==damage['contact_shells'] and len(touches)==7
            report.update(status='PASS_NATIVE_DELAYED_HIT_VISUALS',contact_shells=touches,source='EPV 2006/0')
            print(report['status'],len(touches))
            return
        for m in re.finditer(r'ML_REBUILD: (world_burst|world_simple_fx_emit) ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text):
            events.append((m[1],*[int(v,16)for v in m.groups()[1:]]))
        pairs=[]
        for i,(event,actor,source,ordinal,shell)in enumerate(events):
            if event!='world_burst':continue
            assert i+1<len(events)
            visual=events[i+1]
            assert visual[0]=='world_simple_fx_emit' and visual[1]==actor and visual[2]==0x3f61+ordinal%3 and visual[4]==1,(events[i],visual)
            pairs.append({'damage_source':source,'ordinal':ordinal,'shell':shell,'visual_uid':visual[2]})
        assert len(pairs)>=7 and any(p['ordinal']==6 for p in pairs),pairs
        report.update(status='PASS_NATIVE_DELAYED_HIT_VISUALS',contacts=pairs,
            limits='One native visual per dispatched damage shell; this does not add another collider or damage request.')
        print(report['status'],len(pairs))
    except Exception as exc:report['error']=repr(exc);raise
    finally:
        (f.run/'simple_hit_fx.json').write_text(json.dumps(report,indent=2)+'\n')
        (PROJECT/'research/world_simple_hit_fx.json').write_text(json.dumps(report,indent=2)+'\n');f.close()

if __name__=='__main__':main()

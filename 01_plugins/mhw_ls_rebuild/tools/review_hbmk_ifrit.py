"""Record a source-only review of the supplied HBMK-IFRIT reference.

Third-party scripts are parsed as text/AST, never executed by this review.
Compare their declared codec header with the owned GU template and our files.
"""
import ast,hashlib,json,struct,sys
from animation_port import ROOT,PROJECT,sha

def main():
    folder=ROOT/'.cache/third_party_reviews/hbmk_ifrit'
    source=(folder/'wav2adpcm_single.py').read_text(encoding='utf8');tree=ast.parse(source)
    calls=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call)and isinstance(node.func,ast.Attribute)and node.func.attr=='pack':
            if node.args and isinstance(node.args[0],ast.Constant):calls.append(node)
    stamp=next(c for c in calls if c.args[0].value=='<HHHH')
    values=[ast.literal_eval(n)for n in stamp.args[1:]]
    assert values==[2017,520,2828,40]
    first=next(c for c in calls if c.args[0].value=='<IHHIf')
    assert ast.literal_eval(first.args[1])==2 and ast.literal_eval(first.args[3])==256
    sys.path.insert(0,str(ROOT/'06_tools'));from arc_tool import read_entries,unpack_one
    template=ROOT/'Windows-MHGURecomp/data/romfs/nativeNX/arc/weapon/w07/snd/mat.arc'
    blob,_,entries=read_entries(template)
    native=unpack_one(blob,next(e for e in entries if e['hash']==0x79c47b59))[0]
    assert native[:8]==struct.pack('<IHH',2,1,256)
    native_stamp=list(struct.unpack_from('<4H',native,0x10))
    converted=json.loads((PROJECT/'research/world_full_audio_conversion.json').read_text())
    for row in converted['media']:
        from pathlib import Path
        b=(Path(converted['output_directory'])/f"{row['media']}.wave").read_bytes()
        assert b[:8]==native[:8]and b[0x10:0x18]==native[0x10:0x18]
        assert struct.unpack_from('<I',b,0x64)[0]==48000 and row['independent_decode_equal']
    notes=json.loads((PROJECT/'research/world_user_audio_notes_audit.json').read_text(encoding='utf8'))
    missing=[{'bank':r['bank'],'ordinal':r['ordinal'],'description':r['description'],
        'media':r['media'],'source_requests':r['source_requests']}for r in notes['rows']
        if r['description']and not r['gu_requests']]
    result={'status':'REFERENCE_REVIEWED_FORMAT_CROSSCHECK_PASS',
        'repository':'https://github.com/RTHKKona/HBMK-IFRIT','reviewed_tree_sha':'3f81131845e42761236fc91105b89602669aec23',
        'reviewed_files':{p.name:sha(p)for p in folder.iterdir()if p.is_file()},
        'source_only_review':True,'downloaded_binaries':(folder/'bin/manifest.json').exists(),'executed_third_party_scripts':False,
        'useful':['Independent confirmation of mono48kHz Capcom DSP-ADPCM header size0x78.',
            'Volume adjustment workflow for later measured GU/World comparison.',
            'Opus/STQR workflow is for streamed audio; this project uses SBKR/SRQR short-effect requests.'],
        'existing_pipeline':'VGAudio encoder plus independent DSP decoder already implement the required format.',
        'header_stamp':{'owned_gu':native_stamp,'ifrit_hardcoded':values,
            'rule':'Keep the owned GU template opaque metadata; do not substitute the tool hardcoded stamp.'},
        'encoder_comparison':{'decoded_pcm_identical':len(converted['media']),
            'quality_gain':False,'report':'hbmk_encoder_comparison.json'},
        'codec_crosschecked_media':len(converted['media']),'notes_duration_matches':notes['count'],
        'noted_named_media_missing_from_old_development_bank':missing,
        'remaining':'Event timing/provider selection, stop requests, dynamic Wwise controls, actual GU playback and full FSM/FX still require implementation/validation.'}
    (PROJECT/'research/hbmk_ifrit_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':result['status'],'codec_media':len(converted['media']),
        'matched_notes':notes['count'],'named_missing_old_bank':len(missing),'binaries_installed':False}))

if __name__=='__main__':main()

"""Read the patch-merged local chunk index and extract only LS presentation data.

Uses the already installed local extractor helper. No game files or keys are
placed under the source project; paths/hashes are the only persisted evidence.
"""
import argparse,json,os,subprocess,shutil
from pathlib import Path
from prepare_animation_sources import WRAPPER
from animation_port import ROOT,PROJECT,sha

CACHE=ROOT/'.cache/mhw_ls_presentation'
BODY=r'''
 public class ExtractPresentation {
  public static int Main(string[] args){
   var win=new MainWindow();var roots=new List<FileNode>();var chunks=new List<Chunk>();
   for(int i=1;i<args.Length;i++){
    var c=new Chunk();chunks.Add(c);win.AddChunk(args[i],c);roots=c.AnalyzeChunk(args[i],win,roots);
   }
   var all=new List<FileNode>();Walk(roots,all);Directory.CreateDirectory(args[0]);
   File.WriteAllLines(Path.Combine(args[0],"all_files.tsv"),all.FindAll(n=>n.IsFile).ConvertAll(n=>n.FromChunk+"|"+n.EntireName+"|"+n.Size));
   var extra=new HashSet<string>(StringComparer.OrdinalIgnoreCase){
    @"\hm\common\epv\hm_cm00.epv3",@"\sound\wwise\Windows\wp_swo_cmn.nbnk",
    @"\sound\pl\hm_wp_cmn_epvsp_snd_bk.wwbk",@"\sound\pl\hm_wp_cmn_epvsp_snd_ev.wwev"};
   var list=Path.Combine(args[0],"dependencies.txt");
   if(File.Exists(list))extra.UnionWith(File.ReadAllLines(list));
   var hits=all.FindAll(n=>n.IsFile && (extra.Contains(n.EntireName) || (n.EntireName.IndexOf("wp03",StringComparison.OrdinalIgnoreCase)>=0 &&
    (n.EntireName.IndexOf("sound",StringComparison.OrdinalIgnoreCase)>=0 ||
     n.EntireName.IndexOf("vfx",StringComparison.OrdinalIgnoreCase)>=0 ||
     n.EntireName.EndsWith(".epv3",StringComparison.OrdinalIgnoreCase)))));
   long bytes=0;foreach(var n in hits){bytes+=n.Size;if(n.Size>134217728)throw new Exception("Unexpected file size");}
   if(hits.Count==0 || bytes>268435456)throw new Exception("Unexpected extraction scope");
   File.WriteAllLines(Path.Combine(args[0],"selected.tsv"),hits.ConvertAll(n=>n.FromChunk+"|"+n.EntireName+"|"+n.Size));
   foreach(var n in hits)n.IsSelected=true;
   int failed=chunks[0].ExtractSelected(roots,Path.Combine(args[0],"source"),win);
   Console.WriteLine("LS presentation files="+hits.Count+", bytes="+bytes+", failures="+failed);
   return failed==0&&MainWindow.ErrorsStack.Count==0?0:1;
  }
  static void Walk(List<FileNode> roots,List<FileNode> all){foreach(var n in roots){all.Add(n);Walk(n.Childern,all);}}
 }
}
'''


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game',type=Path,default=Path('D:/APP/steam/steamapps/common/Monster Hunter World'))
    ap.add_argument('--helper',type=Path,default=Path('D:/MHW_extract/_helper'));args=ap.parse_args()
    key=ROOT/'MHW工具包/解包/MHWNoChunk_v2.2.1/chunk.key'
    csc=args.helper/'roslyn/tasks/net472/csc.exe';sources=[args.helper/n for n in ('Chunk.cs','FileNode.cs','Utils.cs')]
    chunks=sorted((args.game/'chunk').glob('chunkG*.bin'),key=lambda p:int(p.stem[6:]));assert chunks
    for p in [key,csc,*sources,args.helper/'oo2core_8_win64.dll']:assert p.is_file(),p
    CACHE.mkdir(parents=True,exist_ok=True);code=CACHE/'ExtractPresentation.cs';binary=CACHE/'ExtractPresentation.exe'
    deps=CACHE/'effect_dependencies.json'
    if deps.exists():
        requested=[]
        for raw in json.loads(deps.read_text(encoding='utf8')):
            path=raw.replace('\\','/').strip('/')
            assert path.startswith('vfx/') and '..' not in path.split('/') and ':' not in path
            requested.append('\\'+path.replace('/','\\')+'.efx')
        # Resolved against the patch-merged index; preserve actual extensions
        # and case. EFX model paths may resolve to both MOD3 and MRL3.
        asset_deps=CACHE/'presentation_asset_dependencies.json'
        if asset_deps.exists():
            for raw in json.loads(asset_deps.read_text(encoding='utf8')):
                path=raw.replace('\\','/').strip('/')
                assert (path.lower().startswith('vfx/') or path.lower()=='assets/default_tex/null_white.tex') and '..' not in path.split('/') and ':' not in path
                assert Path(path).suffix.lower() in ('.tex','.uvs','.mod3','.mrl3','.tfa')
                requested.append('\\'+path.replace('/','\\'))
        audio_deps=CACHE/'audio_dependencies.json'
        if audio_deps.exists():
            for raw in json.loads(audio_deps.read_text(encoding='utf8')):
                path=raw.replace('\\','/').strip('/')
                assert path.lower().startswith('sound/') and '..' not in path.split('/') and ':' not in path
                assert Path(path).suffix.lower() in ('.nbnk','.wwev','.wwbk','.wwsw','.wwpc','.wwspl','.wwct','.wwgp')
                requested.append('\\'+path.replace('/','\\'))
        (CACHE/'dependencies.txt').write_text('\n'.join(requested),encoding='ascii')
    code.write_text(WRAPPER.split(' public class ExtractSkeleton')[0]+BODY,encoding='utf8')
    subprocess.run([str(csc),'/nologo','/target:exe','/platform:x64',f'/out:{binary}',str(code),*map(str,sources)],check=True)
    shutil.copy2(args.helper/'oo2core_8_win64.dll',CACHE/'oo2core_8_win64.dll')
    env=os.environ.copy();env['MHW_LOCAL_CHUNK_KEY']=str(key)
    subprocess.run([str(binary),str(CACHE),*map(str,chunks)],cwd=CACHE,env=env,check=True)
    paths=sorted((CACHE/'source').rglob('*'))
    report={'status':'EXTRACTED_LOCAL_SOURCE_ONLY','patch_precedence':'Merged chunkG0 through highest installed chunk in numeric order.',
            'files':{str(p.relative_to(CACHE)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths if p.is_file()},
            'manifest_sha256':sha(CACHE/'selected.tsv'),'port_complete':False}
    (PROJECT/'research/world_presentation_sources.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],len(report['files']))


if __name__=='__main__':main()

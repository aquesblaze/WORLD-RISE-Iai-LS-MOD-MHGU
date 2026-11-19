"""Reproduce the small local skeleton fixture; no complete game extraction.

Requires the user's existing MHWNoChunk source helper and decompressor. Neither
third-party source/binaries nor the local chunk key are copied into this repo.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from animation_port import ROOT, CACHE, sha
sys.path.insert(0,str(ROOT/'06_tools'))
from arc_tool import read_entries,unpack_one

WRAPPER=r'''
using System;
using System.Collections.Generic;
using System.IO;
namespace MHWNoChunk {
 public class MainWindow {
  public static bool CNMode=false;
  public static Stack<string> ErrorsStack=new Stack<string>();
  public bool PauseFlag {get{return false;}}
  public bool TerminateFlag {get{return false;}}
  private Dictionary<string,Chunk> map=new Dictionary<string,Chunk>(StringComparer.OrdinalIgnoreCase);
  public void AddChunk(string path,Chunk c){map[path]=c;}
  public Chunk GetChunk(string path){return map[path];}
  public void PrintLog(string s){}
  public void SetProgressbar(int a,int b){}
  public void updateExtractProgress(){}
 }
 public static class Properties { public static class Resources {
  public static byte[] chunk=File.ReadAllBytes(Environment.GetEnvironmentVariable("MHW_LOCAL_CHUNK_KEY"));
 } }
 public class ExtractSkeleton {
  public static int Main(string[] args){
   var win=new MainWindow(); var roots=new List<FileNode>(); var chunks=new List<Chunk>();
   for(int i=1;i<args.Length;i++){
    var c=new Chunk();chunks.Add(c);win.AddChunk(args[i],c);roots=c.AnalyzeChunk(args[i],win,roots);
   }
   var all=new List<FileNode>(); Walk(roots,all);
   var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase){
    @"\pl\m_equip\pl001_0000\body\mod\m_body001_0000.mod3",
    @"\pl\f_equip\pl001_0000\body\mod\f_body001_0000.mod3",
    @"\hm\common\mod\debuf_body\m_debuf_body.mod3"};
   var hits=all.FindAll(n=>n.IsFile&&names.Contains(n.EntireName));
   if(hits.Count!=names.Count)throw new Exception("Missing skeleton fixture");
   foreach(var n in hits){if(n.Size>10000000)throw new Exception("Unexpected model size");n.IsSelected=true;}
   Directory.CreateDirectory(args[0]);
   File.WriteAllLines(Path.Combine(args[0],"manifest.txt"),hits.ConvertAll(n=>n.FromChunk+"|"+n.EntireName+"|"+n.Size));
   int failed=chunks[0].ExtractSelected(roots,args[0],win);
   Console.WriteLine("Selected models="+hits.Count+", extraction failures="+failed);
   return failed==0&&MainWindow.ErrorsStack.Count==0?0:1;
  }
  static void Walk(List<FileNode> roots,List<FileNode> all){foreach(var n in roots){all.Add(n);Walk(n.Childern,all);}}
 }
}
'''


def main():
    import os
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game',type=Path,default=Path(r'D:\APP\steam\steamapps\common\Monster Hunter World'))
    parser.add_argument('--helper',type=Path,default=Path(r'D:\MHW_extract\_helper'))
    parser.add_argument('--key',type=Path,default=ROOT/'MHW工具包/解包/MHWNoChunk_v2.2.1/chunk.key')
    args=parser.parse_args()
    csc=args.helper/'roslyn/tasks/net472/csc.exe'
    sources=[args.helper/name for name in ('Chunk.cs','FileNode.cs','Utils.cs')]
    for p in [csc,args.key,args.helper/'oo2core_8_win64.dll',*sources]:
        if not p.is_file():raise SystemExit(f'Missing existing extraction dependency: {p}')
    chunks=sorted((args.game/'chunk').glob('chunkG*.bin'),key=lambda p:int(p.stem[6:]))
    if not chunks:raise SystemExit('No source chunks found')
    CACHE.mkdir(parents=True,exist_ok=True)
    code=CACHE/'ExtractSkeletonRepro.cs';code.write_text(WRAPPER,encoding='utf8')
    binary=CACHE/'ExtractSkeletonRepro.exe'
    subprocess.run([str(csc),'/nologo','/target:exe','/platform:x64',f'/out:{binary}',str(code),*map(str,sources)],check=True)
    shutil.copy2(args.helper/'oo2core_8_win64.dll',CACHE/'oo2core_8_win64.dll')
    env=os.environ.copy();env['MHW_LOCAL_CHUNK_KEY']=str(args.key)
    subprocess.run([str(binary),str(CACHE/'source'),*map(str,chunks)],cwd=CACHE,env=env,check=True)
    for sex in ('m','f'):
        arc=ROOT/f'Windows-MHGURecomp/data/romfs/nativeNX/arc/player/com/{sex}/001/body.arc'
        raw,_,entries=read_entries(arc);models=[]
        for entry in entries:
            data,_=unpack_one(raw,entry)
            if data[:4]==b'MOD\0':models.append(data)
        if len(models)!=1:raise ValueError(f'Expected one body model in {arc}')
        (CACHE/f'gu_{sex}_body001.mod').write_bytes(models[0])
    outputs=[*sorted((CACHE/'source').rglob('*.mod3')),*sorted(CACHE.glob('gu_*.mod'))]
    manifest={str(p):sha(p) for p in outputs}
    (CACHE/'source_hashes.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('Prepared local source skeletons:',len(outputs))


if __name__=='__main__':main()

"""Accept the real installed entry without relabelling development evidence."""
import json,re,time,zipfile
from pathlib import Path
from animation_port import ROOT,PROJECT,sha
from launch_world_test import verify_install,DEST

def main():
    manifest=verify_install();meta=json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())
    run=Path(meta['run']).resolve();assert Path(meta['installed_entry']).resolve()==DEST.resolve()
    assert run.is_relative_to((ROOT/'.cache/mhw_ls_combat/runs').resolve())
    build=manifest['plugin_sha256'];cases=[]
    for rel,expected in manifest['files'].items():assert sha(run/rel)==expected
    assert len(manifest['files'])==12
    names=['feedback3.json','conditional_presentation.json','input_feel.json','loop_control.json',
           'reported_fixes.json','encounter_probe_auto_seven_hit_report.json']
    for name in names:
        path=run/name;data=json.loads(path.read_text(encoding='utf8'))
        assert data['status'].startswith('PASS')and data['plugin_sha256']==build,(name,data['status'])
        cases.append({'name':name,'path':str(path),'status':data['status'],'sha256':sha(path)})
    feedback=json.loads((run/names[0]).read_text());assert len(feedback['cases'])==17
    audio=json.loads((run/names[1]).read_text());assert len(audio['cases'])==7
    assert any(c['move']=='thrust'and c['rank']==1 and c['gauge']==0 and c['expected']for c in audio['cases'])
    auto=json.loads((run/'encounter_probe_auto.json').read_text())
    air=[s for s in auto['rows']if s['motion']==0x5e3]
    assert auto['auto_down_no_attack_input'] and air and all(s['raw_attack_buttons']==0 for s in air)
    cfg=(run/'mhgurecomp.ini').read_text(encoding='utf-8-sig')
    rendering={k:re.search(r'^'+k+r'\s*=\s*(.+)$',cfg,re.M)[1].strip()for k in('Resolution','RenderResolution','FSR','FSRQuality')}
    assert rendering['Resolution']=='1920x1080'and rendering['FSR']=='On'
    assert '[audren] f'not in(run/'log.txt').read_text(errors='replace'),'Dense trace is not a normal-rendering acceptance'
    development=json.loads((PROJECT/'research/world_regression.json').read_text(encoding='utf8'))
    assert development['status']=='PASS_REQUIRED_FIXTURE_CASES'and development['plugin_sha256']==build
    assert len(development['cases'])==35
    archive=ROOT/'02_build/history'/('mhw_ls_rebuild_feedback3_'+str(time.time_ns()))
    assert archive.resolve().is_relative_to((ROOT/'02_build/history').resolve());archive.mkdir(parents=True)
    report={'status':'PASS_INSTALLED_FEEDBACK3_NORMAL_RENDERING','plugin_sha256':build,'run':str(run),
        'entry':str(ROOT.parent/'启动MHGU_独立太刀测试.cmd'),'files':manifest['files'],'cases':cases,
        'rendering':rendering,'dense_audio_trace':False,'development_report_sha256':sha(PROJECT/'research/world_regression.json'),
        'development_cases':35,'source_snapshot_directory':str(archive),
        'limits':'Copied-save fixtures; original media playback and current source conditions confirmed. GU simplified flash rendering and native mixing remain; broader terrain/rig/variable-frame-step equivalence is not certified.'}
    text=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    (run/'installed_acceptance.json').write_text(text,encoding='utf8')
    (PROJECT/'research/world_feedback3_validation.json').write_text(text,encoding='utf8')
    prefix=f'''## 2026-11-12 最新三项反馈修正（本节覆盖下方历史）

当前 NRO `{build}`，已安装到 `{DEST}`；入口 `{ROOT.parent/'启动MHGU_独立太刀测试.cmd'}`。最新源码在 `{PROJECT}`，主目录旧源码未整体覆盖。独立存档和配置保留。

- A/X 后的 R 从原始按键开始计时，早按短按在同一动作的后续允许窗口执行；中断或换动作清理缓冲。普通攻击的气刃一式按原生15点门槛选择16/17，有练气走强化分支，空槽走弱分支。
- 气刃一式插入 A/X 使用原生22（气刃突刺连段），再接24（二式）；二式插入 A/X 使用25上挑，并按上一段上下文接27（三式），保留原生耗气。真实按键与空槽对照已覆盖。
- 大居合308..311保持原身体动作和根旋转，重新表达根平移增量以适配GU旋转空间。四种刃色空放推进/侧向偏差及连续动作时钟已检查，纠正后半段大幅绕回；实际地形仍由原生地面/碰撞处理。
- 看破斩：原版初始化练气门槛0.1，对应GU10/100，EPV2007/0→音效25606；气刃突刺：白刃以上，源Visual bit3第84帧，EPV2005/0→音效25515。四条原始声部已编码、独立解码、实际原生缓冲与系统PCM核对。加入wp03_005/050闪光；无练气看破、无刃色突刺有阴性对照，白刃空槽突刺有阳性对照。

开发运行 `{Path(development['run']).name}` 的35份匹配报告通过；真实D盘CMD入口运行 `{run.name}`，1920×1080 / FSR NativeAA、无密集音频跟踪，17组输入/空放、7组条件音画、9组手感、12次摇杆循环、居合源PCM/收刀及松键自动七段兜割通过。见 `research/world_feedback3_validation.json` 和 `research/world_regression.json`。重定位检查PASS。

测试修正：保留失败摆位/时序诊断；镜头使用固定初始站位、原生推进和侧向偏移，反击记录实际怪物65帧时序。摇杆试验退出显式归零；持续A试验记录R前原始按键，避免把呈现帧保持时间当作动画时钟。无修改反击窗口、碰撞或降低音频相关阈值。

限制：闪光采用原图集/颜色/生命周期与GU渲染；源HDR、复杂粒子、Wwise动态混音/衰减不宣称完整等价。更多地形、骨架和可变大步长仍需实战覆盖。未提交git。源码快照 `{archive/'source.zip'}`，不含游戏原始资源或编译产物。

---

'''
    documents=[PROJECT/'README.md',PROJECT.parents[1]/'07_docs/MHW太刀移植_新会话交接.md']
    for path in documents:path.write_text(prefix+path.read_text(encoding='utf8'),encoding='utf8')
    files={}
    with zipfile.ZipFile(archive/'source.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6)as package:
        for path in PROJECT.rglob('*'):
            if not path.is_file():continue
            rel=path.relative_to(PROJECT)
            if set(rel.parts)&{'target','__pycache__'}or path.suffix.lower()in{'.exe','.nro','.so','.dll','.pyd','.pyc'}:continue
            name='mhw_ls_rebuild/'+rel.as_posix();package.write(path,name);files[name]=sha(path)
        for path in documents[1:]:
            name='docs/'+path.name;package.write(path,name);files[name]=sha(path)
        header=PROJECT.parents[1]/'.cache/mhw_ls_animation_port/attachment_data.h'
        if header.exists():package.write(header,'generated/attachment_data.h');files['generated/attachment_data.h']=sha(header)
    with zipfile.ZipFile(archive/'source.zip')as package:
        import hashlib
        for name,expected in files.items():assert hashlib.sha256(package.read(name)).hexdigest()==expected
    (archive/'snapshot_manifest.json').write_text(json.dumps({'archive_sha256':sha(archive/'source.zip'),'files':files,
        'plugin_sha256':build,'development_report':str(PROJECT/'research/world_regression.json'),'installed_report':str(run/'installed_acceptance.json')},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(report['status'],build,'snapshot',archive)

if __name__=='__main__':main()

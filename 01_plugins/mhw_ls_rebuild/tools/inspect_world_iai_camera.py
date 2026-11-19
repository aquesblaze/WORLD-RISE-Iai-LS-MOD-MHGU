"""Trace Iai trigger31's receiver from its named DTI through camera ownership."""
import json,struct
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from inspect_world_actions import ROOT,PROJECT,BASE,TEXT,RDATA

def main():
    raw=(ROOT/'.cache/mhw_native/text.bin').read_bytes();data=(ROOT/'.cache/mhw_native/rdata.bin').read_bytes()
    cs=Cs(CS_ARCH_X86,CS_MODE_64);cs.detail=True
    def rip(at):
        i=next(cs.disasm(raw[at-TEXT:at-TEXT+16],BASE+at))
        return i.address+i.size+i.operands[1].mem.disp-BASE
    def code(a,z):return [f'{i.address-BASE:x} {i.mnemonic} {i.op_str}' for i in cs.disasm(raw[a-TEXT:z-TEXT],BASE+a)]
    assert rip(0x203001)==data.index(b'uMhCamera\0')+RDATA
    dti=rip(0x20300c);table=rip(0x203022)
    assert dti==rip(0x1b43952)==rip(0x1f9b664)==0x502ccc0
    assert struct.unpack_from('<Q',data,table-RDATA+8)[0]-BASE==0x1f9b660
    assert rip(0x1f9b86e)==0x3497340
    combat=json.loads((PROJECT/'research/world_combat_source.json').read_text(encoding='utf8'))
    resets={}
    for source in ('308','309','310','311'):
        common=[e for e in combat['clips'][source]['raw_events'] if e['type']=='PlMotionCommon']
        keys=next(t['keys'] for e in common for t in e['tracks'] if t['name']=='mCameraResetTime')
        assert len(keys)==2 and abs(keys[0][1]-.7)<1e-6 and keys[1][0]==37 and abs(keys[1][1]-.4)<1e-6
        resets[source]=keys
    assert rip(0x17ff991)==0x2174bf0
    assert struct.unpack_from('<f',data,0x2e4fe54-RDATA)[0]==.5
    assert struct.unpack_from('<f',data,0x2f954c4-RDATA)[0]==2500
    report={'status':'VERIFIED_CAMERA_RECEIVER','source_snapshot':'.cache/mhw_native/source.json',
        'class':'uMhCamera','dti_global':hex(dti),'dti_table':hex(table),'vtable':'0x3497340',
        'source_events':{'frames':[20,37],'reset_time_keys':resets,'pitch_degrees':3,
            'angle_space':'Absolute world pitch/yaw (request+1d=1), not relative to hunter facing.',
            'easing':'2174bf0: displacement * (1 - (elapsed / duration - 1)^4), quartic ease-out.',
            'target':'2122a30 blends the stored hit point halfway toward the nearest of6monster main-bone candidates; fallback is monster origin. It rejects a3D distance<=50 and a zero horizontal direction.',
            'guards':'Local active hunter, valid pending target, source camera lock guards and nonzero angular separation. Not every whiff requests a camera turn.'},
        'chain':['203001 names uMhCamera and initializes DTI502ccc0.',
            '1b43952 creates that DTI;1b439aa binds it to player via1f725a0.',
            '1f725ce stores the camera in player7690.',
            '11a11e8 copies player7690 to context46d0;11a13d7 passes it as r9 to12a8a90.',
            '12a8b42 stores r9 in camera-control subobject1e90.',
            'Big-Iai17ff8c0 ->19a5610 ->context1410 ->1294220 ->camera1f9dfa0.',
            '1f9dfa0 prepares camera angle interpolation; it does not rotate the hunter.'],
        'evidence':{n:code(a,z) for n,(a,z) in {
            'named_type':(0x203001,0x203037),'factory':(0x1f9b660,0x1f9b6be),
            'vtable_assignment':(0x1f9b850,0x1f9b878),'creation_and_binding':(0x1b4394b,0x1b439af),
            'player_camera_setter':(0x1f725a0,0x1f725e4),'context_camera':(0x11a11c0,0x11a1207),
            'forward_camera':(0x11a13d7,0x11a1408),'receiver_assignment':(0x12a8aa0,0x12a8b51),
            'iai_request':(0x17ff931,0x17ffa37),'target_direction':(0x2122a30,0x2122daa),
            'absolute_angle_space':(0x12943fd,0x1294488),'easing':(0x2174bf0,0x2174c23),
            'direction_consumer':(0x1294871,0x12948f1),'camera_setter':(0x1f9dfa0,0x1f9e0ff)}.items()},
        'implementation_status':'Implemented in world_camera.inc through GU23d80: trigger20/37, source linear reset-time curve, absolute3degree pitch, quartic ease-out with current-clock-before-increment order. Native contact/no-color/whiff and eye/look telemetry are verified separately by report_world_camera.py. Source6main-bone candidate selection is currently adapted to GU nearest posed bone; per-monster semantic mapping and obstruction acceptance remain.',
        'live_reference':'world_camera_observation.json records read-only World camera and common-motion float telemetry; it verifies raw interpolation2 as LINEAR and the one-frame evaluation clock lag.'}
    (PROJECT/'research/world_iai_camera_native.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('VERIFIED_CAMERA_RECEIVER: Iai trigger31 controls uMhCamera, not hunter rotation')

if __name__=='__main__':main()

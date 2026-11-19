"""Read the local source parameters; preserve offsets and native consumers."""
import json,re,struct
from Crypto.Cipher import Blowfish
from prepare_world_combat import ROOT,PROJECT,CACHE,SOURCE,sha

def decrypt(path,key):
    keys=dict(re.findall(r'public const string\s+(\w+)\s*=\s*"([^"]+)"',(CACHE/'EncryptionKeys.cs').read_text()))
    def swap(b):return b''.join(b[i:i+4][::-1] for i in range(0,len(b),4))
    return swap(Blowfish.new(keys[key].encode(),Blowfish.MODE_ECB).decrypt(swap(path.read_bytes())))

def shell(path):
    schema=(CACHE/'shlp.bt').read_text();b=decrypt(path,'OWP_DAT_KEY');p=12;out={}
    if b[4:8]!=b'SLP\0':raise ValueError('Unexpected shell parameter')
    types={'uint':'I','int':'i','float':'f','ubyte':'B','byte':'b','ushort':'H','short':'h'}
    def string():
        nonlocal p
        end=b.index(0,p);value=b[p:end].decode();p=end+1;return value
    def value(kind,key):
        nonlocal p
        fmt='<'+types[kind];v=struct.unpack_from(fmt,b,p)[0]
        out[key]={'offset':p,'value':v};p+=struct.calcsize(fmt);return v
    def block(s):
        for line in s.splitlines():
            m=re.match(r'(uint|int|float|ubyte|byte|ushort|short) (\w+)<',line)
            if m:value(*m.groups())
            m=re.match(r'if \((\w+) != 0\).*string (\w+)<',line)
            if m and out[m[1]]['value']:out[m[2]]={'offset':p,'value':string()}
    for _ in range(25):
        if value('uint','asset_header'):string()
    block(schema.split('// Shlp (1)')[1].split('// Number of Linked')[0])
    for _ in range(value('uint','LinkedCount')):
        value('uint','ChildHeader');string();p+=12
    block(schema.split('// EPV')[1].split('// Sound')[0])
    block(schema.split('// Sound')[1].split('// Shlp (2)')[0])
    block(schema.split('// Shlp (2)')[1].split('//')[0])
    return {'sha256':sha(path),'fields':out}

def main():
    path=SOURCE/'wp03_param.w03p';b=decrypt(path,'PL_PARAM_KEY')
    if b[:8]!=b'W03\0\x14\0\0\0':raise ValueError('Unexpected weapon parameter')
    result={'source':str(path),'sha256':sha(path),'action_params':{},'parameters':{}}
    for name,offset,runtime,consumer in [('helm_air',1476,0x9f0,'17fdfa0 -> 1f74df0'),('helm_down',1496,0xa20,'17ff670 trigger4 -> 1f74df0')]:
        values=struct.unpack_from('<5f',b,offset)
        result['action_params'][name]={'file_offset':offset,'runtime_struct':hex(runtime),'consumer':consumer,
            **dict(zip(['gravity','time_rate','x','y','z'],values))}
    for name,offset in [('foresight_resource_fraction',1221),('helm_regen',1233),('helm_red_regen',1237),
                        ('helm_regen_fill_seconds',1241),('helm_red_regen_fill_seconds',1245),
                        ('small_regen',1249),('small_counter_regen',1253),
                        ('small_regen_fill_seconds',1257),('small_counter_regen_fill_seconds',1261),
                        ('foresight_counter_mv_multiplier',1317),
                        ('foresight_armor_seconds',1332),('sheathe_seconds',1344),('iai_armor_seconds',1348),
                        ('big_counter_part_multiplier',1352),('big_delay',1356),('helm_first_delay',1528),
                        ('helm_interval',1532),('helm_last_delay',1536)]:
        result['parameters'][name]={'file_offset':offset,'value':struct.unpack_from('<f',b,offset)[0]}
    result['helm_hit_count']={'file_offset':1540,'value':struct.unpack_from('<I',b,1540)[0]}
    result['regen_native']={'consumer':'2123a72..2123b50','formula':'gauge_fraction += delta_seconds / fill_seconds',
        'independent_timers':['weapon2378 helm','weapon2380 iai'],'stacking':'add both rates while both timers are positive'}
    (PROJECT/'research/world_physics_source.json').write_text(json.dumps(result,indent=2))
    shells={name:shell(SOURCE/f'shell/data/{name}.shlp') for name in ['mikiri','iaigiri','iaikijin','finish_delay_hit_red','iaikijin_delay_hit_red']}
    # FS native init/update17fdae0/17ff620 ->2123270 creates three detectors.
    # Their source lifetimes overlap; native collision timing quantization
    # remains a runtime acceptance item, not an inferred extra frame.
    shells['foresight_detector_union']={'spawn_frames':[0,10,20],
        'lifespan_seconds':shells['mikiri']['fields']['Projectile_Model_Lifespan']['value'],
        'last_end_frame':20+60*shells['mikiri']['fields']['Projectile_Model_Lifespan']['value'],
        'native_consumers':['17fdae0','17ff620','2123270','21038b0','2125060']}
    (PROJECT/'research/world_shell_parameters.json').write_text(json.dumps(shells,indent=2))
    print('Read source physics, regen, delayed-hit and counter-shell parameters')

if __name__=='__main__':main()

"""Check native selector ordering and real source hand-switch boundaries."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as N
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_attachment_preview as a


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.clips={c.id:c for c in a.p.read_lmt_file(a.p.WORLD).actions}

    def test_real_thrust_switches_hands(self):
        clip=self.clips[170]
        self.assertEqual([a.select_function(clip,f,9) for f in (0,29.99,30,199.99,200)],
                         [30,30,47,47,30])

    def test_real_iai_sheath_attachment_lifetime(self):
        self.assertEqual([a.select_function(self.clips[306],f,10) for f in (0,80,271)],[30]*3)
        self.assertEqual([a.select_function(self.clips[307],f,10) for f in (0,24.99,25,137)],
                         [30,30,None,None])

    def test_common_mode_uses_record_order(self):
        def track(bone,value):
            return N(header=N(usage=2,bone_id=bone,buffer_type=1,buffer_size=0,basis=(1,value,1,0)),raw_buffer=b'')
        clip=N(tracks=[track(47,4),track(30,4)])
        self.assertEqual([a.select_function(clip,0,role) for role in (9,10)],[47,47])
        clip.tracks.reverse()
        self.assertEqual([a.select_function(clip,0,role) for role in (9,10)],[30,30])

    def test_invalid_context_rejected(self):
        for frame,role in ((-1,9),(float('nan'),9),(0,0)):
            with self.assertRaises(ValueError):a.select_function(self.clips[306],frame,role)

    def test_source_weapon_motion_events(self):
        raw=a.p.WORLD.read_bytes()
        keys=a.weapon_motion_keys(raw,self.clips[306])
        self.assertEqual([a.weapon_motion_at(keys,f) for f in (0,72.99,73,79.99,80,271)],
                         [-1,-1,3,3,0,0])
        for motion in (307,308,309,310):
            keys=a.weapon_motion_keys(raw,self.clips[motion])
            self.assertEqual([a.weapon_motion_at(keys,f) for f in (0,7.99,8,100)],
                             [2,2,1,1])
        self.assertEqual(a.weapon_motion_keys(raw,self.clips[170]),[])


if __name__=='__main__':unittest.main()

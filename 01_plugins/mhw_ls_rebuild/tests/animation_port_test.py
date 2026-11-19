"""Local-source checks for hierarchy conversion and GU bank preservation."""
import sys
import unittest
import struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import animation_port as p


class PortTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=p.read_skeleton(p.WORLD_MODEL,True)
        cls.target=p.read_skeleton(p.GU_MODEL,False)
        cls.actions={a.id:a for a in p.read_lmt_file(p.WORLD).actions}

    def test_rest_pose_collapse(self):
        rows=p.check_mapping(self.source,self.target)
        self.assertLess(max(x['max_rest_matrix_error'] for x in rows),0.001)
        self.assertEqual(rows[0]['source_chain'],[0,13])
        # Regression: source toe17 is NOT the opposite thigh.
        self.assertEqual(p.BODY_MAP[17],18)
        self.assertNotIn(17,p.BODY_MAP.values())

    def test_remapped_leg_motion_tracks_follow_source_hierarchy(self):
        pose,base=p.source_pose(self.actions[308],self.source)
        output=p.sample_body(pose,base,self.source,self.target,21.5)
        v=pose.sample(21.5,base=base)
        for gu,src in [(17,18),(18,19),(19,20)]:
            q=v[str(self.source.mapping[src]),0]
            self.assertTrue(p.np.allclose(p.quat_matrix(output[gu,0]),p.quat_matrix(q),atol=1e-6))

    def test_sparse_append_never_overwrites_stock(self):
        stock=(p.ROOT/'04_assets/hit_w07/player/mot/w07/w07').read_bytes()
        a=self.actions[140];data=p.bake(a,self.source,self.target)
        bank=p.write_bank([(224,a,data)]);merged=p.append_preview_bank(stock,bank)
        altered=[i for i,(x,y) in enumerate(zip(stock,merged)) if x!=y]
        self.assertTrue(all(8+4*224<=i<12+4*224 for i in altered))
        validation=p.verify_readback(merged,[(224,a,data)])
        self.assertLess(validation['max_rotation_error_degrees'],0.06)
        with self.assertRaisesRegex(ValueError,'overwrite stock'):
            p.append_preview_bank(stock,p.write_bank([(105,a,data)]))

    def test_raw_quaternion_sign_and_terminal_duration(self):
        values=[(0.01,-0.99995,0,0),(-0.01,0.99995,0,0),(0,0,0,-1)]
        codec,basis,raw=p.encode_component(values,0)
        self.assertEqual(codec,6)
        self.assertEqual(struct.unpack_from('<Q',raw,len(raw)-8)[0]>>56,0)
        with self.assertRaises(ValueError):p.encode_component([(float('nan'),0,0)],1)

    def test_model_lengths_remain_native(self):
        components=p.bake(self.actions[306],self.source,self.target)
        self.assertFalse(any(bone>0 and usage==1 for bone,usage in components))
        self.assertIn((0,1),components)
        female=p.read_skeleton(p.CACHE/'gu_f_body001.mod',False)
        for function in p.BODY_MAP:
            a=self.target.local[self.target.mapping[function]][:3,:3]
            b=female.local[female.mapping[function]][:3,:3]
            self.assertTrue(p.np.allclose(a,b,atol=1e-5))


if __name__=='__main__':unittest.main()

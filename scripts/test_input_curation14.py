"""Synthetic source tests; these invoke neither dotnet nor a native worker."""
import base64
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

path=Path(__file__).with_name('input02_sdk14_delta.py')
spec=importlib.util.spec_from_file_location('curation14',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def row(name='Synthetic.First',version='1.0.0'):
    return {'id':name,'version':version,'sha256':'a'*64,'expectedNormalizedContentHash':base64.b64encode(b'a'*64).decode()}

def block(r,primary=False):
    identity=r['id']+'.'+r['version']
    role='repository primary' if primary else 'author primary'
    return ('Verifying '+identity+'\nContent hash: '+r['expectedNormalizedContentHash']+'\nSignature type: '+('Repository' if primary else 'Author')+'\nVerifying the '+role+' signature with certificate:\nSHA256 hash: '+'b'*64+'\nSuccessfully verified package \''+identity+'\'.\n').encode()

class FiniteCuration14(unittest.TestCase):
    def test_batch_author_and_repository_primary(self):
        rows=[row(),row('Synthetic.Second','2.0.0')]
        actual=module.verification_report(block(rows[0])+block(rows[1],True),b'',rows,0)
        self.assertEqual(len(actual),2)
        self.assertEqual(actual[1]['rawSHA256'],rows[1]['sha256'])
        self.assertTrue(all(x['inputAdmission'] is False for x in actual))

    def test_each_unsafe_report_holds(self):
        a=row();good=block(a)
        cases=[(good,b'anything',[a],0),(good,b'',[a],1),
            (good+b'warning: ignored\n',b'',[a],0),
            (good+b'NU3018\n',b'',[a],0),
            (good+b'revocation status unknown\n',b'',[a],0),
            (good+b'\x00',b'',[a],0),
            (good+b'Verifying Unexpected.1.0.0\n',b'',[a],0),
            (good+good,b'',[a],0),(good+good,b'',[a,a],0),
            (good.replace(b'Content hash:',b'Content hash!:'),b'',[a],0),
            (good.replace(a['expectedNormalizedContentHash'].encode(),base64.b64encode(b'c'*64)),b'',[a],0),
            (good,b'',[{**a,'sha256':'UNKNOWN'}],0),
            (good,b'',[{**a,'id':'Other'}],0),
            (good.replace(b'Successfully verified package',b'Not successfully verified package'),b'',[a],0),
            (b'Content hash: invalid\n'+good,b'',[a],0),
            (good.replace(b'Signature type: Author\n',b''),b'',[a],0),
            (good.replace(b'SHA256 hash: ',b'Other hash: '),b'',[a],0)]
        for stdout,stderr,rows,code in cases:
            with self.subTest(index=cases.index((stdout,stderr,rows,code))):
                with self.assertRaises(ValueError):module.verification_report(stdout,stderr,rows,code)

    def test_ordered_explicit_plan_original_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();private=root/'inputs'
            plan=module.command_plan(root/'sdk/dotnet',root/'source',private,[private/'raw/synthetic.1.0.0.nupkg'])
            self.assertEqual(len(plan['commands']),14)
            self.assertEqual(sum(x['maximumSeconds'] for x in plan['commands']),270)
            self.assertEqual(plan['curationSubbudgetSeconds'],300)
            self.assertEqual(plan['commands'][6]['id'],'verify-new-enumerated-originals')
            self.assertEqual(plan['commands'][7]['id'],'lock-ExecutionLab')
            self.assertIn('--no-restore',plan['commands'][-1]['argv'])
            self.assertEqual(plan['SDKExecuted'],0)
            for vector in plan['commands']:
                self.assertTrue(all('<' not in x and '${' not in x for x in vector['argv']))
            for paths in ([],[private/'raw/*.nupkg'],[root/'other.nupkg'],[private/'raw/a.nupkg']*2,[private/'raw/../other.nupkg'],[private/'raw/a:stream.nupkg'],[private/'raw/A.nupkg',private/'raw/a.nupkg']):
                with self.subTest(paths=paths):
                    with self.assertRaises(ValueError):module.command_plan(root/'sdk/dotnet',root/'source',private,paths)

    def test_private_config_has_no_external_package_feed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();doc=ET.fromstring(module.config_bytes(root/'raw',root/'packages',43210,sorted(module.OFFICIAL_REPOSITORY_CERTIFICATES)))
            sources=doc.findall('packageSources/add')
            self.assertEqual(len(sources),1)
            self.assertEqual(sources[0].get('value'),str(root/'raw'))
            self.assertIsNotNone(doc.find('packageSources/clear'))
            self.assertIsNotNone(doc.find('fallbackPackageFolders/clear'))
            self.assertEqual(doc.find('config/add').get('value'),'require')
            self.assertEqual(doc.find('trustedSigners/repository/certificate').get('allowUntrustedRoot'),'false')
            self.assertEqual(doc.find('auditSources/add').get('value'),'http://127.0.0.1:43210/v3/index.json')
            for fingerprints in ([],['UNKNOWN'],['a'*64],['a'*64]*2):
                with self.subTest(fingerprints=fingerprints):
                    with self.assertRaises(ValueError):module.config_bytes(root/'raw',root/'packages',43210,fingerprints)

    def test_no_new_row_clock_or_extra_headroom(self):
        self.assertEqual(module.remaining_curation(0,100,0),300*10**9-100)
        for started,now,curation in ((100,99,100),(0,600*10**9,0),(0,302*10**9,301*10**9)):
            with self.subTest(now=now):
                with self.assertRaises(ValueError):module.remaining_curation(started,now,curation)

if __name__=='__main__':unittest.main()

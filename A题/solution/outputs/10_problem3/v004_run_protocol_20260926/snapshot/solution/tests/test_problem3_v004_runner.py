"""Exercise v004 runner recovery and protection, isolated from real archives."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

S=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(S/'experiments'))
import run_problem3_v004_full as runner
from run_problem2 import save


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.s=root/'solution';self.s.mkdir()
        (root/'data').mkdir();(root/'data/config.txt').write_text('config')
        (root/'data/case_001.json').write_text('{}')
        source=self.s/'fake.py';source.write_text('# source')
        (self.s/'src').mkdir();(self.s/'src/scene_b_window_components.py').write_text('# frozen')
        self.base=root/'base.json';self.base.write_text('{"node_to_subgraph":{},"core_schedules":[[]]}')
        self.out=self.s/'out';self.stack=ExitStack();self.addCleanup(self.stack.close)
        for name,value in [('S',self.s),('source_paths',lambda:[source]),
                           ('base_path',lambda c,n:self.base),('result_path',lambda p:self.out)]:
            self.stack.enter_context(patch.object(runner,name,value))
        self.args=argparse.Namespace(experiment='test',cases=['case_001'],cores=[1],resume=False,
            no_reuse=True,max_actions=None,interrupt_after_start=None)

    def manifest(self):return json.loads((self.out/'manifest.json').read_text(encoding='utf-8'))

    def test_interruption_preserved_and_resume_uses_new_attempt(self):
        self.args.interrupt_after_start=1;runner.run(self.args)
        first=self.manifest()['items'][0]['candidates']['baseline']['generation'][0]
        self.assertEqual(first['status'],'interrupted')
        self.args.resume=True;self.args.interrupt_after_start=None;self.args.max_actions=1
        runner.run(self.args)
        attempts=self.manifest()['items'][0]['candidates']['baseline']['generation']
        self.assertEqual(len(attempts),2);self.assertEqual(attempts[1]['status'],'success')
        self.assertNotEqual(attempts[0]['file'],attempts[1]['file'])

    def test_success_tamper_rejected_before_resume(self):
        self.args.max_actions=1;runner.run(self.args)
        rec=self.manifest()['items'][0]['candidates']['baseline']['generation'][-1]
        (self.out/rec['file']).write_text('{}')
        self.args.resume=True
        with self.assertRaises(ValueError):runner.run(self.args)

    def test_failed_and_timeout_attempts_not_retried(self):
        calls=[]
        def fail(*args):
            calls.append(args)
            return {'status':'timeout' if len(calls)==1 else 'failed','seconds':0,'returncode':1}
        with patch.object(runner,'run_command',fail):
            runner.run(self.args);before=len(calls)
            self.args.resume=True;runner.run(self.args)
        self.assertEqual(before,5);self.assertEqual(len(calls),before)
        self.assertEqual(self.manifest()['invocations'][-1]['actions'],0)

    def test_same_runner_lock_blocks_second_start(self):
        self.out.mkdir()
        with runner.run_lock(self.out):
            with self.assertRaises(OSError):
                with runner.run_lock(self.out):pass

    def test_partial_metadata_write_preserves_previous_manifest(self):
        target=self.s/'manifest.json';save(target,{'old':True})
        original=Path.write_text
        def broken(p,text,*args,**kwargs):
            original(p,text[:5],encoding='utf-8');raise OSError('injected write failure')
        with patch.object(Path,'write_text',broken):
            with self.assertRaises(OSError):save(target,{'new':True})
        self.assertEqual(json.loads(target.read_text()),{'old':True})


if __name__=='__main__':unittest.main()

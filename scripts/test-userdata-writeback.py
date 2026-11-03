#!/usr/bin/env python3
"""Userdata rebuilds must preserve archives and reject delayed writeback errors."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json,os,tempfile,unittest
from unixnu import userdata

class UserdataWriteback(unittest.TestCase):
    def context(self, root):
        images={}
        for name in ('OS','SystemOS'):
            p=root/(name+'.dmg');p.write_bytes((name.encode()*4096)[:4096]);images[name]=p
        source=SimpleNamespace(remote=False,member=lambda name:name,disk_image=lambda name:images[name])
        ctx=SimpleNamespace(work=root/'work',board={'userdata':{'first_lba':0,'last_lba':2047,'lba_bytes':4096,
            'windows':[{'name':name,'component':name} for name in images]}},args=SimpleNamespace(object=[]))
        return ctx,source
    def test_success_preserves_archived_hardlink(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ctx,source=self.context(root);out,image,report=userdata.paths(ctx);out.mkdir(parents=True)
            image.write_bytes(b'archived image');archive=root/'archived.img';os.link(image,archive)
            with patch.object(userdata,'Ipsw',return_value=source):userdata.build(ctx)
            self.assertEqual(archive.read_bytes(),b'archived image')
            record=json.loads(report.read_text());self.assertEqual([x['name'] for x in record['windows']],['OS','SystemOS'])
            self.assertNotEqual(image.stat().st_ino,archive.stat().st_ino)
    def test_wrong_root_digest_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as td:
            ctx,source=self.context(Path(td));ctx.board['root']={'os_image_sha256':'0'*64}
            out,image,report=userdata.paths(ctx);out.mkdir(parents=True)
            image.write_bytes(b'old');report.write_bytes(b'old report')
            with patch.object(userdata,'Ipsw',return_value=source):
                with self.assertRaisesRegex(userdata.Error,'differs from the root profile'):userdata.build(ctx)
            self.assertEqual(image.read_bytes(),b'old');self.assertEqual(report.read_bytes(),b'old report')
    def test_full_vroot_envelope_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ctx,source=self.context(root);policy=root/'manifest.bin'
            policy.write_bytes(b'VROOT01\0'+bytes(536)+bytes(32));ctx.args.object=[f'OS.vroot={policy}']
            with patch.object(userdata,'Ipsw',return_value=source):
                with self.assertRaisesRegex(userdata.Error,'raw block hashes'):userdata.build(ctx)
            self.assertFalse(userdata.paths(ctx)[1].exists())
    def test_vroot_header_offset_packages_only_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ctx,source=self.context(root);policy=root/'manifest.bin';hashes=bytes(range(32))
            policy.write_bytes(b'VROOT01\0'+bytes(536)+hashes);ctx.args.object=[f'OS.vroot={policy}:544']
            with patch.object(userdata,'Ipsw',return_value=source):userdata.build(ctx)
            _,image,report=userdata.paths(ctx);entry=json.loads(report.read_text())['objects'][0]
            self.assertEqual(entry['size'],32)
            with image.open('rb') as f:f.seek(entry['offset']);self.assertEqual(f.read(32),hashes)
    def test_fsync_error_preserves_old_image_and_report(self):
        with tempfile.TemporaryDirectory() as td:
            ctx,source=self.context(Path(td));out,image,report=userdata.paths(ctx);out.mkdir(parents=True)
            image.write_bytes(b'old');report.write_bytes(b'old report')
            with patch.object(userdata,'Ipsw',return_value=source),patch.object(userdata.os,'fsync',side_effect=OSError(5,'I/O error')):
                with self.assertRaises(OSError):userdata.build(ctx)
            self.assertEqual(image.read_bytes(),b'old');self.assertEqual(report.read_bytes(),b'old report')
if __name__=='__main__':unittest.main()

"""Verify encrypted checkpoint and optionally reconstruct compressed tar archives.

Install: python -m pip install cryptography zstandard
Verify: python restore_snapshot.py --key /private/recovery.key --verify
Export: python restore_snapshot.py --key /private/recovery.key --output /private/archives
The output contains sensitive data. Never extract into a running production tree.
"""
import argparse,hashlib,json,io,tarfile,sqlite3
from contextlib import closing
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import zstandard

class Frames(io.RawIOBase):
    def __init__(self,base,files,key):self.base=base;self.files=iter(files);self.aes=AESGCM(key);self.data=b'';self.pos=0
    def readable(self):return True
    def readinto(self,b):
        if self.pos==len(self.data):
            try:f=next(self.files)
            except StopIteration:return 0
            raw=(self.base/f['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('Hash mismatch: '+f['file'])
            if raw[:8]!=b'CADVPS01':raise ValueError('Invalid chunk header')
            self.data=self.aes.decrypt(raw[8:20],raw[20:],None);self.pos=0
        n=min(len(b),len(self.data)-self.pos);b[:n]=self.data[self.pos:self.pos+n];self.pos+=n;return n

def main():
    p=argparse.ArgumentParser();p.add_argument('--key',type=Path,required=True);p.add_argument('--verify',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--database-check-dir',type=Path);p.add_argument('--history-check-file',type=Path);p.add_argument('--sequence',type=int,action='append');a=p.parse_args()
    if not a.verify and not a.output:p.error('Choose --verify or --output')
    base=Path(__file__).resolve().parent;m=json.loads((base/'manifest.json').read_text());key=a.key.read_bytes()
    last_db_archive=[x for x in m['archives'] if x.get('kind')!='configuration-final'][-1]
    for archive in m['archives']:
        if a.sequence is not None and archive['sequence'] not in a.sequence:continue
        stream=io.BufferedReader(Frames(base,archive['files'],key),buffer_size=1024*1024)
        if a.verify:
            count=0;size=0
            with zstandard.ZstdDecompressor().stream_reader(stream,read_across_frames=True) as decoded:
                with tarfile.open(fileobj=decoded,mode='r|') as tar:
                    for member in tar:
                        count+=1;size+=member.size
                        # Advance through every byte, including files after tar metadata.
                        if member.isfile():
                            f=tar.extractfile(member)
                            prefix='root/vps-snapshot-20261009/consistent-databases/'
                            target=None
                            if a.database_check_dir and archive==last_db_archive and member.name.startswith(prefix):
                                relative=Path(member.name[len(prefix):])
                                if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe database path')
                                target=a.database_check_dir/relative;target.parent.mkdir(parents=True,exist_ok=True)
                            if a.history_check_file and archive==last_db_archive and member.name=='root/vps-snapshot-20261009/history.bundle':
                                a.history_check_file.parent.mkdir(parents=True,exist_ok=True)
                                with a.history_check_file.open('wb') as dest:
                                    while data:=f.read(1024*1024):dest.write(data)
                                print('Git history bundle recovered',flush=True)
                            elif target:
                                with target.open('wb') as dest:
                                    while data:=f.read(1024*1024):dest.write(data)
                                with closing(sqlite3.connect(target.resolve().as_uri()+'?mode=ro',uri=True)) as db:
                                    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Database integrity failed')
                                print('SQLite verified: '+str(relative),flush=True)
                            else:
                                while f.read(1024*1024):pass
                while decoded.read(1024*1024):pass
            print(f"Archive {archive['sequence']}: verified {count} entries, {size} bytes",flush=True)
        else:
            a.output.mkdir(parents=True,exist_ok=True)
            target=a.output/f"snapshot-{archive['sequence']:02d}.tar.zst"
            with target.open('wb') as out:
                while data:=stream.read(1024*1024):out.write(data)
            print('Exported '+str(target),flush=True)
if __name__=='__main__':main()

import subprocess
import math
import sys
import os

def get_git_files():
    result = subprocess.run(['git', 'status', '--porcelain', '-z', '--untracked-files=all'], 
                            stdout=subprocess.PIPE)
    if result.returncode != 0:
        print("Error running git status")
        sys.exit(1)
    
    entries = result.stdout.split(b'\0')
    files = []
    i = 0
    while i < len(entries):
        if not entries[i]:
            i += 1
            continue
        status = entries[i][:2]
        path = entries[i][3:]
        if b'R' in status or b'C' in status:
            i += 1 
        try:
            files.append(path.decode('utf-8'))
        except UnicodeDecodeError:
            files.append(path.decode('latin1'))
        i += 1
    return files

print("Getting list of changed files...", flush=True)
files = get_git_files()
if not files:
    print("No changes to commit.", flush=True)
    sys.exit(0)

LARGE_FILE_LIMIT = 95 * 1024 * 1024
filtered_files = []
for f in files:
    try:
        size = os.path.getsize(f)
        if size >= LARGE_FILE_LIMIT:
            print(f"Skipping large file (>=95MB): {f} ({size/1024/1024:.2f} MB)", flush=True)
            continue
    except:
        pass
    filtered_files.append(f)

files = filtered_files
chunk_size = 1000
total_chunks = math.ceil(len(files) / chunk_size)
print(f"Total files: {len(files)}, Chunks: {total_chunks}", flush=True)

def git_add(chunk_files):
    process = subprocess.Popen(['git', 'add', '--pathspec-from-file=-', '--pathspec-file-nul'], 
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    file_list = b'\0'.join(f.encode('utf-8') for f in chunk_files) + b'\0'
    out, err = process.communicate(input=file_list)
    if process.returncode != 0:
        print("git add failed:", err.decode('utf-8', errors='ignore'), flush=True)
        sys.exit(1)

for chunk_num in range(total_chunks):
    start = chunk_num * chunk_size
    end = min(start + chunk_size, len(files))
    chunk_files = files[start:end]
    
    print(f"Committing chunk {chunk_num + 1}/{total_chunks} ({len(chunk_files)} files)", flush=True)
    git_add(chunk_files)
    
    commit_msg = f"chore: automated chunk commit {chunk_num + 1}/{total_chunks}"
    c_res = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
    if c_res.returncode != 0 and "nothing to commit" not in c_res.stdout:
        print("Failed to commit:", c_res.stderr, flush=True)
        sys.exit(1)
    
    if "nothing to commit" not in c_res.stdout:
        push_result = subprocess.run(['git', 'push'], capture_output=True, text=True)
        if push_result.returncode != 0:
            if "has no upstream branch" in push_result.stderr:
                branch_result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
                branch = branch_result.stdout.strip()
                p_res2 = subprocess.run(['git', 'push', '--set-upstream', 'origin', branch], capture_output=True, text=True)
                if p_res2.returncode != 0:
                    print("Failed to push upstream:", p_res2.stderr, flush=True)
                    sys.exit(1)
            else:
                print("Failed to push:", push_result.stderr, flush=True)
                sys.exit(1)

print("All chunks processed successfully.", flush=True)

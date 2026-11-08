from pathlib import Path
import subprocess,sys,json,hashlib
root=Path(__file__).parent/'backup';root.mkdir(exist_ok=True)
p=root/'before_link_changes_flash_4MB.bin'
with (root/'read-flash.log').open('w',encoding='utf-8') as log:
 result=subprocess.run([sys.executable,'-m','esptool','--chip','esp32','--port','COM11','--baud','460800','read_flash','0','0x400000',str(p)],stdout=log,stderr=subprocess.STDOUT)
ok=result.returncode==0 and p.exists() and p.stat().st_size==4194304
record={'success':ok,'exit_code':result.returncode,'size':p.stat().st_size if p.exists() else 0}
if ok:record['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
(root/'backup-result.json').write_text(json.dumps(record,indent=2))

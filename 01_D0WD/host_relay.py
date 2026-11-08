import socket,select,json,time,os,ipaddress
from pathlib import Path
root=Path(__file__).parent/'udp-run';root.mkdir(exist_ok=True)
front=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);front.bind(('10.212.8.109',9999))
back=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);back.connect(('172.29.238.42',9999))
peer=None;received=returned=0;last=0
(root/'relay.pid').write_text(str(os.getpid()))
print('Relay listening on Windows WiFi UDP 9999; backend WSL UDP 9999',flush=True)
while True:
 for s in select.select([front,back],[],[],1)[0]:
  try:
   if s is front:
    data,addr=front.recvfrom(65535)
    if not ipaddress.ip_address(addr[0]) in ipaddress.ip_network('10.212.8.0/24'):continue
    if peer!=addr:peer=addr;print('Client',addr[0],addr[1],flush=True)
    back.send(data);received+=1
   else:
    data=back.recv(65535)
    if peer:front.sendto(data,peer);returned+=1
  except (ConnectionResetError,ConnectionRefusedError,OSError) as e:
   print(type(e).__name__,str(e),flush=True)
 if time.monotonic()-last>5:
  (root/'relay-status.json').write_text(json.dumps({'client':peer,'to_agent':received,'to_board':returned,'updated':time.time()}));last=time.monotonic()

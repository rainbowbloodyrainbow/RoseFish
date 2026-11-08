import socket,select,json,time,os,ipaddress
from pathlib import Path

root=Path(__file__).parent
front=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
front.bind(('127.0.0.1', 65431))
flows={};reverse={};received=returned=0;last=0
(root/'relay.pid').write_text(str(os.getpid()))
print('micro-ROS relay: WiFi UDP 8888 -> WSL UDP 8888; independent client flows',flush=True)

def remove(addr):
    back,_=flows.pop(addr)
    reverse.pop(back,None)
    back.close()

try:
    while True:
        now=time.monotonic()
        for addr,(_,used) in list(flows.items()):
            if now-used>0.6:remove(addr)
        for s in select.select([front,*reverse],[],[],.1)[0]:
            try:
                if s is front:
                    data,addr=front.recvfrom(65535)
                    if ipaddress.ip_address(addr[0]) not in ipaddress.ip_network('127.0.0.0/8'):continue
                    if addr not in flows:
                        if len(flows)>=128:remove(min(flows,key=lambda a:flows[a][1]))
                        back=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                        back.connect(('127.0.0.1', 65430))
                        flows[addr]=(back,now);reverse[back]=addr
                        print('Client flow',addr,flush=True)
                    back,_=flows[addr];flows[addr]=(back,now)
                    back.send(data);received+=1
                else:
                    addr=reverse[s]
                    data=s.recv(65535)
                    front.sendto(data,addr);returned+=1
                    # Backend retries do not prove the board-side UDP flow is alive.
                    # Keep the timestamp of the last packet received from the board.
            except (ConnectionResetError,ConnectionRefusedError,OSError) as e:
                print(type(e).__name__,str(e),flush=True)
        if now-last>0.05:
            (root/'relay-status.json').write_text(json.dumps({'clients':list(flows),'to_agent':received,'to_board':returned,'updated':time.time()}))
            last=now
finally:
    for addr in list(flows):remove(addr)
    front.close()

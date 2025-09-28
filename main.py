from pyroute2 import IPRoute, NDB
import pprint
import socket

class RouterInterface:
    netsize: int
    ip: str
    broadcast_ip: str
    label: str
    def __init__(self, netsize: int, ip: str, broadcast_ip: str, label: str):
        self.netsize = netsize
        self.ip = ip
        self.broadcast_ip = broadcast_ip
        self.label = label


def get_addrs(ndb: NDB) -> [RouterInterface]:
    result = []
    for record in ndb.addresses.summary():
        values = record._values
        if values[3].find('.') == -1:
            continue

        addr = RouterInterface(values[4], values[3], '255.255.255.255', values[2])
        result.append(addr)
    return result


def broadcast(ip: str, msg: str):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # using port 0 for auto port
    sock.bind((ip, 0))
    # port 8888 bc i like 8
    sock.sendto(msg, ("255.255.255.255", 8888))
    sock.close()

def main():
    s=socket(AF_INET, SOCK_DGRAM)
    s.bind('', 8888)
    with NDB() as ndb:
        addrs = get_addrs(ndb)
        for addr in addrs:
            broadcast(addr.broadcast_ip, addr.ip)
        while(True):
            msg = s.recvfrom(1024)
            print(msg)

if __name__ == "__main__":
    main()

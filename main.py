from pyroute2 import NDB
import os
import socket
import ipaddress
from ping3 import ping
from time import time

class Route:
    network: ipaddress.IPv4Network
    latency: int
    gateway: ipaddress.IPv4Address
    def __init__(self, *args):
        if len(args) == 1:
            if isinstance(args[0], tuple):
                """
                Construtor para tupla que recebemos do socket UDP
                msg: byte string para desserializar
                sender: tupla (ip, porta) de quem enviou a mensagem
                """
                msg = args[0][0]
                sender = args[0][1]
                self.gateway = ipaddress.IPv4Address(sender[0])
                self.network = ipaddress.ip_network((msg[8:12], int.from_bytes(msg[12:13], 'little')))
                self.latency = int.from_bytes(msg[:8], 'little')
            elif isinstance(args[0], ipaddress.IPv4Network):
                self.network = args[0]
                self.latency = 0
            else:
                raise RuntimeError("failed to create route using: " + type(args) + args)
        else:
            for arg in args:
                if isinstance(arg, ipaddress.IPv4Network):
                    self.network = arg
                elif isinstance(arg, ipaddress.IPv4Address):
                    self.gateway = arg
                elif isinstance(arg, int):
                    self.latency = arg
    def __str__(self):
        return "Route(" + self.network.with_prefixlen + ", " + str(self.latency) + ", " + self.gateway.compressed + ")"
    def packed(self) -> bytes:
        return self.latency.to_bytes(8, 'little') + self.network.network_address.packed + self.network.prefixlen.to_bytes(1)

class RouterInterface:
    ip: ipaddress.IPv4Address
    network: ipaddress.IPv4Network
    label: str
    def __init__(self, network: ipaddress.IPv4Network, ip: ipaddress.IPv4Address, label: str):
        self.network = network
        self.ip = ip
        self.label = label
    def to_route(self) -> Route:
        return Route(self.network)


def get_addrs(ndb: NDB) -> [RouterInterface]:
    result = []
    for record in ndb.addresses.dump():
        values = record._values
        ip = ipaddress.ip_address(values[7])
        if type(ip) != ipaddress.IPv4Address or ip.is_loopback or  values[10] == None:
            """
            Ignora interfaces de loopback, interfaces sem endereço de broadcast e tudo que não é ipv4 
            """
            continue
        network = ipaddress.ip_network((ip.compressed, values[3]), strict=False)

        addr = RouterInterface(network, ip, values[9])
        result.append(addr)
    return result


def broadcast(ip: ipaddress.IPv4Address, broadcast_ip: str, msg: bytes):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    # using port 0 for auto port
    sock.bind((ip.compressed, 0))
    # port 8888 bc i like 8
    sock.sendto(msg, (broadcast_ip, 8888))
    sock.close()

def broadcast_networks(addr, addrs):
    for routerInterface in addrs:
        if addr.ip != routerInterface.ip:
            continue
        broadcast(addr.ip, addr.network.broadcast_address.compressed, routerInterface.to_route().packed())

def spread_the_word(ndb, addrs):
    for addr in addrs:
        broadcast_networks(addr, addrs)

def calc_latency(ip: ipaddress.IPv4Address):
    return ping(ip.compressed, unit='ms')

class Consumer:
    routes = {}
    sock: socket.socket
    ndb: NDB
    def __init__(self, ndb: NDB):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.sock.setblocking(0)
        self.sock.bind(('', 8888))
        self.ndb = ndb
    def recv_route(self) -> Route | None:
        try:
            msg = self.sock.recvfrom(1024)
        except socket.error as e:
            if e.errno != socket.errno.EAGAIN and e.errno != socket.errno.EWOULDBLOCK:
                print("Socket erro", e)
            return None
        return Route(msg)
    def process_route(self, route: Route, neighbors):
        if neighbors[route.network.with_prefixlen]:
            return
        route.latency += calc_latency(route.gateway)
        old_route = self.routes[route.network.with_prefixlen]
        if old_route == None:
            self.ndb.routes.create(
                    dst=route.network.with_prefixlen,
                    gateway=route.gateway.compressed
            ).commit()
            self.routes[route.network.with_prefixlen] = route
            return
        if old_route.latency < route.latency:
            return
        self.routes[route.network.with_prefixlen] = route
        with self.ndb.routes[route.network.with_prefixlen] as old_table_route:
            old_table_route.set('gateway', route.gateway.compressed)

class Publisher:
    neighbors = {}
    ndb: NDB
    def __init__(self, ndb: NDB):
        self.ndb = ndb
    def publish(self):
        addrs = get_addrs(self.ndb)
        for addr in addrs:
            self.neighbors[addr.network.with_prefixlen] = True
        spread_the_word(self.ndb, addrs)
    def get_neighbors(self):
        return self.neighbors

def main():
    last_update = 0
    if os.path.exists('/init.sh'):
        system('/init.sh')
    with NDB() as ndb:
        publisher = Publisher(ndb)
        consumer = Consumer(ndb)
        while(True):
            """
            missing the interval checks
            """
            new_time = time()
            if (new_time - last_update) > 30:
                last_update = new_time
                publisher.publish()
            route = consumer.recv_route()
            if route == None:
                continue
            consumer.process_route(route, publisher.neighbors)

if __name__ == "__main__":
    main()

# 1. 修改网络拓扑：CustomTopo::build，修改h(主机的名称)与links
# 2. 修改路由：通过传入configure_policy_routes的参数

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
import time
import sys

class CustomTopo(Topo):
    def build(self):
        h = [f'h{i}' for i in range(1, 17)]

        # Add links with given bandwidth and delay specifications
        links = [
            (1, 4, 20, 4),
            (4, 5, 10, 4),
            (5, 6, 10, 4),
            (6, 7, 20, 4),
            (7, 8, 20, 4),
            (8, 9, 20, 4),
            (9, 2, 20, 4),

            (1, 10, 20, 4),
            (10, 11, 20, 4),
            (11, 12, 10, 4),
            (12, 13, 20, 4),
            (13, 14, 20, 4),
            (14, 15, 20, 4),
            (15, 2, 20, 4),

            (1, 3, 20, 4),
            (3, 4, 20, 4),
            (4, 5, 20, 4),
            (5, 11, 20, 4),
            (11, 12, 20, 4),
            (12, 16, 20, 4),
            (16, 2, 20, 4),
        ]

        
        # Add hosts
        h = [None] + [self.addHost(host) for host in h]

        intfs = dict()

        def _addLink_(i, j, bandwidth, delay):
            l1 = intfs.get(i, [])
            l2 = intfs.get(j, [])
            intfName1 = h[i] + '-eth' + str(len(l1))
            intfName2 = h[j] + '-eth' + str(len(l2))
            l1.append(len(l1))
            l2.append(len(l2))
            self.addLink(h[i], h[j], intfName1=intfName1, intfName2=intfName2, bw=bandwidth, delay=str(delay) + 'ms')
            intfs[i] = l1
            intfs[j] = l2

        for h1, h2, bw, delay in links:
            _addLink_(h1, h2, bw, delay)

def configure_policy_routes(net, routes):
    # routes: ["h1-eth0=h2=h3=h4-eth0", "h1-eth1=h5=h6=h4-eth0"]
    # route(字符串)中每一项以`=`分隔，第一项和最后一项为接口名，其余项为主机名

    # 配置IP地址
    i = 1
    for link in net.links:
        intf1, intf2 = link.intf1.name, link.intf2.name
        h1 = net.get(intf1.split('-')[0])
        h2 = net.get(intf2.split('-')[0])
        h1.setIP(f'10.0.{i}.1', 24, intf1)
        h2.setIP(f'10.0.{i}.2', 24, intf2)
        i += 1

    def getIntf(h, neigh):
        # 寻找`h`和`neigh`连接的接口
        # 返回: (h-intf, neigh-intf)
        for link in net.links:
            intf1, intf2 = link.intf1, link.intf2 # 实体
            h1 = intf1.name.split('-')[0] # 名称
            h2 = intf2.name.split('-')[0] # 名称
            if h1 in [h, neigh] and h2 in [h, neigh]:
                return (intf1, intf2) if h1 == h else (intf2, intf1)
    
    # 在`h`的路由表中添加表项：到`dst`的下一跳为`next`
    def addRoute(h, next, dst):
        """
        h: 配置路由的host
        next: 下一跳的host
        dst: 目标IP
        """
        host = net.get(h)
        print("===========add route:", f'ip route add {dst} via {getIntf(h, next)[1].IP()}')
        host.cmd(f'ip route add {dst} via {getIntf(h, next)[1].IP()}')

    def setForward(h):
        h = net.get(h)
        h.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")

    for i in range(len(routes)):
        l = routes[i].split('=')
        l[0] = getIntf(l[0], l[1])[0].name
        l[-1] = getIntf(l[-1], l[-2])[0].name
        routes[i] = '='.join(l)

    gateways = dict()
    for route in routes:
        h = route.split('=')
        h0 = h[0].split('-')[0]
        if gateways.get(h0) is None:
            gateways[h0] = dict()
        gateways[h0][h[0]] = h[1]

        h0 = h[-1].split('-')[0]
        if gateways.get(h0) is None:
            gateways[h0] = dict()
        gateways[h0][h[-1]] = h[-2]
    for h, gws in gateways.items():
        h = net.get(h)
        for i, (intf, gw) in enumerate(gws.items()):
            h.cmd(f'ip rule add from {h.IP(intf=intf)} table {i + 1}')
            h.cmd(f'ip route add default via {getIntf(h.name, gw)[1].IP()} table {i + 1}')
            if getIntf(h.name, gw)[0].name.find('eth0') >= 0:
                h.cmd(f'route add default gw {getIntf(h.name, gw)[1].IP()} dev {getIntf(h.name, gw)[0].name}')
        # h.cmd(f'route add default gw {getIntf(h.name, gw)[1].IP()} dev {getIntf(h.name, gw)[0].name}')

    for route in routes:
        h = route.split('=')
        src = net.get(h[0].split('-')[0]).IP(intf=h[0])
        dst = net.get(h[-1].split('-')[0]).IP(intf=h[-1])
        h[0] = h[0].split('-')[0]
        h[-1] = h[-1].split('-')[0]
        for i in range(1, len(h) - 1):
            setForward(h[i])
            addRoute(h[i], h[i - 1], src)
            addRoute(h[i], h[i + 1], dst)

def capturePackets(host):
    # 抓取`host`上的所有包
    for intf in host.intfList():
        host.cmd(f'tcpdump -XX -n -i {intf.name} -w {intf.name}.pcap &')

def run(algo):
    topo = CustomTopo()
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    net.start()
    
    configure_policy_routes(net, 
                            ['h1=h4=h5=h6=h7=h8=h9=h2', 
                             'h1=h10=h11=h12=h13=h14=h15=h2',
                             'h1=h3=h4=h5=h11=h12=h16=h2'])

    dumpNodeConnections(net.hosts)

    h1, h2 = net.get('h1', 'h2')
    h1.cmd(f"sysctl net.ipv4.tcp_congestion_control={algo}")
    h1.cmd('tcpdump -XX -n -i h1-eth2 -w ku/h1-eth2.pcap &')
    time.sleep(3)
    h1.cmd('python3 tcp_sender.py &')
    time.sleep(3)
    h2.cmd('python3 tcp_receiver.py 10.0.1.1')
    
    CLI(net)
    # net.pingAll()
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')

    algo = 'cubic'
    if len(sys.argv) > 1:
        algo = sys.argv[1]
    run(algo)

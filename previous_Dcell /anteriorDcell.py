#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import time

def MyNet():
    net = Mininet(controller=RemoteController, switch=OVSSwitch)
    c1 = net.addController('c1', controller=RemoteController, ip="172.20.0.2", port=6653)

    # Hosts
    h00 = net.addHost('h00', ip='10.0.0.1/24')
    h01 = net.addHost('h01', ip='10.0.0.2/24')
    h10 = net.addHost('h10', ip='10.0.0.3/24')
    h11 = net.addHost('h11', ip='10.0.0.4/24')
    h20 = net.addHost('h20', ip='10.0.0.5/24')
    h21 = net.addHost('h21', ip='10.0.0.6/24')

    # Switches
    s1 = net.addSwitch('s1', protocols="OpenFlow13")
    s2 = net.addSwitch('s2', protocols="OpenFlow13")
    s3 = net.addSwitch('s3', protocols="OpenFlow13")

    # Enlaces intra-celda (eth0 de cada host a su switch)
    net.addLink(h00, s1) # s1 port 1 -> h00
    net.addLink(h01, s1) # s1 port 2 -> h01
    net.addLink(h10, s2) # s2 port 1 -> h10
    net.addLink(h11, s2) # s2 port 2 -> h11
    net.addLink(h20, s3) # s3 port 1 -> h20
    net.addLink(h21, s3) # s3 port 2 -> h21

    # Enlaces inter-celda DCell (eth1 de cada host)
    net.addLink(h00, h10)
    net.addLink(h01, h20)
    net.addLink(h11, h21)

    net.build()
    c1.start()
    net.start()

    time.sleep(2)

    # Nota: Los flujos OpenFlow (ARP e IPv4 por in-port) son gestionados por OpenDaylight
    # vía el script 'subir_flows.py' conforme a la topología DCell.

    # Configuración de IPs en eth1
    links_directos = [
        ('h00', 'h10', '10.1.0.1', '10.1.0.2'),
        ('h01', 'h20', '10.2.0.1', '10.2.0.2'),
        ('h11', 'h21', '10.3.0.1', '10.3.0.2')
    ]

    for h1, h2, ip1, ip2 in links_directos:
        net.get(h1).cmd(f'ip addr add {ip1}/24 dev {h1}-eth1')
        net.get(h2).cmd(f'ip addr add {ip2}/24 dev {h2}-eth1')

    src_ip = {
        'h00': '10.0.0.1', 'h01': '10.0.0.2',
        'h10': '10.0.0.3', 'h11': '10.0.0.4',
        'h20': '10.0.0.5', 'h21': '10.0.0.6',
    }

    # Rutas estáticas DCell (especificando dev explícito)
    rutas = [
        ('h00', '10.0.0.2', '10.0.0.2', 'h00-eth0'),
        ('h00', '10.0.0.3', '10.1.0.2', 'h00-eth1'),
        ('h00', '10.0.0.4', '10.1.0.2', 'h00-eth1'),
        ('h00', '10.0.0.5', '10.0.0.2', 'h00-eth0'),
        ('h00', '10.0.0.6', '10.0.0.2', 'h00-eth0'),

        ('h01', '10.0.0.1', '10.0.0.1', 'h01-eth0'),
        ('h01', '10.0.0.3', '10.0.0.1', 'h01-eth0'),
        ('h01', '10.0.0.4', '10.0.0.1', 'h01-eth0'),
        ('h01', '10.0.0.5', '10.2.0.2', 'h01-eth1'),
        ('h01', '10.0.0.6', '10.2.0.2', 'h01-eth1'),

        ('h10', '10.0.0.1', '10.1.0.1', 'h10-eth1'),
        ('h10', '10.0.0.2', '10.1.0.1', 'h10-eth1'),
        ('h10', '10.0.0.4', '10.0.0.4', 'h10-eth0'),
        ('h10', '10.0.0.5', '10.0.0.4', 'h10-eth0'),
        ('h10', '10.0.0.6', '10.0.0.4', 'h10-eth0'),

        ('h11', '10.0.0.1', '10.0.0.3', 'h11-eth0'),
        ('h11', '10.0.0.2', '10.0.0.3', 'h11-eth0'),
        ('h11', '10.0.0.3', '10.0.0.3', 'h11-eth0'),
        ('h11', '10.0.0.5', '10.3.0.2', 'h11-eth1'),
        ('h11', '10.0.0.6', '10.3.0.2', 'h11-eth1'),

        ('h20', '10.0.0.1', '10.2.0.1', 'h20-eth1'),
        ('h20', '10.0.0.2', '10.2.0.1', 'h20-eth1'),
        ('h20', '10.0.0.3', '10.0.0.6', 'h20-eth0'),
        ('h20', '10.0.0.4', '10.0.0.6', 'h20-eth0'),
        ('h20', '10.0.0.6', '10.0.0.6', 'h20-eth0'),

        ('h21', '10.0.0.1', '10.0.0.5', 'h21-eth0'),
        ('h21', '10.0.0.2', '10.0.0.5', 'h21-eth0'),
        ('h21', '10.0.0.3', '10.3.0.1', 'h21-eth1'),
        ('h21', '10.0.0.4', '10.3.0.1', 'h21-eth1'),
        ('h21', '10.0.0.5', '10.0.0.5', 'h21-eth0'),
    ]

    for host, destino, via, dev in rutas:
        net.get(host).cmd(f'ip route add {destino}/32 via {via} dev {dev} src {src_ip[host]}')

    # Habilitar reenvío IP y deshabilitar rp_filter en todas las interfaces
    for host in net.hosts:
        host.cmd('sysctl -w net.ipv4.ip_forward=1')
        host.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        host.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        host.cmd(f'sysctl -w net.ipv4.conf.{host.name}-eth0.rp_filter=0')
        host.cmd(f'sysctl -w net.ipv4.conf.{host.name}-eth1.rp_filter=0')

    net.staticArp()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    MyNet()
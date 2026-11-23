#!/usr/bin/env python3
"""
Topología dinámica DCell para Mininet con integración a OpenDaylight.
"""

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import time
import sys
import json

ODL_IP = "172.20.0.2"
ODL_PORT = 6653

def DynamicDCell(num_cells=3):
    if num_cells < 2:
        print("Error: Se necesitan al menos 2 celdas para formar un DCell.")
        return

    # En DCell_1, cada celda tiene n = g - 1 hosts
    hosts_per_cell = num_cells - 1

    net = Mininet(controller=RemoteController, switch=OVSSwitch)
    c1 = net.addController('c1', controller=RemoteController, ip=ODL_IP, port=ODL_PORT)

    switches = {}
    hosts = {}
    src_ip = {}

    info(f'*** Creando {num_cells} celdas con {hosts_per_cell} hosts cada una ***\n')

    # 1. Crear Switches, Hosts y enlaces internos (Host <-> Switch de su celda)
    ip_counter = 1
    for i in range(num_cells):
        sw_name = f's{i+1}'
        switches[i] = net.addSwitch(sw_name, protocols="OpenFlow13")

        for j in range(hosts_per_cell):
            # Corrección: separador '_' para evitar colisión de nombres (ej. h1_10 vs h11_0)
            h_name = f'h{i}_{j}'
            
            # Formato de IP escalable
            h_ip = f'10.0.{i}.{j+1}' if num_cells >= 16 else f'10.0.0.{ip_counter}'
            src_ip[h_name] = h_ip
            
            hosts[(i, j)] = net.addHost(h_name, ip=f'{h_ip}/24')
            net.addLink(hosts[(i, j)], switches[i])
            ip_counter += 1

    # 2. Algoritmo de cableado DCell_1 (Enlaces directos entre celdas)
    links_directos = []
    cell_gateway = {}

    subnet_counter = 1
    for i in range(num_cells):
        for k in range(i + 1, num_cells):
            h1_idx = k - 1
            h2_idx = i
            h1_name = f'h{i}_{h1_idx}'
            h2_name = f'h{k}_{h2_idx}'

            ip1 = f'10.{subnet_counter}.0.1'
            ip2 = f'10.{subnet_counter}.0.2'

            net.addLink(hosts[(i, h1_idx)], hosts[(k, h2_idx)])
            links_directos.append((h1_name, h2_name, ip1, ip2))

            cell_gateway[(i, k)] = (h1_name, ip2)
            cell_gateway[(k, i)] = (h2_name, ip1)

            subnet_counter += 1

    # Guardar metadata de la topología para que create_flows.py sepa cuántos flujos crear
    topo_info = {
        "num_cells": num_cells,
        "hosts_per_cell": hosts_per_cell,
        "src_ip": src_ip
    }
    with open("/tmp/dcell_topo_info.json", "w") as f:
        json.dump(topo_info, f, indent=2)

    # 3. Construir e iniciar la red
    net.build()
    c1.start()
    net.start()

    time.sleep(2)

    # 4. Asignar IPs a las interfaces secundarias (eth1)
    info('*** Configurando interfaces secundarias directas (eth1) ***\n')
    for h1, h2, ip1, ip2 in links_directos:
        net.get(h1).cmd(f'ip addr add {ip1}/24 dev {h1}-eth1')
        net.get(h2).cmd(f'ip addr add {ip2}/24 dev {h2}-eth1')

    # 5. Habilitar reenvío IP en los hosts
    info('*** Habilitando IP Forwarding en hosts ***\n')
    for host in net.hosts:
        host.cmd('sysctl -w net.ipv4.ip_forward=1')
        host.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        host.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        host.cmd(f'sysctl -w net.ipv4.conf.{host.name}-eth0.rp_filter=0')
        host.cmd(f'sysctl -w net.ipv4.conf.{host.name}-eth1.rp_filter=0')

    # 6. Cálculo e instalación de rutas estáticas DCell
    info('*** Instalando rutas estáticas en hosts ***\n')
    for i in range(num_cells):
        for j in range(hosts_per_cell):
            h_src = f'h{i}_{j}'
            
            for dst_cell in range(num_cells):
                for dst_host in range(hosts_per_cell):
                    h_dst = f'h{dst_cell}_{dst_host}'
                    if h_src == h_dst:
                        continue
                    
                    dst_ip = src_ip[h_dst]

                    if i == dst_cell:
                        via_ip = dst_ip
                    else:
                        bridge_host, neighbor_eth1_ip = cell_gateway[(i, dst_cell)]
                        if h_src == bridge_host:
                            via_ip = neighbor_eth1_ip
                        else:
                            via_ip = src_ip[bridge_host]

                    net.get(h_src).cmd(f'ip route add {dst_ip}/32 via {via_ip} src {src_ip[h_src]}')

    net.staticArp()
    info('\n=======================================================\n')
    info(' [✓] Topología DCell en Mininet levantada con éxito.\n')
    info(' Abre otra terminal y ejecuta: python3 create_flows.py\n')
    info(' Luego regresa aquí y prueba con: pingall\n')
    info('=======================================================\n\n')
    
    # Abre la consola interactiva de Mininet
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    if len(sys.argv) > 1:
        celdas = int(sys.argv[1])
    else:
        try:
            entrada = input("Ingresa el número de celdas (por defecto 3): ").strip()
            celdas = int(entrada) if entrada else 3
        except ValueError:
            celdas = 3

    DynamicDCell(celdas)

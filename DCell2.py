#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import time
import sys

def DynamicDCell(num_cells=4):
    if num_cells < 2:
        print("Error: Se necesitan al menos 2 celdas para formar un DCell.")
        return

    # En DCell_1, para conectar 'g' celdas entre sí (grafo completo),
    # cada celda necesita exactamente n = g - 1 hosts.
    hosts_per_cell = num_cells - 1

    net = Mininet(controller=RemoteController, switch=OVSSwitch)
    c1 = net.addController('c1', controller=RemoteController, ip="10.103.150.31", port=6653)

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
            h_name = f'h{i}{j}'
            h_ip = f'10.0.0.{ip_counter}'
            src_ip[h_name] = h_ip
            
            # Se asigna la IP principal en eth0 automáticamente al crear el host
            hosts[(i, j)] = net.addHost(h_name, ip=f'{h_ip}/24')
            
            # El puerto del switch corresponderá a j + 1 (1, 2, ..., hosts_per_cell)
            net.addLink(hosts[(i, j)], switches[i])
            ip_counter += 1

    # 2. Algoritmo de cableado DCell_1 (Enlaces directos entre celdas)
    # Regla DCell: para dos celdas i < k, se conecta el host [i, k-1] con el host [k, i]
    links_directos = []
    # Diccionario para saber qué host local conecta con qué celda externa:
    # cell_gateway[(celda_origen, celda_destino)] = (nombre_host_puente, ip_vecino_en_eth1)
    cell_gateway = {}

    subnet_counter = 1
    for i in range(num_cells):
        for k in range(i + 1, num_cells):
            h1_idx = k - 1
            h2_idx = i
            h1_name = f'h{i}{h1_idx}'
            h2_name = f'h{k}{h2_idx}'

            ip1 = f'10.{subnet_counter}.0.1'
            ip2 = f'10.{subnet_counter}.0.2'

            net.addLink(hosts[(i, h1_idx)], hosts[(k, h2_idx)])
            links_directos.append((h1_name, h2_name, ip1, ip2))

            # Registrar quién es el puente entre la celda i y la celda k
            cell_gateway[(i, k)] = (h1_name, ip2)
            cell_gateway[(k, i)] = (h2_name, ip1)

            subnet_counter += 1

    # 3. Construir e iniciar la red
    net.build()
    c1.start()
    net.start()

    time.sleep(2)

    # 4. Configurar flujos OpenFlow13 dinámicamente en todos los switches
    info('*** Configurando flujos OpenFlow13 en switches ***\n')
    for i in range(num_cells):
        sw = net.get(f's{i+1}')
        sw.cmd(f'ovs-ofctl -O OpenFlow13 del-flows s{i+1}')
        sw.cmd(f'ovs-ofctl -O OpenFlow13 add-flow s{i+1} "priority=200,arp,actions=NORMAL"')
        
        for j in range(hosts_per_cell):
            h_name = f'h{i}{j}'
            h_ip = src_ip[h_name]
            port = j + 1
            sw.cmd(f'ovs-ofctl -O OpenFlow13 add-flow s{i+1} "priority=200,ip,nw_dst={h_ip},actions=output:{port}"')
        
        # Regla general de respaldo para tráfico IP en tránsito dentro del switch
        sw.cmd(f'ovs-ofctl -O OpenFlow13 add-flow s{i+1} "priority=100,ip,actions=NORMAL"')

    # 5. Asignar IPs a las interfaces secundarias (eth1) de los enlaces entre celdas
    info('*** Configurando enlaces directos entre hosts (eth1) ***\n')
    for h1, h2, ip1, ip2 in links_directos:
        net.get(h1).cmd(f'ip addr add {ip1}/24 dev {h1}-eth1')
        net.get(h2).cmd(f'ip addr add {ip2}/24 dev {h2}-eth1')

    # 6. Habilitar IP Forwarding y desactivar rp_filter en todos los hosts
    info('*** Habilitando IP Forwarding en los hosts ***\n')
    for host in net.hosts:
        host.cmd('sysctl -w net.ipv4.ip_forward=1')
        host.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        host.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')

    # 7. Cálculo e inyección dinámica de tablas de enrutamiento
    info('*** Calculando e instalando rutas estáticas ***\n')
    for i in range(num_cells):
        for j in range(hosts_per_cell):
            h_src = f'h{i}{j}'
            
            for dst_cell in range(num_cells):
                for dst_host in range(hosts_per_cell):
                    h_dst = f'h{dst_cell}{dst_host}'
                    if h_src == h_dst:
                        continue
                    
                    dst_ip = src_ip[h_dst]

                    if i == dst_cell:
                        # Destino en la misma celda: alcanzable directamente por el switch local
                        via_ip = dst_ip
                    else:
                        # Destino en otra celda (dst_cell):
                        # Buscamos qué host de nuestra celda 'i' tiene el cable directo hacia 'dst_cell'
                        bridge_host, neighbor_eth1_ip = cell_gateway[(i, dst_cell)]
                        
                        if h_src == bridge_host:
                            # Si YO soy el host puente de mi celda, salgo por mi interfaz eth1 hacia el vecino
                            via_ip = neighbor_eth1_ip
                        else:
                            # Si NO soy el puente, le envío el paquete al host puente de mi propia celda (por eth0)
                            via_ip = src_ip[bridge_host]

                    net.get(h_src).cmd(f'ip route add {dst_ip}/32 via {via_ip} src {src_ip[h_src]}')

    net.staticArp()
    info('*** Topología DCell lista. Prueba con "pingall" ***\n')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    # Puedes pasar el número de celdas como argumento: sudo python3 DCell.py 4
    # O si no pasas argumento, te lo preguntará al iniciar.
    if len(sys.argv) > 1:
        celdas = int(sys.argv[1])
    else:
        try:
            entrada = input("Ingresa el número de celdas (por defecto 3): ").strip()
            celdas = int(entrada) if entrada else 3
        except ValueError:
            celdas = 3

    DynamicDCell(celdas)
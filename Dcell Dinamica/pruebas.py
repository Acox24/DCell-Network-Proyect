#!/usr/bin/env python3

import subprocess
import time
import re
import csv
import sys
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def get_host_pid(host_name):
    """Obtiene el PID del proceso bash asociado al host en Mininet."""
    try:
        out = subprocess.check_output(
            ['pgrep', '-f', f'mininet:{host_name}$'],
            text=True
        ).strip()
        return out.splitlines()[0]
    except subprocess.CalledProcessError:
        print(f"Error: No se encontró el host '{host_name}'. ¿Está levantada la topología?")
        sys.exit(1)


def run_in_host(pid, cmd, background=False):
    """Ejecuta un comando dentro del namespace del host usando mnexec."""
    full_cmd = ['mnexec', '-a', pid] + cmd
    if background:
        return subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
    res = subprocess.run(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return res.stdout


def parse_ping(output):
    match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/([\d.]+) ms', output)
    if match:
        return float(match.group(1)), float(match.group(2))
    return 0.0, 0.0


def parse_iperf_tcp(output):
    matches = re.findall(r'([\d.]+)\s+(Gbits|Mbits|Kbits)/sec', output)
    if matches:
        val_str, unit = matches[-1]
        val = float(val_str)
        if unit == 'Gbits':
            return val * 1000.0
        elif unit == 'Kbits':
            return val / 1000.0
        return val
    return 0.0


def parse_iperf_udp(output):
    match = re.search(r'([\d.]+)\s+ms\s+\d+/\s*\d+\s+\(([\d.]+)%\)', output)
    if match:
        return float(match.group(1)), float(match.group(2))
    return 0.0, 0.0


def obtener_ip_host(c, h, hosts_per_cell=15):
    """Calcula la IP /24 asignada en la topología de 16 celdas (10.0.0.1 - 10.0.0.240)."""
    ip_counter = c * hosts_per_cell + h + 1
    return f"10.0.0.{ip_counter}"


def bridge_host_para_celda(celda_origen, celda_destino):
    """En DCell_1, el host de celda_origen que conecta directo a celda_destino."""
    return celda_destino - 1 if celda_origen < celda_destino else celda_destino


def construir_prueba(id_prueba, tipo, c1, h1, c2, h2):
    src = f"h{c1}_{h1}"
    dst = f"h{c2}_{h2}"
    dst_ip = obtener_ip_host(c2, h2)

    if tipo == 'Intra-celda':
        saltos_l3_l2 = f'0 L3 / 1 L2 (s{c1+1})'
        saltos_num = 1
    elif tipo == 'Inter-celda directo':
        saltos_l3_l2 = '1 L3 / 0 L2 (eth1)'
        saltos_num = 1
    else:
        b1 = bridge_host_para_celda(c1, c2)
        l3_hops = 2 if h1 == b1 else 3
        l2_hops = 1 if h1 == b1 else 2
        saltos_l3_l2 = f'{l3_hops} L3 / {l2_hops} L2 (tránsito)'
        saltos_num = l3_hops + l2_hops

    return {
        'id_prueba': id_prueba,
        'tipo': tipo,
        'src': src,
        'dst': dst,
        'ip': dst_ip,
        'saltos_l3_l2': saltos_l3_l2,
        'saltos_num': saltos_num
    }


def obtener_pruebas_fijas():
    """Devuelve 5 pruebas fijas por categoría (15 pruebas en total)."""
    pares = [
        # 5 Intra-celda
        ('Intra-celda', 0, 0, 0, 1),
        ('Intra-celda', 1, 2, 1, 3),
        ('Intra-celda', 3, 0, 3, 4),
        ('Intra-celda', 7, 5, 7, 6),
        ('Intra-celda', 15, 0, 15, 1),

        # 5 Inter-celda directo (eth1)
        ('Inter-celda directo', 0, 0, 1, 0),
        ('Inter-celda directo', 0, 1, 2, 0),
        ('Inter-celda directo', 1, 1, 2, 1),
        ('Inter-celda directo', 0, 14, 15, 0),
        ('Inter-celda directo', 4, 1, 5, 4),

        # 5 Inter-celda multi-salto (tránsito por hosts puente)
        ('Inter-celda multi-salto', 0, 0, 2, 1),
        ('Inter-celda multi-salto', 0, 2, 3, 5),
        ('Inter-celda multi-salto', 1, 0, 4, 3),
        ('Inter-celda multi-salto', 5, 0, 10, 2),
        ('Inter-celda multi-salto', 8, 1, 15, 7),
    ]

    return [
        construir_prueba(f"EXP-{idx:02d}", tipo, c1, h1, c2, h2)
        for idx, (tipo, c1, h1, c2, h2) in enumerate(pares, start=1)
    ]


def run_flow_test(prueba, duracion_tcp=5, duracion_udp=5):
    id_prueba = prueba['id_prueba']
    nombre = prueba['tipo']
    h_src = prueba['src']
    h_dst = prueba['dst']
    dst_ip = prueba['ip']

    print(f">>> [{id_prueba}] {nombre}: {h_src} -> {h_dst} ({dst_ip})")

    pid_src = get_host_pid(h_src)
    pid_dst = get_host_pid(h_dst)

    # 1. Ping (RTT promedio y desviación mdev)
    ping_out = run_in_host(pid_src, ['ping', '-c', '15', dst_ip])
    rtt_avg, rtt_mdev = parse_ping(ping_out)

    # 2. iperf TCP
    run_in_host(pid_dst, ['killall', '-9', 'iperf'])
    srv_tcp = run_in_host(pid_dst, ['iperf', '-s'], background=True)
    time.sleep(0.4)
    tcp_out = run_in_host(pid_src, ['iperf', '-c', dst_ip, '-t', str(duracion_tcp)])
    srv_tcp.terminate()
    run_in_host(pid_dst, ['killall', '-9', 'iperf'])
    tcp_mbps = parse_iperf_tcp(tcp_out)

    # 3. iperf UDP a 200 Mbps
    srv_udp = run_in_host(pid_dst, ['iperf', '-s', '-u'], background=True)
    time.sleep(0.4)
    run_in_host(pid_src, ['iperf', '-c', dst_ip, '-u', '-b', '200M', '-t', str(duracion_udp)])
    time.sleep(0.8)
    srv_udp.terminate()
    udp_server_out, _ = srv_udp.communicate()
    run_in_host(pid_dst, ['killall', '-9', 'iperf'])
    jitter_ms, loss_pct = parse_iperf_udp(udp_server_out)

    return {
        'ID Prueba': id_prueba,
        'Tipo de Flujo': nombre,
        'Trayectoria': f'{h_src} -> {h_dst}',
        'Saltos': prueba['saltos_num'],
        'Saltos L3/L2': prueba['saltos_l3_l2'],
        'Throughput TCP (Mbps)': round(tcp_mbps, 2),
        'RTT Promedio (ms)': round(rtt_avg, 3),
        'Desviación RTT mdev (ms)': round(rtt_mdev, 3),
        'Jitter UDP 200M (ms)': round(jitter_ms, 3),
        'Pérdida UDP (%)': round(loss_pct, 2)
    }


def run_concurrencia_test(pruebas_directas, duracion_tcp=5):
    """Satura 3 enlaces inter-celda directos en paralelo (estilo EXP-04 del reporte)."""
    subconjunto = pruebas_directas[:3]
    print("\n>>> [EXP-16] Concurrencia total (3 enlaces inter-celda directos en paralelo):")

    servidores = []
    for p in subconjunto:
        pid_dst = get_host_pid(p['dst'])
        run_in_host(pid_dst, ['killall', '-9', 'iperf'])
        srv = run_in_host(pid_dst, ['iperf', '-s'], background=True)
        servidores.append((pid_dst, srv))
    time.sleep(0.5)

    clientes = []
    for p in subconjunto:
        pid_src = get_host_pid(p['src'])
        cli = run_in_host(pid_src, ['iperf', '-c', p['ip'], '-t', str(duracion_tcp)], background=True)
        clientes.append((p, cli))

    total_tcp = 0.0
    trayectorias = []
    for p, cli in clientes:
        out, _ = cli.communicate()
        mbps = parse_iperf_tcp(out)
        total_tcp += mbps
        trayectorias.append(f"{p['src']}->{p['dst']} ({mbps:.0f}M)")
        print(f"    Flujo {p['src']} -> {p['dst']}: {mbps:.2f} Mbps")

    for pid_dst, srv in servidores:
        srv.terminate()
        run_in_host(pid_dst, ['killall', '-9', 'iperf'])

    return {
        'ID Prueba': 'EXP-16',
        'Tipo de Flujo': 'Concurrencia total',
        'Trayectoria': ', '.join(trayectorias),
        'Saltos': 1,
        'Saltos L3/L2': '1 L3 / 0 L2 (concurrente)',
        'Throughput TCP (Mbps)': round(total_tcp, 2),
        'RTT Promedio (ms)': 0.0,
        'Desviación RTT mdev (ms)': 0.0,
        'Jitter UDP 200M (ms)': 0.0,
        'Pérdida UDP (%)': 0.0
    }


def generar_graficas(resultados, filename='resultados_dcell_16_15pruebas.png'):
    individuales = [r for r in resultados if r['Tipo de Flujo'] != 'Concurrencia total']
    grupos = defaultdict(list)
    for r in individuales:
        grupos[r['Tipo de Flujo']].append(r)

    orden = ['Intra-celda', 'Inter-celda directo', 'Inter-celda multi-salto']
    flujos = [f for f in orden if f in grupos]

    tcp = [sum(x['Throughput TCP (Mbps)'] for x in grupos[f]) / len(grupos[f]) for f in flujos]
    rtt = [sum(x['RTT Promedio (ms)'] for x in grupos[f]) / len(grupos[f]) for f in flujos]
    mdev = [sum(x['Desviación RTT mdev (ms)'] for x in grupos[f]) / len(grupos[f]) for f in flujos]
    jitter = [sum(x['Jitter UDP 200M (ms)'] for x in grupos[f]) / len(grupos[f]) for f in flujos]
    loss = [sum(x['Pérdida UDP (%)'] for x in grupos[f]) / len(grupos[f]) for f in flujos]

    fig, axs = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle('Benchmark DCell (16 celdas, /24) — 5 pruebas fijas por tipo de flujo', fontsize=13, fontweight='bold')

    axs[0, 0].bar(flujos, tcp, color=['#2b5c8f', '#3a7ca5', '#5da271'])
    axs[0, 0].set_title('Throughput TCP promedio (Mbps)')
    axs[0, 0].set_ylabel('Mbps')
    axs[0, 0].grid(axis='y', linestyle='--', alpha=0.5)

    axs[0, 1].bar(flujos, rtt, yerr=mdev, capsize=5, color=['#d9822b', '#e6a15c', '#f2c185'])
    axs[0, 1].set_title('RTT promedio ± mdev (ms)')
    axs[0, 1].set_ylabel('ms')
    axs[0, 1].grid(axis='y', linestyle='--', alpha=0.5)

    axs[1, 0].bar(flujos, jitter, color=['#6c5b7b', '#8e7c9e', '#b0a0bf'])
    axs[1, 0].set_title('Jitter UDP a 200 Mbps (ms)')
    axs[1, 0].set_ylabel('ms')
    axs[1, 0].grid(axis='y', linestyle='--', alpha=0.5)

    axs[1, 1].bar(flujos, loss, color=['#c0392b', '#d9534f', '#e67e73'])
    axs[1, 1].set_title('Pérdida de paquetes UDP (%)')
    axs[1, 1].set_ylabel('%')
    axs[1, 1].grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(filename, dpi=300)
    print(f"Gráfica guardada en: {filename}")


if __name__ == '__main__':
    duracion_tcp = 5
    duracion_udp = 5

    pruebas = obtener_pruebas_fijas()
    resultados = [run_flow_test(p, duracion_tcp=duracion_tcp, duracion_udp=duracion_udp) for p in pruebas]

    directas = [p for p in pruebas if p['tipo'] == 'Inter-celda directo']
    resultados.append(run_concurrencia_test(directas, duracion_tcp=duracion_tcp))

    fieldnames = [
        'ID Prueba',
        'Tipo de Flujo',
        'Trayectoria',
        'Saltos',
        'Saltos L3/L2',
        'Throughput TCP (Mbps)',
        'RTT Promedio (ms)',
        'Desviación RTT mdev (ms)',
        'Jitter UDP 200M (ms)',
        'Pérdida UDP (%)'
    ]

    csv_file = 'resultados_dcell_16_15pruebas.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(resultados)
    print(f"\nTabla guardada en: {csv_file}")

    print("\n" + "="*132)
    print(f"{'ID':<7} | {'Tipo de Flujo':<23} | {'Trayectoria':<24} | {'Saltos L3/L2':<24} | {'TCP (Mbps)':<10} | {'RTT (ms)':<8} | {'mdev':<6} | {'Jitter':<7} | {'Loss %':<6}")
    print("-"*132)
    for r in resultados:
        tray = r['Trayectoria']
        if len(tray) > 24:
            tray = tray[:21] + "..."
        print(f"{r['ID Prueba']:<7} | {r['Tipo de Flujo']:<23} | {tray:<24} | {r['Saltos L3/L2']:<24} | {r['Throughput TCP (Mbps)']:<10} | {r['RTT Promedio (ms)']:<8} | {r['Desviación RTT mdev (ms)']:<6} | {r['Jitter UDP 200M (ms)']:<7} | {r['Pérdida UDP (%)']:<6}")
    print("="*132 + "\n")

    generar_graficas(resultados)
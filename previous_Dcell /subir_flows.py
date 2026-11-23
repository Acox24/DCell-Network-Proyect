#!/usr/bin/env python3
"""
Script para automatizar la inserción de flujos OpenFlow en OpenDaylight vía RESTCONF (RFC 8040).
"""

import sys
import os
import argparse
import requests

# Configuración por defecto
DEFAULT_ODL_IP = "172.20.0.2"
DEFAULT_ODL_PORT = 8181
DEFAULT_USER = "admin"
DEFAULT_PASS = "admin"

# Definición de flujos y destinos:
# (archivo, node_id, table_id, flow_id, descripcion)
FLOW_DEFINITIONS = [
    # Reglas ARP para conmutación normal (L2 broadcast y aprendizaje) en cada switch
    ("ARP.json", "openflow:1", 0, "1", "Regla ARP en switch s1 (NORMAL)"),
    ("ARP.json", "openflow:2", 0, "1", "Regla ARP en switch s2 (NORMAL)"),
    ("ARP.json", "openflow:3", 0, "1", "Regla ARP en switch s3 (NORMAL)"),

    # Flujos IPv4 intra-celda
    ("A101.json", "openflow:1", 0, "101", "Celda 0: h00 (port 1) -> h01 (port 2)"),
    ("A102.json", "openflow:1", 0, "102", "Celda 0: h01 (port 2) -> h00 (port 1)"),
    ("A201.json", "openflow:2", 0, "201", "Celda 1: h10 (port 1) -> h11 (port 2)"),
    ("A202.json", "openflow:2", 0, "202", "Celda 1: h11 (port 2) -> h10 (port 1)"),
    ("A301.json", "openflow:3", 0, "301", "Celda 2: h20 (port 1) -> h21 (port 2)"),
    ("A302.json", "openflow:3", 0, "302", "Celda 2: h21 (port 2) -> h20 (port 1)"),
]

def main():
    parser = argparse.ArgumentParser(description="Automatiza la subida de flujos OpenDaylight.")
    parser.add_argument("--ip", default=DEFAULT_ODL_IP, help=f"IP de OpenDaylight (default: {DEFAULT_ODL_IP})")
    parser.add_argument("--port", type=int, default=DEFAULT_ODL_PORT, help=f"Puerto RESTCONF (default: {DEFAULT_ODL_PORT})")
    parser.add_argument("--user", default=DEFAULT_USER, help=f"Usuario (default: {DEFAULT_USER})")
    parser.add_argument("--password", default=DEFAULT_PASS, help=f"Contraseña (default: {DEFAULT_PASS})")
    parser.add_argument("--flows-dir", default=None, help="Ruta a la carpeta con los archivos JSON (por defecto busca 'Flows' junto al script)")
    args = parser.parse_args()

    # Ubicar carpeta Flows
    script_dir = os.path.dirname(os.path.abspath(__file__))
    flows_dir = args.flows_dir or os.path.join(script_dir, "Flows")
    if not os.path.isdir(flows_dir):
        print(f"[!] Error: No se encontró la carpeta de flujos en: {flows_dir}")
        sys.exit(1)

    base_url = f"http://{args.ip}:{args.port}"
    auth = (args.user, args.password)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # 1. Verificar conectividad con OpenDaylight
    print(f"[*] Verificando conexión con OpenDaylight en {base_url}...")
    try:
        r = requests.get(f"{base_url}/rests/data", auth=auth, timeout=5)
        if r.status_code not in (200, 404, 409):
            print(f"[!] Advertencia: OpenDaylight respondió con código inesperado: {r.status_code}")
        else:
            print(f"[+] Conexión establecida con OpenDaylight (HTTP status: {r.status_code})\n")
    except requests.exceptions.RequestException as e:
        print(f"[X] No se pudo conectar a OpenDaylight: {e}")
        print("    Verifica que el contenedor OpenDaylight esté iniciado y Karaf tenga los features activos.")
        sys.exit(1)

    # 2. Subir cada uno de los flujos
    print(f"[*] Iniciando subida de flujos desde '{flows_dir}'...\n")
    success_count = 0

    for filename, node_id, table_id, flow_id, description in FLOW_DEFINITIONS:
        file_path = os.path.join(flows_dir, filename)
        if not os.path.isfile(file_path):
            print(f"[-] Archivo faltante: {filename} (saltando)")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            flow_data = f.read()

        # Endpoint RESTCONF RFC 8040
        endpoint = (
            f"{base_url}/rests/data/opendaylight-inventory:nodes"
            f"/node={node_id}/flow-node-inventory:table={table_id}/flow={flow_id}"
        )

        try:
            res = requests.put(endpoint, data=flow_data, headers=headers, auth=auth, timeout=10)
            if res.status_code in (200, 201, 204):
                print(f"  [OK {res.status_code}] {filename:<10} -> {node_id} (flow {flow_id}) | {description}")
                success_count += 1
            else:
                print(f"  [FALLO {res.status_code}] {filename:<10} -> {node_id} (flow {flow_id}) | Error: {res.text[:100]}")
        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] {filename:<10} -> {node_id} | Excepción: {e}")

    print(f"\n[✓] Proceso completado: {success_count}/{len(FLOW_DEFINITIONS)} flujos instalados exitosamente.")

if __name__ == "__main__":
    main()

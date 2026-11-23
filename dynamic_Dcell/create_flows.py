#!/usr/bin/env python3
"""
Script dinámico para generar y subir flujos a OpenDaylight (RESTCONF RFC 8040)
según el número de celdas DCell configuradas.
"""

import os
import sys
import json
import argparse
import requests

DEFAULT_ODL_IP = "172.20.0.2"
DEFAULT_ODL_PORT = 8181
DEFAULT_USER = "admin"
DEFAULT_PASS = "admin"

def generar_flujo_arp(flow_id="1"):
    return {
        "flow": [
            {
                "table_id": 0,
                "id": str(flow_id),
                "priority": 200,
                "match": {
                    "ethernet-match": {
                        "ethernet-type": { "type": 2054 }
                    }
                },
                "instructions": {
                    "instruction": [
                        {
                            "order": 0,
                            "apply-actions": {
                                "action": [
                                    {
                                        "order": 0,
                                        "output-action": { "output-node-connector": "NORMAL" }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        ]
    }

def generar_flujo_fallback(flow_id="2"):
    """Regla de respaldo: si el destino IP es de otra celda pero viaja a través del switch hacia el host puente."""
    return {
        "flow": [
            {
                "table_id": 0,
                "id": str(flow_id),
                "priority": 100,
                "match": {
                    "ethernet-match": {
                        "ethernet-type": { "type": 2048 }
                    }
                },
                "instructions": {
                    "instruction": [
                        {
                            "order": 0,
                            "apply-actions": {
                                "action": [
                                    {
                                        "order": 0,
                                        "output-action": { "output-node-connector": "NORMAL" }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        ]
    }

def generar_flujo_ipv4(flow_id, dst_ip, out_port):
    return {
        "flow": [
            {
                "table_id": 0,
                "id": str(flow_id),
                "priority": 200,
                "match": {
                    "ethernet-match": {
                        "ethernet-type": { "type": 2048 }
                    },
                    "ipv4-destination": f"{dst_ip}/32"
                },
                "instructions": {
                    "instruction": [
                        {
                            "order": 0,
                            "apply-actions": {
                                "action": [
                                    {
                                        "order": 0,
                                        "output-action": { "output-node-connector": str(out_port) }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        ]
    }

def main():
    parser = argparse.ArgumentParser(description="Genera y sube flujos dinámicos a OpenDaylight.")
    parser.add_argument("--cells", type=int, default=None, help="Número de celdas DCell (ej. 3, 4, 12)")
    parser.add_argument("--ip", default=DEFAULT_ODL_IP, help=f"IP de ODL (default: {DEFAULT_ODL_IP})")
    parser.add_argument("--port", type=int, default=DEFAULT_ODL_PORT, help=f"Puerto RESTCONF (default: {DEFAULT_ODL_PORT})")
    args = parser.parse_args()

    num_cells = args.cells
    src_ip_map = {}

    if os.path.exists("/tmp/dcell_topo_info.json"):
        with open("/tmp/dcell_topo_info.json", "r") as f:
            topo = json.load(f)
            if not num_cells:
                num_cells = topo.get("num_cells")
            src_ip_map = topo.get("src_ip", {})

    if not num_cells:
        try:
            num_cells = int(input("Ingresa el número de celdas creadas en Mininet: ").strip())
        except ValueError:
            print("Número de celdas inválido.")
            sys.exit(1)

    hosts_per_cell = num_cells - 1
    flows_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Flows")
    os.makedirs(flows_dir, exist_ok=True)

    base_url = f"http://{args.ip}:{args.port}"
    auth = (DEFAULT_USER, DEFAULT_PASS)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    print(f"[*] Verificando conexión con OpenDaylight en {base_url}...")
    try:
        r = requests.get(f"{base_url}/rests/data", auth=auth, timeout=5)
        print(f"[+] Conectado a OpenDaylight (HTTP {r.status_code})\n")
    except requests.exceptions.RequestException as e:
        print(f"[X] Error de conexión con ODL: {e}")
        sys.exit(1)

    # 1. Guardar archivos base
    arp_data = generar_flujo_arp(flow_id="1")
    with open(os.path.join(flows_dir, "ARP.json"), "w") as f:
        json.dump(arp_data, f, indent=2)

    fallback_data = generar_flujo_fallback(flow_id="2")
    with open(os.path.join(flows_dir, "FALLBACK_NORMAL.json"), "w") as f:
        json.dump(fallback_data, f, indent=2)

    total_uploaded = 0
    total_expected = (num_cells * 2) + (num_cells * hosts_per_cell)

    print(f"[*] Generando e instalando flujos para {num_cells} switches (DCell_1)...\n")

    ip_counter = 1
    for i in range(num_cells):
        node_id = f"openflow:{i+1}"
        
        # 1. Flujo ARP (priority 200, NORMAL)
        endpoint_arp = f"{base_url}/rests/data/opendaylight-inventory:nodes/node={node_id}/flow-node-inventory:table=0/flow=1"
        res = requests.put(endpoint_arp, json=arp_data, headers=headers, auth=auth, timeout=10)
        if res.status_code in (200, 201, 204):
            print(f"  [OK {res.status_code}] Switch {node_id} -> Flujo ARP instalado")
            total_uploaded += 1
        else:
            print(f"  [FALLO {res.status_code}] Switch {node_id} ARP: {res.text[:80]}")

        # 2. Flujo Fallback L2 NORMAL para tráfico inter-celda en tránsito por el switch local (priority 100)
        endpoint_fb = f"{base_url}/rests/data/opendaylight-inventory:nodes/node={node_id}/flow-node-inventory:table=0/flow=2"
        res = requests.put(endpoint_fb, json=fallback_data, headers=headers, auth=auth, timeout=10)
        if res.status_code in (200, 201, 204):
            print(f"  [OK {res.status_code}] Switch {node_id} -> Flujo Fallback (NORMAL) instalado")
            total_uploaded += 1
        else:
            print(f"  [FALLO {res.status_code}] Switch {node_id} Fallback: {res.text[:80]}")

        # 3. Flujos IPv4 por cada host conectado directamente al switch
        for j in range(hosts_per_cell):
            h_name = f"h{i}_{j}"
            h_ip = src_ip_map.get(h_name)
            if not h_ip:
                h_ip = f"10.0.{i}.{j+1}" if num_cells >= 16 else f"10.0.0.{ip_counter}"
            
            port = j + 1
            flow_id = 100 + port
            ipv4_data = generar_flujo_ipv4(flow_id, h_ip, port)
            
            flow_filename = f"flow_s{i+1}_port{port}.json"
            with open(os.path.join(flows_dir, flow_filename), "w") as f:
                json.dump(ipv4_data, f, indent=2)

            endpoint_flow = f"{base_url}/rests/data/opendaylight-inventory:nodes/node={node_id}/flow-node-inventory:table=0/flow={flow_id}"
            res = requests.put(endpoint_flow, json=ipv4_data, headers=headers, auth=auth, timeout=10)
            if res.status_code in (200, 201, 204):
                print(f"  [OK {res.status_code}] Switch {node_id} (flow {flow_id}) -> IP {h_ip} a puerto {port}")
                total_uploaded += 1
            else:
                print(f"  [FALLO {res.status_code}] Switch {node_id} flow {flow_id}: {res.text[:80]}")

            ip_counter += 1

    print(f"\n[✓] Completado: {total_uploaded}/{total_expected} flujos generados y subidos exitosamente a ODL.")

if __name__ == "__main__":
    main()

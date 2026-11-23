# Comandos útiles

## Docker

- Ver contenedores activos (`-a` para todos):
  ```bash
docker ps
```

- Iniciar un contenedor:
  ```bash
docker start <NOMBRE_O_ID_DEL_CONTENEDOR>
```

- Ver imágenes instaladas:
  ```bash
sudo docker images
```

- Detener un contenedor:
  ```bash
docker stop <NOMBRE_O_ID>
```

- Eliminar un contenedor:
  ```bash
docker rm <NOMBRE_O_ID>
```

- Crear un contenedor a partir de una imagen:
  ```bash
sudo docker run -t -d --name <NOMBRE> <IMAGEN>
```

- Obtener la IP de un contenedor:
  ```bash
sudo docker inspect <NOMBRE_O_ID> | grep -i ipaddress
```

- Detener todos los contenedores:
  ```bash
docker stop $(docker ps -q)
```

- Acceder a un contenedor:
  ```bash
docker exec -it <NOMBRE_O_ID> /bin/bash
```

- Salir del contenedor:
  ```bash
Ctrl + D
```

- Crear un contenedor Mininet con privilegios:
  ```bash
sudo docker run -itd \
  --name Mininet \
  --privileged \
  --network bridge \
  iwaseyusuke/mininet:latest
```

- Ver contenedores y su red asociada:
  ```bash
docker ps -a --format "table {{.Names}}\t{{.Networks}}"
```

- Reiniciar Docker:
  ```bash
sudo systemctl restart docker
```

- Obtener la IP de un contenedor por formato:
  ```bash
docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <NOMBRE_O_ID>
```

- Ver interfaces bridge:
  ```bash
sudo brctl show
```

- Conectar un contenedor a una red:
  ```bash
docker network connect --ip 172.20.0.3 sdn-network Mininet
```

- Ver interfaces del kernel:
  ```bash
ip -br link
```

- Apagar Docker completamente:
  ```bash
sudo systemctl stop docker.service docker.socket
```

- Resolver la red SDN:
  ```bash
chmod +x ./fix-sdn-net.sh
```

## Crear interfaz puente

```bash
sudo ip link add name br-f0112628d3ef type bridge
sudo ip addr add 172.20.0.1/16 dev br-f0112628d3ef
sudo ip link set br-f0112628d3ef up
```

Esclavizar interfaces virtuales:

```bash
sudo ip link set vethcaec63d master br-f0112628d3ef
sudo ip link set veth53fe9e3 master br-f0112628d3ef
```

Permitir tráfico en el firewall:

```bash
sudo iptables -A FORWARD -i br-f0112628d3ef -o br-f0112628d3ef -j ACCEPT
```

## OpenDaylight CLI

- Ver conexiones activas:
  ```bash
ofp : show-session-stats
```

- Ejecutar la CLI de ODL:
  ```bash
./bin/karaf
```

- Instalar herramientas OpenFlow:
  ```bash
feature:install \
  odl-openflowplugin-flow-services-rest \
  odl-openflowplugin-app-table-miss-enforcer \
  odl-openflowplugin-nxm-extensions
```

- Configurar Java:
  ```bash
export JAVA_HOME=/usr
```

## Karaf

- Definir la variable de entorno de Java:
  ```bash
export JAVA_HOME=/usr
```

## Mininet

- Crear una red topológica remota:
  ```bash
mn --controller=remote,ip=172.20.0.2,port=6653 \
  --topo=tree,2 \
  --switch=ovsk,protocols=OpenFlow13
```

- Obtener el mapeo de la red (`net`):
  ```bash
net
```

- Ver conectividad IP y puerto:
  ```bash
nc -zv 172.20.0.2 6653
```

- Imagen y comandos útiles para Mininet en Docker:
  - [Docker Hub - iwaseyusuke/mininet](https://hub.docker.com/r/iwaseyusuke/mininet)

## Direcciones de ejemplo

- IP de OpenDaylight: `172.20.0.2`
- IP de Mininet: `172.20.0.3`

## Nota

Estos comandos son de apoyo para la configuración del entorno SDN y pueden requerir ajustes según la topología y la infraestructura local utilizada.


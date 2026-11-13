**ip** **COMANDOS UTILES**  
**DOCKER**  
- Ver contenedores (-a para activos): docker ps  
- Activar un contenedor: docker start <NOMBRE_O_ID_DEL_CONTENEDOR>  
- Ver imagenes en tu sistema:  sudo docker images  
- Detener un contenedor: docker stop <nombre_o_id>  
- Borrar un contenedor: docker rm <nombre_o_id>  
- Crear un contenedor en base a una imagen: sudo docker run -t -d -- name ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAADUlEQVR4nGP4//8/AwAI/AL+p5qgoAAAAABJRU5ErkJggg==)  
- Obtener IP de un contenedor: sudo docker inspect  | grep -i ipaddress  
- Detener todos los contenedores: docker stop $(docker ps -q)  
- Acceder a un contendor: docker exec -it my_container /bin/bash  
- Ver ip de contenedor:  
- Contenedor MIninet con privilegios: sudo docker run -itd   
   
 --name Mininet   
   
 --privileged   
   
 --network bridge   
   
 iwaseyusuke/mininet:latest  
- Salir de un contenedor: Ctrl + D  
- Ver contenedores y su respectiva red:  
   
 docker network disconnect -f experiment-network OpenDaylight  
   
 docker network create experiment-network  
   
 docker network connect experiment-network OpenDaylight  
   
 docker ps -a --format "table {{.Names}}\t{{.Networks}}"  
- Reiniciar Docker: systemctl restart docker  
- Ver ip de contenedor: docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' nombre_o_id_del_contenedor  
- Ver interfaces br: sudo brctl show  
- Conectar contenedor a una red: docker network connect --ip 172.20.0.3 sdn-network Mininet.  
- Ver interfaces que tiene el kernel: ip -br link  
- Apagar docker completamente: sudo systemctl stop docker.service docker.socket  
- Resolver red sdn net: chmod +x ./fix-sdn-net.sh  
**CREAR INTERFAZ PUENTE**  
sudo ip link add name br-f0112628d3ef type bridge  
   
 sudo ip addr add 172.20.0.1/16 dev br-f0112628d3ef  
   
 sudo ip link set br-f0112628d3ef up  
Esclavizar extermos virutales:  
sudo ip link set vethcaec63d master br-f0112628d3ef  
   
 sudo ip link set veth53fe9e3 master br-f0112628d3ef  
Permitir envio de paquetes en el firewall  
sudo iptables -A FORWARD -i br-f0112628d3ef -o br-f0112628d3ef -j ACCEPT  
**OpenDaylight CLI**  
- Ver si existen conexiones activas: ofp : show-session-stats  
- Ejecutar OD CLI $> ./ bin / karaf  
- Instalar herramientes openflow: feature:install odl-openflowplugin-flow-services-rest odl-openflowplugin-app-table-miss-enforcer odl-openflowplugin-nxm-extensions  
- Setear Java: export JAVA_HOME=/usr  
**Karaf**  
- Definir variable de entorno de JAVA:  export JAVA _ HOME =/ usr  
**Mininet**  
- Crear red topologica: mn --controller=remote,ip=172.20.0.2,port=6653   
   
 --topo=tree,2   
   
 --switch=ovsk,protocols=OpenFlow13  
- net: obtener mapeo  
- Ver conectividad de ip y puerto: nc -zv 172.20.0.2 6653  
Imagen y comandos para mininet en docker: [https://hub.docker.com/r/iwaseyusuke/mininet](https://hub.docker.com/r/iwaseyusuke/mininet "https://hub.docker.com/r/iwaseyusuke/mininet")  
**IP OD:** 172.20.0.2  
   
 **IP Mininet:** 172.20.0.3  

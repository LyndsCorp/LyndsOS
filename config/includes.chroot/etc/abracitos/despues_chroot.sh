#!/bin/bash

plymouth-set-default-theme lyndsos
update-initramfs -u

# Se actualiza a si mismo
echo "Actualizando Casata"
casata install casata -y
casata add oficial
casata add forge
casata update

# LYNDS Project
echo "Instalando apps de LYNDS Project"
casata install lynds-wallpapers-installer -y
casata install lyndshub -y
casata install lyndsfetch -y

# Monojo Project
echo "Instalando apps de Monojo Project"
casata install mc-lan -y
casata install md-lan -y
casata install monojo-music -y
casata install monojo-calculator -y

echo "Instalando Infernal, el lenguaje de programación"
casata install infernal -y

echo "Instalando Zen Browser"
casata install zen-browser -y

exit 0

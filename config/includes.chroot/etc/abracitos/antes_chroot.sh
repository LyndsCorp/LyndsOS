#!/bin/bash

export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

echo "Configurando repositorios oficiales de Debian..."
cat <<EOF > /etc/apt/sources.list
deb http://deb.debian.org/debian/ trixie main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian/ trixie main contrib non-free non-free-firmware
deb http://deb.debian.org/debian-security/ trixie-security main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian-security/ trixie-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian/ trixie-updates main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian/ trixie-updates main contrib non-free non-free-firmware
EOF

rm -rf /var/lib/apt/lists/*
apt-get update

echo "Instalando locales y soporte de idioma..."
apt-get install -y locales
echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
echo "{locale_val} UTF-8" >> /etc/locale.gen
dpkg-reconfigure -f noninteractive locales
echo "LANG={locale_val}" > /etc/default/locale
echo "LC_ALL={locale_val}" >> /etc/default/locale
update-locale LANG={locale_val} LC_ALL={locale_val}
export LANG={locale_val}
export LC_ALL={locale_val}

echo "Instalando paquetes básicos críticos del sistema..."
apt-get install -y linux-image-amd64 sudo network-manager console-setup plymouth plymouth-themes ca-certificates dbus jq wget {grub_packages}

update-ca-certificates

if [ ! -z "{string_paquetes_extra}" ]; then
    echo "Instalando lista de paquetes adicionales..."
    apt-get purge --autoremove pulseaudio 2>/dev/null || true
    apt-get install -y {string_paquetes_extra}
fi

{grub_install_block}

groupadd -r -g 104 messagebus 2>/dev/null || true
useradd -r -g messagebus -u 104 -d /var/run/dbus -s /bin/false messagebus 2>/dev/null || true
systemd-machine-id-setup --root=/
groupadd -r video 2>/dev/null || true
groupadd -r render 2>/dev/null || true

ln -sf /usr/share/zoneinfo/{timezone} /etc/localtime
echo "{timezone}" > /etc/timezone
dpkg-reconfigure -f noninteractive tzdata

cat <<EOF > /etc/default/keyboard
XKBMODEL="pc105"
XKBLAYOUT="{kb_data['layout']}"
XKBVARIANT="{kb_data['variant']}"
EOF

echo "{self.hostname.get()}" > /etc/hostname
echo "127.0.1.1 {self.hostname.get()}" >> /etc/hosts

{autologin_script_block}

systemctl enable NetworkManager >/dev/null 2>&1
systemctl enable sddm >/dev/null 2>&1

exit 0

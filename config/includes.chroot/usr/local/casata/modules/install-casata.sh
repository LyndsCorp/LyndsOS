#!/bin/bash

# /usr/local/casata/modules/install-casata.sh
# Copyright (C) 2026, GPL v3+, Lynds Corp., Aros Legendarios, David Baña Szymaniak
# Script de actualización de Casata

shopt -s nullglob
set -euo pipefail

GLOBAL_ROOT="/usr/local/casata"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ------------------------------------------------------------
# Detección de bugs y recomendación de reparación
# ------------------------------------------------------------
_sugerir_reparacion_casata() {
    local codigo=$?
    if [ "$codigo" -ne 0 ]; then
        printf '%b\n' "${RED}Se detectó un error inesperado (código ${codigo}).${NC}" >&2
        printf '%b\n' "${YELLOW}Recomendación: ejecuta 'sudo casata install casata' para reparar Casata.${NC}" >&2
    fi
}
trap _sugerir_reparacion_casata ERR

# Variable para limpieza
TEMP_DIR=""

cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

# Procesar argumentos (solo -y es relevante, -d se ignora en actualización)
AUTO_YES=0
for arg in "$@"; do
    case "$arg" in
        -y) AUTO_YES=1 ;;
    esac
done

[ "$EUID" -ne 0 ] && { echo -e "${RED}La actualización de Casata requiere root.${NC}"; exit 1; }

echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}Actualizando Casata${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"

# Obtener versión local
LOCAL_VERSION="desconocida"
if [ -f "$GLOBAL_ROOT/VERSION" ]; then
    LOCAL_VERSION=$(cat "$GLOBAL_ROOT/VERSION")
fi

# Obtener versión remota desde GitHub
REMOTE_VERSION="desconocida"
REMOTE_URL="https://raw.githubusercontent.com/LyndsCorp/Casata/main/usr/local/casata/VERSION"
echo -e "${YELLOW}Consultando versión remota...${NC}"
if wget -q --timeout=10 -O /tmp/casata_remote_version "$REMOTE_URL" 2>/dev/null; then
    REMOTE_VERSION=$(cat /tmp/casata_remote_version 2>/dev/null | tr -d '[:space:]')
    rm -f /tmp/casata_remote_version
fi

echo -e "${YELLOW}Versión local:  $LOCAL_VERSION${NC}"
echo -e "${YELLOW}Versión remota: $REMOTE_VERSION${NC}"

# Comparar versiones (si están disponibles)
if [ "$LOCAL_VERSION" != "desconocida" ] && [ "$REMOTE_VERSION" != "desconocida" ]; then
    if [ "$LOCAL_VERSION" = "$REMOTE_VERSION" ]; then
        echo -e "${GREEN}Ya tienes la última versión.${NC}"
        if [ $AUTO_YES -eq 0 ]; then
            read -p "¿Reinstalar igualmente? [s/N] " resp < /dev/tty
            [[ ! "$resp" =~ ^[sSyY] ]] && exit 0
        else
            echo -e "${YELLOW}Usando -y: se reinstalará.${NC}"
        fi
    else
        echo -e "${GREEN}Hay una actualización disponible ($REMOTE_VERSION).${NC}"
    fi
fi

if [ $AUTO_YES -eq 0 ]; then
    read -p "¿Descargar e instalar la última versión? [S/n] " resp < /dev/tty
    [[ "$resp" =~ ^[Nn] ]] && exit 0
fi

TEMP_DIR=$(mktemp -d)
TARBALL_URL="https://github.com/LyndsCorp/Casata/archive/refs/heads/main.tar.gz"
echo -e "${YELLOW}Descargando desde GitHub...${NC}"
if ! wget -q --show-progress -O "$TEMP_DIR/casata.tar.gz" "$TARBALL_URL"; then
    echo -e "${RED}Error al descargar la actualización.${NC}"
    exit 1
fi

echo -e "${YELLOW}Extrayendo archivos...${NC}"
tar -xzf "$TEMP_DIR/casata.tar.gz" -C "$TEMP_DIR"
EXTRACTED=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "Casata-*" | head -1)
if [ -z "$EXTRACTED" ] || [ ! -d "$EXTRACTED/usr" ]; then
    echo -e "${RED}Error: Estructura del archivo descargado inválida.${NC}"
    exit 1
fi

# Instalar binario principal
cp -f "$EXTRACTED/usr/bin/casata" /usr/bin/casata
chmod +x /usr/bin/casata

# Reemplazar módulos
rm -rf "$GLOBAL_ROOT/modules"
cp -a "$EXTRACTED/usr/local/casata/modules" "$GLOBAL_ROOT/"
chmod +x "$GLOBAL_ROOT"/modules/*.sh

# Reemplazar librerías
rm -rf "$GLOBAL_ROOT/lib"
cp -a "$EXTRACTED/usr/local/casata/lib" "$GLOBAL_ROOT/"
chmod +x "$GLOBAL_ROOT"/lib/*.sh

# Copiar archivos informativos
cp -f "$EXTRACTED/usr/local/casata/"{HELP,VERSION,WELCOME,SAVE_FILES.txt} "$GLOBAL_ROOT/" 2>/dev/null

# Fusionar repositorios oficiales
if [ -d "$EXTRACTED/usr/local/casata/repos" ]; then
    echo -e "${YELLOW}Fusionando repositorios oficiales (se conservan los personalizados)...${NC}"
    cp -a "$EXTRACTED/usr/local/casata/repos/." "$GLOBAL_ROOT/repos/"
    echo -e "${GREEN}Repositorios actualizados correctamente.${NC}"
else
    echo -e "${YELLOW}Aviso: No se encontró la carpeta 'repos' en la actualización; se mantiene la versión actual.${NC}"
fi

echo -e "${GREEN}Casata actualizado correctamente a la versión $REMOTE_VERSION.${NC}"
exit 0

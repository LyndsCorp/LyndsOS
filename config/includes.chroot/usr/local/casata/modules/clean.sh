#!/bin/bash
# /usr/local/casata/modules/clean.sh
# Copyright (C) 2026 David Baña Szymaniak

shopt -s nullglob

# Cargar librería de historial
if [ -f "/usr/local/casata/lib/history-lib.sh" ]; then
    source "/usr/local/casata/lib/history-lib.sh"
fi

CASATA_ROOT="/usr/local/casata"
SINGREPOS_DIR="$CASATA_ROOT/repos/singrepos"
DATA_DIR="$CASATA_ROOT/data"
METAREPOS_DIR="$CASATA_ROOT/repos/metarepos"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Buscando archivos huérfanos en el ecosistema...${NC}"

# --- Limpieza de descargas incompletas en apps ---
echo -e "${YELLOW}--> Verificando descargas incompletas en apps...${NC}"
for app_dir in "$CASATA_ROOT"/apps/*/; do
    [ -d "$app_dir" ] || continue
    # Contar solo archivos regulares (no directorios) dentro de la carpeta
    file_count=$(find "$app_dir" -maxdepth 1 -type f | wc -l)
    if [ "$file_count" -eq 1 ]; then
        echo -e "  ${RED}[Eliminar]${NC} Carpeta de app incompleta: $(basename "$app_dir")"
        rm -rf "$app_dir"
        log_cleanup_path "$app_dir"
    fi
done

# --- Limpieza de singrepos huérfanos (código original) ---
VALID_PKGS=$(mktemp)
trap 'rm -f "$VALID_PKGS"' EXIT

for METAREPO in "$METAREPOS_DIR"/*.json; do
    [ -f "$METAREPO" ] || continue
    jq -r 'to_entries[] | select(.key != "name" and .key != "metarepo") | .key' "$METAREPO" >> "$VALID_PKGS"
done

echo -e "${GREEN}--> Verificando singrepos...${NC}"
for FILE in "$SINGREPOS_DIR"/*.json; do
    [ -f "$FILE" ] || continue
    PKG_NAME=$(basename "$FILE" .json)

    if ! grep -q "^${PKG_NAME}$" "$VALID_PKGS"; then
        echo -e "  ${RED}[Eliminar]${NC} Singrepo huérfano: $PKG_NAME"
        rm -f "$FILE"
        log_cleanup_path "$FILE"
        if [ -f "$DATA_DIR/${PKG_NAME}.json" ]; then
            rm -f "$DATA_DIR/${PKG_NAME}.json"
            log_cleanup_path "$DATA_DIR/${PKG_NAME}.json"
            echo -e "  ${RED}[Eliminar]${NC} Datos asociados: ${PKG_NAME}.json"
            echo
        fi
    fi
done

echo -e "\n${GREEN}¡Limpieza completada!${NC}"

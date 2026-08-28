#!/bin/bash
# /usr/local/casata/modules/clean.sh

shopt -s nullglob

CASATA_ROOT="/usr/local/casata"
SINGREPOS_DIR="$CASATA_ROOT/repos/singrepos"
DATA_DIR="$CASATA_ROOT/data"
METAREPOS_DIR="$CASATA_ROOT/repos/metarepos"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Buscando archivos huérfanos en el ecosistema...${NC}"

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
        if [ -f "$DATA_DIR/${PKG_NAME}.json" ]; then
            rm -f "$DATA_DIR/${PKG_NAME}.json"
            echo -e "  ${RED}[Eliminar]${NC} Datos asociados: ${PKG_NAME}.json"
        fi
    fi
done

echo -e "\n${GREEN}¡Limpieza completada!${NC}"

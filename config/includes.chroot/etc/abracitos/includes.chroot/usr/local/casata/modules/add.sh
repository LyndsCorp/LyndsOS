#!/bin/bash
#/usr/local/casata/modules/add.sh

shopt -s nullglob
set -euo pipefail

TYPE="${1:-}"
URL="${2:-}"

CASATA_ROOT="/usr/local/casata"
METAREPOS_DIR="$CASATA_ROOT/repos/metarepos"
SINGREPOS_DIR="$CASATA_ROOT/repos/singrepos"
DATA_DIR="$CASATA_ROOT/data"
OFICIAL_FILE="$CASATA_ROOT/repos/OFICIAL"
COMMUNITY_FILE="$CASATA_ROOT/repos/COMMUNITY"
FORGE_FILE="$CASATA_ROOT/repos/FORGE"
OTHERS_FILE="$CASATA_ROOT/repos/OTHERS"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$METAREPOS_DIR" "$SINGREPOS_DIR" "$DATA_DIR"

TEMP_FILE=""
cleanup() { [ -n "${TEMP_FILE:-}" ] && [ -f "$TEMP_FILE" ] && rm -f "$TEMP_FILE"; }
trap cleanup EXIT

if ! command -v jq &>/dev/null || ! command -v wget &>/dev/null; then
    echo -e "${RED}Error: Se requieren 'jq' y 'wget'.${NC}"
    exit 1
fi

process_singrepo() {
    local url="$1"
    local temp_sing=$(mktemp)
    TEMP_FILE="$temp_sing"
    echo -e "     ${YELLOW}Descargando singrepo...${NC}"
    if wget -q --timeout=30 --tries=2 -O "$temp_sing" "$url"; then
        local pkg_name=$(jq -r '.name // empty' "$temp_sing")
        local data_url=$(jq -r '.data_url // empty' "$temp_sing")
        if [ -n "$pkg_name" ] && [ -n "$data_url" ]; then
            mv "$temp_sing" "$SINGREPOS_DIR/${pkg_name}.json"
            chmod 644 "$SINGREPOS_DIR/${pkg_name}.json"
            TEMP_FILE=""
            echo -ne "     ${GREEN}[+] Registrado singrepo: ${pkg_name}${NC} ... "
            if wget -q --timeout=30 --tries=2 -O "$DATA_DIR/${pkg_name}.json" "$data_url"; then
                chmod 644 "$DATA_DIR/${pkg_name}.json"
                echo -e "${GREEN}OK${NC}"
            else
                echo -e "${RED}FALLO datos${NC}"
            fi
        else
            echo -e "     ${RED}[!] JSON inválido${NC}"
        fi
    else
        echo -e "     ${RED}[!] Error red${NC}"
    fi
}

process_metarepo() {
    local url="$1"
    local temp_meta=$(mktemp)
    TEMP_FILE="$temp_meta"
    echo -e "${YELLOW}Procesando metarepo: $url${NC}"
    if ! wget -q --timeout=30 --tries=2 -O "$temp_meta" "$url"; then
        echo -e "   ${RED}[!] Error descarga${NC}"
        return 1
    fi
    if ! jq empty "$temp_meta" 2>/dev/null; then
        echo -e "   ${RED}[!] JSON inválido${NC}"
        return 1
    fi
    local repo_name=$(jq -r '.name // empty' "$temp_meta")
    if [ -z "$repo_name" ]; then
        echo -e "   ${RED}[!] Sin nombre${NC}"
        return 1
    fi
    local target_file="$METAREPOS_DIR/${repo_name}.json"
    mv "$temp_meta" "$target_file"
    chmod 644 "$target_file"
    TEMP_FILE=""
    echo -e "   ${GREEN}[✓] Metarepo guardado: $repo_name${NC}"
    echo -e "   ${YELLOW}Indexando...${NC}"
    jq -r 'to_entries[] | select(.key != "name" and .key != "metarepo") | .value' "$target_file" | while read -r singrepo_url; do
        [[ "$singrepo_url" == http* ]] && process_singrepo "$singrepo_url"
    done
}

# Función unificada para procesar listas maestras (comunity, forge, others)
process_master_list() {
    local file="$1"
    local label="$2"
    if [ ! -f "$file" ]; then
        echo -e "${RED}Falta $file${NC}"
        return 1
    fi
    MASTER_URL=$(tr -d '[:space:]' < "$file")
    [ -z "$MASTER_URL" ] && { echo -e "${RED}${label} vacío${NC}"; return 1; }
    echo -e "${GREEN}Índice ${label}: $MASTER_URL${NC}"
    TEMP_LIST=$(mktemp)
    TEMP_FILE="$TEMP_LIST"
    if ! wget -q --timeout=30 --tries=2 -O "$TEMP_LIST" "$MASTER_URL"; then
        echo -e "${RED}PROBLEMA DE RED DEL CLIENTE: Error descarga índice${NC}"
        return 1
    fi
    if ! jq -e 'type == "array"' "$TEMP_LIST" >/dev/null 2>&1; then
        echo -e "${RED}PROBLEMA DE SERVIDOR: Índice no es array JSON${NC}"
        return 1
    fi
    REPO_COUNT=0; ERRORS=0
    while read -r repo_url; do
        [ -n "$repo_url" ] || continue
        REPO_COUNT=$((REPO_COUNT + 1))
        echo -e "\n--- Repositorio $REPO_COUNT ---"
        process_metarepo "$repo_url" && echo -e "   ${GREEN}OK${NC}" || { ERRORS=$((ERRORS+1)); echo -e "   ${YELLOW}Fallo${NC}"; }
    done < <(jq -r '.[]' "$TEMP_LIST")
    echo -e "\n${GREEN}Completado. Procesados: $REPO_COUNT, Errores: $ERRORS${NC}"
}

# Normalización de alias
case "$TYPE" in
    comunity|community|comunidad|comunitario) TYPE="community" ;;
    forge|forja|forjado)                   TYPE="forge" ;;
    others|other|otro|otros)       TYPE="others" ;;
esac

case "$TYPE" in
    singrepo)
        [ -z "$URL" ] && { echo -e "${RED}Falta URL${NC}"; exit 1; }
        process_singrepo "$URL"
        ;;
    repo)
        [ -z "$URL" ] && { echo -e "${RED}Falta URL${NC}"; exit 1; }
        process_metarepo "$URL"
        ;;
    oficial)
        if [ ! -f "$OFICIAL_FILE" ]; then
            echo -e "${RED}Falta $OFICIAL_FILE${NC}"
            exit 1
        fi
        process_master_list "$OFICIAL_FILE" "oficial"
        ;;
    community)
        process_master_list "$COMMUNITY_FILE" "community"
        ;;
    forge)
        process_master_list "$FORGE_FILE" "forge"
        ;;
    others)
        process_master_list "$OTHERS_FILE" "others"
        ;;
    *)
        echo -e "${RED}Uso: casata add <singrepo|repo|oficial|community|forge|others> [URL]${NC}"
        exit 1
        ;;
esac

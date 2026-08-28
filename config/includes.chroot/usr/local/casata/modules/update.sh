#!/bin/bash

# /usr/local/casata/modules/update.sh
# Copyright (C) 2026, GPL v3+, Lynds Corp., Aros Legendarios, David Baña Szymaniak
# Script de actualización de repositorios de Casata (versión 1.2.1)

# Novedades:
#   - Procesa primero los metarepos listados en PRIORITY (en orden).
#   - Pregunta solo si dos metarepos en la misma ejecución intentan escribir el mismo singrepo.
#   - Flag -y: omite todas las nuevas versiones en caso de conflicto dentro de la misma ejecución.

shopt -s nullglob
set -euo pipefail

CASATA_ROOT="/usr/local/casata"
METAREPOS_DIR="$CASATA_ROOT/repos/metarepos"
SINGREPOS_DIR="$CASATA_ROOT/repos/singrepos"
DATA_DIR="$CASATA_ROOT/data"
PRIORITY_FILE="$METAREPOS_DIR/PRIORITY"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$METAREPOS_DIR" "$SINGREPOS_DIR" "$DATA_DIR"

# --- Manejo de argumentos ---
AUTO_SKIP=0   # Con -y se saltan todas las sobrescrituras en conflictos de la misma ejecución
for arg in "$@"; do
    case "$arg" in
        -y) AUTO_SKIP=1 ;;
        *)
            echo -e "${RED}Opción desconocida: $arg${NC}"
            exit 1
            ;;
    esac
done

LOCK_FILE="/var/lock/casata-update.lock"
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo -e "${RED}Ya hay una actualización en curso.${NC}"
    exit 1
fi

cleanup() {
    flock -u 200 2>/dev/null
    rm -f /tmp/casata_update_*.tmp 2>/dev/null
}
trap cleanup EXIT

echo -e "${YELLOW}Actualizando ecosistema de paquetes Casata...${NC}"

if [ -z "$(ls -A "$METAREPOS_DIR"/*.json 2>/dev/null)" ]; then
    echo -e "${RED}No hay metarepos agregados. Usa 'casata add repo URL' primero.${NC}"
    exit 0
fi

# ------------------------------------------------------------
# Variables globales para control de conflictos y prioridad
# ------------------------------------------------------------
declare -A SINGREPO_ORIGIN   # [nombre_pkg]="nombre_metarepo" (solo en esta ejecución)
declare -A PROCESSED_METAREPOS
ERRORES=0

# ------------------------------------------------------------
# Función: procesar un único metarepo
# ------------------------------------------------------------
procesar_metarepo() {
    local REPO_FILE="$1"
    [ ! -f "$REPO_FILE" ] && return

    # --- Actualizar el propio metarepo si tiene URL de descarga ---
    METAREPO_URL=$(jq -r '.metarepo // empty' "$REPO_FILE")
    if [ -n "$METAREPO_URL" ]; then
        echo -e "\n${BLUE}🔄 Actualizando metarepo:${NC} $(jq -r '.name // "desconocido"' "$REPO_FILE")"
        TEMP_META=$(mktemp /tmp/casata_update_XXXXXX.tmp)
        if wget -q --timeout=30 --tries=2 -O "$TEMP_META" "$METAREPO_URL"; then
            if jq empty "$TEMP_META" 2>/dev/null; then
                mv "$TEMP_META" "$REPO_FILE"
                chmod 644 "$REPO_FILE"
                echo -e "${GREEN}✓ Metarepo actualizado${NC}"
            else
                echo -e "${RED}✗ ERROR: falló la descarga del metarepo (JSON inválido). Conservando versión anterior.${NC}"
                rm -f "$TEMP_META"
                ((ERRORES++))
            fi
        else
            echo -e "${RED}✗ ERROR: falló la descarga del metarepo (error de red o servidor). Conservando metarepo local.${NC}"
            rm -f "$TEMP_META"
            ((ERRORES++))
        fi
    fi

    # --- Sincronizar cada paquete del metarepo ---
    REPO_NAME=$(jq -r '.name // "Desconocido"' "$REPO_FILE")
    echo -e "\n${GREEN}► Sincronizando paquetes desde:${NC} $REPO_NAME"

    while read -r PKG_NAME SINGREPO_URL; do
        [ -z "$PKG_NAME" ] || [ -z "$SINGREPO_URL" ] && continue
        echo -e "  -> Procesando paquete: ${YELLOW}$PKG_NAME${NC}"

        # --- Descargar singrepo ---
        TEMP_SING=$(mktemp /tmp/casata_update_XXXXXX.tmp)
        if ! wget -q --timeout=20 --tries=2 -O "$TEMP_SING" "$SINGREPO_URL"; then
            echo -e "     ${RED}✗ ERROR: falló la descarga del singrepo (error de red o servidor).${NC}"
            rm -f "$TEMP_SING"
            ((ERRORES++))
            continue
        fi

        if ! jq empty "$TEMP_SING" 2>/dev/null; then
            echo -e "     ${RED}✗ ERROR: falló la descarga del singrepo (JSON inválido).${NC}"
            rm -f "$TEMP_SING"
            ((ERRORES++))
            continue
        fi

        SINGREPO_DEST="$SINGREPOS_DIR/${PKG_NAME}.json"

        # --- Detección de conflicto SOLO si otro metarepo YA escribió este paquete en esta ejecución ---
        if [[ -v SINGREPO_ORIGIN[$PKG_NAME] ]]; then
            origen_anterior="${SINGREPO_ORIGIN[$PKG_NAME]}"
            # Solo hay conflicto si el origen anterior es distinto al metarepo actual
            if [ "$origen_anterior" != "$REPO_NAME" ]; then
                echo -e "     ${YELLOW}⚠ Conflicto: '$PKG_NAME' ya fue actualizado por '$origen_anterior'."
                echo -e "     El metarepo '$REPO_NAME' también intenta sobrescribirlo.${NC}"

                if [ $AUTO_SKIP -eq 1 ]; then
                    echo -e "     ${YELLOW}Flag -y activo: se omite la versión de '$REPO_NAME'.${NC}"
                    rm -f "$TEMP_SING"
                    continue
                fi

                read -p "     ¿Deseas conservar la versión de '$origen_anterior' y omitir la de '$REPO_NAME'? [s/N/a (abortar)]: " resp < /dev/tty
                case "$resp" in
                    [sS])
                        echo -e "     ${YELLOW}Conservando versión de '$origen_anterior'. Se omite '$REPO_NAME'.${NC}"
                        rm -f "$TEMP_SING"
                        continue
                        ;;
                    [aA])
                        echo -e "${RED}Abortando actualización por solicitud del usuario.${NC}"
                        exit 1
                        ;;
                    *)
                        echo -e "     ${YELLOW}Sobrescribiendo con la versión de '$REPO_NAME'...${NC}"
                        ;;
                esac
            fi
            # Si el origen anterior es el mismo no se pregunta, se sobrescribe
        else
            # El singrepo ya existía de antes pero no ha sido escrito en esta ejecución -> actualización normal
            if [ -f "$SINGREPO_DEST" ]; then
                echo -e "     ${YELLOW}ℹ Actualizando singrepo...${NC}"
            fi
        fi

        # --- Instalar el singrepo ---
        mv "$TEMP_SING" "$SINGREPO_DEST"
        chmod 644 "$SINGREPO_DEST"
        SINGREPO_ORIGIN["$PKG_NAME"]="$REPO_NAME"
        echo -e "     ${GREEN}✓ Singrepo actualizado${NC}"

        # --- Descargar metadatos (data_url) ---
        DATA_URL=$(jq -r '.data_url // empty' "$SINGREPO_DEST")
        [ -z "$DATA_URL" ] && { echo -e "     ${YELLOW}⚠ ERROR DEL SERVIDOR: Sin data_url${NC}"; continue; }

        echo -n "     ↳ Descargando metadatos... "
        TEMP_DATA=$(mktemp /tmp/casata_update_XXXXXX.tmp)
        if wget -q --timeout=20 --tries=2 -O "$TEMP_DATA" "$DATA_URL"; then
            if jq empty "$TEMP_DATA" 2>/dev/null; then
                mv "$TEMP_DATA" "$DATA_DIR/${PKG_NAME}.json"
                chmod 644 "$DATA_DIR/${PKG_NAME}.json"
                echo -e "${GREEN}OK${NC}"
            else
                echo -e "${RED}ERROR: falló la descarga de los metadatos (JSON inválido).${NC}"
                rm -f "$TEMP_DATA"
                ((ERRORES++))
            fi
        else
            echo -e "${RED}ERROR: falló la descarga de los metadatos (error de red o servidor).${NC}"
            rm -f "$TEMP_DATA"
            ((ERRORES++))
        fi
    done < <(jq -r 'to_entries[] | select(.key != "name" and .key != "metarepo") | "\(.key) \(.value)"' "$REPO_FILE")
}

# ------------------------------------------------------------
# 1. Cargar metarepos prioritarios desde PRIORITY
# ------------------------------------------------------------
declare -a PRIORITY_FILES=()
if [ -f "$PRIORITY_FILE" ]; then
    #echo -e "${BLUE}Leyendo metarepos prioritarios desde PRIORITY...${NC}"
    while IFS= read -r line; do
        # Eliminar espacios e ignorar comentarios/vacías
        line=$(echo "$line" | sed 's/#.*//; s/^[[:space:]]*//; s/[[:space:]]*$//')
        [ -z "$line" ] && continue

        # Buscar el archivo .json correspondiente
        if [ -f "$METAREPOS_DIR/$line" ]; then
            PRIORITY_FILES+=("$METAREPOS_DIR/$line")
        elif [ -f "$METAREPOS_DIR/$line.json" ]; then
            PRIORITY_FILES+=("$METAREPOS_DIR/$line.json")
        fi
    done < "$PRIORITY_FILE"
fi

# ------------------------------------------------------------
# 2. Procesar metarepos en orden: primero PRIORITY, luego el resto
# ------------------------------------------------------------
TOTAL_PRIORITY=${#PRIORITY_FILES[@]}
echo -e "${BLUE}Procesando $TOTAL_PRIORITY metarepo(s) prioritario(s)...${NC}"
for REPO_FILE in "${PRIORITY_FILES[@]}"; do
    procesar_metarepo "$REPO_FILE"
    PROCESSED_METAREPOS["$REPO_FILE"]=1
done

echo -e "\n${BLUE}Procesando el resto de metarepos...${NC}"
for REPO_FILE in "$METAREPOS_DIR"/*.json; do
    [ -f "$REPO_FILE" ] || continue
    if [ -z "${PROCESSED_METAREPOS["$REPO_FILE"]+x}" ]; then
        procesar_metarepo "$REPO_FILE"
    fi
done

# ------------------------------------------------------------
# Resumen final
# ------------------------------------------------------------
TOTAL_METAREPOS=$(ls -1 "$METAREPOS_DIR"/*.json 2>/dev/null | wc -l)
echo ""
if [ $ERRORES -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ Actualización completada sin errores.${NC}"
    echo -e "Metarepos procesados: $TOTAL_METAREPOS"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
else
    echo -e "${YELLOW}════════════════════════════════════════${NC}"
    echo -e "${YELLOW}⚠ Actualización completada con $ERRORES error(es).${NC}"
    echo -e "Metarepos procesados: $TOTAL_METAREPOS"
    echo -e "${YELLOW}════════════════════════════════════════${NC}"
    exit 1
fi

#!/bin/bash

# /usr/local/casata/modules/update.sh
# Copyright (C) 2026 David Baña Szymaniak
# GPL v3 License
# Script de actualización de repositorios de Casata

shopt -s nullglob
set -euo pipefail

# Cargar librería de historial
if [ -f "/usr/local/casata/lib/history-lib.sh" ]; then
    source "/usr/local/casata/lib/history-lib.sh"
fi

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
AUTO_SKIP=0
TARGET_METAREPOS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -y)
            AUTO_SKIP=1
            shift
            ;;
        -*)
            echo -e "${RED}Opción desconocida: $1${NC}"
            exit 1
            ;;
        *)
            TARGET_METAREPOS+=("$1")
            shift
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

METAREPO_FILES=("$METAREPOS_DIR"/*.json)
if [ ${#METAREPO_FILES[@]} -eq 0 ]; then
    echo -e "${RED}No hay metarepos agregados. Usa 'casata add repo URL' primero.${NC}"
    exit 0
fi

# --- Función de validación de nombre de metarepo ---
valid_metarepo_name() {
    local name="$1"
    [[ "$name" != */* ]] && [[ -n "$name" ]]
}

# --- Función para resolver un nombre de metarepo a su archivo ---
resolver_metarepo() {
    local name="$1"
    local file=""

    if ! valid_metarepo_name "$name"; then
        return 1
    fi

    if [ -f "$METAREPOS_DIR/$name" ]; then
        file="$METAREPOS_DIR/$name"
    elif [ -f "$METAREPOS_DIR/$name.json" ]; then
        file="$METAREPOS_DIR/$name.json"
    else
        return 1
    fi
    printf '%s' "$file"
}

# --- Leer PRIORITY (si existe) ---
declare -a PRIORITY_FILES=()
if [ -f "$PRIORITY_FILE" ]; then
    while IFS= read -r line; do
        line=$(echo "$line" | sed 's/#.*//; s/^[[:space:]]*//; s/[[:space:]]*$//')
        [ -z "$line" ] && continue

        # Solo nombres simples, sin rutas
        if ! valid_metarepo_name "$line"; then
            echo -e "${YELLOW}Advertencia: entrada inválida en PRIORITY ignorada: '$line'${NC}"
            continue
        fi

        if [ -f "$METAREPOS_DIR/$line" ]; then
            PRIORITY_FILES+=("$METAREPOS_DIR/$line")
        elif [ -f "$METAREPOS_DIR/$line.json" ]; then
            PRIORITY_FILES+=("$METAREPOS_DIR/$line.json")
        fi
    done < "$PRIORITY_FILE"
fi

# --- Resolver metarepos solicitados ---
declare -a REQUESTED_FILES=()
if [ ${#TARGET_METAREPOS[@]} -gt 0 ]; then
    for repo in "${TARGET_METAREPOS[@]}"; do
        if ! valid_metarepo_name "$repo"; then
            echo -e "${RED}Nombre de metarepo inválido: '$repo'. No se permiten rutas (nombres con '/').${NC}"
            exit 1
        fi

        resolved=$(resolver_metarepo "$repo") || {
            echo -e "${RED}No se encontró el metarepo '$repo' en los metarepos añadidos.${NC}"
            exit 1
        }

        # Evitar duplicados
        duplicate=false
        for f in "${REQUESTED_FILES[@]}"; do
            if [ "$f" = "$resolved" ]; then
                duplicate=true
                break
            fi
        done

        if [ "$duplicate" = false ]; then
            REQUESTED_FILES+=("$resolved")
        fi
    done
fi

# ------------------------------------------------------------
# Variables globales para control de conflictos y prioridad
# ------------------------------------------------------------
declare -A SINGREPO_ORIGIN
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
                log_repo_updated "$(jq -r '.name // "desconocido"' "$REPO_FILE")" "OK"
            else
                echo -e "${RED}✗ ERROR: falló la descarga del metarepo (JSON inválido). Conservando versión anterior.${NC}"
                rm -f "$TEMP_META"
                log_repo_updated "$(jq -r '.name // "desconocido"' "$REPO_FILE")" "ERROR"
                ((ERRORES++))
            fi
        else
            echo -e "${RED}✗ ERROR: falló la descarga del metarepo (error de red o servidor). Conservando metarepo local.${NC}"
            rm -f "$TEMP_META"
            log_repo_updated "$(jq -r '.name // "desconocido"' "$REPO_FILE")" "ERROR"
            ((ERRORES++))
        fi
    fi

    # --- Sincronizar cada paquete del metarepo ---
    REPO_NAME=$(jq -r '.name // "Desconocido"' "$REPO_FILE")
    echo -e "\n${GREEN}► Sincronizando paquetes desde:${NC} $REPO_NAME"

    while read -r PKG_NAME SINGREPO_URL; do
        [ -z "$PKG_NAME" ] || [ -z "$SINGREPO_URL" ] && continue
        echo -e "  -> Procesando paquete: ${YELLOW}$PKG_NAME${NC}"

        TEMP_SING=$(mktemp /tmp/casata_update_XXXXXX.tmp)
        if ! wget -q --timeout=20 --tries=2 -O "$TEMP_SING" "$SINGREPO_URL"; then
            echo -e "     ${RED}✗ ERROR: falló la descarga del singrepo (error de red o servidor).${NC}"
            rm -f "$TEMP_SING"
            log_repo_updated "$PKG_NAME" "ERROR"
            ((ERRORES++))
            continue
        fi

        if ! jq empty "$TEMP_SING" 2>/dev/null; then
            echo -e "     ${RED}✗ ERROR: falló la descarga del singrepo (JSON inválido).${NC}"
            rm -f "$TEMP_SING"
            log_repo_updated "$PKG_NAME" "ERROR"
            ((ERRORES++))
            continue
        fi

        SINGREPO_DEST="$SINGREPOS_DIR/${PKG_NAME}.json"

        if [[ -v SINGREPO_ORIGIN[$PKG_NAME] ]]; then
            origen_anterior="${SINGREPO_ORIGIN[$PKG_NAME]}"
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
        else
            if [ -f "$SINGREPO_DEST" ]; then
                echo -e "     ${YELLOW}ℹ Actualizando singrepo...${NC}"
            fi
        fi

        mv "$TEMP_SING" "$SINGREPO_DEST"
        chmod 644 "$SINGREPO_DEST"
        SINGREPO_ORIGIN["$PKG_NAME"]="$REPO_NAME"
        echo -e "     ${GREEN}✓ Singrepo actualizado${NC}"
        log_repo_updated "$PKG_NAME" "OK"

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
# Procesar metarepos
# ------------------------------------------------------------
if [ ${#REQUESTED_FILES[@]} -gt 0 ]; then
    # Ordenar los solicitados respetando PRIORITY
    declare -A REQUESTED_SET
    for f in "${REQUESTED_FILES[@]}"; do
        REQUESTED_SET["$f"]=1
    done

    declare -A ORDERED_SET
    declare -a ORDERED_TARGETS=()

    # Primero los que están en PRIORITY, en el orden de PRIORITY
    for pf in "${PRIORITY_FILES[@]}"; do
        if [[ -v REQUESTED_SET["$pf"] ]] && [ -z "${ORDERED_SET["$pf"]+x}" ]; then
            ORDERED_TARGETS+=("$pf")
            ORDERED_SET["$pf"]=1
        fi
    done

    # Después el resto, en el orden dado por el usuario
    for f in "${REQUESTED_FILES[@]}"; do
        if [ -z "${ORDERED_SET["$f"]+x}" ]; then
            ORDERED_TARGETS+=("$f")
            ORDERED_SET["$f"]=1
        fi
    done

    TOTAL_METAREPOS=${#ORDERED_TARGETS[@]}
    echo -e "\n${BLUE}Actualizando $TOTAL_METAREPOS metarepo(s) especificado(s)...${NC}"
    for REPO_FILE in "${ORDERED_TARGETS[@]}"; do
        procesar_metarepo "$REPO_FILE"
    done
else
    # Sin metarepos especificados: usar PRIORITY y luego el resto
    TOTAL_PRIORITY=${#PRIORITY_FILES[@]}
    echo -e "${BLUE}Procesando $TOTAL_PRIORITY metarepo(s) prioritario(s)...${NC}"
    for REPO_FILE in "${PRIORITY_FILES[@]}"; do
        procesar_metarepo "$REPO_FILE"
        PROCESSED_METAREPOS["$REPO_FILE"]=1
    done

    echo -e "\n${BLUE}Procesando el resto de metarepos...${NC}"
    for REPO_FILE in "${METAREPO_FILES[@]}"; do
        if [ -z "${PROCESSED_METAREPOS["$REPO_FILE"]+x}" ]; then
            procesar_metarepo "$REPO_FILE"
        fi
    done

    TOTAL_METAREPOS=${#METAREPO_FILES[@]}
fi

# ------------------------------------------------------------
# Resumen final
# ------------------------------------------------------------
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

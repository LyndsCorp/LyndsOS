#!/bin/bash
# /usr/local/casata/modules/list.sh

shopt -s nullglob

CASATA_ROOT="/usr/local/casata"
DATA_DIR="$CASATA_ROOT/data"
SYS_DIR="$CASATA_ROOT/apps"
USR_DIR="$HOME/.local/casata/apps"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Flags
SHOW_VERSION=0
SHOW_DESC=0

# Procesar argumentos (si no hay, se queda todo en 0)
for arg in "$@"; do
    case "$arg" in
        -v|--version)
            SHOW_VERSION=1
            ;;
        -d|--description)
            SHOW_DESC=1
            ;;
        -vd|-dv)
            SHOW_VERSION=1
            SHOW_DESC=1
            ;;
        -*)
            echo -e "${RED}Opción desconocida: $arg${NC}"
            echo "Uso: casata list [-v] [-d] [-vd]"
            exit 1
            ;;
        *)
            # Si hay un argumento que no es opción, ignorar (podría ser un nombre, pero no se usa)
            ;;
    esac
done

# Recoger aplicaciones instaladas (globales + usuario)
APPS_LIST=()
[ -d "$SYS_DIR" ] && for app in "$SYS_DIR"/*; do
    [ -d "$app" ] && APPS_LIST+=("$(basename "$app")")
done
[ -d "$USR_DIR" ] && for app in "$USR_DIR"/*; do
    [ -d "$app" ] && APPS_LIST+=("$(basename "$app")")
done

# Eliminar duplicados
if [ ${#APPS_LIST[@]} -gt 0 ]; then
    APPS_LIST=($(printf "%s\n" "${APPS_LIST[@]}" | sort -u))
fi

if [ ${#APPS_LIST[@]} -eq 0 ]; then
    echo -e "${YELLOW}No hay aplicaciones instaladas.${NC}"
    exit 0
fi

# --- Sin opciones: solo nombres ---
if [ $SHOW_VERSION -eq 0 ] && [ $SHOW_DESC -eq 0 ]; then
    echo -e "${GREEN}Aplicaciones instaladas:${NC}"
    for PKG_NAME in "${APPS_LIST[@]}"; do
        echo "  $PKG_NAME"
    done
    echo -e "\n${YELLOW}Total: ${#APPS_LIST[@]} aplicaciones instaladas.${NC}"
    exit 0
fi

# --- Con opciones: mostrar tabla ---
if [ $SHOW_VERSION -eq 1 ] && [ $SHOW_DESC -eq 1 ]; then
    printf "${GREEN}%-30s %-15s %s${NC}\n" "NOMBRE" "VERSIÓN" "DESCRIPCIÓN"
    echo "----------------------------------------------------------------------"
elif [ $SHOW_VERSION -eq 1 ]; then
    printf "${GREEN}%-30s %-15s${NC}\n" "NOMBRE" "VERSIÓN"
    echo "----------------------------------------------"
elif [ $SHOW_DESC -eq 1 ]; then
    printf "${GREEN}%-30s %s${NC}\n" "NOMBRE" "DESCRIPCIÓN"
    echo "--------------------------------------------------------------"
fi

for PKG_NAME in "${APPS_LIST[@]}"; do
    # Obtener versión si se pide
    VERSION=""
    if [ $SHOW_VERSION -eq 1 ]; then
        if [ -d "$SYS_DIR/$PKG_NAME" ] && [ -f "$SYS_DIR/$PKG_NAME/VERSION" ]; then
            VERSION=$(cat "$SYS_DIR/$PKG_NAME/VERSION")
        elif [ -d "$USR_DIR/$PKG_NAME" ] && [ -f "$USR_DIR/$PKG_NAME/VERSION" ]; then
            VERSION=$(cat "$USR_DIR/$PKG_NAME/VERSION")
        else
            VERSION="desconocida"
        fi
    fi

    # Obtener descripción si se pide
    DESC=""
    if [ $SHOW_DESC -eq 1 ] && [ -f "$DATA_DIR/${PKG_NAME}.json" ] && [ -r "$DATA_DIR/${PKG_NAME}.json" ]; then
        DESC=$(jq -r '.description // ""' "$DATA_DIR/${PKG_NAME}.json" 2>/dev/null)
    fi

    if [ $SHOW_VERSION -eq 1 ] && [ $SHOW_DESC -eq 1 ]; then
        printf "%-30s %-15s %s\n" "$PKG_NAME" "$VERSION" "$DESC"
    elif [ $SHOW_VERSION -eq 1 ]; then
        printf "%-30s %-15s\n" "$PKG_NAME" "$VERSION"
    elif [ $SHOW_DESC -eq 1 ]; then
        printf "%-30s %s\n" "$PKG_NAME" "$DESC"
    fi
done

echo -e "\n${YELLOW}Total: ${#APPS_LIST[@]} aplicaciones instaladas.${NC}"

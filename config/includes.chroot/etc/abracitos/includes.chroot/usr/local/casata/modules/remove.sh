#!/bin/bash
# /usr/local/casata/modules/remove.sh - elimina múltiples paquetes

shopt -s nullglob

GLOBAL_ROOT="/usr/local/casata"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Función para eliminar un solo paquete
remove_one() {
    local PKG_NAME="$1"
    local AUTO_YES="$2"
    local USER_INSTALL="$3"

    # Configurar rutas
    if [ $USER_INSTALL -eq 1 ]; then
        APPS_DIR="$HOME/.local/casata/apps"
        GUIDE_TARGET="GUIDE-USER.json"
        INSTALL_TYPE="Usuario"
    else
        if [ "$EUID" -ne 0 ]; then
            echo -e "${RED}Error: La desinstalación global requiere permisos de root.${NC}"
            echo -e "Usa ${YELLOW}sudo casata remove $PKG_NAME${NC} o ${YELLOW}casata remove --user $PKG_NAME${NC}."
            return 1
        fi
        APPS_DIR="$GLOBAL_ROOT/apps"
        GUIDE_TARGET="GUIDE.json"
        INSTALL_TYPE="Global"
    fi

    APP_DIR="$APPS_DIR/${PKG_NAME}"

    if [ ! -d "$APP_DIR" ]; then
        echo -e "${RED}Error: El paquete '$PKG_NAME' no está instalado ($INSTALL_TYPE).${NC}"
        return 1
    fi

    if [ $AUTO_YES -eq 0 ]; then
        echo -e "${YELLOW}Se eliminará $PKG_NAME ($INSTALL_TYPE) y todos sus enlaces.${NC}"
        read -p "¿Estás seguro? [S/n] " response < /dev/tty
        if [[ "$response" =~ ^([nN][oO]|[nN])$ ]]; then
            echo "Desinstalación abortada para $PKG_NAME."
            return 1
        fi
    fi

    echo -e "${GREEN}Desinstalando $PKG_NAME ($INSTALL_TYPE)...${NC}"

    GUIDE_FILE="$APP_DIR/$GUIDE_TARGET"

    # Eliminar enlaces simbólicos
    if [ -f "$GUIDE_FILE" ]; then
        echo " -> Eliminando enlaces del sistema..."
        jq -c '.links[]' "$GUIDE_FILE" 2>/dev/null | while read -r item; do
            DEST=$(echo "$item" | jq -r '.dest')
            LINK_NAME=$(echo "$item" | jq -r '.name')
            [ "$DEST" == "null" ] || [ "$LINK_NAME" == "null" ] && continue
            DEST="${DEST/#\~/$HOME}"
            DEST="${DEST//\$HOME/$HOME}"
            TARGET_LINK="$DEST/$LINK_NAME"
            if [ -L "$TARGET_LINK" ]; then
                rm -f "$TARGET_LINK"
                echo -e "   [-] Enlace eliminado: ${RED}$LINK_NAME${NC}"
            else
                if [ -e "$TARGET_LINK" ]; then
                    echo -e "   [!] Omitido (no es un enlace): $TARGET_LINK"
                else
                    echo -e "   [=] No existía: $LINK_NAME"
                fi
            fi
        done
    else
        echo -e "${YELLOW}Aviso: No se encontró $GUIDE_TARGET. No se eliminarán enlaces, solo la carpeta base.${NC}"
    fi

    echo " -> Eliminando archivos base de la aplicación..."
    rm -rf "$APP_DIR"

    echo -e "${GREEN}¡$PKG_NAME desinstalado correctamente!${NC}"
    return 0
}

# --- INICIO DEL SCRIPT (múltiples paquetes) ---
AUTO_YES=0
USER_INSTALL=0
PACKAGES=()

for arg in "$@"; do
    case "$arg" in
        -y) AUTO_YES=1 ;;
        --user) USER_INSTALL=1 ;;
        -*)
            echo -e "${RED}Opción desconocida: $arg${NC}"
            exit 1
            ;;
        *) PACKAGES+=("$arg") ;;
    esac
done

if [ ${#PACKAGES[@]} -eq 0 ]; then
    echo -e "${RED}Error: Falta el nombre del paquete.${NC}"
    exit 1
fi

FAILED=()
for PKG in "${PACKAGES[@]}"; do
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Desinstalando: $PKG${NC}"
    echo -e "${GREEN}========================================${NC}"
    if remove_one "$PKG" "$AUTO_YES" "$USER_INSTALL"; then
        echo -e "${GREEN}✔ $PKG desinstalado correctamente.${NC}"
    else
        echo -e "${RED}✖ Falló la desinstalación de $PKG.${NC}"
        FAILED+=("$PKG")
    fi
done

echo -e "\n${GREEN}════════════════════════════════════════${NC}"
if [ ${#FAILED[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ Todos los paquetes se desinstalaron correctamente.${NC}"
else
    echo -e "${RED}✖ Los siguientes paquetes fallaron: ${FAILED[*]}${NC}"
fi
echo -e "${GREEN}════════════════════════════════════════${NC}"

if [ ${#FAILED[@]} -gt 0 ]; then
    exit 1
fi
exit 0

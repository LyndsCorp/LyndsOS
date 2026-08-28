#!/bin/bash
# Instalador de lyndsfetch.sh
# Coloca el script en /usr/bin (root) o en ~/.local/bin (usuario normal)

set -euo pipefail

SCRIPT_NAME="lyndsfetch"
SOURCE="./lyndsfetch.sh"

# Colores para los mensajes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar que el archivo fuente existe
if [[ ! -f "$SOURCE" ]]; then
    echo -e "${RED}Error: No se encuentra $SCRIPT_NAME en el directorio actual.${NC}"
    echo "Asegúrate de ejecutar este instalador desde la carpeta que contiene $SCRIPT_NAME."
    exit 1
fi

# Determinar ruta de instalación
if [[ $EUID -eq 0 ]]; then
    DEST_DIR="/usr/bin"
    DEST="$DEST_DIR/$SCRIPT_NAME"
    TYPE="root"
else
    DEST_DIR="$HOME/.local/bin"
    DEST="$DEST_DIR/$SCRIPT_NAME"
    TYPE="usuario"
fi

# Preguntar si desea instalar
echo -e "${YELLOW}Se instalará $SCRIPT_NAME en: $DEST${NC}"
read -p "¿Desea instalarlo? (s/N): " respuesta
if [[ ! "$respuesta" =~ ^[sSyY]$ ]]; then
    echo "Instalación cancelada."
    exit 0
fi

# Crear directorio de destino si no existe
if [[ ! -d "$DEST_DIR" ]]; then
    echo -e "${YELLOW}Creando directorio $DEST_DIR...${NC}"
    mkdir -p "$DEST_DIR" || {
        echo -e "${RED}Error al crear $DEST_DIR.${NC}"
        exit 1
    }
fi

# Preguntar si ya existe y queremos sobreescribir
if [[ -e "$DEST" ]]; then
    read -p "El archivo ya existe en $DEST. ¿Sobrescribir? (s/N): " sobres
    if [[ ! "$sobres" =~ ^[sSyY]$ ]]; then
        echo "Instalación cancelada."
        exit 0
    fi
fi

# Copiar el script
cp "$SOURCE" "$DEST" || {
    echo -e "${RED}Error al copiar $SCRIPT_NAME a $DEST.${NC}"
    exit 1
}

# Hacerlo ejecutable
chmod +x "$DEST"

echo -e "${GREEN}✅ $SCRIPT_NAME instalado correctamente en $DEST${NC}"

# Si es usuario, verificar que ~/.local/bin esté en el PATH
if [[ "$TYPE" == "usuario" ]]; then
    if [[ ":$PATH:" != *":$DEST_DIR:"* ]]; then
        echo -e "${YELLOW}⚠️  Atención: $DEST_DIR no está en tu PATH.${NC}"
        echo "Agrega esta línea a tu ~/.bashrc o ~/.profile para usar el comando globalmente:"
        echo 'export PATH="$HOME/.local/bin:$PATH"'
    fi
fi

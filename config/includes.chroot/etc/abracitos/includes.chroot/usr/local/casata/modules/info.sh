#!/bin/bash
# /usr/local/casata/modules/info.sh

CASATA_ROOT="/usr/local/casata"
APPS_DIR="$CASATA_ROOT/apps"
DATA_DIR="$CASATA_ROOT/data"

# Parsear argumentos
FLAG=""
PKG_NAME=""

if [[ "$1" == "-l" || "$1" == "--license" ]]; then
    FLAG="license"
    PKG_NAME=$2
elif [[ "$1" == "-r" || "$1" == "--readme" ]]; then
    FLAG="readme"
    PKG_NAME=$2
else
    PKG_NAME=$1
fi

[ -z "$PKG_NAME" ] && { echo -e "${RED}Error: Falta el nombre del paquete.${NC}"; exit 1; }

DB_FILE="$DATA_DIR/${PKG_NAME}.json"
APP_DIR="$APPS_DIR/${PKG_NAME}"

# Comprobar si existe en la base de datos
if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}Error: El paquete '${PKG_NAME}' no existe en la base de datos.${NC}"
    exit 1
fi

# Si piden licencia o readme, mostrar contenido si está instalada
if [ -n "$FLAG" ]; then
    if [ ! -d "$APP_DIR" ]; then
        echo -e "${RED}El paquete no está instalado. No se puede leer el archivo local.${NC}"
        exit 1
    fi
    
    if [ "$FLAG" == "license" ] && [ -f "$APP_DIR/LICENSE" ]; then
        echo -e "${YELLOW}=== LICENCIA de $PKG_NAME ===${NC}"
        cat "$APP_DIR/LICENSE"
        exit 0
    elif [ "$FLAG" == "readme" ] && [ -f "$APP_DIR/README.md" ]; then
        echo -e "${YELLOW}=== README de $PKG_NAME ===${NC}"
        cat "$APP_DIR/README.md"
        exit 0
    else
        echo -e "${RED}El archivo solicitado no se encontró en la instalación de $PKG_NAME.${NC}"
        exit 1
    fi
fi

# Extraer datos de la base de datos
NAME=$(jq -r '.name' "$DB_FILE")
DESC=$(jq -r '.description // "No disponible"' "$DB_FILE")
SIZE=$(jq -r '.size // "Desconocido"' "$DB_FILE")
USAGE=$(jq -r '.usage // "No especificado"' "$DB_FILE")
DB_VERSION=$(jq -r '.version // "Desconocida"' "$DB_FILE")
DEPS=$(jq -r '.dependencies // [] | join(", ")' "$DB_FILE")
[ -z "$DEPS" ] && DEPS="Ninguna"

# Comprobar estado de instalación y versión
STATUS_STR="${RED}No instalado${NC}"
INSTALLED_VERSION="-"

if [ -d "$APP_DIR" ]; then
    if [ -f "$APP_DIR/VERSION" ]; then
        INSTALLED_VERSION=$(cat "$APP_DIR/VERSION")
        
        # Comparación de versiones
        if [ "$INSTALLED_VERSION" == "$DB_VERSION" ]; then
            STATUS_STR="${GREEN}Instalado (Actualizado)${NC}"
        else
            # sort -V ordena correctamente versiones (ej. 1.9 vs 1.10)
            OLDER=$(printf '%s\n' "$INSTALLED_VERSION" "$DB_VERSION" | sort -V | head -n1)
            if [ "$OLDER" == "$INSTALLED_VERSION" ]; then
                STATUS_STR="${YELLOW}Instalado (Actualización disponible a $DB_VERSION)${NC}"
            else
                STATUS_STR="${GREEN}Instalado (Versión superior a BD)${NC}"
            fi
        fi
    else
        STATUS_STR="${YELLOW}Instalado (Versión desconocida)${NC}"
    fi
fi

# Imprimir la ficha
echo -e "${GREEN}==================================================${NC}"
echo -e " Paquete: ${YELLOW}$NAME${NC}"
echo -e " Estado:  $STATUS_STR"
echo -e " Versión: Local [$INSTALLED_VERSION] | Repositorio [$DB_VERSION]"
echo -e "${GREEN}==================================================${NC}"
echo -e " Descripción:  $DESC"
echo -e " Tamaño:       $SIZE"
echo -e " Dependencias: $DEPS"
echo -e " Uso:          $USAGE"
echo -e "${GREEN}==================================================${NC}"

#!/bin/bash
# /usr/local/casata/modules/info.sh

CASATA_ROOT="/usr/local/casata"
APPS_DIR="$CASATA_ROOT/apps"
DATA_DIR="$CASATA_ROOT/data"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ------------------------------------------------------------
# Función para resolver versiones que pueden ser URLs
# ------------------------------------------------------------
resolve_version() {
    local version_input="$1"
    if [[ "$version_input" =~ ^[Hh][Tt][Tt][Pp] ]]; then
        local temp_file=$(mktemp)
        if wget -q --timeout=10 --tries=1 -O "$temp_file" "$version_input" 2>/dev/null; then
            local resolved=$(cat "$temp_file" | tr -d '[:space:]')
            rm -f "$temp_file"
            if [ -n "$resolved" ]; then
                echo "$resolved"
            else
                rm -f "$temp_file"
                echo -e "${RED}Error: La URL de versión devolvió contenido vacío.${NC}" >&2
                return 1
            fi
        else
            rm -f "$temp_file"
            echo -e "${RED}Error: No se pudo descargar la versión desde $version_input.${NC}" >&2
            return 1
        fi
    else
        echo "$version_input"
    fi
}

# Parsear argumentos (permite flag antes o después del nombre)
FLAG=""
PKG_NAME=""
for arg in "$@"; do
    case "$arg" in
        -r|--readme)
            if [ -n "$FLAG" ]; then
                echo -e "${RED}Error: Solo se permite un flag.${NC}" >&2
                exit 1
            fi
            FLAG="readme"
            ;;
        -l|--license-short)
            if [ -n "$FLAG" ]; then
                echo -e "${RED}Error: Solo se permite un flag.${NC}" >&2
                exit 1
            fi
            FLAG="license-short"
            ;;
        -L|--license-full)
            if [ -n "$FLAG" ]; then
                echo -e "${RED}Error: Solo se permite un flag.${NC}" >&2
                exit 1
            fi
            FLAG="license-full"
            ;;
        -*)
            echo -e "${RED}Error: Opción desconocida: $arg${NC}" >&2
            exit 1
            ;;
        *)
            if [ -n "$PKG_NAME" ]; then
                echo -e "${RED}Error: Demasiados argumentos.${NC}" >&2
                exit 1
            fi
            PKG_NAME="$arg"
            ;;
    esac
done

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

    case "$FLAG" in
        "license-short")
            if [ -f "$APP_DIR/LICENSE" ]; then
                echo -e "${YELLOW}=== LICENCIA (primera línea, -L para entera) de $PKG_NAME ===${NC}"
                head -n 1 "$APP_DIR/LICENSE"
                exit 0
            else
                echo -e "${RED}No se encontró el archivo LICENSE en $PKG_NAME.${NC}"
                exit 1
            fi
            ;;
        "license-full")
            if [ -f "$APP_DIR/LICENSE" ]; then
                echo -e "${YELLOW}=== LICENCIA completa de $PKG_NAME ===${NC}"
                cat "$APP_DIR/LICENSE"
                exit 0
            else
                echo -e "${RED}No se encontró el archivo LICENSE en $PKG_NAME.${NC}"
                exit 1
            fi
            ;;
        "readme")
            if [ -f "$APP_DIR/README.md" ]; then
                echo -e "${YELLOW}=== README de $PKG_NAME ===${NC}"
                cat "$APP_DIR/README.md"
                exit 0
            else
                echo -e "${RED}No se encontró el archivo README.md en $PKG_NAME.${NC}"
                exit 1
            fi
            ;;
    esac
fi

# Extraer datos de la base de datos
NAME=$(jq -r '.name' "$DB_FILE")
DESC=$(jq -r '.description // "No disponible"' "$DB_FILE")
SIZE=$(jq -r '.size // "Desconocido"' "$DB_FILE")
USAGE=$(jq -r '.usage // "No especificado"' "$DB_FILE")

# Versión de repositorio (puede ser URL)
DB_VERSION=$(jq -r '.version // "Desconocida"' "$DB_FILE")
if ! DB_VERSION=$(resolve_version "$DB_VERSION"); then
    DB_VERSION="Desconocida"
fi

DEPS=$(jq -r '.dependencies // [] | join(", ")' "$DB_FILE")
[ -z "$DEPS" ] && DEPS="Ninguna"

# ---- Nuevos campos de metadatos ----
PROJECT=$(jq -r '.project // ""' "$DB_FILE")
IS_OPEN=$(jq -r '.is_open_source // false' "$DB_FILE")
SOURCE_CODE=$(jq -r '.source_code // ""' "$DB_FILE")
ORIGIN=$(jq -r '.origin // ""' "$DB_FILE")
DEVELOPER=$(jq -r '.developer // ""' "$DB_FILE")
LICENSE=$(jq -r '.license // ""' "$DB_FILE")
LICENSE_FILE=$(jq -r '.license_file // ""' "$DB_FILE")
COPYRIGHT_TITLE=$(jq -r '.copyright_title // ""' "$DB_FILE")
COPYRIGHT_YEAR=$(jq -r '.copyright_year // ""' "$DB_FILE")

# Comprobar estado de instalación y versión
STATUS_STR="${RED}No instalado${NC}"
INSTALLED_VERSION="-"

if [ -d "$APP_DIR" ]; then
    if [ -f "$APP_DIR/VERSION" ]; then
        INSTALLED_VERSION=$(cat "$APP_DIR/VERSION")

        if [ "$INSTALLED_VERSION" == "$DB_VERSION" ]; then
            STATUS_STR="${GREEN}Instalado (Actualizado)${NC}"
        else
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

# ---- Mostrar metadatos ----
echo -e "${GREEN}--------------------------------------------------${NC}"
echo -e "${GREEN}📋 Metadatos${NC}"

# Proyecto (nuevo)
if [ -n "$PROJECT" ]; then
    echo -e " Proyecto:     $PROJECT"
else
    echo -e " Proyecto:     ${YELLOW}(no especificado)${NC}"
fi

# Licencia
if [ -n "$LICENSE" ]; then
    echo -e " Licencia:     $LICENSE"
else
    echo -e " Licencia:     ${YELLOW}(no especificada)${NC}"
fi

# Código fuente (solo si open source)
if [ "$IS_OPEN" = "true" ] || [ "$IS_OPEN" = "1" ]; then
    if [ -n "$SOURCE_CODE" ]; then
        echo -e " Código fuente: $SOURCE_CODE"
    else
        echo -e " Código fuente: ${YELLOW}(no especificado)${NC}"
    fi
else
    echo -e " Código fuente: ${RED}No es de código abierto${NC}"
fi

# Origen
if [ -n "$ORIGIN" ]; then
    echo -e " Origen:       $ORIGIN"
else
    echo -e " Origen:       ${YELLOW}(no especificado)${NC}"
fi

# Desarrollador
if [ -n "$DEVELOPER" ]; then
    echo -e " Desarrollador: $DEVELOPER"
else
    echo -e " Desarrollador: ${YELLOW}(no especificado)${NC}"
fi

# Copyright
if [ -n "$COPYRIGHT_TITLE" ] && [ -n "$COPYRIGHT_YEAR" ]; then
    echo -e " Copyright:    $COPYRIGHT_YEAR $COPYRIGHT_TITLE"
elif [ -n "$COPYRIGHT_TITLE" ]; then
    echo -e " Copyright:    $COPYRIGHT_TITLE (año no especificado)"
elif [ -n "$COPYRIGHT_YEAR" ]; then
    echo -e " Copyright:    $COPYRIGHT_YEAR (titular no especificado)"
else
    echo -e " Copyright:    ${YELLOW}(no especificado)${NC}"
fi

echo -e "${GREEN}==================================================${NC}"

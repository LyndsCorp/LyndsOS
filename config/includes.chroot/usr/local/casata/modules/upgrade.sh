#!/bin/bash
# /usr/local/casata/modules/upgrade.sh
# Actualiza paquetes instalados globalmente (sistema) a la última versión disponible en el repositorio.
# Solo se permiten actualizaciones globales
# Copyright (C) 2026 David Baña Szymaniak

shopt -s nullglob
set -euo pipefail

# Cargar librería de historial
if [ -f "/usr/local/casata/lib/history-lib.sh" ]; then
    source "/usr/local/casata/lib/history-lib.sh"
fi

CASATA_ROOT="/usr/local/casata"
DATA_DIR="$CASATA_ROOT/data"
SYS_DIR="$CASATA_ROOT/apps"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ------------------------------------------------------------
# Función para resolver versiones que pueden ser URLs
# Solo se aplica al campo "version" de los metadatos JSON
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

# Procesar argumentos
AUTO_YES=0

for arg in "$@"; do
    case "$arg" in
        -y|--yes)      AUTO_YES=1 ;;
        *) echo -e "${RED}Opción desconocida: $arg${NC}"; exit 1 ;;
    esac
done

# Directorio de paquetes globales (único permitido)
DIR="$SYS_DIR"

# Recopilar paquetes instalados: lista de "pkg|version"
INSTALLED_LIST=()
if [ -d "$DIR" ]; then
    for app_dir in "$DIR"/*; do
        [ -d "$app_dir" ] || continue
        pkg_name=$(basename "$app_dir")
        version_file="$app_dir/VERSION"
        if [ -f "$version_file" ]; then
            # Versión instalada: se lee directamente (nunca es URL)
            installed_version=$(cat "$version_file")
        else
            installed_version="desconocida"
        fi
        INSTALLED_LIST+=("$pkg_name|$installed_version")
    done
fi

if [ ${#INSTALLED_LIST[@]} -eq 0 ]; then
    echo -e "${YELLOW}No hay paquetes instalados globalmente.${NC}"
    exit 0
fi

# Obtener versiones del repositorio para cada paquete
declare -A REPO_VERSIONS
for entry in "${INSTALLED_LIST[@]}"; do
    IFS='|' read -r pkg installed_version <<< "$entry"
    repo_file="$DATA_DIR/${pkg}.json"
    if [ -f "$repo_file" ]; then
        repo_version=$(jq -r '.version // "0.0.0"' "$repo_file" 2>/dev/null)
        # El campo version de metadatos puede ser URL, resolver
        if ! repo_version=$(resolve_version "$repo_version"); then
            repo_version=""
        fi
        [ -z "$repo_version" ] || [ "$repo_version" = "null" ] && repo_version="0.0.0"
        REPO_VERSIONS["$pkg"]="$repo_version"
    else
        REPO_VERSIONS["$pkg"]=""
    fi
done

# Determinar paquetes actualizables
UPDATABLE=()
for entry in "${INSTALLED_LIST[@]}"; do
    IFS='|' read -r pkg installed_version <<< "$entry"
    repo_version="${REPO_VERSIONS[$pkg]:-}"
    [ -z "$repo_version" ] && continue  # sin repositorio, no se puede actualizar

    if [ "$installed_version" = "desconocida" ]; then
        UPDATABLE+=("$pkg|$installed_version|$repo_version")
    else
        older=$(printf '%s\n' "$installed_version" "$repo_version" | sort -V | head -n1)
        if [ "$older" = "$installed_version" ] && [ "$installed_version" != "$repo_version" ]; then
            UPDATABLE+=("$pkg|$installed_version|$repo_version")
        fi
    fi
done

if [ ${#UPDATABLE[@]} -eq 0 ]; then
    echo -e "${GREEN}Todos los paquetes globales están actualizados.${NC}"
    exit 0
fi

# Mostrar tabla
echo -e "${YELLOW}Paquetes con actualizaciones disponibles:${NC}"
printf "${GREEN}%-4s %-20s %-15s %-15s${NC}\n" "Nº" "Paquete" "Instalado" "Disponible"
echo "--------------------------------------------------------------"
i=1
for entry in "${UPDATABLE[@]}"; do
    IFS='|' read -r pkg installed_ver repo_version <<< "$entry"
    printf "%-4d %-20s %-15s %-15s\n" "$i" "$pkg" "$installed_ver" "$repo_version"
    i=$((i+1))
done

# Selección
if [ $AUTO_YES -eq 1 ]; then
    SELECTION="all"
else
    echo ""
    read -p "Selecciona números (separados por espacio), 'all' o 'none': " selection
    SELECTION="${selection:-none}"
fi

# Procesar selección
SELECTED_PKGS=()
if [[ "$SELECTION" == "all" ]]; then
    for entry in "${UPDATABLE[@]}"; do
        IFS='|' read -r pkg installed_ver repo_version <<< "$entry"
        SELECTED_PKGS+=("$pkg")
    done
elif [[ "$SELECTION" == "none" ]]; then
    echo -e "${YELLOW}No se actualizará ningún paquete.${NC}"
    exit 0
else
    for num in $SELECTION; do
        if [[ "$num" =~ ^[0-9]+$ ]] && [ "$num" -ge 1 ] && [ "$num" -le ${#UPDATABLE[@]} ]; then
            idx=$((num-1))
            entry="${UPDATABLE[$idx]}"
            IFS='|' read -r pkg installed_ver repo_version <<< "$entry"
            SELECTED_PKGS+=("$pkg")
        else
            echo -e "${RED}Número inválido: $num${NC}"
        fi
    done
fi

if [ ${#SELECTED_PKGS[@]} -eq 0 ]; then
    echo -e "${YELLOW}No se seleccionó ningún paquete.${NC}"
    exit 0
fi

# Actualizar
echo -e "${GREEN}Actualizando paquetes seleccionados...${NC}"
for pkg in "${SELECTED_PKGS[@]}"; do
    echo -e "${YELLOW}Actualizando $pkg (global)...${NC}"
    if sudo casata install -y "$pkg"; then
        echo -e "${GREEN}✔ $pkg actualizado correctamente.${NC}"
        log_event "UPGRADE_PACKAGE" "package=\"$pkg\" result=SUCCESS"
    else
        echo -e "${RED}✖ Falló la actualización de $pkg.${NC}"
        log_event "UPGRADE_PACKAGE" "package=\"$pkg\" result=FAILURE"
    fi
done

echo -e "${GREEN}Proceso de actualización completado.${NC}"

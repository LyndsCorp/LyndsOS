#!/bin/bash
# /usr/local/casata/modules/upgrade.sh
# Actualiza paquetes instalados a la última versión disponible en el repositorio.

shopt -s nullglob
set -euo pipefail

CASATA_ROOT="/usr/local/casata"
DATA_DIR="$CASATA_ROOT/data"
SYS_DIR="$CASATA_ROOT/apps"
USR_DIR="$HOME/.local/casata/apps"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Procesar argumentos
AUTO_YES=0
USER_ONLY=0
SYSTEM_ONLY=0

for arg in "$@"; do
    case "$arg" in
        -y|--yes)      AUTO_YES=1 ;;
        --user)        USER_ONLY=1 ;;
        --system)      SYSTEM_ONLY=1 ;;
        *) echo -e "${RED}Opción desconocida: $arg${NC}"; exit 1 ;;
    esac
done

if [ $USER_ONLY -eq 1 ] && [ $SYSTEM_ONLY -eq 1 ]; then
    echo -e "${RED}No se pueden usar --user y --system simultáneamente.${NC}"
    exit 1
fi

# Directorios a revisar según opciones
DIRS=()
if [ $SYSTEM_ONLY -eq 1 ]; then
    DIRS=("$SYS_DIR")
elif [ $USER_ONLY -eq 1 ]; then
    DIRS=("$USR_DIR")
else
    DIRS=("$SYS_DIR" "$USR_DIR")
fi

# Recopilar paquetes instalados: lista de "pkg|version|location"
INSTALLED_LIST=()
for dir in "${DIRS[@]}"; do
    [ -d "$dir" ] || continue
    for app_dir in "$dir"/*; do
        [ -d "$app_dir" ] || continue
        pkg_name=$(basename "$app_dir")
        version_file="$app_dir/VERSION"
        if [ -f "$version_file" ]; then
            installed_version=$(cat "$version_file")
        else
            installed_version="desconocida"
        fi
        if [[ "$dir" == "$SYS_DIR" ]]; then
            location="global"
        else
            location="user"
        fi
        INSTALLED_LIST+=("$pkg_name|$installed_version|$location")
    done
done

if [ ${#INSTALLED_LIST[@]} -eq 0 ]; then
    echo -e "${YELLOW}No hay paquetes instalados.${NC}"
    exit 0
fi

# Obtener versiones del repositorio para cada paquete
declare -A REPO_VERSIONS
for entry in "${INSTALLED_LIST[@]}"; do
    IFS='|' read -r pkg installed_version location <<< "$entry"
    repo_file="$DATA_DIR/${pkg}.json"
    if [ -f "$repo_file" ]; then
        repo_version=$(jq -r '.version // "0.0.0"' "$repo_file" 2>/dev/null)
        [ -z "$repo_version" ] || [ "$repo_version" = "null" ] && repo_version="0.0.0"
        REPO_VERSIONS["$pkg|$location"]="$repo_version"
    else
        REPO_VERSIONS["$pkg|$location"]=""
    fi
done

# Determinar paquetes actualizables
UPDATABLE=()
for entry in "${INSTALLED_LIST[@]}"; do
    IFS='|' read -r pkg installed_version location <<< "$entry"
    key="$pkg|$location"
    repo_version="${REPO_VERSIONS[$key]:-}"
    [ -z "$repo_version" ] && continue  # sin repositorio, no se puede actualizar

    if [ "$installed_version" = "desconocida" ]; then
        # Sin versión local, ofrecemos actualizar (pero mostramos "desconocida")
        UPDATABLE+=("$entry|$repo_version|desconocida")
    else
        older=$(printf '%s\n' "$installed_version" "$repo_version" | sort -V | head -n1)
        if [ "$older" = "$installed_version" ] && [ "$installed_version" != "$repo_version" ]; then
            UPDATABLE+=("$entry|$repo_version|$installed_version")
        fi
    fi
done

if [ ${#UPDATABLE[@]} -eq 0 ]; then
    echo -e "${GREEN}Todos los paquetes están actualizados.${NC}"
    exit 0
fi

# Mostrar tabla
echo -e "${YELLOW}Paquetes con actualizaciones disponibles:${NC}"
printf "${GREEN}%-4s %-20s %-15s %-15s %-10s${NC}\n" "Nº" "Paquete" "Instalado" "Disponible" "Ubicación"
echo "----------------------------------------------------------------------"
i=1
for entry in "${UPDATABLE[@]}"; do
    IFS='|' read -r pkg installed_version location repo_version installed_ver <<< "$entry"
    printf "%-4d %-20s %-15s %-15s %-10s\n" "$i" "$pkg" "$installed_ver" "$repo_version" "$location"
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
        IFS='|' read -r pkg installed_version location repo_version installed_ver <<< "$entry"
        SELECTED_PKGS+=("$pkg|$location")
    done
elif [[ "$SELECTION" == "none" ]]; then
    echo -e "${YELLOW}No se actualizará ningún paquete.${NC}"
    exit 0
else
    for num in $SELECTION; do
        if [[ "$num" =~ ^[0-9]+$ ]] && [ "$num" -ge 1 ] && [ "$num" -le ${#UPDATABLE[@]} ]; then
            idx=$((num-1))
            entry="${UPDATABLE[$idx]}"
            IFS='|' read -r pkg installed_version location repo_version installed_ver <<< "$entry"
            SELECTED_PKGS+=("$pkg|$location")
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
for entry in "${SELECTED_PKGS[@]}"; do
    IFS='|' read -r pkg location <<< "$entry"
    echo -e "${YELLOW}Actualizando $pkg ($location)...${NC}"
    if [ "$location" = "global" ]; then
        sudo casata install -y "$pkg"
    else
        casata install -y --user "$pkg"
    fi
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✔ $pkg actualizado correctamente.${NC}"
    else
        echo -e "${RED}✖ Falló la actualización de $pkg.${NC}"
    fi
done

echo -e "${GREEN}Proceso de actualización completado.${NC}"

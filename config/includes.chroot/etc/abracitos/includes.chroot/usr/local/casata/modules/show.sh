#!/bin/bash
#/usr/local/casata/modules/show.sh

# Definir las rutas
SYS_DIR="/usr/local/casata/apps"
USR_DIR="$HOME/.local/casata/apps"

# Función para listar y contar
listar_apps() {
    local directorio="$1"
    local titulo="$2"

    echo "--- $titulo ---"
    
    # Verificar si el directorio existe
    if [ -d "$directorio" ]; then
        # Listar nombres base
        find "$directorio" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; 2>/dev/null | sed 's/^/  /'
        
        # Calcular el total (redirigimos errores a /dev/null si el dir está vacío o inaccesible)
        local total=$(find "$directorio" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
        echo "  (Total: $total)"
    else
        echo "  (No se encuentra el directorio, prueba a instalar una app)"
        echo "  (Total: 0)"
    fi
    echo ""
}

echo "========================================="
echo "Aplicaciones instaladas mediante Casata"
echo "========================================="
echo ""

# Llamadas a la función
listar_apps "$SYS_DIR" "Apps del Sistema"
listar_apps "$USR_DIR" "Apps del Usuario"

echo "========================================="

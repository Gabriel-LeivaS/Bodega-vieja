#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para corregir problemas de codificación en templates."""

import os

# Ruta base de templates
BASE = r'g:\OneDrive\OneDrive - alu.ucm.cl\Estudios\Semestres\Septimo semestre\Desarrollo de Software\1\respaldo bodega\bodega menu\Bodega-Vieja-main\templates'

# Archivos a corregir
FILES = ['nosotros.html', 'servicios.html', 'contacto.html']

# Mapeo de caracteres mal codificados
REPLACEMENTS = [
    ('Ã³', 'ó'),
    ('Ã­', 'í'),
    ('Ã±', 'ñ'),
    ('Ãº', 'ú'),
    ('Ã¡', 'á'),
    ('Ã©', 'é'),
    ('Â¿', '¿'),
    ('Â¡', '¡'),
    ('ï¿½', 'ñ'),
    ('�', 'ñ'),
    ('Ã'', 'Ñ'),
]

def fix_file(filename):
    """Corrige la codificación de un archivo."""
    filepath = os.path.join(BASE, filename)
    
    # Leer contenido
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Aplicar reemplazos
    original_content = content
    for old, new in REPLACEMENTS:
        content = content.replace(old, new)
    
    # Escribir solo si hubo cambios
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'✅ {filename} - Corregido')
        return True
    else:
        print(f'⚪ {filename} - Sin cambios')
        return False

if __name__ == '__main__':
    print('=== Corrección de codificación ===\n')
    
    fixed = 0
    for filename in FILES:
        if fix_file(filename):
            fixed += 1
    
    print(f'\n🎉 Archivos corregidos: {fixed}/{len(FILES)}')

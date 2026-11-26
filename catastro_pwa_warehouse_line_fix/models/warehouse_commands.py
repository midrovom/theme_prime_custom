# -*- coding: utf-8 -*-
"""Helpers puros para comandos x2many de sale.order.

No alteran explicitamente las bodegas de lineas ya configuradas.
"""


def add_warehouse_to_new_lines(commands, warehouse_id):
    """Completa warehouse_id solo en comandos (0, 0, values) que no lo tienen.

    Se construye una lista nueva para no modificar los dict originales que otro
    modulo pueda conservar en memoria. Los comandos de editar/eliminar/enlazar
    quedan inalterados.
    """
    if not warehouse_id or not commands:
        return commands
    result = []
    for cmd in commands:
        if (isinstance(cmd, (tuple, list)) and len(cmd) >= 3
                and cmd[0] == 0 and isinstance(cmd[2], dict)
                and not cmd[2].get("warehouse_id")):
            values = dict(cmd[2])
            values["warehouse_id"] = warehouse_id
            replacement = list(cmd)
            replacement[2] = values
            result.append(tuple(replacement) if isinstance(cmd, tuple) else replacement)
        else:
            result.append(cmd)
    return result

"""Forma única del CUIT para que con guiones y sin guiones sea el mismo valor."""


def cuit_canonico(value: str) -> str | None:
    """Devuelve XX-XXXXXXXX-X, o None si no hay 11 dígitos."""
    limpio = (value or "").strip().replace("-", "").replace(" ", "")
    if not limpio.isdigit() or len(limpio) != 11:
        return None
    return f"{limpio[:2]}-{limpio[2:10]}-{limpio[10]}"

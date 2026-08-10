"""Selecao canonica N4 sem colapsar ocorrencias com detalhe superior proprio."""

from __future__ import annotations


def install_occurrence_aware_key(motor) -> None:
    if getattr(motor, "_n4_occurrence_key_installed", False):
        return
    original_key = motor._face_unit_geom_key

    def occurrence_aware_key(unit):
        key = original_key(unit)
        if float(unit.get("painel_sup_alt", 0) or 0) > 0.5:
            bbox = unit.get("bbox") or {}
            occurrence = tuple(
                round(float(bbox.get(name, 0) or 0), 1)
                for name in ("x_left", "y_bot", "x_right", "y_top")
            )
            return key + (occurrence,)
        return key

    motor._face_unit_geom_key = occurrence_aware_key
    motor._n4_occurrence_key_installed = True


def select_n4_face_units(motor, face_units, viga_nome=None):
    install_occurrence_aware_key(motor)
    return motor.select_canonical_face_units(face_units, viga_nome)


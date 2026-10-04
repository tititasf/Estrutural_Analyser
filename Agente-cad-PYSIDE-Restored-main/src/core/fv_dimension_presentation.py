"""N3 FV dimension presentation; never round structural or panel geometry."""
from pathlib import Path


def format_fv_n3_dimensions(path: str | Path) -> int:
    """Re-render generated dimension labels with one decimal and a comma.

    This is an N3 export policy, outside the certified STOG geometry engine.
    Definition points and measured values remain exact. No N2/N4 is changed.
    """
    import ezdxf

    doc = ezdxf.readfile(path)
    dimensions = list(doc.modelspace().query('DIMENSION'))
    for dimension in dimensions:
        override = dimension.override()
        # ezdxf treats dimrnd=0 as integer rounding, not disabled rounding.
        override.update({'dimdec': 1, 'dimdsep': ord(','), 'dimzin': 8, 'dimrnd': 0.1})
        override.render()
    if dimensions:
        doc.saveas(path)
    return len(dimensions)

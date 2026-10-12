"""Caches restricted to one contextual analysis, never across jobs."""
from contextvars import ContextVar
from functools import wraps

level_cache = ContextVar('cad_analysis_levels', default=None)


def analysis_run_cache(function):
    @wraps(function)
    def scoped(*args, **kwargs):
        if level_cache.get() is not None:
            return function(*args, **kwargs)
        token = level_cache.set({})
        try:
            return function(*args, **kwargs)
        finally:
            level_cache.reset(token)
    return scoped

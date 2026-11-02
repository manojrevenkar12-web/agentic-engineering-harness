"""Grading: what a reviewer would decide about a change, decomposed into checks that can be audited.

Only this package and aeh.prove read a task's grader directory.
"""

from .grader import Grade, grade

__all__ = ["Grade", "grade"]

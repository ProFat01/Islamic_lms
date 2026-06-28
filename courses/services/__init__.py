"""
courses/services/__init__.py

This file converts courses/services.py (a single module, Phase 4C) into
courses/services/ (a package, Phase 5A) WITHOUT breaking any existing
import. Every existing `from .services import CourseRecommendationService`
statement anywhere in the codebase (courses/views.py) continues to work
unchanged, because this package re-exports the same name at the same
import path.

Phase 5B adds StudyPlannerService to the same re-export pattern.

After all phases:
    from .services import CourseRecommendationService   # Phase 4C
    from .services import AILearningAdvisorService       # Phase 5A
    from .services import StudyPlannerService            # Phase 5B
"""

from .recommendation import CourseRecommendationService
from .ai_learning_advisor import AILearningAdvisorService
from .study_planner import StudyPlannerService

__all__ = [
    'CourseRecommendationService',
    'AILearningAdvisorService',
    'StudyPlannerService',
]
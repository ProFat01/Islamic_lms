"""
courses/services/__init__.py

This file converts courses/services.py (a single module, Phase 4C) into
courses/services/ (a package, Phase 5A) WITHOUT breaking any existing
import. Every existing `from .services import CourseRecommendationService`
statement anywhere in the codebase (courses/views.py) continues to work
unchanged, because this package re-exports the same name at the same
import path.

Migration steps for this file structure change (see deliverable notes):
    1. Create the new folder: courses/services/
    2. Move the existing courses/services.py content into:
           courses/services/recommendation.py
       (renamed, content otherwise byte-for-byte identical)
    3. Place this file at:
           courses/services/__init__.py
    4. Add the new advisor module at:
           courses/services/ai_learning_advisor.py
    5. Delete the old flat courses/services.py file.

After this change:
    from .services import CourseRecommendationService   # still works
    from .services import AILearningAdvisorService       # now also works
"""

from .recommendation import CourseRecommendationService
from .ai_learning_advisor import AILearningAdvisorService

__all__ = [
    'CourseRecommendationService',
    'AILearningAdvisorService',
]

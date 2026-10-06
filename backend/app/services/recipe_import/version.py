"""Which revision of the import pipeline produced a recipe.

``IMPORT_VERSION`` is stamped on every recipe imported from a URL
(``Recipe.import_version``). Bump it by one whenever a change here would give
an already-imported recipe something new: a field the model now fills in, a
better prompt, a new unit, a mapping fix. Recipes carrying an older number are
then *stale*, and the admin's bulk reimport (``services/recipe_reimport.py``)
brings them up to date, a batch at a time.

It is deliberately not the app's version: most releases never touch the import
pipeline, and every stale recipe costs a page fetch and a model call to
refresh. A number that only moves when the pipeline does keeps a release from
re-reading the whole catalogue for nothing.
"""

IMPORT_VERSION = 1

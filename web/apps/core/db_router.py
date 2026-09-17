"""
ThingsBoard database router.
All models in apps.core.tb_models use the 'thingsboard' DB connection (read-only).
Everything else uses 'default'.
"""


class ThingsBoardRouter:
    TB_APP_LABEL = 'tb_readonly'

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.TB_APP_LABEL:
            return 'thingsboard'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.TB_APP_LABEL:
            return None  # never write
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.TB_APP_LABEL:
            return False
        return db == 'default'

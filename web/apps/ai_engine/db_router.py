class AnalysisRouter:
    """
    A router to control all database operations on models in the
    ai_engine application.
    """
    route_app_labels = {'ai_engine'}

    def db_for_read(self, model, **hints):
        if model._meta.model_name == 'analysisresult':
            return 'analysis_db'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.model_name == 'analysisresult':
            return 'analysis_db'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations if both objects are in the same database
        db_set = {'analysis_db', 'default'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'ai_engine' and model_name == 'analysisresult':
            return db == 'analysis_db'
        
        # If it's a different model in ai_engine (like RiskAssessment), let it go to default DB
        if app_label == 'ai_engine':
            return db == 'default'
            
        return None

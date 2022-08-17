from django.apps import AppConfig
import views


class PythonStarterConfig(AppConfig):
    name = 'python_starter'

    def ready(self):
        views.start_app()
        # put your startup code here
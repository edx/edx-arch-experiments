"""
Codejail service URLs.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('api/v0/code-exec', views.code_exec_view_v0, name='code_exec_v0'),
]

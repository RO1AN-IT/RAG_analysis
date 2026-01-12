"""
URL конфигурация для RAG API.
"""

from django.urls import path
from . import views

app_name = 'rag_api'

urlpatterns = [
    path('query/', views.QueryView.as_view(), name='query'),
    path('heygen/prepare-text/', views.HeyGenPrepareTextView.as_view(), name='heygen_prepare_text'),
    path('heygen/status/', views.HeyGenStatusView.as_view(), name='heygen_status'),
    path('heygen/streaming-token/', views.HeyGenStreamingTokenView.as_view(), name='heygen_streaming_token'),
]


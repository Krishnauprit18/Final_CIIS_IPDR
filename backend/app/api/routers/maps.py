"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["maps"])

router.add_api_route('/map/suspicious-phones/html', handlers.map_suspicious_phones_html, methods=['GET'], name='map_suspicious_phones_html')
router.add_api_route('/map/suspicious-phones-network/html', handlers.map_suspicious_phones_network_html, methods=['GET'], name='map_suspicious_phones_network_html')
router.add_api_route('/map/case-network/html', handlers.map_case_network_html, methods=['GET'], name='map_case_network_html')

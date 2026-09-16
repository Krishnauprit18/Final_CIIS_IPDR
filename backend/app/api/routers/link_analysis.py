"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["link-analysis"])

router.add_api_route('/link-analysis/phone', handlers.link_analysis_phone, methods=['GET'], name='link_analysis_phone')
router.add_api_route('/link-analysis/phone/', handlers.link_analysis_phone_alias, methods=['GET'], name='link_analysis_phone_alias')
router.add_api_route('/link-analysis/phone-map/html', handlers.link_analysis_phone_map_html, methods=['GET'], name='link_analysis_phone_map_html')
router.add_api_route('/link-analysis/phone-phone-map/html', handlers.link_analysis_phone_phone_map_html, methods=['GET'], name='link_analysis_phone_phone_map_html')

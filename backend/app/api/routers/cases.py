"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["cases"])

router.add_api_route('/cases/{case_id}/ai-analyze', handlers.ai_analyze_case, methods=['POST'], name='ai_analyze_case')
router.add_api_route('/cases', handlers.create_case, methods=['POST'], name='create_case')
router.add_api_route('/cases', handlers.list_cases, methods=['GET'], name='list_cases')
router.add_api_route('/cases/{case_id}/save-search', handlers.save_search_to_case, methods=['POST'], name='save_search_to_case')
router.add_api_route('/cases/{case_id}/searches', handlers.list_saved_searches, methods=['GET'], name='list_saved_searches')
router.add_api_route('/cases/{case_id}/export-pack', handlers.export_case_pack, methods=['POST'], name='export_case_pack')

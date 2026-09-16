"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["processing"])

router.add_api_route('/process-data', handlers.process_data, methods=['POST'], name='process_data')
router.add_api_route('/process-data/async', handlers.process_data_async, methods=['POST'], name='process_data_async')
router.add_api_route('/data', handlers.get_data, methods=['GET'], name='get_data')

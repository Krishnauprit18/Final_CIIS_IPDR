"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["search"])

router.add_api_route('/search/phone/{phone_number}', handlers.search_by_phone_number, methods=['GET'], name='search_by_phone_number')
router.add_api_route('/search/ip/{ip_address}', handlers.search_by_ip_address, methods=['GET'], name='search_by_ip_address')
router.add_api_route('/search/date-range', handlers.search_by_date_range, methods=['GET'], name='search_by_date_range')
router.add_api_route('/search/communication-type', handlers.search_by_communication_type, methods=['GET'], name='search_by_communication_type')
router.add_api_route('/search/customer', handlers.search_by_customer, methods=['GET'], name='search_by_customer')
router.add_api_route('/search/advanced', handlers.advanced_search, methods=['POST'], name='advanced_search')
router.add_api_route('/search/suggestions', handlers.get_search_suggestions, methods=['GET'], name='get_search_suggestions')
router.add_api_route('/search/statistics', handlers.get_search_statistics, methods=['GET'], name='get_search_statistics')
router.add_api_route('/search/export', handlers.export_search_results, methods=['POST'], name='export_search_results')

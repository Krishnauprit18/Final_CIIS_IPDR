"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["analytics"])

router.add_api_route('/graph', handlers.get_graph_data, methods=['GET'], name='get_graph_data')
router.add_api_route('/relationships', handlers.get_relationships, methods=['GET'], name='get_relationships')
router.add_api_route('/relationships/summary', handlers.get_relationship_summary, methods=['GET'], name='get_relationship_summary')
router.add_api_route('/relationships/bparty-summary', handlers.get_bparty_summary, methods=['GET'], name='get_bparty_summary')
router.add_api_route('/correlation/a2b', handlers.correlation_a2b, methods=['GET'], name='correlation_a2b')
router.add_api_route('/relationships/suspicious', handlers.get_suspicious_patterns, methods=['GET'], name='get_suspicious_patterns')
router.add_api_route('/relationships/export/{format}', handlers.export_relationships, methods=['GET'], name='export_relationships')
router.add_api_route('/filters/investigation-focus', handlers.apply_investigation_focus_filters, methods=['GET'], name='apply_investigation_focus_filters')
router.add_api_route('/filters/priority', handlers.apply_priority_filters, methods=['GET'], name='apply_priority_filters')
router.add_api_route('/filters/exclude-routine', handlers.exclude_routine_traffic, methods=['GET'], name='exclude_routine_traffic')
router.add_api_route('/filters/risk-based', handlers.apply_risk_based_filters, methods=['GET'], name='apply_risk_based_filters')
router.add_api_route('/filters/geographic', handlers.apply_geographic_filters, methods=['GET'], name='apply_geographic_filters')
router.add_api_route('/filters/time-window', handlers.apply_time_window_filters, methods=['GET'], name='apply_time_window_filters')
router.add_api_route('/filters/communication-patterns', handlers.apply_communication_pattern_filters, methods=['GET'], name='apply_communication_pattern_filters')
router.add_api_route('/filters/customer-profile', handlers.apply_customer_profile_filters, methods=['GET'], name='apply_customer_profile_filters')
router.add_api_route('/filters/statistics', handlers.get_filter_statistics, methods=['GET'], name='get_filter_statistics')
router.add_api_route('/filters/report', handlers.get_filter_report, methods=['GET'], name='get_filter_report')
router.add_api_route('/filters/reset', handlers.reset_filters, methods=['GET'], name='reset_filters')

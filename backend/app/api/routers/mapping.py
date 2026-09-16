"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["mapping"])

router.add_api_route('/mapping/phone-connections', handlers.get_phone_connection_table, methods=['GET'], name='get_phone_connection_table')
router.add_api_route('/mapping/ip-connections', handlers.get_ip_connection_table, methods=['GET'], name='get_ip_connection_table')
router.add_api_route('/mapping/customer-connections', handlers.get_customer_connection_table, methods=['GET'], name='get_customer_connection_table')
router.add_api_route('/mapping/communication-matrix/{matrix_type}', handlers.get_communication_matrix, methods=['GET'], name='get_communication_matrix')
router.add_api_route('/mapping/visualization/{network_type}', handlers.generate_network_visualization, methods=['GET'], name='generate_network_visualization')
router.add_api_route('/mapping/interactive-visualization/{network_type}', handlers.generate_interactive_visualization, methods=['GET'], name='generate_interactive_visualization')
router.add_api_route('/mapping/geographic-visualization', handlers.generate_geographic_visualization, methods=['GET'], name='generate_geographic_visualization')
router.add_api_route('/mapping/timeline-visualization', handlers.generate_timeline_visualization, methods=['GET'], name='generate_timeline_visualization')
router.add_api_route('/mapping/statistics', handlers.get_communication_statistics, methods=['GET'], name='get_communication_statistics')
router.add_api_route('/mapping/export-all-tables', handlers.export_all_mapping_tables, methods=['GET'], name='export_all_mapping_tables')
router.add_api_route('/mapping/network-analysis/{network_type}', handlers.analyze_network_properties, methods=['GET'], name='analyze_network_properties')

"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["analysis"])

router.add_api_route('/suspicious/comprehensive-analysis', handlers.run_comprehensive_suspicious_analysis, methods=['GET'], name='run_comprehensive_suspicious_analysis')
router.add_api_route('/suspicious/late-night-activity', handlers.detect_late_night_activity, methods=['GET'], name='detect_late_night_activity')
router.add_api_route('/suspicious/short-duration-patterns', handlers.detect_short_duration_patterns, methods=['GET'], name='detect_short_duration_patterns')
router.add_api_route('/suspicious/high-frequency-activity', handlers.detect_high_frequency_activity, methods=['GET'], name='detect_high_frequency_activity')
router.add_api_route('/suspicious/port-scanning-behavior', handlers.detect_port_scanning_behavior, methods=['GET'], name='detect_port_scanning_behavior')
router.add_api_route('/suspicious/protocol-anomalies', handlers.detect_protocol_anomalies, methods=['GET'], name='detect_protocol_anomalies')
router.add_api_route('/suspicious/geographic-anomalies', handlers.detect_geographic_anomalies, methods=['GET'], name='detect_geographic_anomalies')
router.add_api_route('/suspicious/burst-activity-patterns', handlers.detect_burst_activity_patterns, methods=['GET'], name='detect_burst_activity_patterns')
router.add_api_route('/suspicious/off-hours-business-activity', handlers.detect_off_hours_business_activity, methods=['GET'], name='detect_off_hours_business_activity')
router.add_api_route('/suspicious/statistical-anomalies', handlers.detect_statistical_anomalies, methods=['GET'], name='detect_statistical_anomalies')
router.add_api_route('/suspicious/detection-statistics', handlers.get_detection_statistics, methods=['GET'], name='get_detection_statistics')
router.add_api_route('/suspicious/export-alerts', handlers.export_suspicious_alerts, methods=['POST'], name='export_suspicious_alerts')
router.add_api_route('/suspicious/update-thresholds', handlers.update_alert_thresholds, methods=['GET'], name='update_alert_thresholds')
router.add_api_route('/suspicious/behavioral-baselines', handlers.get_behavioral_baselines, methods=['GET'], name='get_behavioral_baselines')

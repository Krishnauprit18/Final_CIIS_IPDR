"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["normalization"])

router.add_api_route('/normalization/formats', handlers.get_supported_formats, methods=['GET'], name='get_supported_formats')
router.add_api_route('/normalization/schema', handlers.get_standard_schema, methods=['GET'], name='get_standard_schema')
router.add_api_route('/normalization/stats', handlers.get_normalization_statistics, methods=['GET'], name='get_normalization_statistics')
router.add_api_route('/normalization/analyze-sample', handlers.analyze_sample_data, methods=['POST'], name='analyze_sample_data')
router.add_api_route('/normalization/upload-with-mapping', handlers.upload_with_custom_mapping, methods=['POST'], name='upload_with_custom_mapping')
router.add_api_route('/normalization/batch-upload', handlers.batch_upload_files, methods=['POST'], name='batch_upload_files')
router.add_api_route('/normalization/provider-mappings', handlers.get_provider_mappings, methods=['GET'], name='get_provider_mappings')

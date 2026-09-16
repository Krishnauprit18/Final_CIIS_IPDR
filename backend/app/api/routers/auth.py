"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["auth"])

router.add_api_route('/auth/login', handlers.login, methods=['POST'], name='login')
router.add_api_route('/auth/register', handlers.register, methods=['POST'], name='register')
router.add_api_route('/auth/logout', handlers.logout, methods=['POST'], name='logout')
router.add_api_route('/auth/verify', handlers.verify_session, methods=['GET'], name='verify_session')
router.add_api_route('/auth/me', handlers.get_profile, methods=['GET'], name='get_profile')
router.add_api_route('/auth/profile', handlers.update_profile, methods=['PUT'], name='update_profile')
router.add_api_route('/auth/change-password', handlers.change_password, methods=['POST'], name='change_password')

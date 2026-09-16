"""Phase 1 API router.

Routes are organized by domain while preserving the existing handler behavior.
"""
from fastapi import APIRouter
from app import legacy_handlers as handlers

router = APIRouter(tags=["health"])

router.add_api_route('/', handlers.read_root, methods=['GET'], name='read_root')

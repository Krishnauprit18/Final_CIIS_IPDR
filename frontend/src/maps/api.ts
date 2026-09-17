import { API_BASE_URL } from '../api/client';

export function suspiciousPhonesMapUrl(days = 30) {
  return `${API_BASE_URL}/map/suspicious-phones/html?days=${days}`;
}

export function caseNetworkMapUrl(caseId: number) {
  return `${API_BASE_URL}/map/case-network/html?case_id=${caseId}`;
}

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
import re
from datetime import datetime, timedelta
from ipaddress import ip_address, AddressValueError
from collections import defaultdict
import json

class CommunicationFilters:
    """
    Advanced filtering system to exclude irrelevant records and focus on 
    communication sessions useful for law enforcement investigations.
    """
    
    def __init__(self, data: pd.DataFrame):
        self.original_data = data.copy()
        self.filtered_data = data.copy()
        self.filter_stats = {
            'original_records': len(data),
            'filtered_records': 0,
            'excluded_records': 0,
            'filters_applied': []
        }
        
    def reset_filters(self):
        """Reset to original unfiltered data"""
        self.filtered_data = self.original_data.copy()
        self.filter_stats = {
            'original_records': len(self.original_data),
            'filtered_records': len(self.filtered_data),
            'excluded_records': 0,
            'filters_applied': []
        }
    
    def apply_investigation_priority_filters(self) -> pd.DataFrame:
        """
        Apply high-priority filters for investigation relevance:
        - Focus on suspicious ports and protocols
        - Long duration communications
        - Public IP destinations
        - Unusual time patterns
        """
        before_count = len(self.filtered_data)
        
        # Priority Filter 1: Suspicious/Investigation-relevant ports
        suspicious_ports = [22, 23, 3389, 5900, 1433, 3306, 5432, 6379, 443, 80, 5060, 5061, 5222, 5223]
        port_filter = self.filtered_data['Destination Port'].isin(suspicious_ports)
        
        # Priority Filter 2: Long duration communications (potential for data exfiltration/surveillance)
        duration_threshold = self.filtered_data['Duration'].quantile(0.75)  # Top 25% longest sessions
        duration_filter = self.filtered_data['Duration'] >= duration_threshold
        
        # Priority Filter 3: Public IP destinations (external communications)
        public_ip_filter = self.filtered_data['Destination IP'].apply(self._is_public_ip)
        
        # Priority Filter 4: Off-hours communications (potential suspicious activity)
        time_filter = self.filtered_data.apply(self._is_suspicious_time, axis=1)
        
        # Combine filters with OR logic (keep if ANY condition is met)
        investigation_mask = port_filter | duration_filter | public_ip_filter | time_filter
        
        self.filtered_data = self.filtered_data[investigation_mask]
        
        after_count = len(self.filtered_data)
        self.filter_stats['filters_applied'].append({
            'filter_name': 'investigation_priority',
            'records_before': before_count,
            'records_after': after_count,
            'excluded': before_count - after_count
        })
        
        return self.filtered_data
    
    def exclude_routine_traffic(self) -> pd.DataFrame:
        """
        Exclude routine/benign traffic that's typically not investigation-relevant:
        - DNS queries to common resolvers
        - Short-duration HTTP/HTTPS to known CDNs
        - Internal network communications
        - Broadcast/multicast traffic
        """
        before_count = len(self.filtered_data)
        
        # Exclude routine DNS queries (port 53) to public resolvers with short duration
        dns_mask = (
            (self.filtered_data['Destination Port'] == 53) & 
            (self.filtered_data['Duration'] < 5) &
            (self.filtered_data['Destination IP'].isin(['8.8.8.8', '8.8.4.4', '1.1.1.1', '1.0.0.1']))
        )
        
        # Exclude very short HTTP/HTTPS sessions (< 10 seconds) - likely automated/benign
        short_web_mask = (
            (self.filtered_data['Destination Port'].isin([80, 443])) &
            (self.filtered_data['Duration'] < 10)
        )
        
        # Exclude internal network communications (private to private)
        internal_mask = (
            self.filtered_data['Source IP'].apply(self._is_private_ip) &
            self.filtered_data['Destination IP'].apply(self._is_private_ip)
        )
        
        # Exclude broadcast/multicast destinations
        broadcast_mask = self.filtered_data['Destination IP'].apply(self._is_broadcast_multicast)
        
        # Combine exclusion filters with OR logic (exclude if ANY condition is met)
        exclude_mask = dns_mask | short_web_mask | internal_mask | broadcast_mask
        
        # Keep records that DON'T match exclusion criteria
        self.filtered_data = self.filtered_data[~exclude_mask]
        
        after_count = len(self.filtered_data)
        self.filter_stats['filters_applied'].append({
            'filter_name': 'exclude_routine_traffic',
            'records_before': before_count,
            'records_after': after_count,
            'excluded': before_count - after_count
        })
        
        return self.filtered_data
    
    def filter_by_risk_indicators(self, risk_threshold: float = 0.5) -> pd.DataFrame:
        """
        Filter based on risk indicators for investigation priority
        """
        before_count = len(self.filtered_data)
        
        # Calculate risk scores for each record
        self.filtered_data['risk_score'] = self.filtered_data.apply(self._calculate_risk_score, axis=1)
        
        # Keep only high-risk communications
        self.filtered_data = self.filtered_data[self.filtered_data['risk_score'] >= risk_threshold]
        
        after_count = len(self.filtered_data)
        self.filter_stats['filters_applied'].append({
            'filter_name': f'risk_indicators_threshold_{risk_threshold}',
            'records_before': before_count,
            'records_after': after_count,
            'excluded': before_count - after_count
        })
        
        return self.filtered_data
    
    def filter_by_customer_profile(self, 
                                 high_value_customers: List[str] = None,
                                 exclude_customers: List[str] = None) -> pd.DataFrame:
        """
        Filter based on customer profiles of investigation interest
        """
        before_count = len(self.filtered_data)
        
        customer_mask = pd.Series([True] * len(self.filtered_data))
        
        # Focus on high-value customers if specified
        if high_value_customers:
            customer_mask &= (
                self.filtered_data['SubscriberID'].isin(high_value_customers) |
                self.filtered_data['CustName'].isin(high_value_customers) |
                self.filtered_data['Phone'].isin(high_value_customers)
            )
        
        # Exclude specific customers if specified
        if exclude_customers:
            exclude_mask = (
                self.filtered_data['SubscriberID'].isin(exclude_customers) |
                self.filtered_data['CustName'].isin(exclude_customers) |
                self.filtered_data['Phone'].isin(exclude_customers)
            )
            customer_mask &= ~exclude_mask
        
        self.filtered_data = self.filtered_data[customer_mask]
        
        after_count = len(self.filtered_data)
        self.filter_stats['filters_applied'].append({
            'filter_name': 'customer_profile',
            'records_before': before_count,
            'records_after': after_count,
            'excluded': before_count - after_count
        })
        
        return self.filtered_data
    
    def filter_by_geographic_region(self, 
                                  lat_range: Tuple[float, float] = None,
                                  lon_range: Tuple[float, float] = None,
                                  cities: List[str] = None) -> pd.DataFrame:
        """
        Filter by geographic regions of investigation interest
        """
        before_count = len(self.filtered_data)
        
        geo_mask = pd.Series([True] * len(self.filtered_data))
        
        # Filter by latitude range
        if lat_range:
            geo_mask &= (
                (self.filtered_data['Latitude'] >= lat_range[0]) &
                (self.filtered_data['Latitude'] <= lat_range[1])
            )
        
        # Filter by longitude range  
        if lon_range:
            geo_mask &= (
                (self.filtered_data['Longitude'] >= lon_range[0]) &
                (self.filtered_data['Longitude'] <= lon_range[1])
            )
        
        # Filter by specific cities
        if cities:
            city_mask = pd.Series([False] * len(self.filtered_data))
            for city in cities:
                city_mask |= self.filtered_data['Address'].str.contains(city, case=False, na=False)
            geo_mask &= city_mask
        
        self.filtered_data = self.filtered_data[geo_mask]
        
        after_count = len(self.filtered_data)
        self.filter_stats['filters_applied'].append({
            'filter_name': 'geographic_region',
            'records_before': before_count,
            'records_after': after_count,
            'excluded': before_count - after_count
        })
        
        return self.filtered_data
    
    def filter_by_time_window(self, 
                            start_time: str = None,
                            end_time: str = None,
                            time_of_day_start: str = None,
                            time_of_day_end: str = None) -> pd.DataFrame:
        """
        Filter by specific time windows of investigation interest
        """
        before_count = len(self.filtered_data)
        
        time_mask = pd.Series([True] * len(self.filtered_data))
        
        # Filter by date range
        if start_time and end_time:
            time_mask &= (
                (self.filtered_data['Start Time'] >= start_time) &
                (self.filtered_data['Start Time'] <= end_time)
            )
        
        # Filter by time of day (e.g., 22:00-05:00 for late night)
        if time_of_day_start and time_of_day_end:
            hour_mask = self.filtered_data['Start Time'].apply(
                lambda x: self._is_time_in_range(x, time_of_day_start, time_of_day_end)
            )
            time_mask &= hour_mask
        
        self.filtered_data = self.filtered_data[time_mask]
        
        after_count = len(self.filtered_data)
        self.filter_stats['filters_applied'].append({
            'filter_name': 'time_window',
            'records_before': before_count,
            'records_after': after_count,
            'excluded': before_count - after_count
        })
        
        return self.filtered_data
    
    def filter_by_communication_patterns(self) -> pd.DataFrame:
        """
        Filter based on suspicious communication patterns:
        - Port scanning behavior
        - Bulk data transfers
        - Repeated connections to same destinations
        """
        before_count = len(self.filtered_data)
        
        # Identify port scanning patterns (same source IP to many destinations)
        source_dest_counts = self.filtered_data.groupby('Source IP')['Destination IP'].nunique()
        port_scanners = source_dest_counts[source_dest_counts >= 5].index  # 5+ unique destinations
        
        # Identify bulk communicators (high data volume or long duration)
        bulk_duration_threshold = self.filtered_data['Duration'].quantile(0.9)  # Top 10%
        
        # Pattern-based filters
        pattern_mask = (
            # Port scanning sources
            self.filtered_data['Source IP'].isin(port_scanners) |
            # Long duration sessions
            (self.filtered_data['Duration'] >= bulk_duration_threshold) |
            # Multiple connections to same destination (potential persistence)
            self.filtered_data.duplicated(subset=['Source IP', 'Destination IP'], keep=False)
        )
        
        self.filtered_data = self.filtered_data[pattern_mask]
        
        after_count = len(self.filtered_data)
        self.filter_stats['filters_applied'].append({
            'filter_name': 'communication_patterns',
            'records_before': before_count,
            'records_after': after_count,
            'excluded': before_count - after_count
        })
        
        return self.filtered_data
    
    def apply_investigation_focus_filters(self, config: Dict = None) -> pd.DataFrame:
        """
        Apply comprehensive investigation-focused filtering pipeline
        """
        if config is None:
            config = {
                'apply_priority_filters': True,
                'exclude_routine_traffic': True,
                'risk_threshold': 0.3,
                'include_communication_patterns': True
            }
        
        # Reset to start fresh
        self.reset_filters()
        
        # Apply investigation priority filters
        if config.get('apply_priority_filters', True):
            self.apply_investigation_priority_filters()
        
        # Exclude routine traffic
        if config.get('exclude_routine_traffic', True):
            self.exclude_routine_traffic()
        
        # Apply risk-based filtering
        risk_threshold = config.get('risk_threshold', 0.3)
        if risk_threshold > 0:
            self.filter_by_risk_indicators(risk_threshold)
        
        # Include suspicious communication patterns
        if config.get('include_communication_patterns', True):
            self.filter_by_communication_patterns()
        
        # Update final stats
        self.filter_stats['filtered_records'] = len(self.filtered_data)
        self.filter_stats['excluded_records'] = (
            self.filter_stats['original_records'] - self.filter_stats['filtered_records']
        )
        
        return self.filtered_data
    
    def get_filter_statistics(self) -> Dict:
        """Get detailed statistics about filtering process"""
        return {
            'summary': self.filter_stats,
            'data_reduction_percentage': (
                (self.filter_stats['excluded_records'] / self.filter_stats['original_records']) * 100
                if self.filter_stats['original_records'] > 0 else 0
            ),
            'investigation_relevance_score': self._calculate_investigation_relevance_score()
        }
    
    def get_filtered_data(self) -> pd.DataFrame:
        """Get the current filtered dataset"""
        return self.filtered_data.copy()
    
    def export_filter_report(self) -> Dict:
        """Export comprehensive filter report for investigation"""
        stats = self.get_filter_statistics()
        
        # Analyze filtered data characteristics
        if not self.filtered_data.empty:
            analysis = {
                'protocol_distribution': self.filtered_data['Protocol'].value_counts().to_dict(),
                'top_destination_ports': self.filtered_data['Destination Port'].value_counts().head(10).to_dict(),
                'public_ip_percentage': (
                    self.filtered_data['Destination IP'].apply(self._is_public_ip).sum() / 
                    len(self.filtered_data) * 100
                ),
                'unique_sources': self.filtered_data['Source IP'].nunique(),
                'unique_destinations': self.filtered_data['Destination IP'].nunique(),
                'avg_duration': self.filtered_data['Duration'].mean(),
                'high_risk_sessions': len(self.filtered_data[
                    self.filtered_data.get('risk_score', pd.Series([0] * len(self.filtered_data))) > 0.7
                ]) if 'risk_score' in self.filtered_data.columns else 0
            }
        else:
            analysis = {}
        
        return {
            'filter_statistics': stats,
            'filtered_data_analysis': analysis,
            'investigation_recommendations': self._generate_investigation_recommendations()
        }
    
    # Helper methods
    def _is_public_ip(self, ip_str: str) -> bool:
        """Check if IP is public"""
        try:
            return not ip_address(str(ip_str)).is_private
        except (ValueError, AddressValueError):
            return False
    
    def _is_private_ip(self, ip_str: str) -> bool:
        """Check if IP is private"""
        try:
            return ip_address(str(ip_str)).is_private
        except (ValueError, AddressValueError):
            return False
    
    def _is_broadcast_multicast(self, ip_str: str) -> bool:
        """Check if IP is broadcast or multicast"""
        try:
            ip = ip_address(str(ip_str))
            return ip.is_multicast or str(ip).endswith('.255')
        except (ValueError, AddressValueError):
            return False
    
    def _is_suspicious_time(self, row) -> bool:
        """Check if communication happened during suspicious hours (10 PM - 5 AM)"""
        try:
            start_time = str(row['Start Time'])
            hour_match = re.search(r'-(\d{2}):', start_time)
            if hour_match:
                hour = int(hour_match.group(1))
                return hour >= 22 or hour <= 5
        except:
            pass
        return False
    
    def _is_time_in_range(self, timestamp: str, start_time: str, end_time: str) -> bool:
        """Check if timestamp falls within time range"""
        try:
            hour_match = re.search(r'-(\d{2}):', str(timestamp))
            if hour_match:
                hour = int(hour_match.group(1))
                start_hour = int(start_time.split(':')[0])
                end_hour = int(end_time.split(':')[0])
                
                if start_hour <= end_hour:
                    return start_hour <= hour <= end_hour
                else:  # Overnight range
                    return hour >= start_hour or hour <= end_hour
        except:
            pass
        return False
    
    def _calculate_risk_score(self, row) -> float:
        """Calculate risk score for a communication record"""
        risk_score = 0.0
        
        # High risk ports
        high_risk_ports = [22, 23, 3389, 5900, 1433, 3306]
        if row['Destination Port'] in high_risk_ports:
            risk_score += 0.4
        
        # Public IP destinations
        if self._is_public_ip(row['Destination IP']):
            risk_score += 0.2
        
        # Long duration
        if row['Duration'] > 300:  # > 5 minutes
            risk_score += 0.2
        
        # Suspicious time
        if self._is_suspicious_time(row):
            risk_score += 0.3
        
        # SSH/Remote access protocols
        if row['Destination Port'] in [22, 3389, 5900]:
            risk_score += 0.2
        
        return min(risk_score, 1.0)
    
    def _calculate_investigation_relevance_score(self) -> float:
        """Calculate overall investigation relevance score"""
        if self.filtered_data.empty:
            return 0.0
        
        relevance_indicators = 0
        total_indicators = 5
        
        # High risk sessions
        if 'risk_score' in self.filtered_data.columns:
            high_risk_ratio = (self.filtered_data['risk_score'] > 0.5).sum() / len(self.filtered_data)
            if high_risk_ratio > 0.1:  # > 10% high risk
                relevance_indicators += 1
        
        # Public IP communications
        public_ip_ratio = self.filtered_data['Destination IP'].apply(self._is_public_ip).sum() / len(self.filtered_data)
        if public_ip_ratio > 0.3:  # > 30% public IPs
            relevance_indicators += 1
        
        # Suspicious ports usage
        suspicious_ports = [22, 23, 3389, 5900, 1433, 3306]
        suspicious_port_ratio = self.filtered_data['Destination Port'].isin(suspicious_ports).sum() / len(self.filtered_data)
        if suspicious_port_ratio > 0.05:  # > 5% suspicious ports
            relevance_indicators += 1
        
        # Off-hours activity
        off_hours_ratio = self.filtered_data.apply(self._is_suspicious_time, axis=1).sum() / len(self.filtered_data)
        if off_hours_ratio > 0.2:  # > 20% off-hours
            relevance_indicators += 1
        
        # Long duration sessions
        long_duration_ratio = (self.filtered_data['Duration'] > 300).sum() / len(self.filtered_data)
        if long_duration_ratio > 0.1:  # > 10% long sessions
            relevance_indicators += 1
        
        return (relevance_indicators / total_indicators) * 100
    
    def _generate_investigation_recommendations(self) -> List[str]:
        """Generate investigation recommendations based on filtered data"""
        recommendations = []
        
        if self.filtered_data.empty:
            recommendations.append("No relevant communication data found with current filters")
            return recommendations
        
        # Analyze filtered data for recommendations
        if 'risk_score' in self.filtered_data.columns:
            high_risk_count = (self.filtered_data['risk_score'] > 0.7).sum()
            if high_risk_count > 0:
                recommendations.append(f"Priority: Investigate {high_risk_count} high-risk communication sessions")
        
        # Port analysis
        suspicious_ports = [22, 23, 3389, 5900]
        suspicious_comms = self.filtered_data[self.filtered_data['Destination Port'].isin(suspicious_ports)]
        if not suspicious_comms.empty:
            recommendations.append(f"Investigate {len(suspicious_comms)} remote access attempts (SSH/RDP/VNC)")
        
        # Off-hours activity
        off_hours_count = self.filtered_data.apply(self._is_suspicious_time, axis=1).sum()
        if off_hours_count > 0:
            recommendations.append(f"Review {off_hours_count} late-night communications for suspicious activity")
        
        # Bulk communicators
        source_counts = self.filtered_data['Source IP'].value_counts()
        bulk_sources = source_counts[source_counts > 10]
        if not bulk_sources.empty:
            recommendations.append(f"Investigate {len(bulk_sources)} sources with high communication volume")
        
        # Public IP destinations
        public_ip_count = self.filtered_data['Destination IP'].apply(self._is_public_ip).sum()
        if public_ip_count > 0:
            recommendations.append(f"Analyze {public_ip_count} external communications to public IPs")
        
        return recommendations
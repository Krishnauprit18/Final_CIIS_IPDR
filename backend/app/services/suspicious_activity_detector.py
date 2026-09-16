import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Set, Any
import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import statistics
import warnings
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.svm import OneClassSVM
import scipy.stats as stats
warnings.filterwarnings('ignore')

class SuspiciousActivityDetector:
    """
    Advanced suspicious activity detection system for IPDR data analysis.
    Automatically identifies unusual communication behaviors and patterns.
    """
    
    def __init__(self, data: pd.DataFrame):
        self.data = data.copy()
        self.suspicious_patterns = {}
        self.behavioral_baselines = {}
        self.anomaly_scores = {}
        self.alert_thresholds = {
            'late_night_calls': {'hour_start': 22, 'hour_end': 5, 'min_count': 3},
            'short_duration_calls': {'max_duration': 30, 'min_count': 5},
            'long_duration_calls': {'min_duration': 1800, 'min_count': 2},  # 30 minutes
            'high_frequency_calls': {'min_count': 20, 'time_window_hours': 24},
            'unusual_protocols': {'suspicious_protocols': ['ICMP'], 'min_count': 3},
            'port_scanning': {'unique_ports_threshold': 10, 'time_window_hours': 1},
            'geographic_anomalies': {'max_distance_km': 500, 'time_window_hours': 1},
            'burst_activity': {'calls_per_minute': 5, 'duration_minutes': 10},
            'steganography_indicators': {'small_data_transfers': True, 'min_count': 10},
            'off_hours_activity': {'business_hour_start': 9, 'business_hour_end': 17}
        }
        
        # Initialize detection
        self._prepare_data()
        self._establish_baselines()
        
    def _prepare_data(self):
        """Prepare and clean data for analysis"""
        # Parse timestamps
        self.data['Start_DateTime'] = pd.to_datetime(self.data['Start Time'], 
                                                    format='%Y-%m-%d-%H:%M:%S', 
                                                    errors='coerce')
        self.data['End_DateTime'] = pd.to_datetime(self.data['End Time'], 
                                                  format='%Y-%m-%d-%H:%M:%S', 
                                                  errors='coerce')
        
        # Extract time components
        self.data['Hour'] = self.data['Start_DateTime'].dt.hour
        self.data['Day'] = self.data['Start_DateTime'].dt.day
        self.data['DayOfWeek'] = self.data['Start_DateTime'].dt.dayofweek
        self.data['Date'] = self.data['Start_DateTime'].dt.date
        
        # Clean numeric fields
        self.data['Duration'] = pd.to_numeric(self.data['Duration'], errors='coerce').fillna(0)
        self.data['Source Port'] = pd.to_numeric(self.data['Source Port'], errors='coerce').fillna(0)
        self.data['Destination Port'] = pd.to_numeric(self.data['Destination Port'], errors='coerce').fillna(0)
        
        # Geographic calculations
        self.data['Latitude'] = pd.to_numeric(self.data['Latitude'], errors='coerce').fillna(0)
        self.data['Longitude'] = pd.to_numeric(self.data['Longitude'], errors='coerce').fillna(0)
        
    def _establish_baselines(self):
        """Establish behavioral baselines for anomaly detection"""
        self.behavioral_baselines = {
            'avg_duration': self.data['Duration'].mean(),
            'std_duration': self.data['Duration'].std(),
            'avg_calls_per_day': len(self.data) / self.data['Date'].nunique(),
            'common_protocols': self.data['Protocol'].value_counts().to_dict(),
            'common_hours': self.data['Hour'].value_counts().to_dict(),
            'avg_calls_per_customer': self.data.groupby('SubscriberID').size().mean(),
            'common_ports': self.data['Destination Port'].value_counts().head(20).to_dict(),
            'duration_percentiles': {
                '25th': self.data['Duration'].quantile(0.25),
                '75th': self.data['Duration'].quantile(0.75),
                '90th': self.data['Duration'].quantile(0.90),
                '95th': self.data['Duration'].quantile(0.95)
            }
        }
        
    def detect_late_night_activity(self) -> List[Dict]:
        """Detect unusual late-night communication patterns"""
        alerts = []
        thresholds = self.alert_thresholds['late_night_calls']
        
        # Filter late-night calls (22:00-05:00)
        late_night_mask = (
            (self.data['Hour'] >= thresholds['hour_start']) | 
            (self.data['Hour'] <= thresholds['hour_end'])
        )
        late_night_calls = self.data[late_night_mask]
        
        # Group by subscriber and analyze patterns
        subscriber_late_night = late_night_calls.groupby('SubscriberID').agg({
            'CustName': 'first',
            'Phone': 'first',
            'Start_DateTime': 'count',
            'Duration': ['sum', 'mean'],
            'Hour': lambda x: list(x),
            'Destination IP': 'nunique'
        }).round(2)
        
        subscriber_late_night.columns = ['Customer_Name', 'Phone', 'Call_Count', 
                                       'Total_Duration', 'Avg_Duration', 'Hours', 'Unique_Destinations']
        
        # Identify suspicious patterns
        suspicious_subscribers = subscriber_late_night[
            subscriber_late_night['Call_Count'] >= thresholds['min_count']
        ]
        
        for subscriber_id, data in suspicious_subscribers.iterrows():
            alert = {
                'alert_type': 'Late Night Activity',
                'severity': 'HIGH' if data['Call_Count'] > 10 else 'MEDIUM',
                'subscriber_id': subscriber_id,
                'customer_name': data['Customer_Name'],
                'phone': data['Phone'],
                'call_count': data['Call_Count'],
                'total_duration': data['Total_Duration'],
                'avg_duration': data['Avg_Duration'],
                'hours_active': sorted(list(set(data['Hours']))),
                'unique_destinations': data['Unique_Destinations'],
                'suspicion_score': min(100, (data['Call_Count'] / thresholds['min_count']) * 30),
                'description': f"Unusual late-night activity: {data['Call_Count']} calls between 22:00-05:00"
            }
            alerts.append(alert)
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def detect_short_duration_patterns(self) -> List[Dict]:
        """Detect patterns of unusually short duration calls"""
        alerts = []
        threshold = self.alert_thresholds['short_duration_calls']
        
        # Filter short calls
        short_calls = self.data[self.data['Duration'] <= threshold['max_duration']]
        
        # Group by subscriber
        subscriber_short_calls = short_calls.groupby('SubscriberID').agg({
            'CustName': 'first',
            'Phone': 'first',
            'Start_DateTime': 'count',
            'Duration': 'mean',
            'Destination IP': 'nunique',
            'Protocol': lambda x: list(x.unique())
        }).round(2)
        
        subscriber_short_calls.columns = ['Customer_Name', 'Phone', 'Short_Call_Count', 
                                        'Avg_Duration', 'Unique_Destinations', 'Protocols']
        
        # Identify suspicious patterns
        suspicious = subscriber_short_calls[
            subscriber_short_calls['Short_Call_Count'] >= threshold['min_count']
        ]
        
        for subscriber_id, data in suspicious.iterrows():
            # Calculate percentage of short calls for this subscriber
            total_calls = len(self.data[self.data['SubscriberID'] == subscriber_id])
            short_call_percentage = (data['Short_Call_Count'] / total_calls) * 100
            
            alert = {
                'alert_type': 'Short Duration Pattern',
                'severity': 'HIGH' if short_call_percentage > 80 else 'MEDIUM',
                'subscriber_id': subscriber_id,
                'customer_name': data['Customer_Name'],
                'phone': data['Phone'],
                'short_call_count': data['Short_Call_Count'],
                'avg_duration': data['Avg_Duration'],
                'short_call_percentage': round(short_call_percentage, 2),
                'unique_destinations': data['Unique_Destinations'],
                'protocols': data['Protocols'],
                'suspicion_score': min(100, short_call_percentage),
                'description': f"High frequency of short calls: {data['Short_Call_Count']} calls ≤{threshold['max_duration']}s ({short_call_percentage:.1f}%)"
            }
            alerts.append(alert)
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def detect_high_frequency_activity(self) -> List[Dict]:
        """Detect unusually high frequency communication patterns"""
        alerts = []
        threshold = self.alert_thresholds['high_frequency_calls']
        
        # Group by subscriber and date for daily activity analysis
        daily_activity = self.data.groupby(['SubscriberID', 'Date']).agg({
            'CustName': 'first',
            'Phone': 'first',
            'Start_DateTime': 'count',
            'Duration': 'sum',
            'Destination IP': 'nunique'
        }).reset_index()
        
        daily_activity.columns = ['SubscriberID', 'Date', 'Customer_Name', 'Phone', 
                                'Daily_Calls', 'Total_Duration', 'Unique_Destinations']
        
        # Find subscribers with high daily activity
        high_frequency_days = daily_activity[
            daily_activity['Daily_Calls'] >= threshold['min_count']
        ]
        
        # Group by subscriber to get overall pattern
        subscriber_patterns = high_frequency_days.groupby('SubscriberID').agg({
            'Customer_Name': 'first',
            'Phone': 'first',
            'Daily_Calls': ['count', 'mean', 'max'],
            'Total_Duration': 'mean',
            'Unique_Destinations': 'mean'
        }).round(2)
        
        subscriber_patterns.columns = ['Customer_Name', 'Phone', 'High_Activity_Days', 
                                     'Avg_Daily_Calls', 'Max_Daily_Calls', 
                                     'Avg_Duration', 'Avg_Destinations']
        
        for subscriber_id, data in subscriber_patterns.iterrows():
            intensity_score = (data['Avg_Daily_Calls'] / threshold['min_count']) * 100
            
            alert = {
                'alert_type': 'High Frequency Activity',
                'severity': 'HIGH' if data['Max_Daily_Calls'] > 50 else 'MEDIUM',
                'subscriber_id': subscriber_id,
                'customer_name': data['Customer_Name'],
                'phone': data['Phone'],
                'high_activity_days': data['High_Activity_Days'],
                'avg_daily_calls': data['Avg_Daily_Calls'],
                'max_daily_calls': data['Max_Daily_Calls'],
                'avg_duration': data['Avg_Duration'],
                'avg_destinations': data['Avg_Destinations'],
                'suspicion_score': min(100, intensity_score),
                'description': f"High frequency activity: avg {data['Avg_Daily_Calls']} calls/day, max {data['Max_Daily_Calls']} calls/day"
            }
            alerts.append(alert)
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def detect_port_scanning_behavior(self) -> List[Dict]:
        """Detect potential port scanning activities"""
        alerts = []
        threshold = self.alert_thresholds['port_scanning']
        
        # Group by subscriber and time windows to detect scanning
        self.data['Time_Window'] = self.data['Start_DateTime'].dt.floor('1H')  # 1-hour windows
        
        port_analysis = self.data.groupby(['SubscriberID', 'Time_Window']).agg({
            'CustName': 'first',
            'Phone': 'first',
            'Destination Port': 'nunique',
            'Destination IP': 'nunique',
            'Start_DateTime': 'count',
            'Duration': 'mean'
        }).reset_index()
        
        port_analysis.columns = ['SubscriberID', 'Time_Window', 'Customer_Name', 'Phone',
                               'Unique_Ports', 'Unique_IPs', 'Connection_Count', 'Avg_Duration']
        
        # Identify potential port scanning
        potential_scanning = port_analysis[
            port_analysis['Unique_Ports'] >= threshold['unique_ports_threshold']
        ]
        
        for _, data in potential_scanning.iterrows():
            scanning_intensity = (data['Unique_Ports'] / data['Connection_Count']) * 100
            
            alert = {
                'alert_type': 'Port Scanning Behavior',
                'severity': 'HIGH' if data['Unique_Ports'] > 20 else 'MEDIUM',
                'subscriber_id': data['SubscriberID'],
                'customer_name': data['Customer_Name'],
                'phone': data['Phone'],
                'time_window': data['Time_Window'],
                'unique_ports_accessed': data['Unique_Ports'],
                'unique_ips_targeted': data['Unique_IPs'],
                'total_connections': data['Connection_Count'],
                'avg_duration': data['Avg_Duration'],
                'scanning_intensity': round(scanning_intensity, 2),
                'suspicion_score': min(100, (data['Unique_Ports'] / threshold['unique_ports_threshold']) * 50),
                'description': f"Port scanning detected: {data['Unique_Ports']} unique ports accessed in 1 hour"
            }
            alerts.append(alert)
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def detect_protocol_anomalies(self) -> List[Dict]:
        """Detect unusual protocol usage patterns"""
        alerts = []
        threshold = self.alert_thresholds['unusual_protocols']
        
        # Analyze protocol usage by subscriber
        protocol_usage = self.data.groupby(['SubscriberID', 'Protocol']).agg({
            'CustName': 'first',
            'Phone': 'first',
            'Start_DateTime': 'count',
            'Duration': ['sum', 'mean']
        }).reset_index()
        
        protocol_usage.columns = ['SubscriberID', 'Protocol', 'Customer_Name', 'Phone',
                                'Usage_Count', 'Total_Duration', 'Avg_Duration']
        
        # Focus on suspicious protocols
        suspicious_protocol_usage = protocol_usage[
            (protocol_usage['Protocol'].isin(threshold['suspicious_protocols'])) &
            (protocol_usage['Usage_Count'] >= threshold['min_count'])
        ]
        
        for _, data in suspicious_protocol_usage.iterrows():
            # Get total calls for percentage calculation
            total_calls = len(self.data[self.data['SubscriberID'] == data['SubscriberID']])
            usage_percentage = (data['Usage_Count'] / total_calls) * 100
            
            alert = {
                'alert_type': 'Protocol Anomaly',
                'severity': 'HIGH' if data['Protocol'] == 'ICMP' else 'MEDIUM',
                'subscriber_id': data['SubscriberID'],
                'customer_name': data['Customer_Name'],
                'phone': data['Phone'],
                'suspicious_protocol': data['Protocol'],
                'usage_count': data['Usage_Count'],
                'usage_percentage': round(usage_percentage, 2),
                'total_duration': data['Total_Duration'],
                'avg_duration': data['Avg_Duration'],
                'suspicion_score': min(100, usage_percentage * 2),
                'description': f"Unusual {data['Protocol']} usage: {data['Usage_Count']} connections ({usage_percentage:.1f}%)"
            }
            alerts.append(alert)
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def detect_geographic_anomalies(self) -> List[Dict]:
        """Detect geographically suspicious activities"""
        alerts = []
        
        # Group by subscriber and analyze geographic patterns
        subscriber_locations = self.data.groupby('SubscriberID').agg({
            'CustName': 'first',
            'Phone': 'first',
            'Latitude': 'nunique',
            'Longitude': 'nunique',
            'Address': 'first',
            'Start_DateTime': 'count'
        }).reset_index()
        
        subscriber_locations.columns = ['SubscriberID', 'Customer_Name', 'Phone',
                                      'Unique_Latitudes', 'Unique_Longitudes', 
                                      'Address', 'Total_Calls']
        
        # Identify subscribers with multiple locations
        multi_location_users = subscriber_locations[
            (subscriber_locations['Unique_Latitudes'] > 1) |
            (subscriber_locations['Unique_Longitudes'] > 1)
        ]
        
        for _, data in multi_location_users.iterrows():
            location_diversity = data['Unique_Latitudes'] + data['Unique_Longitudes']
            
            alert = {
                'alert_type': 'Geographic Anomaly',
                'severity': 'MEDIUM',
                'subscriber_id': data['SubscriberID'],
                'customer_name': data['Customer_Name'],
                'phone': data['Phone'],
                'registered_address': data['Address'],
                'unique_latitudes': data['Unique_Latitudes'],
                'unique_longitudes': data['Unique_Longitudes'],
                'total_calls': data['Total_Calls'],
                'location_diversity': location_diversity,
                'suspicion_score': min(100, location_diversity * 20),
                'description': f"Multiple geographic locations: {data['Unique_Latitudes']} lat, {data['Unique_Longitudes']} lon variations"
            }
            alerts.append(alert)
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def detect_burst_activity_patterns(self) -> List[Dict]:
        """Detect burst communication patterns"""
        alerts = []
        threshold = self.alert_thresholds['burst_activity']
        
        # Create 10-minute time windows
        self.data['Burst_Window'] = self.data['Start_DateTime'].dt.floor('10T')
        
        # Analyze activity in each window
        burst_analysis = self.data.groupby(['SubscriberID', 'Burst_Window']).agg({
            'CustName': 'first',
            'Phone': 'first',
            'Start_DateTime': 'count',
            'Duration': ['sum', 'mean'],
            'Destination IP': 'nunique'
        }).reset_index()
        
        burst_analysis.columns = ['SubscriberID', 'Burst_Window', 'Customer_Name', 'Phone',
                                'Calls_Per_Window', 'Total_Duration', 'Avg_Duration', 'Unique_Destinations']
        
        # Identify burst patterns
        burst_patterns = burst_analysis[
            burst_analysis['Calls_Per_Window'] >= threshold['calls_per_minute'] * threshold['duration_minutes']
        ]
        
        for _, data in burst_patterns.iterrows():
            calls_per_minute = data['Calls_Per_Window'] / threshold['duration_minutes']
            
            alert = {
                'alert_type': 'Burst Activity Pattern',
                'severity': 'HIGH' if calls_per_minute > 10 else 'MEDIUM',
                'subscriber_id': data['SubscriberID'],
                'customer_name': data['Customer_Name'],
                'phone': data['Phone'],
                'burst_window': data['Burst_Window'],
                'calls_in_burst': data['Calls_Per_Window'],
                'calls_per_minute': round(calls_per_minute, 2),
                'total_duration': data['Total_Duration'],
                'avg_duration': data['Avg_Duration'],
                'unique_destinations': data['Unique_Destinations'],
                'suspicion_score': min(100, calls_per_minute * 10),
                'description': f"Burst activity: {data['Calls_Per_Window']} calls in 10 minutes ({calls_per_minute:.1f} calls/min)"
            }
            alerts.append(alert)
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def detect_off_hours_business_activity(self) -> List[Dict]:
        """Detect unusual business-hours activity patterns"""
        alerts = []
        threshold = self.alert_thresholds['off_hours_activity']
        
        # Define business hours and off-hours
        business_hours_mask = (
            (self.data['Hour'] >= threshold['business_hour_start']) &
            (self.data['Hour'] <= threshold['business_hour_end'])
        )
        
        off_hours_calls = self.data[~business_hours_mask]
        business_hours_calls = self.data[business_hours_mask]
        
        # Analyze off-hours vs business hours ratio
        off_hours_analysis = off_hours_calls.groupby('SubscriberID').agg({
            'CustName': 'first',
            'Phone': 'first',
            'Start_DateTime': 'count'
        })
        
        business_hours_analysis = business_hours_calls.groupby('SubscriberID').agg({
            'Start_DateTime': 'count'
        })
        
        # Merge and calculate ratios
        activity_comparison = off_hours_analysis.merge(
            business_hours_analysis, 
            left_index=True, right_index=True, 
            how='outer', suffixes=('_off', '_business')
        ).fillna(0)
        
        activity_comparison['total_calls'] = (
            activity_comparison['Start_DateTime_off'] + 
            activity_comparison['Start_DateTime_business']
        )
        activity_comparison['off_hours_percentage'] = (
            activity_comparison['Start_DateTime_off'] / 
            activity_comparison['total_calls'] * 100
        )
        
        # Identify unusual off-hours activity
        unusual_off_hours = activity_comparison[
            (activity_comparison['off_hours_percentage'] > 60) &
            (activity_comparison['Start_DateTime_off'] >= 5)
        ]
        
        for subscriber_id, data in unusual_off_hours.iterrows():
            alert = {
                'alert_type': 'Off-Hours Business Activity',
                'severity': 'MEDIUM',
                'subscriber_id': subscriber_id,
                'customer_name': data['CustName'],
                'phone': data['Phone'],
                'off_hours_calls': data['Start_DateTime_off'],
                'business_hours_calls': data['Start_DateTime_business'],
                'off_hours_percentage': round(data['off_hours_percentage'], 2),
                'total_calls': data['total_calls'],
                'suspicion_score': min(100, data['off_hours_percentage']),
                'description': f"High off-hours activity: {data['off_hours_percentage']:.1f}% of calls outside business hours"
            }
            alerts.append(alert)
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def detect_statistical_anomalies(self) -> List[Dict]:
        """Detect statistical anomalies using machine learning techniques"""
        alerts = []
        
        try:
            # Prepare features for anomaly detection
            feature_data = self.data.groupby('SubscriberID').agg({
                'Duration': ['count', 'mean', 'std', 'min', 'max'],
                'Hour': lambda x: len(set(x)),  # Unique hours
                'Destination Port': 'nunique',
                'Destination IP': 'nunique',
                'Protocol': lambda x: len(set(x))
            }).fillna(0)
            
            # Flatten column names
            feature_data.columns = ['_'.join(col).strip() for col in feature_data.columns]
            
            # Apply Isolation Forest
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            anomaly_scores = iso_forest.fit_predict(feature_data)
            anomaly_scores_normalized = iso_forest.score_samples(feature_data)
            
            # Identify anomalies
            anomaly_indices = np.where(anomaly_scores == -1)[0]
            
            for idx in anomaly_indices:
                subscriber_id = feature_data.index[idx]
                subscriber_info = self.data[self.data['SubscriberID'] == subscriber_id].iloc[0]
                
                alert = {
                    'alert_type': 'Statistical Anomaly',
                    'severity': 'MEDIUM',
                    'subscriber_id': subscriber_id,
                    'customer_name': subscriber_info['CustName'],
                    'phone': subscriber_info['Phone'],
                    'anomaly_score': round(abs(anomaly_scores_normalized[idx]), 3),
                    'features': {
                        'call_count': feature_data.iloc[idx]['Duration_count'],
                        'avg_duration': feature_data.iloc[idx]['Duration_mean'],
                        'unique_hours': feature_data.iloc[idx]['Hour_<lambda>'],
                        'unique_ports': feature_data.iloc[idx]['Destination Port_nunique'],
                        'unique_ips': feature_data.iloc[idx]['Destination IP_nunique']
                    },
                    'suspicion_score': min(100, abs(anomaly_scores_normalized[idx]) * 100),
                    'description': f"Statistical anomaly detected in communication patterns"
                }
                alerts.append(alert)
                
        except Exception as e:
            print(f"Warning: Statistical anomaly detection failed: {str(e)}")
        
        return sorted(alerts, key=lambda x: x['suspicion_score'], reverse=True)
    
    def run_comprehensive_analysis(self) -> Dict[str, List[Dict]]:
        """Run all suspicious activity detection algorithms"""
        print("🔍 Running comprehensive suspicious activity analysis...")
        
        all_alerts = {
            'late_night_activity': self.detect_late_night_activity(),
            'short_duration_patterns': self.detect_short_duration_patterns(),
            'high_frequency_activity': self.detect_high_frequency_activity(),
            'port_scanning_behavior': self.detect_port_scanning_behavior(),
            'protocol_anomalies': self.detect_protocol_anomalies(),
            'geographic_anomalies': self.detect_geographic_anomalies(),
            'burst_activity_patterns': self.detect_burst_activity_patterns(),
            'off_hours_business_activity': self.detect_off_hours_business_activity(),
            'statistical_anomalies': self.detect_statistical_anomalies()
        }
        
        return all_alerts
    
    def generate_summary_report(self, alerts: Dict[str, List[Dict]]) -> Dict:
        """Generate comprehensive summary report"""
        total_alerts = sum(len(alert_list) for alert_list in alerts.values())
        
        # Count by severity
        severity_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        top_suspects = {}
        
        for alert_type, alert_list in alerts.items():
            for alert in alert_list:
                severity = alert.get('severity', 'LOW')
                severity_counts[severity] += 1
                
                # Track top suspects
                subscriber_id = alert['subscriber_id']
                if subscriber_id not in top_suspects:
                    top_suspects[subscriber_id] = {
                        'customer_name': alert['customer_name'],
                        'phone': alert['phone'],
                        'alert_types': [],
                        'total_suspicion_score': 0,
                        'severity_counts': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
                    }
                
                top_suspects[subscriber_id]['alert_types'].append(alert_type)
                top_suspects[subscriber_id]['total_suspicion_score'] += alert.get('suspicion_score', 0)
                top_suspects[subscriber_id]['severity_counts'][severity] += 1
        
        # Get top 10 suspects
        top_suspects_sorted = sorted(
            top_suspects.items(), 
            key=lambda x: x[1]['total_suspicion_score'], 
            reverse=True
        )[:10]
        
        # Alert type distribution
        alert_type_counts = {alert_type: len(alert_list) for alert_type, alert_list in alerts.items()}
        
        summary = {
            'analysis_timestamp': datetime.now().isoformat(),
            'total_records_analyzed': len(self.data),
            'total_alerts_generated': total_alerts,
            'severity_distribution': severity_counts,
            'alert_type_distribution': alert_type_counts,
            'top_suspects': [
                {
                    'rank': idx + 1,
                    'subscriber_id': subscriber_id,
                    'customer_name': data['customer_name'],
                    'phone': data['phone'],
                    'alert_types': list(set(data['alert_types'])),
                    'total_suspicion_score': data['total_suspicion_score'],
                    'severity_counts': data['severity_counts']
                }
                for idx, (subscriber_id, data) in enumerate(top_suspects_sorted)
            ],
            'behavioral_baselines': self.behavioral_baselines,
            'alert_thresholds': self.alert_thresholds,
            'recommendations': self._generate_recommendations(alerts)
        }
        
        return summary
    
    def _generate_recommendations(self, alerts: Dict[str, List[Dict]]) -> List[str]:
        """Generate investigation recommendations based on detected patterns"""
        recommendations = []
        
        # Check for high-priority alerts
        high_severity_count = sum(
            len([a for a in alert_list if a.get('severity') == 'HIGH'])
            for alert_list in alerts.values()
        )
        
        if high_severity_count > 0:
            recommendations.append(f"URGENT: Investigate {high_severity_count} high-severity alerts immediately")
        
        # Late night activity recommendations
        if alerts['late_night_activity']:
            recommendations.append(f"Review {len(alerts['late_night_activity'])} cases of late-night activity for operational security")
        
        # Port scanning recommendations
        if alerts['port_scanning_behavior']:
            recommendations.append(f"Investigate {len(alerts['port_scanning_behavior'])} potential port scanning activities for cyber threats")
        
        # Burst activity recommendations
        if alerts['burst_activity_patterns']:
            recommendations.append(f"Analyze {len(alerts['burst_activity_patterns'])} burst communication patterns for coordination activities")
        
        # Statistical anomaly recommendations
        if alerts['statistical_anomalies']:
            recommendations.append(f"Deep dive into {len(alerts['statistical_anomalies'])} statistical anomalies for hidden patterns")
        
        # General recommendations
        if sum(len(alert_list) for alert_list in alerts.values()) > 50:
            recommendations.append("High alert volume detected - consider refining thresholds or expanding investigation team")
        
        return recommendations
    
    def export_alerts_to_csv(self, alerts: Dict[str, List[Dict]], filename: str = "suspicious_activities.csv"):
        """Export all alerts to CSV format for external analysis"""
        all_alerts_flat = []
        
        for alert_type, alert_list in alerts.items():
            for alert in alert_list:
                flat_alert = {
                    'Alert_Type': alert_type,
                    'Severity': alert.get('severity', 'UNKNOWN'),
                    'Subscriber_ID': alert['subscriber_id'],
                    'Customer_Name': alert['customer_name'],
                    'Phone': alert['phone'],
                    'Suspicion_Score': alert.get('suspicion_score', 0),
                    'Description': alert['description']
                }
                
                # Add specific fields based on alert type
                for key, value in alert.items():
                    if key not in flat_alert and isinstance(value, (str, int, float)):
                        flat_alert[key] = value
                
                all_alerts_flat.append(flat_alert)
        
        alerts_df = pd.DataFrame(all_alerts_flat)
        alerts_df.to_csv(filename, index=False)
        return filename
    
    def get_detection_statistics(self) -> Dict:
        """Get statistics about the detection process"""
        return {
            'data_records_processed': len(self.data),
            'unique_subscribers': self.data['SubscriberID'].nunique(),
            'date_range': {
                'start': str(self.data['Start_DateTime'].min()),
                'end': str(self.data['Start_DateTime'].max())
            },
            'behavioral_baselines': self.behavioral_baselines,
            'alert_thresholds': self.alert_thresholds,
            'data_quality': {
                'missing_timestamps': self.data['Start_DateTime'].isnull().sum(),
                'invalid_durations': (self.data['Duration'] < 0).sum(),
                'missing_locations': ((self.data['Latitude'] == 0) | (self.data['Longitude'] == 0)).sum()
            }
        }

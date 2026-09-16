import pandas as pd
import networkx as nx
from typing import Dict, List, Tuple, Optional, Set
import re
from ipaddress import ip_address, ip_network, AddressValueError
from collections import defaultdict
import json

class RelationshipExtractor:
    """
    Extract and map A-Party (initiator) and B-Party (recipient) relationships from IPDR logs.
    Handles synthetic.csv format with rich customer and network data.
    """
    
    def __init__(self, data: pd.DataFrame, allowlist_ips: Optional[Set[str]] = None, denylist_ips: Optional[Set[str]] = None):
        self.data = data
        self.relationships = []
        self.a_party_stats = defaultdict(dict)
        self.b_party_stats = defaultdict(dict)
        # Investigative context lists
        self.allowlist_ips = set(allowlist_ips or [])
        self.denylist_ips = set(denylist_ips or [])
        
    def extract_relationships(self) -> List[Dict]:
        """
        Extract A-Party to B-Party relationships with detailed mapping.
        Returns list of relationship records with enriched data.
        """
        relationships = []
        
        for _, row in self.data.iterrows():
            # A-Party (Initiator) identification
            a_party = {
                'source_ip': row['Source IP'],
                'source_port': row['Source Port'],
                'nat_ip': row['NAT IP'],
                'nat_port': row['NAT Port'],
                'user_id': row['UserID'],
                'subscriber_id': row['SubscriberID'],
                'customer_name': row['CustName'],
                'phone': row['Phone'],
                'alt_phone': row['Alt-Phone'],
                'email': row['Email'],
                'address': row['Address'],
                'customer_id': row['CustID'],
                'device': row['Device'],
                'ip_type': row['IP Type'],
                'location': {
                    'latitude': row['Latitude'],
                    'longitude': row['Longitude']
                }
            }
            
            # B-Party (Recipient) identification
            b_party = {
                'destination_ip': row['Destination IP'],
                'destination_port': row['Destination Port'],
                'is_public_ip': self._is_public_ip(row['Destination IP']),
                'ip_category': self._categorize_ip(row['Destination IP']),
                # Optional B-party attributes if present in normalized dataset
                'b_phone': row.get('B-Phone') if isinstance(row, dict) else (row['B-Phone'] if 'B-Phone' in row else ''),
                'b_subscriber_id': row.get('B-SubscriberID') if isinstance(row, dict) else (row['B-SubscriberID'] if 'B-SubscriberID' in row else ''),
                'b_customer_name': row.get('B-CustName') if isinstance(row, dict) else (row['B-CustName'] if 'B-CustName' in row else ''),
            }
            
            # Communication session details
            session = {
                'protocol': row['Protocol'],
                'start_time': row['Start Time'],
                'end_time': row['End Time'],
                'duration': row['Duration'],
                'session_id': f"{row['Source IP']}:{row['Source Port']}-{row['Destination IP']}:{row['Destination Port']}-{row['Start Time']}"
            }
            
            # Create relationship record
            relationship = {
                'a_party': a_party,
                'b_party': b_party,
                'session': session,
                'relationship_type': self._determine_relationship_type(row),
                'risk_score': self._calculate_risk_score(row)
            }
            
            relationships.append(relationship)
            
        self.relationships = relationships
        return relationships
    
    def _is_public_ip(self, ip_str: str) -> bool:
        """Check if IP is public (exclude private, loopback, multicast, link-local, reserved, CGNAT, docs, bench)."""
        try:
            ip_str = str(ip_str)
            if not ip_str:
                return False
            if ip_str in self.denylist_ips:
                return False
            if ip_str in self.allowlist_ips:
                return True
            ip = ip_address(ip_str)
            # Exclude non-global scopes
            if ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
                return False
            # Exclude CGNAT 100.64.0.0/10 and other special-use ranges
            special_blocks = [
                '100.64.0.0/10',   # CGNAT
                '198.18.0.0/15',   # Benchmarking
                '192.0.0.0/24',    # IETF Protocol Assignments subset
                '192.0.2.0/24',    # TEST-NET-1
                '198.51.100.0/24', # TEST-NET-2
                '203.0.113.0/24',  # TEST-NET-3
                '240.0.0.0/4',     # Reserved (future use)
            ]
            for cidr in special_blocks:
                try:
                    if ip in ip_network(cidr):
                        return False
                except Exception:
                    continue
            return True
        except (ValueError, AddressValueError):
            return False
    
    def _categorize_ip(self, ip_str: str) -> str:
        """Categorize IP address type"""
        try:
            ip = ip_address(str(ip_str))
            if ip.is_private:
                return "private"
            elif ip.is_multicast:
                return "multicast"
            elif ip.is_loopback:
                return "loopback"
            else:
                return "public"
        except (ValueError, AddressValueError):
            return "invalid"
    
    def _determine_relationship_type(self, row) -> str:
        """Determine type of communication relationship"""
        port = int(row['Destination Port'])
        protocol = row['Protocol']
        
        # Common service ports
        if port == 80 or port == 443:
            return "web_traffic"
        elif port == 53:
            return "dns_query"
        elif port == 22:
            return "ssh_connection"
        elif port in [5060, 5061]:
            return "sip_voip"
        elif port == 5222 or port == 5223:
            return "xmpp_messaging"
        elif port in range(1024, 65535) and protocol == "UDP":
            return "p2p_communication"
        else:
            return "other_service"
    
    def _calculate_risk_score(self, row) -> float:
        """Calculate risk score based on various factors"""
        risk_score = 0.0
        
        # High risk ports
        high_risk_ports = [22, 23, 3389, 5900]  # SSH, Telnet, RDP, VNC
        if int(row['Destination Port']) in high_risk_ports:
            risk_score += 0.3
        
        # Public IP destinations are higher risk
        if self._is_public_ip(row['Destination IP']):
            risk_score += 0.2
        
        # Long duration sessions
        if int(row['Duration']) > 300:  # > 5 minutes
            risk_score += 0.1
        
        # Late night communications (assuming 24h format)
        start_time = row['Start Time']
        if isinstance(start_time, str):
            hour_match = re.search(r'-(\d{2}):', start_time)
            if hour_match:
                hour = int(hour_match.group(1))
                if hour >= 22 or hour <= 5:  # 10 PM to 5 AM
                    risk_score += 0.2
        
        return min(risk_score, 1.0)  # Cap at 1.0
    
    def get_a_party_summary(self) -> Dict:
        """Generate summary statistics for A-Party (initiators)"""
        if not self.relationships:
            self.extract_relationships()
        
        a_party_summary = defaultdict(lambda: {
            'total_connections': 0,
            'unique_destinations': set(),
            'protocols_used': set(),
            'total_duration': 0,
            'risk_connections': 0,
            'customer_info': {}
        })
        
        for rel in self.relationships:
            a_party_id = rel['a_party']['subscriber_id']
            dest_ip = rel['b_party']['destination_ip']
            
            a_party_summary[a_party_id]['total_connections'] += 1
            a_party_summary[a_party_id]['unique_destinations'].add(dest_ip)
            a_party_summary[a_party_id]['protocols_used'].add(rel['session']['protocol'])
            a_party_summary[a_party_id]['total_duration'] += int(rel['session']['duration'])
            
            if rel['risk_score'] > 0.5:
                a_party_summary[a_party_id]['risk_connections'] += 1
            
            # Store customer info (same for all records of this subscriber)
            a_party_summary[a_party_id]['customer_info'] = {
                'name': rel['a_party']['customer_name'],
                'phone': rel['a_party']['phone'],
                'email': rel['a_party']['email'],
                'address': rel['a_party']['address']
            }
        
        # Convert sets to lists for JSON serialization
        for party_id in a_party_summary:
            a_party_summary[party_id]['unique_destinations'] = list(a_party_summary[party_id]['unique_destinations'])
            a_party_summary[party_id]['protocols_used'] = list(a_party_summary[party_id]['protocols_used'])
            a_party_summary[party_id]['unique_destination_count'] = len(a_party_summary[party_id]['unique_destinations'])
        
        return dict(a_party_summary)
    
    def get_b_party_summary(self) -> Dict:
        """Generate summary statistics for B-Party (recipients)"""
        if not self.relationships:
            self.extract_relationships()
        
        b_party_summary = defaultdict(lambda: {
            'total_connections': 0,
            'unique_sources': set(),
            'protocols_used': set(),
            'ip_category': '',
            'is_public': False,
            'common_ports': defaultdict(int)
        })
        
        for rel in self.relationships:
            b_party_ip = rel['b_party']['destination_ip']
            source_ip = rel['a_party']['source_ip']
            port = rel['b_party']['destination_port']
            
            b_party_summary[b_party_ip]['total_connections'] += 1
            b_party_summary[b_party_ip]['unique_sources'].add(source_ip)
            b_party_summary[b_party_ip]['protocols_used'].add(rel['session']['protocol'])
            b_party_summary[b_party_ip]['ip_category'] = rel['b_party']['ip_category']
            b_party_summary[b_party_ip]['is_public'] = rel['b_party']['is_public_ip']
            b_party_summary[b_party_ip]['common_ports'][port] += 1
        
        # Convert sets to lists and get most common ports
        for ip in b_party_summary:
            b_party_summary[ip]['unique_sources'] = list(b_party_summary[ip]['unique_sources'])
            b_party_summary[ip]['protocols_used'] = list(b_party_summary[ip]['protocols_used'])
            b_party_summary[ip]['unique_source_count'] = len(b_party_summary[ip]['unique_sources'])
            
            # Get top 3 most common ports
            common_ports = dict(b_party_summary[ip]['common_ports'])
            b_party_summary[ip]['top_ports'] = sorted(common_ports.items(), 
                                                    key=lambda x: x[1], 
                                                    reverse=True)[:3]
            del b_party_summary[ip]['common_ports']  # Remove defaultdict
        
        return dict(b_party_summary)

    def get_b_party_phone_summary(self) -> Dict:
        """Generate summary statistics for B-Party phones when available"""
        if not self.relationships:
            self.extract_relationships()

        phone_summary = defaultdict(lambda: {
            'total_connections': 0,
            'unique_sources': set(),
            'protocols_used': set(),
            'destination_ips': set()
        })

        for rel in self.relationships:
            b_phone = (rel.get('b_party') or {}).get('b_phone')
            if not b_phone or b_phone == '+910000000000':
                continue
            source_ip = rel['a_party']['source_ip']
            b_ip = rel['b_party']['destination_ip']
            phone_summary[b_phone]['total_connections'] += 1
            phone_summary[b_phone]['unique_sources'].add(source_ip)
            phone_summary[b_phone]['protocols_used'].add(rel['session']['protocol'])
            phone_summary[b_phone]['destination_ips'].add(b_ip)

        # Convert sets
        for ph in phone_summary:
            phone_summary[ph]['unique_sources'] = list(phone_summary[ph]['unique_sources'])
            phone_summary[ph]['protocols_used'] = list(phone_summary[ph]['protocols_used'])
            phone_summary[ph]['destination_ips'] = list(phone_summary[ph]['destination_ips'])
            phone_summary[ph]['unique_source_count'] = len(phone_summary[ph]['unique_sources'])

        return dict(phone_summary)
    
    def identify_suspicious_patterns(self) -> Dict:
        """Identify suspicious communication patterns"""
        if not self.relationships:
            self.extract_relationships()
        
        patterns = {
            'high_risk_connections': [],
            'port_scanning_suspects': [],
            'bulk_communicators': [],
            'late_night_activity': []
        }
        
        # High risk connections (risk_score > 0.7)
        for rel in self.relationships:
            if rel['risk_score'] > 0.7:
                patterns['high_risk_connections'].append({
                    'a_party': rel['a_party']['subscriber_id'],
                    'customer_name': rel['a_party']['customer_name'],
                    'b_party': rel['b_party']['destination_ip'],
                    'risk_score': rel['risk_score'],
                    'session_id': rel['session']['session_id']
                })
        
        # Analyze A-Party patterns
        a_party_data = self.get_a_party_summary()
        
        # Port scanning suspects (many unique destinations)
        for party_id, data in a_party_data.items():
            if data['unique_destination_count'] > 10:
                patterns['port_scanning_suspects'].append({
                    'subscriber_id': party_id,
                    'customer_name': data['customer_info']['name'],
                    'unique_destinations': data['unique_destination_count'],
                    'total_connections': data['total_connections']
                })
        
        # Bulk communicators (high connection count)
        for party_id, data in a_party_data.items():
            if data['total_connections'] > 20:
                patterns['bulk_communicators'].append({
                    'subscriber_id': party_id,
                    'customer_name': data['customer_info']['name'],
                    'total_connections': data['total_connections'],
                    'total_duration': data['total_duration']
                })
        
        # Late night activity
        for rel in self.relationships:
            start_time = rel['session']['start_time']
            if isinstance(start_time, str):
                hour_match = re.search(r'-(\d{2}):', start_time)
                if hour_match:
                    hour = int(hour_match.group(1))
                    if hour >= 22 or hour <= 5:
                        patterns['late_night_activity'].append({
                            'subscriber_id': rel['a_party']['subscriber_id'],
                            'customer_name': rel['a_party']['customer_name'],
                            'destination_ip': rel['b_party']['destination_ip'],
                            'start_time': start_time,
                            'duration': rel['session']['duration']
                        })
        
        return patterns
    
    def create_network_graph(self) -> nx.Graph:
        """Create network graph for visualization"""
        if not self.relationships:
            self.extract_relationships()
        
        G = nx.Graph()
        
        for rel in self.relationships:
            a_node = f"{rel['a_party']['subscriber_id']}"
            b_node = f"{rel['b_party']['destination_ip']}"
            
            # Add nodes with attributes
            G.add_node(a_node, 
                      node_type='a_party',
                      customer_name=rel['a_party']['customer_name'],
                      phone=rel['a_party']['phone'])
            
            G.add_node(b_node, 
                      node_type='b_party',
                      ip_category=rel['b_party']['ip_category'],
                      is_public=rel['b_party']['is_public_ip'])
            
            # Add edge with session information
            G.add_edge(a_node, b_node,
                      protocol=rel['session']['protocol'],
                      duration=rel['session']['duration'],
                      risk_score=rel['risk_score'],
                      relationship_type=rel['relationship_type'])
        
        return G
    
    def export_relationships(self, output_format='json') -> str:
        """Export relationships in specified format"""
        if not self.relationships:
            self.extract_relationships()
        
        if output_format == 'json':
            return json.dumps(self.relationships, indent=2, default=str)
        elif output_format == 'summary':
            return json.dumps({
                'a_party_summary': self.get_a_party_summary(),
                'b_party_summary': self.get_b_party_summary(),
                'b_party_phone_summary': self.get_b_party_phone_summary(),
                'suspicious_patterns': self.identify_suspicious_patterns()
            }, indent=2, default=str)
        else:
            raise ValueError("Supported formats: 'json', 'summary'")

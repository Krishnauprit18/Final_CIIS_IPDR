import pandas as pd
import networkx as nx
import numpy as np
from typing import Dict, List, Tuple, Optional, Set, Any
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns
from collections import defaultdict, Counter
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo
from datetime import datetime, timedelta
import base64
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')

class CommunicationMapper:
    """
    Advanced communication mapping system for visualizing relationships and patterns
    between phone numbers, IPs, and customers in IPDR data.
    """
    
    def __init__(self, data: pd.DataFrame):
        self.data = data.copy()
        self.phone_network = nx.Graph()
        self.ip_network = nx.Graph()
        self.customer_network = nx.Graph()
        self.combined_network = nx.MultiGraph()
        self.communication_tables = {}
        self.mapping_stats = {
            'total_communications': 0,
            'unique_phones': 0,
            'unique_ips': 0,
            'unique_customers': 0,
            'communication_pairs': 0
        }
        
        # Initialize networks
        self._build_communication_networks()
        
    def _build_communication_networks(self):
        """Build various network representations of communication data"""
        if self.data.empty:
            return
            
        # Phone-based network (using phone numbers as nodes)
        self._build_phone_network()
        
        # IP-based network (using IP addresses as nodes)
        self._build_ip_network()
        
        # Customer-based network (using customer names/IDs as nodes)
        self._build_customer_network()
        
        # Combined multi-layer network
        self._build_combined_network()
        
        # Update statistics
        self._update_mapping_stats()
    
    def _build_phone_network(self):
        """Build network based on phone number communications"""
        self.phone_network = nx.Graph()
        
        for _, row in self.data.iterrows():
            phone = row['Phone']
            # Since we have source and destination IPs but not phone-to-phone direct communications,
            # we'll create connections based on shared infrastructure/timing
            
            # Add phone as node with attributes
            if pd.notna(phone) and phone != '+910000000000':
                self.phone_network.add_node(phone, 
                                          customer_name=row['CustName'],
                                          subscriber_id=row['SubscriberID'],
                                          source_ip=row['Source IP'],
                                          destination_ip=row['Destination IP'],
                                          location=(row['Latitude'], row['Longitude']),
                                          address=row['Address'],
                                          email=row['Email'],
                                          protocol=row['Protocol'],
                                          duration=row['Duration'],
                                          timestamp=row['Start Time'])
        
        # Create edges based on temporal proximity or shared destinations
        self._create_phone_connections()
    
    def _build_ip_network(self):
        """Build network based on IP address communications"""
        self.ip_network = nx.DiGraph()  # Directed for source -> destination
        
        for _, row in self.data.iterrows():
            source_ip = row['Source IP']
            dest_ip = row['Destination IP']
            
            # Add source IP node
            self.ip_network.add_node(source_ip,
                                   node_type='source',
                                   phone=row['Phone'],
                                   customer_name=row['CustName'],
                                   location=(row['Latitude'], row['Longitude']),
                                   device=row['Device'])
            
            # Add destination IP node
            self.ip_network.add_node(dest_ip,
                                   node_type='destination')
            
            # Add communication edge
            if self.ip_network.has_edge(source_ip, dest_ip):
                # Update existing edge
                self.ip_network[source_ip][dest_ip]['weight'] += 1
                self.ip_network[source_ip][dest_ip]['total_duration'] += row['Duration']
                self.ip_network[source_ip][dest_ip]['protocols'].add(row['Protocol'])
                self.ip_network[source_ip][dest_ip]['ports'].add(row['Destination Port'])
            else:
                # Create new edge
                self.ip_network.add_edge(source_ip, dest_ip,
                                       weight=1,
                                       total_duration=row['Duration'],
                                       protocols={row['Protocol']},
                                       ports={row['Destination Port']},
                                       start_time=row['Start Time'],
                                       end_time=row['End Time'])
    
    def _build_customer_network(self):
        """Build network based on customer communications"""
        self.customer_network = nx.Graph()
        
        # Group communications by customer
        customer_comms = self.data.groupby('SubscriberID').agg({
            'CustName': 'first',
            'Phone': 'first',
            'Address': 'first',
            'Email': 'first',
            'Destination IP': 'nunique',
            'Duration': 'sum',
            'Protocol': lambda x: list(set(x)),
            'Latitude': 'first',
            'Longitude': 'first'
        }).reset_index()
        
        # Add customer nodes
        for _, customer in customer_comms.iterrows():
            self.customer_network.add_node(customer['SubscriberID'],
                                         customer_name=customer['CustName'],
                                         phone=customer['Phone'],
                                         address=customer['Address'],
                                         email=customer['Email'],
                                         unique_destinations=customer['Destination IP'],
                                         total_duration=customer['Duration'],
                                         protocols=customer['Protocol'],
                                         location=(customer['Latitude'], customer['Longitude']))
        
        # Create edges based on shared communication patterns
        self._create_customer_connections(customer_comms)
    
    def _build_combined_network(self):
        """Build multi-layer network combining phones, IPs, and customers"""
        self.combined_network = nx.MultiGraph()
        
        for _, row in self.data.iterrows():
            phone = row['Phone']
            source_ip = row['Source IP']
            dest_ip = row['Destination IP']
            customer_id = row['SubscriberID']
            
            # Add nodes with different types
            self.combined_network.add_node(f"phone_{phone}", 
                                         node_type='phone',
                                         label=phone,
                                         customer_name=row['CustName'])
            
            self.combined_network.add_node(f"customer_{customer_id}",
                                         node_type='customer',
                                         label=row['CustName'],
                                         phone=phone)
            
            self.combined_network.add_node(f"source_ip_{source_ip}",
                                         node_type='source_ip',
                                         label=source_ip)
            
            self.combined_network.add_node(f"dest_ip_{dest_ip}",
                                         node_type='dest_ip',
                                         label=dest_ip)
            
            # Add edges between related entities
            self.combined_network.add_edge(f"customer_{customer_id}", f"phone_{phone}", 
                                         edge_type='owns')
            self.combined_network.add_edge(f"phone_{phone}", f"source_ip_{source_ip}",
                                         edge_type='uses')
            self.combined_network.add_edge(f"source_ip_{source_ip}", f"dest_ip_{dest_ip}",
                                         edge_type='communicates',
                                         protocol=row['Protocol'],
                                         duration=row['Duration'])
    
    def _create_phone_connections(self):
        """Create connections between phones based on communication patterns"""
        # Group by time windows to find potential phone-to-phone connections
        time_window = timedelta(minutes=30)  # 30-minute window
        
        phone_times = {}
        for phone in self.phone_network.nodes():
            phone_data = [(node, data['timestamp']) for node, data in self.phone_network.nodes(data=True) 
                         if node == phone]
            if phone_data:
                phone_times[phone] = phone_data[0][1]
        
        # Create edges between phones that communicated within time window
        phones = list(phone_times.keys())
        for i, phone1 in enumerate(phones):
            for phone2 in phones[i+1:]:
                try:
                    time1 = datetime.strptime(phone_times[phone1], '%Y-%m-%d-%H:%M:%S')
                    time2 = datetime.strptime(phone_times[phone2], '%Y-%m-%d-%H:%M:%S')
                    
                    if abs(time1 - time2) <= time_window:
                        self.phone_network.add_edge(phone1, phone2, 
                                                   connection_type='temporal_proximity',
                                                   time_diff=abs(time1 - time2).total_seconds())
                except:
                    continue
    
    def _create_customer_connections(self, customer_comms):
        """Create connections between customers based on shared patterns"""
        customers = customer_comms['SubscriberID'].tolist()
        
        for i, customer1 in enumerate(customers):
            for customer2 in customers[i+1:]:
                # Connect customers from same city
                addr1 = customer_comms[customer_comms['SubscriberID'] == customer1]['Address'].iloc[0]
                addr2 = customer_comms[customer_comms['SubscriberID'] == customer2]['Address'].iloc[0]
                
                if pd.notna(addr1) and pd.notna(addr2):
                    # Extract city names
                    city1 = addr1.split(',')[-2].strip() if ',' in addr1 else ''
                    city2 = addr2.split(',')[-2].strip() if ',' in addr2 else ''
                    
                    if city1 == city2 and city1:
                        self.customer_network.add_edge(customer1, customer2,
                                                     connection_type='same_city',
                                                     city=city1)
    
    def create_phone_connection_table(self) -> pd.DataFrame:
        """Create table showing phone number connections and patterns"""
        connections = []
        
        for phone in self.phone_network.nodes():
            node_data = self.phone_network.nodes[phone]
            
            # Get connection count
            connection_count = len(list(self.phone_network.neighbors(phone)))
            
            connections.append({
                'Phone': phone,
                'Customer_Name': node_data.get('customer_name', 'Unknown'),
                'Subscriber_ID': node_data.get('subscriber_id', 'Unknown'),
                'Source_IP': node_data.get('source_ip', 'Unknown'),
                'Destination_IP': node_data.get('destination_ip', 'Unknown'),
                'Address': node_data.get('address', 'Unknown'),
                'Email': node_data.get('email', 'Unknown'),
                'Protocol': node_data.get('protocol', 'Unknown'),
                'Duration': node_data.get('duration', 0),
                'Connections': connection_count,
                'Latitude': node_data.get('location', (0, 0))[0],
                'Longitude': node_data.get('location', (0, 0))[1]
            })
        
        return pd.DataFrame(connections)
    
    def create_ip_connection_table(self) -> pd.DataFrame:
        """Create table showing IP address connections and communication patterns"""
        connections = []
        
        for source, dest, data in self.ip_network.edges(data=True):
            connections.append({
                'Source_IP': source,
                'Destination_IP': dest,
                'Communication_Count': data.get('weight', 1),
                'Total_Duration': data.get('total_duration', 0),
                'Protocols': ', '.join(data.get('protocols', set())),
                'Destination_Ports': ', '.join(map(str, data.get('ports', set()))),
                'First_Contact': data.get('start_time', 'Unknown'),
                'Last_Contact': data.get('end_time', 'Unknown')
            })
        
        return pd.DataFrame(connections)
    
    def create_customer_connection_table(self) -> pd.DataFrame:
        """Create table showing customer connections and relationships"""
        connections = []
        
        for customer in self.customer_network.nodes():
            node_data = self.customer_network.nodes[customer]
            neighbors = list(self.customer_network.neighbors(customer))
            
            connections.append({
                'Subscriber_ID': customer,
                'Customer_Name': node_data.get('customer_name', 'Unknown'),
                'Phone': node_data.get('phone', 'Unknown'),
                'Address': node_data.get('address', 'Unknown'),
                'Email': node_data.get('email', 'Unknown'),
                'Unique_Destinations': node_data.get('unique_destinations', 0),
                'Total_Duration': node_data.get('total_duration', 0),
                'Protocols': ', '.join(node_data.get('protocols', [])),
                'Connected_Customers': len(neighbors),
                'Connected_To': ', '.join(neighbors) if neighbors else 'None',
                'Latitude': node_data.get('location', (0, 0))[0],
                'Longitude': node_data.get('location', (0, 0))[1]
            })
        
        return pd.DataFrame(connections)
    
    def create_communication_matrix(self, matrix_type='phone') -> pd.DataFrame:
        """Create adjacency matrix for communication relationships"""
        if matrix_type == 'phone':
            network = self.phone_network
            nodes = list(network.nodes())
        elif matrix_type == 'ip':
            network = self.ip_network
            nodes = list(network.nodes())
        elif matrix_type == 'customer':
            network = self.customer_network
            nodes = list(network.nodes())
        else:
            raise ValueError("matrix_type must be 'phone', 'ip', or 'customer'")
        
        # Create adjacency matrix
        matrix = pd.DataFrame(0, index=nodes, columns=nodes)
        
        for source, target, data in network.edges(data=True):
            weight = data.get('weight', 1) if 'weight' in data else 1
            matrix.loc[source, target] = weight
            if not network.is_directed():
                matrix.loc[target, source] = weight
        
        return matrix
    
    def generate_network_visualization(self, network_type='combined', 
                                     layout='spring', save_path=None) -> str:
        """Generate network visualization using matplotlib"""
        if network_type == 'phone':
            G = self.phone_network
            title = 'Phone Number Communication Network'
        elif network_type == 'ip':
            G = self.ip_network
            title = 'IP Address Communication Network'
        elif network_type == 'customer':
            G = self.customer_network
            title = 'Customer Communication Network'
        elif network_type == 'combined':
            G = self.combined_network
            title = 'Combined Communication Network'
        else:
            raise ValueError("network_type must be 'phone', 'ip', 'customer', or 'combined'")
        
        plt.figure(figsize=(16, 12))
        
        # Choose layout
        if layout == 'spring':
            pos = nx.spring_layout(G, k=1, iterations=50)
        elif layout == 'circular':
            pos = nx.circular_layout(G)
        elif layout == 'kamada_kawai':
            pos = nx.kamada_kawai_layout(G)
        else:
            pos = nx.spring_layout(G)
        
        # Draw network based on type
        if network_type == 'combined':
            self._draw_combined_network(G, pos)
        else:
            self._draw_single_network(G, pos, network_type)
        
        plt.title(title, fontsize=16, fontweight='bold')
        plt.axis('off')
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            return save_path
        else:
            # Save to base64 string
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            return f"data:image/png;base64,{image_base64}"
    
    def _draw_single_network(self, G, pos, network_type):
        """Draw single-layer network"""
        # Node colors and sizes
        if network_type == 'phone':
            node_colors = ['lightblue' for _ in G.nodes()]
            node_sizes = [300 + G.degree(node) * 50 for node in G.nodes()]
        elif network_type == 'ip':
            node_colors = []
            for node in G.nodes():
                if G.nodes[node].get('node_type') == 'source':
                    node_colors.append('lightgreen')
                else:
                    node_colors.append('lightcoral')
            node_sizes = [200 + G.degree(node) * 30 for node in G.nodes()]
        else:  # customer
            node_colors = ['lightyellow' for _ in G.nodes()]
            node_sizes = [400 + G.degree(node) * 100 for node in G.nodes()]
        
        # Draw edges
        nx.draw_networkx_edges(G, pos, alpha=0.6, edge_color='gray', width=1)
        
        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, 
                              node_size=node_sizes, alpha=0.8)
        
        # Draw labels
        labels = {}
        for node in G.nodes():
            if network_type == 'phone':
                labels[node] = node[-4:]  # Last 4 digits
            elif network_type == 'ip':
                labels[node] = node.split('.')[-1]  # Last octet
            else:  # customer
                name = G.nodes[node].get('customer_name', str(node))
                labels[node] = name[:8] if len(name) > 8 else name
        
        nx.draw_networkx_labels(G, pos, labels, font_size=8)
    
    def _draw_combined_network(self, G, pos):
        """Draw multi-layer combined network with different node types"""
        # Define colors for different node types
        node_colors = []
        node_sizes = []
        
        for node in G.nodes():
            node_type = G.nodes[node].get('node_type', 'unknown')
            if node_type == 'phone':
                node_colors.append('lightblue')
                node_sizes.append(300)
            elif node_type == 'customer':
                node_colors.append('lightgreen')
                node_sizes.append(400)
            elif node_type == 'source_ip':
                node_colors.append('orange')
                node_sizes.append(200)
            elif node_type == 'dest_ip':
                node_colors.append('lightcoral')
                node_sizes.append(150)
            else:
                node_colors.append('gray')
                node_sizes.append(100)
        
        # Draw edges with different colors based on edge type
        edge_colors = []
        for u, v, data in G.edges(data=True):
            edge_type = data.get('edge_type', 'unknown')
            if edge_type == 'owns':
                edge_colors.append('blue')
            elif edge_type == 'uses':
                edge_colors.append('green')
            elif edge_type == 'communicates':
                edge_colors.append('red')
            else:
                edge_colors.append('gray')
        
        # Draw network
        nx.draw_networkx_edges(G, pos, edge_color=edge_colors, alpha=0.6, width=1)
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, 
                              node_size=node_sizes, alpha=0.8)
        
        # Create legend
        legend_elements = [
            mpatches.Patch(color='lightblue', label='Phone Numbers'),
            mpatches.Patch(color='lightgreen', label='Customers'),
            mpatches.Patch(color='orange', label='Source IPs'),
            mpatches.Patch(color='lightcoral', label='Destination IPs')
        ]
        plt.legend(handles=legend_elements, loc='upper right')
    
    def generate_interactive_visualization(self, network_type='combined') -> str:
        """Generate interactive network visualization using Plotly"""
        if network_type == 'phone':
            G = self.phone_network
            title = 'Interactive Phone Communication Network'
        elif network_type == 'ip':
            G = self.ip_network
            title = 'Interactive IP Communication Network'
        elif network_type == 'customer':
            G = self.customer_network
            title = 'Interactive Customer Network'
        elif network_type == 'combined':
            G = self.combined_network
            title = 'Interactive Combined Communication Network'
        else:
            raise ValueError("network_type must be 'phone', 'ip', 'customer', or 'combined'")
        
        # Generate layout
        pos = nx.spring_layout(G, k=1, iterations=50)
        
        # Extract edge coordinates
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        # Create edge trace
        edge_trace = go.Scatter(x=edge_x, y=edge_y,
                              line=dict(width=0.5, color='#888'),
                              hoverinfo='none',
                              mode='lines')
        
        # Extract node coordinates and info
        node_x = []
        node_y = []
        node_info = []
        node_colors = []
        
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            # Node info for hover
            node_data = G.nodes[node]
            if network_type == 'combined':
                node_type = node_data.get('node_type', 'unknown')
                label = node_data.get('label', str(node))
                info = f"Type: {node_type}<br>Label: {label}"
                # Color by node type
                if node_type == 'phone':
                    node_colors.append('blue')
                elif node_type == 'customer':
                    node_colors.append('green')
                elif node_type == 'source_ip':
                    node_colors.append('orange')
                elif node_type == 'dest_ip':
                    node_colors.append('red')
                else:
                    node_colors.append('gray')
            else:
                info = f"Node: {node}<br>Connections: {G.degree(node)}"
                node_colors.append('lightblue')
            
            node_info.append(info)
        
        # Create node trace
        node_trace = go.Scatter(x=node_x, y=node_y,
                              mode='markers+text',
                              hoverinfo='text',
                              text=node_info,
                              marker=dict(size=10,
                                        color=node_colors,
                                        line=dict(width=2)))
        
        # Create figure
        fig = go.Figure(data=[edge_trace, node_trace],
                       layout=go.Layout(
                          title=title,
                          titlefont_size=16,
                          showlegend=False,
                          hovermode='closest',
                          margin=dict(b=20,l=5,r=5,t=40),
                          annotations=[ dict(
                              text="Interactive network visualization - hover over nodes for details",
                              showarrow=False,
                              xref="paper", yref="paper",
                              x=0.005, y=-0.002 ) ],
                          xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                          yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))
        
        return fig.to_html(include_plotlyjs='cdn')
    
    def create_geographic_visualization(self) -> str:
        """Create geographic visualization of communication patterns"""
        # Extract geographic data
        geo_data = []
        for _, row in self.data.iterrows():
            geo_data.append({
                'lat': row['Latitude'],
                'lon': row['Longitude'],
                'customer': row['CustName'],
                'phone': row['Phone'],
                'address': row['Address'],
                'destination_ip': row['Destination IP'],
                'protocol': row['Protocol'],
                'duration': row['Duration']
            })
        
        geo_df = pd.DataFrame(geo_data)
        
        # Create map
        fig = px.scatter_mapbox(geo_df, lat='lat', lon='lon',
                               hover_name='customer',
                               hover_data=['phone', 'address', 'protocol', 'duration'],
                               color='protocol',
                               size='duration',
                               color_continuous_scale='viridis',
                               zoom=5,
                               height=600)
        
        fig.update_layout(mapbox_style='open-street-map',
                         title='Geographic Distribution of Communications')
        
        return fig.to_html(include_plotlyjs='cdn')
    
    def generate_communication_timeline(self) -> str:
        """Generate timeline visualization of communication patterns"""
        # Prepare timeline data
        timeline_data = self.data.copy()
        timeline_data['Start Time'] = pd.to_datetime(timeline_data['Start Time'], 
                                                    format='%Y-%m-%d-%H:%M:%S')
        timeline_data['Hour'] = timeline_data['Start Time'].dt.hour
        timeline_data['Date'] = timeline_data['Start Time'].dt.date
        
        # Hourly communication patterns
        hourly_stats = timeline_data.groupby('Hour').agg({
            'Protocol': 'count',
            'Duration': 'sum'
        }).rename(columns={'Protocol': 'Communication_Count'})
        
        # Create timeline visualization
        fig = make_subplots(rows=2, cols=1,
                          subplot_titles=('Communications by Hour of Day', 
                                        'Total Duration by Hour'))
        
        # Communication count by hour
        fig.add_trace(
            go.Bar(x=hourly_stats.index, y=hourly_stats['Communication_Count'],
                  name='Communication Count',
                  marker_color='lightblue'),
            row=1, col=1
        )
        
        # Duration by hour
        fig.add_trace(
            go.Bar(x=hourly_stats.index, y=hourly_stats['Duration'],
                  name='Total Duration (seconds)',
                  marker_color='lightcoral'),
            row=2, col=1
        )
        
        fig.update_layout(height=600, title_text="Communication Timeline Analysis")
        fig.update_xaxes(title_text="Hour of Day")
        
        return fig.to_html(include_plotlyjs='cdn')
    
    def get_communication_statistics(self) -> Dict:
        """Get comprehensive statistics about communication patterns"""
        stats = {
            'network_stats': {
                'phone_network': {
                    'nodes': self.phone_network.number_of_nodes(),
                    'edges': self.phone_network.number_of_edges(),
                    'density': nx.density(self.phone_network),
                    'connected_components': nx.number_connected_components(self.phone_network)
                },
                'ip_network': {
                    'nodes': self.ip_network.number_of_nodes(),
                    'edges': self.ip_network.number_of_edges(),
                    'density': nx.density(self.ip_network)
                },
                'customer_network': {
                    'nodes': self.customer_network.number_of_nodes(),
                    'edges': self.customer_network.number_of_edges(),
                    'density': nx.density(self.customer_network),
                    'connected_components': nx.number_connected_components(self.customer_network)
                }
            },
            'communication_patterns': {
                'total_communications': len(self.data),
                'unique_phones': self.data['Phone'].nunique(),
                'unique_source_ips': self.data['Source IP'].nunique(),
                'unique_destination_ips': self.data['Destination IP'].nunique(),
                'unique_customers': self.data['SubscriberID'].nunique(),
                'protocol_distribution': self.data['Protocol'].value_counts().to_dict(),
                'average_duration': self.data['Duration'].mean(),
                'total_duration': self.data['Duration'].sum()
            },
            'geographic_distribution': {
                'unique_locations': self.data[['Latitude', 'Longitude']].drop_duplicates().shape[0],
                'cities': self._extract_cities_from_addresses()
            }
        }
        
        return stats
    
    def _extract_cities_from_addresses(self) -> Dict:
        """Extract city distribution from addresses"""
        cities = []
        for address in self.data['Address'].dropna():
            if ',' in address:
                city = address.split(',')[-2].strip()
                cities.append(city)
        
        return Counter(cities)
    
    def _update_mapping_stats(self):
        """Update internal mapping statistics"""
        self.mapping_stats = {
            'total_communications': len(self.data),
            'unique_phones': self.data['Phone'].nunique(),
            'unique_ips': self.data['Source IP'].nunique() + self.data['Destination IP'].nunique(),
            'unique_customers': self.data['SubscriberID'].nunique(),
            'communication_pairs': self.ip_network.number_of_edges()
        }
    
    def export_all_tables(self) -> Dict[str, pd.DataFrame]:
        """Export all communication tables"""
        return {
            'phone_connections': self.create_phone_connection_table(),
            'ip_connections': self.create_ip_connection_table(),
            'customer_connections': self.create_customer_connection_table(),
            'phone_matrix': self.create_communication_matrix('phone'),
            'ip_matrix': self.create_communication_matrix('ip'),
            'customer_matrix': self.create_communication_matrix('customer')
        }
    
    def get_mapping_stats(self) -> Dict:
        """Get current mapping statistics"""
        return self.mapping_stats.copy()
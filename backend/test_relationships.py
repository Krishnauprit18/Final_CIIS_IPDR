#!/usr/bin/env python3
"""
Test script for relationship extraction functionality with synthetic.csv
"""

import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from relationship_extractor import RelationshipExtractor

def test_relationship_extraction():
    """Test the relationship extraction with synthetic.csv data"""
    
    # Load synthetic.csv
    csv_path = "/home/krishna/Music/CIIS (Part 2)/Scenario A1-ARFF/synthetic.csv"
    
    try:
        print("Loading synthetic.csv...")
        data = pd.read_csv(csv_path)
        print(f"Loaded {len(data)} records")
        print(f"Columns: {list(data.columns)}")
        
        # Initialize relationship extractor
        print("\nInitializing RelationshipExtractor...")
        extractor = RelationshipExtractor(data)
        
        # Test relationship extraction
        print("\nExtracting relationships...")
        relationships = extractor.extract_relationships()
        print(f"Extracted {len(relationships)} relationships")
        
        # Test first relationship details
        if relationships:
            print("\nFirst relationship details:")
            first_rel = relationships[0]
            print(f"A-Party Customer: {first_rel['a_party']['customer_name']}")
            print(f"A-Party Phone: {first_rel['a_party']['phone']}")
            print(f"A-Party Source IP: {first_rel['a_party']['source_ip']}")
            print(f"B-Party Destination IP: {first_rel['b_party']['destination_ip']}")
            print(f"B-Party is Public IP: {first_rel['b_party']['is_public_ip']}")
            print(f"Relationship Type: {first_rel['relationship_type']}")
            print(f"Risk Score: {first_rel['risk_score']}")
        
        # Test A-Party summary
        print("\nGenerating A-Party summary...")
        a_party_summary = extractor.get_a_party_summary()
        print(f"Found {len(a_party_summary)} unique A-Party subscribers")
        
        # Show top 3 A-Party communicators
        sorted_a_parties = sorted(a_party_summary.items(), 
                                key=lambda x: x[1]['total_connections'], 
                                reverse=True)[:3]
        print("\nTop 3 A-Party communicators:")
        for party_id, data in sorted_a_parties:
            print(f"  {party_id}: {data['customer_info']['name']} - {data['total_connections']} connections")
        
        # Test B-Party summary
        print("\nGenerating B-Party summary...")
        b_party_summary = extractor.get_b_party_summary()
        print(f"Found {len(b_party_summary)} unique B-Party destinations")
        
        # Show top 3 B-Party destinations
        sorted_b_parties = sorted(b_party_summary.items(), 
                                key=lambda x: x[1]['total_connections'], 
                                reverse=True)[:3]
        print("\nTop 3 B-Party destinations:")
        for ip, data in sorted_b_parties:
            print(f"  {ip}: {data['total_connections']} connections, Public: {data['is_public']}")
        
        # Test suspicious patterns
        print("\nIdentifying suspicious patterns...")
        patterns = extractor.identify_suspicious_patterns()
        print(f"High risk connections: {len(patterns['high_risk_connections'])}")
        print(f"Port scanning suspects: {len(patterns['port_scanning_suspects'])}")
        print(f"Bulk communicators: {len(patterns['bulk_communicators'])}")
        print(f"Late night activity: {len(patterns['late_night_activity'])}")
        
        if patterns['high_risk_connections']:
            print("\nHigh risk connections:")
            for conn in patterns['high_risk_connections'][:3]:
                print(f"  {conn['customer_name']} -> {conn['b_party']} (Risk: {conn['risk_score']:.2f})")
        
        # Test network graph creation
        print("\nCreating network graph...")
        graph = extractor.create_network_graph()
        print(f"Graph created with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
        
        print("\n✅ All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_relationship_extraction()
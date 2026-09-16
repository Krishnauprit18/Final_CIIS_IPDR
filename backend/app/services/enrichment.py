import os
import csv
from typing import Optional, Dict
from ipaddress import ip_address, ip_network


class IPEntityEnricher:
    """
    Offline-friendly IP enricher. Looks up ASN/Org/Country from a local CSV cache if present.
    CSV format: ip,asn,org,country
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.cache: Dict[str, Dict[str, str]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        path = os.path.join(self.base_dir, "enrichment", "ip_enrichment.csv")
        if not os.path.exists(path):
            return
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ip = str(row.get("ip", "")).strip()
                    if ip:
                        self.cache[ip] = {
                            "asn": str(row.get("asn", "")).strip(),
                            "org": str(row.get("org", "")).strip(),
                            "country": str(row.get("country", "")).strip(),
                        }
        except Exception:
            # If cache fails to load, keep empty
            self.cache = {}

    def enrich_ip(self, ip_str: str) -> Dict[str, Optional[str]]:
        ip_s = str(ip_str or "").strip()
        info = {
            "ip": ip_s,
            "asn": None,
            "org": None,
            "country": None,
            "is_public": None,
            "category": None,
        }
        try:
            ip_obj = ip_address(ip_s)
            # Determine category/public
            category = "public"
            if ip_obj.is_private:
                category = "private"
            elif ip_obj.is_loopback:
                category = "loopback"
            elif ip_obj.is_multicast:
                category = "multicast"
            elif ip_obj.is_link_local:
                category = "link_local"
            elif ip_obj.is_reserved:
                category = "reserved"
            # Special ranges to treat as non-public
            special_blocks = [
                "100.64.0.0/10",  # CGNAT
                "198.18.0.0/15",  # Benchmark
                "192.0.0.0/24",   # Protocol assignments subset
                "192.0.2.0/24",   # TEST-NET-1
                "198.51.100.0/24",# TEST-NET-2
                "203.0.113.0/24", # TEST-NET-3
                "240.0.0.0/4",    # Reserved
            ]
            if any(ip_obj in ip_network(c) for c in special_blocks):
                category = "special"
            info["category"] = category
            info["is_public"] = (category == "public")
        except Exception:
            info["category"] = "invalid"
            info["is_public"] = False

        # Cache lookup
        if ip_s in self.cache:
            match = self.cache[ip_s]
            info.update({
                "asn": match.get("asn") or None,
                "org": match.get("org") or None,
                "country": match.get("country") or None,
            })
        return info


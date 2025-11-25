"""
IP Filtering module for ProxyOX
Supports blacklist and whitelist with persistence
"""
import json
import logging
from pathlib import Path
from typing import Set, Dict
import ipaddress

logger = logging.getLogger("ip_filter")

class IPFilter:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.blacklist_file = self.data_dir / "blacklist.json"
        self.whitelist_file = self.data_dir / "whitelist.json"
        
        self.blacklist: Set[str] = set()
        self.whitelist: Set[str] = set()
        self.blocked_count: Dict[str, int] = {}  # Compteur de blocages par IP
        
        self._load()
    
    def _load(self):
        """Charge les listes depuis les fichiers"""
        if self.blacklist_file.exists():
            try:
                with open(self.blacklist_file, 'r') as f:
                    data = json.load(f)
                    self.blacklist = set(data.get('ips', []))
                    self.blocked_count = data.get('blocked_count', {})
                logger.info(f"Loaded {len(self.blacklist)} IPs from blacklist")
            except Exception as e:
                logger.error(f"Failed to load blacklist: {e}")
        
        if self.whitelist_file.exists():
            try:
                with open(self.whitelist_file, 'r') as f:
                    data = json.load(f)
                    self.whitelist = set(data.get('ips', []))
                logger.info(f"Loaded {len(self.whitelist)} IPs from whitelist")
            except Exception as e:
                logger.error(f"Failed to load whitelist: {e}")
    
    def _save_blacklist(self):
        """Sauvegarde la blacklist"""
        try:
            with open(self.blacklist_file, 'w') as f:
                json.dump({
                    'ips': list(self.blacklist),
                    'blocked_count': self.blocked_count
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save blacklist: {e}")
    
    def _save_whitelist(self):
        """Sauvegarde la whitelist"""
        try:
            with open(self.whitelist_file, 'w') as f:
                json.dump({
                    'ips': list(self.whitelist)
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save whitelist: {e}")
    
    def is_allowed(self, ip: str) -> bool:
        """
        Vérifie si une IP est autorisée
        Règles:
        1. Si whitelist non vide: seules les IPs whitelistées sont autorisées
        2. Sinon: toutes les IPs sauf celles blacklistées sont autorisées
        """
        # Normaliser l'IP (enlever le port si présent)
        if isinstance(ip, tuple):
            ip = ip[0]
        
        # Si whitelist active, seules ces IPs passent
        if self.whitelist:
            return ip in self.whitelist
        
        # Sinon, tout passe sauf blacklist
        if ip in self.blacklist:
            self.blocked_count[ip] = self.blocked_count.get(ip, 0) + 1
            return False
        
        return True
    
    def add_to_blacklist(self, ip: str) -> bool:
        """Ajoute une IP à la blacklist"""
        try:
            # Valider l'IP
            ipaddress.ip_address(ip)
            self.blacklist.add(ip)
            self._save_blacklist()
            logger.info(f"Added {ip} to blacklist")
            return True
        except ValueError:
            logger.error(f"Invalid IP address: {ip}")
            return False
    
    def remove_from_blacklist(self, ip: str) -> bool:
        """Retire une IP de la blacklist"""
        if ip in self.blacklist:
            self.blacklist.remove(ip)
            if ip in self.blocked_count:
                del self.blocked_count[ip]
            self._save_blacklist()
            logger.info(f"Removed {ip} from blacklist")
            return True
        return False
    
    def add_to_whitelist(self, ip: str) -> bool:
        """Ajoute une IP à la whitelist"""
        try:
            # Valider l'IP
            ipaddress.ip_address(ip)
            self.whitelist.add(ip)
            self._save_whitelist()
            logger.info(f"Added {ip} to whitelist")
            return True
        except ValueError:
            logger.error(f"Invalid IP address: {ip}")
            return False
    
    def remove_from_whitelist(self, ip: str) -> bool:
        """Retire une IP de la whitelist"""
        if ip in self.whitelist:
            self.whitelist.remove(ip)
            self._save_whitelist()
            logger.info(f"Removed {ip} from whitelist")
            return True
        return False
    
    def clear_blacklist(self):
        """Vide la blacklist"""
        self.blacklist.clear()
        self.blocked_count.clear()
        self._save_blacklist()
        logger.info("Cleared blacklist")
    
    def clear_whitelist(self):
        """Vide la whitelist"""
        self.whitelist.clear()
        self._save_whitelist()
        logger.info("Cleared whitelist")
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques de filtrage"""
        return {
            'blacklist': {
                'count': len(self.blacklist),
                'ips': list(self.blacklist)
            },
            'whitelist': {
                'count': len(self.whitelist),
                'ips': list(self.whitelist)
            },
            'blocked_count': self.blocked_count,
            'total_blocked': sum(self.blocked_count.values())
        }

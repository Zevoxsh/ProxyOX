#!/usr/bin/env python3
"""
ProxyOX Configuration Checker
Validates the config.yaml file for syntax and logical errors
"""
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any

class ConfigChecker:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config: Dict[str, Any] = {}
        
    def check(self) -> bool:
        """Run all checks and return True if config is valid"""
        print(f"🔍 Checking configuration file: {self.config_path}")
        print("=" * 60)
        
        # Check file exists
        if not self._check_file_exists():
            return False
        
        # Parse YAML
        if not self._parse_yaml():
            return False
        
        # Validate structure
        self._validate_structure()
        self._validate_global_config()
        self._validate_frontends()
        self._validate_backends()
        self._validate_references()
        self._validate_ports()
        
        # Print results
        self._print_results()
        
        return len(self.errors) == 0
    
    def _check_file_exists(self) -> bool:
        """Check if config file exists"""
        if not self.config_path.exists():
            self.errors.append(f"Configuration file not found: {self.config_path}")
            return False
        return True
    
    def _parse_yaml(self) -> bool:
        """Parse YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            print("✅ YAML syntax is valid")
            return True
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parsing error: {e}")
            return False
    
    def _validate_structure(self):
        """Validate basic structure"""
        if not isinstance(self.config, dict):
            self.errors.append("Config must be a dictionary")
            return
        
        # Check required sections
        if "frontends" not in self.config:
            self.errors.append("Missing 'frontends' section")
        elif not isinstance(self.config["frontends"], list):
            self.errors.append("'frontends' must be a list")
        
        if "backends" not in self.config:
            self.errors.append("Missing 'backends' section")
        elif not isinstance(self.config["backends"], list):
            self.errors.append("'backends' must be a list")
    
    def _validate_global_config(self):
        """Validate global configuration"""
        if "global" not in self.config:
            self.warnings.append("No 'global' section found (using defaults)")
            return
        
        global_cfg = self.config["global"]
        
        # Check log level
        if "log-level" in global_cfg:
            valid_levels = ["debug", "info", "warning", "error", "critical"]
            if global_cfg["log-level"].lower() not in valid_levels:
                self.warnings.append(f"Invalid log-level: {global_cfg['log-level']} (valid: {valid_levels})")
        
        # Check numeric values
        if "timeout" in global_cfg:
            try:
                timeout = int(global_cfg["timeout"])
                if timeout <= 0:
                    self.warnings.append("timeout should be positive")
            except ValueError:
                self.errors.append("timeout must be a number")
        
        if "max-connections" in global_cfg:
            try:
                max_conn = int(global_cfg["max-connections"])
                if max_conn <= 0:
                    self.warnings.append("max-connections should be positive")
            except ValueError:
                self.errors.append("max-connections must be a number")
    
    def _validate_frontends(self):
        """Validate frontend configurations"""
        if "frontends" not in self.config:
            return
        
        frontend_names = set()
        
        for idx, fe in enumerate(self.config["frontends"]):
            context = f"Frontend #{idx + 1}"
            
            if not isinstance(fe, dict):
                self.errors.append(f"{context}: must be a dictionary")
                continue
            
            # Check required fields
            if "name" not in fe:
                self.warnings.append(f"{context}: missing 'name' (will use auto-generated)")
            else:
                if fe["name"] in frontend_names:
                    self.errors.append(f"{context}: duplicate name '{fe['name']}'")
                frontend_names.add(fe["name"])
                context = f"Frontend '{fe['name']}'"
            
            if "bind" not in fe:
                self.errors.append(f"{context}: missing 'bind' address")
            else:
                if not self._validate_bind_address(fe["bind"]):
                    self.errors.append(f"{context}: invalid bind format '{fe['bind']}' (expected host:port)")
            
            # Check mode
            if "mode" in fe:
                valid_modes = ["tcp", "udp", "http", "https"]
                if fe["mode"].lower() not in valid_modes:
                    self.errors.append(f"{context}: invalid mode '{fe['mode']}' (valid: {valid_modes})")
            else:
                self.warnings.append(f"{context}: no mode specified (defaulting to 'tcp')")
            
            # Check backend reference
            if "default_backend" not in fe and "domain_routes" not in fe:
                self.errors.append(f"{context}: must specify 'default_backend' or 'domain_routes'")
            
            # Validate domain routes if present
            if "domain_routes" in fe:
                if not isinstance(fe["domain_routes"], list):
                    self.errors.append(f"{context}: 'domain_routes' must be a list")
                else:
                    for route_idx, route in enumerate(fe["domain_routes"]):
                        if "domain" not in route:
                            self.errors.append(f"{context}, route #{route_idx + 1}: missing 'domain'")
                        if "backend" not in route:
                            self.errors.append(f"{context}, route #{route_idx + 1}: missing 'backend'")
            
            # Check TLS configuration
            if fe.get("tls", False):
                if "certfile" not in fe:
                    self.errors.append(f"{context}: TLS enabled but 'certfile' not specified")
                elif not Path(fe["certfile"]).exists():
                    self.warnings.append(f"{context}: certfile not found: {fe['certfile']}")
                
                if "keyfile" not in fe:
                    self.errors.append(f"{context}: TLS enabled but 'keyfile' not specified")
                elif not Path(fe["keyfile"]).exists():
                    self.warnings.append(f"{context}: keyfile not found: {fe['keyfile']}")
    
    def _validate_backends(self):
        """Validate backend configurations"""
        if "backends" not in self.config:
            return
        
        backend_names = set()
        
        for idx, be in enumerate(self.config["backends"]):
            context = f"Backend #{idx + 1}"
            
            if not isinstance(be, dict):
                self.errors.append(f"{context}: must be a dictionary")
                continue
            
            # Check name
            if "name" not in be:
                self.errors.append(f"{context}: missing 'name'")
                continue
            
            if be["name"] in backend_names:
                self.errors.append(f"{context}: duplicate name '{be['name']}'")
            backend_names.add(be["name"])
            context = f"Backend '{be['name']}'"
            
            # Check server
            if "server" not in be:
                self.errors.append(f"{context}: missing 'server' address")
            else:
                if not self._validate_bind_address(be["server"]):
                    self.errors.append(f"{context}: invalid server format '{be['server']}' (expected host:port)")
    
    def _validate_references(self):
        """Validate that frontend->backend references exist"""
        if "frontends" not in self.config or "backends" not in self.config:
            return
        
        # Build backend name set
        backend_names = {be["name"] for be in self.config["backends"] if "name" in be}
        
        # Check all frontend references
        for fe in self.config["frontends"]:
            fe_name = fe.get("name", "unnamed")
            
            # Check default backend
            if "default_backend" in fe:
                if fe["default_backend"] not in backend_names:
                    self.errors.append(
                        f"Frontend '{fe_name}': references non-existent backend '{fe['default_backend']}'"
                    )
            
            # Check domain routes
            if "domain_routes" in fe:
                for route in fe.get("domain_routes", []):
                    if "backend" in route and route["backend"] not in backend_names:
                        self.errors.append(
                            f"Frontend '{fe_name}': domain route references non-existent backend '{route['backend']}'"
                        )
    
    def _validate_ports(self):
        """Check for port conflicts"""
        if "frontends" not in self.config:
            return
        
        ports_used = {}
        
        for fe in self.config["frontends"]:
            if "bind" not in fe:
                continue
            
            try:
                host, port = fe["bind"].split(":")
                port = int(port)
                bind_key = f"{host}:{port}"
                
                if bind_key in ports_used:
                    self.errors.append(
                        f"Port conflict: {bind_key} used by both '{fe.get('name', 'unnamed')}' "
                        f"and '{ports_used[bind_key]}'"
                    )
                else:
                    ports_used[bind_key] = fe.get("name", "unnamed")
            except ValueError:
                pass  # Already caught in bind validation
    
    def _validate_bind_address(self, addr: str) -> bool:
        """Validate bind address format (host:port)"""
        if ":" not in addr:
            return False
        try:
            host, port = addr.rsplit(":", 1)
            port = int(port)
            return 1 <= port <= 65535
        except ValueError:
            return False
    
    def _print_results(self):
        """Print check results"""
        print("\n" + "=" * 60)
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   • {error}")
        
        print("\n" + "=" * 60)
        
        if len(self.errors) == 0:
            print("✅ Configuration is VALID!")
            if len(self.warnings) > 0:
                print(f"   (but has {len(self.warnings)} warning(s))")
        else:
            print(f"❌ Configuration has {len(self.errors)} error(s)")
            print("   Please fix the errors before starting ProxyOX")
        
        print("=" * 60)


def main():
    """Main entry point"""
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    
    checker = ConfigChecker(config_file)
    is_valid = checker.check()
    
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()

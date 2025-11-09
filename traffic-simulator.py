import httpx
import random
import time
import json
import logging
import sys
import os
import subprocess
import argparse
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""
    
    FORMATS = {
        logging.DEBUG: Colors.OKCYAN + "%(asctime)s - DEBUG: %(message)s" + Colors.ENDC,
        logging.INFO: Colors.OKGREEN + "%(asctime)s - INFO: %(message)s" + Colors.ENDC,
        logging.WARNING: Colors.WARNING + "%(asctime)s - WARN: %(message)s" + Colors.ENDC,
        logging.ERROR: Colors.FAIL + "%(asctime)s - ERROR: %(message)s" + Colors.ENDC,
        logging.CRITICAL: Colors.FAIL + Colors.BOLD + "%(asctime)s - CRITICAL: %(message)s" + Colors.ENDC,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        return formatter.format(record)

@dataclass
class SimulationStats:
    """Track detailed simulation statistics"""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    auth_errors: int = 0
    operation_counts: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        'pet': {'create': 0, 'update': 0, 'delete': 0, 'get': 0, 'query': 0},
        'user': {'create': 0, 'update': 0, 'delete': 0, 'get': 0, 'login': 0},
        'order': {'create': 0, 'get': 0, 'delete': 0, 'inventory': 0}
    })
    response_times: List[float] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

def setup_logging(debug: bool = False) -> logging.Logger:
    """Setup enhanced logging with color support"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()
    
    # File handler (no colors)
    file_handler = logging.FileHandler("petstore_simulator.log")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler (with colors)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(ColoredFormatter())
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def print_banner(config: Dict[str, Any]):
    """Print colorful startup banner"""
    banner = f"""
{Colors.HEADER}{Colors.BOLD}{'='*80}
   PETSTORE API TRAFFIC SIMULATOR v2.0
{'='*80}{Colors.ENDC}

{Colors.OKCYAN}Configuration:{Colors.ENDC}
  • API URL:            {Colors.BOLD}{config['url']}{Colors.ENDC}
  • Duration:           {Colors.BOLD}{config['duration']} minutes{Colors.ENDC}
  • Operations/minute:  {Colors.BOLD}{config['rate']}{Colors.ENDC}
  • Parallel threads:   {Colors.BOLD}{config.get('parallel', 1)}{Colors.ENDC}
  • Authentication:     {Colors.BOLD}{config['auth_method']}{Colors.ENDC}
  • Minimum Entities:   {Colors.BOLD}Pets: {config['min_pets']}, Users: {config['min_users']}, Orders: {config['min_orders']}{Colors.ENDC}

{Colors.OKGREEN}Initializing simulator...{Colors.ENDC}
{Colors.HEADER}{'='*80}{Colors.ENDC}
"""
    print(banner)

def generate_jwt_tokens(duration_minutes: int, token_dir: str = "petstore-api-keys/temp_tokens") -> List[str]:
    """Generate JWT tokens for test users"""
    os.makedirs(token_dir, exist_ok=True)
    
    # Find private key
    private_key_paths = [
        "private-key.pem",
        "petstore-api-keys/private-key.pem",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "petstore-api-keys/private-key.pem")
    ]
    
    private_key_path = None
    for path in private_key_paths:
        if os.path.exists(path):
            private_key_path = path
            logger.info(f"✓ Found private key at: {Colors.BOLD}{path}{Colors.ENDC}")
            break
    
    if not private_key_path:
        logger.error(f"{Colors.FAIL}✗ Private key not found!{Colors.ENDC}")
        logger.error("  Generate one at: https://mkjwk.org")
        sys.exit(1)
    
    # User configurations with varied expiration times
    base_expiration = duration_minutes * 60 + 60
    users = [
        {"username": "user1", "customer_type": "premium", "email": "user1@example.com", 
         "expiration": int(duration_minutes * 60 * 0.35)},  # Expires early
        {"username": "user2", "customer_type": "standard", "email": "user2@example.com",
         "expiration": int(duration_minutes * 60 * 0.5)},   # Expires halfway
        {"username": "user3", "customer_type": "free", "email": "user3@example.com",
         "expiration": base_expiration}  # Full duration
    ]
    
    # Find token generation script
    script_paths = [
        "petstore-api-keys/create_customer_token.py",
        "create_customer_token.py",
        os.path.join(os.path.dirname(__file__), "petstore-api-keys/create_customer_token.py"),
    ]
    
    script_path = None
    for path in script_paths:
        if os.path.exists(path):
            script_path = path
            break
    
    if not script_path:
        logger.error(f"{Colors.FAIL}✗ Token generation script not found!{Colors.ENDC}")
        sys.exit(1)
    
    token_files = []
    python_executables = ["python3", "python"]
    
    logger.info(f"\n{Colors.OKCYAN}Generating JWT tokens...{Colors.ENDC}")
    for user in users:
        success = False
        for python_exec in python_executables:
            try:
                cmd = [
                    python_exec, script_path,
                    "--username", user["username"],
                    "--customer-type", user["customer_type"],
                    "--email", user["email"],
                    "--expiration", str(user["expiration"]),
                    "--output-dir", token_dir
                ]
                
                if private_key_path != "private-key.pem":
                    cmd.extend(["--key-path", private_key_path])
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    continue
                
                # Find generated token file
                token_file = None
                for line in result.stdout.splitlines():
                    if "Token saved to:" in line:
                        token_file = line.split("Token saved to:")[1].strip()
                        break
                
                if not token_file:
                    potential_files = [f for f in os.listdir(token_dir) 
                                     if f.startswith(user["username"]) and f.endswith(".jwt")]
                    if potential_files:
                        token_file = os.path.join(token_dir, max(potential_files, 
                                         key=lambda f: os.path.getmtime(os.path.join(token_dir, f))))
                
                if token_file:
                    token_files.append(token_file)
                    logger.info(f"  {Colors.OKGREEN}✓{Colors.ENDC} Generated token for {Colors.BOLD}{user['username']}{Colors.ENDC} ({user['customer_type']})")
                    success = True
                    break
                
            except Exception as e:
                logger.debug(f"Failed with {python_exec}: {str(e)}")
        
        if not success:
            logger.error(f"  {Colors.FAIL}✗{Colors.ENDC} Failed to generate token for {user['username']}")
    
    if not token_files:
        logger.error(f"{Colors.FAIL}No tokens generated. Exiting.{Colors.ENDC}")
        sys.exit(1)
    
    logger.info(f"{Colors.OKGREEN}✓ Successfully generated {len(token_files)} tokens{Colors.ENDC}\n")
    return token_files

class PetstoreTrafficSimulator:
    """Enhanced Petstore API Traffic Simulator with realistic behavior"""
    
    def __init__(self, base_url: str, api_key: str, min_pets: int = 10, 
                 min_users: int = 5, min_orders: int = 3, jwt_token_files: List[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.min_pets = min_pets
        self.min_users = min_users
        self.min_orders = min_orders
        
        # Statistics tracker
        self.stats = SimulationStats()
        
        # Load JWT tokens
        self.jwt_tokens = []
        self.jwt_token_info = {}
        if jwt_token_files:
            for token_file in jwt_token_files:
                try:
                    with open(token_file, 'r') as f:
                        token = f.read().strip()
                        username = os.path.basename(token_file).split('_')[0]
                        self.jwt_tokens.append(token)
                        self.jwt_token_info[token] = {
                            'username': username,
                            'file': os.path.basename(token_file)
                        }
                except Exception as e:
                    logger.error(f"Failed to load token from {token_file}: {e}")
        
        if self.jwt_tokens:
            logger.info(f"✓ Loaded {Colors.BOLD}{len(self.jwt_tokens)}{Colors.ENDC} JWT tokens")
        elif self.api_key:
            logger.info("✓ Using API key authentication")
        
        # Enhanced user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15"
        ]
        
        # HTTP/2 client
        self.session = httpx.Client(http2=True, timeout=10.0)
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Entity tracking
        self.pet_ids = []
        self.user_ids = []
        self.order_ids = []
        self.usernames = []
        
        # Pet data
        self.pet_names = ["Buddy", "Max", "Bella", "Luna", "Charlie", "Lucy", "Cooper", 
                          "Daisy", "Rocky", "Sadie", "Duke", "Molly", "Bear", "Maggie"]
        self.pet_statuses = ["available", "pending", "sold"]
        self.pet_categories = [
            {"id": 1, "name": "Dogs"}, {"id": 2, "name": "Cats"},
            {"id": 3, "name": "Birds"}, {"id": 4, "name": "Fish"}
        ]
        self.pet_tags = [
            {"id": 1, "name": "friendly"}, {"id": 2, "name": "trained"},
            {"id": 3, "name": "playful"}, {"id": 4, "name": "quiet"}
        ]
        
        self.order_statuses = ["placed", "approved", "delivered"]
        
        # Protected entities (don't delete base data)
        self.protected_pet_ids = set(range(1, 6))
        self.protected_user_ids = set(range(1, 6))
        self.protected_order_ids = set(range(1, 6))
        
        self.initialize()
    
    def _get_auth_header(self) -> Dict[str, str]:
        """Get authentication header with JWT token rotation"""
        if self.jwt_tokens:
            token = random.choice(self.jwt_tokens)
            return {"api-key-petstore": token}
        return {"api-key-petstore": self.api_key} if self.api_key else {}
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[httpx.Response]:
        """Make HTTP request with enhanced error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        headers = kwargs.get('headers', {})
        headers.update({
            "User-Agent": random.choice(self.user_agents),
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        # Add auth for protected endpoints
        normalized_endpoint = endpoint.lstrip('/')
        requires_auth = (normalized_endpoint.startswith("pet") or "/pet" in endpoint or 
                        "inventory" in normalized_endpoint)
        
        if requires_auth:
            headers.update(self._get_auth_header())
        
        kwargs['headers'] = headers
        
        try:
            start_time = time.time()
            response = getattr(self.session, method.lower())(url, **kwargs)
            duration = time.time() - start_time
            
            self.stats.response_times.append(duration)
            self.stats.total_operations += 1
            
            if method.lower() == 'delete' and response.status_code in [200, 204]:
                self.stats.successful_operations += 1
                return response
            
            response.raise_for_status()
            self.stats.successful_operations += 1
            
            # Log with timing
            logger.debug(f"✓ {method.upper():6} {endpoint:30} [{response.status_code}] {duration*1000:.0f}ms")
            
            return response
        
        except httpx.HTTPStatusError as e:
            self.stats.failed_operations += 1
            status = e.response.status_code if hasattr(e, 'response') else 'unknown'
            
            if status in [401, 403]:
                self.stats.auth_errors += 1
                if self.jwt_tokens:
                    token = kwargs['headers'].get('api-key-petstore', '')
                    token_info = self.jwt_token_info.get(token, {})
                    logger.warning(
                        f"{Colors.WARNING}⚠ Auth error [{status}] - "
                        f"Token: {token_info.get('username', 'unknown')}{Colors.ENDC}"
                    )
            else:
                logger.warning(f"✗ {method.upper()} {endpoint} [{status}]")
            
            # Clean up 404 entities
            if status == 404:
                self._cleanup_missing_entity(endpoint)
            
            return None
            
        except Exception as e:
            self.stats.failed_operations += 1
            logger.error(f"✗ {method} {endpoint}: {str(e)[:50]}")
            return None
    
    def _cleanup_missing_entity(self, endpoint: str):
        """Remove tracked entities that no longer exist"""
        for pet_id in list(self.pet_ids):
            if str(pet_id) in endpoint:
                self.pet_ids.remove(pet_id)
                break
        for username in list(self.usernames):
            if username in endpoint:
                self.usernames.remove(username)
                break
    
    def initialize(self):
        """Initialize system state"""
        logger.info(f"{Colors.OKCYAN}Initializing system state...{Colors.ENDC}")
        self.refresh_state()
        self.ensure_minimum_entities()
        logger.info(f"{Colors.OKGREEN}✓ Initialization complete{Colors.ENDC}\n")
    
    def refresh_state(self):
        """Refresh entity tracking"""
        # Get inventory
        inventory_response = self._make_request("get", "/store/inventory")
        if inventory_response:
            inventory = inventory_response.json()
            total_pets = sum(count for status, count in inventory.items() if isinstance(count, int))
            logger.info(f"  Found {Colors.BOLD}{total_pets}{Colors.ENDC} pets in inventory")
            
            # Get pet IDs by status
            for status in self.pet_statuses:
                response = self._make_request("get", f"/pet/findByStatus?status={status}")
                if response:
                    pets = response.json()
                    for pet in pets:
                        if "id" in pet and pet["id"] not in self.pet_ids:
                            self.pet_ids.append(pet["id"])
        
        logger.info(f"  Tracking: {Colors.BOLD}{len(self.pet_ids)}{Colors.ENDC} pets, "
                   f"{Colors.BOLD}{len(self.usernames)}{Colors.ENDC} users, "
                   f"{Colors.BOLD}{len(self.order_ids)}{Colors.ENDC} orders")
    
    def ensure_minimum_entities(self):
        """Ensure minimum entities exist"""
        to_create = {
            'pets': max(0, self.min_pets - len(self.pet_ids)),
            'users': max(0, self.min_users - len(self.usernames)),
            'orders': max(0, self.min_orders - len(self.order_ids))
        }
        
        for entity, count in to_create.items():
            if count > 0:
                logger.info(f"  Creating {Colors.BOLD}{count}{Colors.ENDC} {entity}")
                for _ in range(count):
                    if entity == 'pets':
                        self.create_random_pet()
                    elif entity == 'users':
                        self.create_random_user()
                    elif entity == 'orders' and self.pet_ids:
                        self.create_random_order()
    
    def generate_random_string(self, length: int = 8) -> str:
        return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
    
    # Pet operations
    def create_random_pet(self) -> Optional[int]:
        pet_data = {
            "name": random.choice(self.pet_names),
            "photoUrls": [f"https://example.com/pets/{self.generate_random_string()}.jpg"],
            "status": random.choice(self.pet_statuses),
            "category": random.choice(self.pet_categories),
            "tags": random.sample(self.pet_tags, k=random.randint(1, 3))
        }
        
        response = self._make_request("post", "/pet", json=pet_data)
        if response:
            new_pet = response.json()
            if "id" in new_pet:
                pet_id = new_pet["id"]
                self.pet_ids.append(pet_id)
                self.stats.operation_counts['pet']['create'] += 1
                logger.info(f"{Colors.OKGREEN}✓{Colors.ENDC} Created pet #{pet_id}: {pet_data['name']}")
                return pet_id
        return None
    
    def update_pet(self, pet_id: int) -> bool:
        response = self._make_request("get", f"/pet/{pet_id}")
        if not response:
            return False
        
        pet_data = response.json()
        pet_data["status"] = random.choice(self.pet_statuses)
        pet_data["name"] = random.choice(self.pet_names)
        
        response = self._make_request("put", "/pet", json=pet_data)
        if response:
            self.stats.operation_counts['pet']['update'] += 1
            logger.info(f"✓ Updated pet #{pet_id}")
            return True
        return False
    
    def delete_pet(self, pet_id: int) -> bool:
        response = self._make_request("delete", f"/pet/{pet_id}")
        if response and response.status_code in [200, 204]:
            if pet_id in self.pet_ids:
                self.pet_ids.remove(pet_id)
            self.stats.operation_counts['pet']['delete'] += 1
            logger.info(f"✓ Deleted pet #{pet_id}")
            return True
        return False
    
    def get_pet_by_id(self, pet_id: int) -> Optional[Dict]:
        response = self._make_request("get", f"/pet/{pet_id}")
        if response:
            self.stats.operation_counts['pet']['get'] += 1
            return response.json()
        return None
    
    def find_pets_by_status(self, status: str) -> List[Dict]:
        response = self._make_request("get", f"/pet/findByStatus?status={status}")
        if response:
            self.stats.operation_counts['pet']['query'] += 1
            return response.json()
        return []
    
    # User operations
    def create_random_user(self) -> Optional[str]:
        username = f"user_{self.generate_random_string()}"
        user_data = {
            "username": username,
            "firstName": f"First_{self.generate_random_string(4)}",
            "lastName": f"Last_{self.generate_random_string(4)}",
            "email": f"{username}@example.com",
            "password": "password123",
            "phone": f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
        }
        
        response = self._make_request("post", "/user", json=user_data)
        if response:
            self.usernames.append(username)
            self.stats.operation_counts['user']['create'] += 1
            logger.info(f"{Colors.OKGREEN}✓{Colors.ENDC} Created user: {username}")
            return username
        return None
    
    def delete_user(self, username: str) -> bool:
        response = self._make_request("delete", f"/user/{username}")
        if response:
            if username in self.usernames:
                self.usernames.remove(username)
            self.stats.operation_counts['user']['delete'] += 1
            logger.info(f"✓ Deleted user: {username}")
            return True
        return False
    
    # Order operations
    def create_random_order(self) -> Optional[int]:
        if not self.pet_ids:
            return None
        
        order_data = {
            "petId": random.choice(self.pet_ids),
            "quantity": random.randint(1, 3),
            "shipDate": (datetime.now() + timedelta(days=random.randint(1, 30))).isoformat() + "Z",
            "status": random.choice(self.order_statuses),
            "complete": random.choice([True, False])
        }
        
        response = self._make_request("post", "/store/order", json=order_data)
        if response:
            new_order = response.json()
            if "id" in new_order:
                order_id = new_order["id"]
                self.order_ids.append(order_id)
                self.stats.operation_counts['order']['create'] += 1
                logger.info(f"{Colors.OKGREEN}✓{Colors.ENDC} Created order #{order_id}")
                return order_id
        return None
    
    def get_inventory(self) -> Optional[Dict]:
        response = self._make_request("get", "/store/inventory")
        if response:
            self.stats.operation_counts['order']['inventory'] += 1
            return response.json()
        return None
    
    # Operation wrappers with smart behavior
    def op_delete_pet(self):
        deletable_pets = [p for p in self.pet_ids if p not in self.protected_pet_ids]
        if deletable_pets and len(deletable_pets) > (self.min_pets - len(self.protected_pet_ids)):
            self.delete_pet(random.choice(deletable_pets))
        else:
            self.create_random_pet()
    
    def simulate_random_operation(self):
        """Simulate realistic API operation with weighted probabilities"""
        operations = [
            (self.create_random_pet, 10),
            (lambda: self.update_pet(random.choice(self.pet_ids)) if self.pet_ids else None, 8),
            (self.op_delete_pet, 5),
            (lambda: self.get_pet_by_id(random.choice(self.pet_ids)) if self.pet_ids else None, 20),
            (lambda: self.find_pets_by_status(random.choice(self.pet_statuses)), 15),
            (self.create_random_user, 8),
            (lambda: self.delete_user(random.choice([u for u in self.usernames if not u.startswith('user1') and not u.startswith('user2')])) if len(self.usernames) > self.min_users else None, 3),
            (self.create_random_order, 10),
            (self.get_inventory, 12)
        ]
        
        ops, weights = zip(*operations)
        operation = random.choices(ops, weights=weights)[0]
        operation()
    
    def run_simulation(self, duration_minutes: int = 10, operations_per_minute: int = 30):
        """Run sequential simulation"""
        logger.info(f"{Colors.HEADER}Starting simulation for {duration_minutes} minutes...{Colors.ENDC}\n")
        
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        sleep_time = 60 / operations_per_minute
        
        try:
            while datetime.now() < end_time:
                self.simulate_random_operation()
                time.sleep(sleep_time)
                
                # Progress updates
                if self.stats.total_operations % 100 == 0:
                    self._print_progress()
                
                if self.stats.total_operations % 50 == 0:
                    self.ensure_minimum_entities()
        
        except KeyboardInterrupt:
            logger.warning(f"\n{Colors.WARNING}Simulation interrupted by user{Colors.ENDC}")
        
        self.generate_summary_report()
    
    def run_parallel_simulation(self, duration_minutes: int = 10, 
                              operations_per_minute: int = 30, concurrency: int = 3):
        """Run parallel simulation"""
        logger.info(f"{Colors.HEADER}Starting parallel simulation with {concurrency} threads...{Colors.ENDC}\n")
        
        sleep_time = 60 / operations_per_minute
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        def worker():
            count = 0
            while datetime.now() < end_time:
                self.simulate_random_operation()
                count += 1
                time.sleep(sleep_time)
            return count
        
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker) for _ in range(concurrency)]
            
            try:
                while datetime.now() < end_time:
                    time.sleep(10)
                    self._print_progress()
                    self.ensure_minimum_entities()
            except KeyboardInterrupt:
                logger.warning(f"\n{Colors.WARNING}Parallel simulation interrupted{Colors.ENDC}")
        
        self.generate_summary_report()
    
    def _print_progress(self):
        """Print progress update"""
        elapsed = time.time() - self.stats.start_time
        ops = self.stats.total_operations
        success_rate = (self.stats.successful_operations / max(ops, 1)) * 100
        logger.info(
            f"{Colors.OKCYAN}Progress: {elapsed/60:.1f}min | "
            f"Ops: {ops} | Success: {success_rate:.1f}%{Colors.ENDC}"
        )
    
    def generate_summary_report(self):
        """Generate enhanced summary report"""
        duration = time.time() - self.stats.start_time
        ops = self.stats.total_operations
        success_rate = (self.stats.successful_operations / max(ops, 1)) * 100
        
        avg_response = sum(self.stats.response_times) / len(self.stats.response_times) if self.stats.response_times else 0
        
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}")
        print(f"   PETSTORE API SIMULATION - SUMMARY REPORT")
        print(f"{'='*80}{Colors.ENDC}\n")
        
        print(f"{Colors.OKBLUE}{Colors.BOLD}OVERALL PERFORMANCE{Colors.ENDC}")
        print(f"{'─'*80}")
        print(f"  Duration:              {Colors.BOLD}{duration/60:.1f} minutes{Colors.ENDC}")
        print(f"  Total Operations:      {Colors.BOLD}{ops:,}{Colors.ENDC}")
        print(f"  Successful:            {Colors.OKGREEN}{self.stats.successful_operations:,}{Colors.ENDC}")
        print(f"  Failed:                {Colors.FAIL}{self.stats.failed_operations:,}{Colors.ENDC}")
        print(f"  Success Rate:          {Colors.BOLD}{success_rate:.2f}%{Colors.ENDC}")
        print(f"  Avg Response Time:     {Colors.BOLD}{avg_response*1000:.0f}ms{Colors.ENDC}")
        print(f"  Throughput:            {Colors.BOLD}{ops/duration:.1f} ops/sec{Colors.ENDC}\n")
        
        if self.stats.auth_errors > 0:
            auth_rate = (self.stats.auth_errors / self.stats.failed_operations) * 100
            print(f"{Colors.WARNING}AUTHENTICATION{Colors.ENDC}")
            print(f"{'─'*80}")
            print(f"  Auth Errors:           {Colors.WARNING}{self.stats.auth_errors} ({auth_rate:.1f}% of failures){Colors.ENDC}\n")
        
        print(f"{Colors.OKBLUE}{Colors.BOLD}OPERATIONS BY ENTITY{Colors.ENDC}")
        print(f"{'─'*80}")
        
        for entity, ops_dict in self.stats.operation_counts.items():
            entity_total = sum(ops_dict.values())
            entity_pct = (entity_total / max(self.stats.total_operations, 1)) * 100
            print(f"\n  {entity.upper()} Operations: {Colors.BOLD}{entity_total:,}{Colors.ENDC} ({entity_pct:.1f}%)")
            
            for op_type, count in ops_dict.items():
                if count > 0:
                    op_pct = (count / max(entity_total, 1)) * 100
                    print(f"    {op_type.capitalize():12} {count:5,} ({op_pct:5.1f}%)")
        
        print(f"\n{Colors.OKBLUE}{Colors.BOLD}CURRENT STATE{Colors.ENDC}")
        print(f"{'─'*80}")
        print(f"  Pets:                  {Colors.BOLD}{len(self.pet_ids)}{Colors.ENDC}")
        print(f"  Users:                 {Colors.BOLD}{len(self.usernames)}{Colors.ENDC}")
        print(f"  Orders:                {Colors.BOLD}{len(self.order_ids)}{Colors.ENDC}")
        
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
        
        logger.info(f"{Colors.OKGREEN}Report saved to: petstore_simulator.log{Colors.ENDC}")
    
    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()

def main():
    parser = argparse.ArgumentParser(description="Petstore API Traffic Simulator v2.0")
    parser.add_argument("--url", required=True, help="Base URL of the Petstore API")
    parser.add_argument("--api-key", help="API key for authentication")
    parser.add_argument("--duration", type=int, default=10, help="Duration in minutes (default: 10)")
    parser.add_argument("--rate", type=int, default=30, help="Operations per minute (default: 30)")
    parser.add_argument("--min-pets", type=int, default=10, help="Minimum pets (default: 10)")
    parser.add_argument("--min-users", type=int, default=5, help="Minimum users (default: 5)")
    parser.add_argument("--min-orders", type=int, default=3, help="Minimum orders (default: 3)")
    parser.add_argument("--parallel", type=int, default=0, help="Parallel threads (default: 0)")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout (default: 10)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--use-jwt", action="store_true", help="Use JWT tokens")
    parser.add_argument("--token-dir", default="petstore-api-keys/temp_tokens", help="JWT token directory")
    
    args = parser.parse_args()
    
    if not args.api_key and not args.use_jwt:
        logger.error(f"{Colors.FAIL}Error: Either --api-key or --use-jwt required{Colors.ENDC}")
        parser.print_help()
        sys.exit(1)
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Print configuration banner
    config = {
        'url': args.url,
        'duration': args.duration,
        'rate': args.rate,
        'parallel': args.parallel,
        'auth_method': 'JWT Tokens' if args.use_jwt else 'API Key',
        'min_pets': args.min_pets,
        'min_users': args.min_users,
        'min_orders': args.min_orders
    }
    print_banner(config)
    
    # Generate JWT tokens if needed
    jwt_token_files = []
    if args.use_jwt:
        jwt_token_files = generate_jwt_tokens(args.duration, args.token_dir)
    
    # Create simulator
    simulator = PetstoreTrafficSimulator(
        base_url=args.url,
        api_key=args.api_key or "",
        min_pets=args.min_pets,
        min_users=args.min_users,
        min_orders=args.min_orders,
        jwt_token_files=jwt_token_files
    )
    
    simulator.timeout = args.timeout
    
    # Run simulation
    if args.parallel > 0:
        simulator.run_parallel_simulation(
            duration_minutes=args.duration,
            operations_per_minute=args.rate,
            concurrency=args.parallel
        )
    else:
        simulator.run_simulation(
            duration_minutes=args.duration,
            operations_per_minute=args.rate
        )
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
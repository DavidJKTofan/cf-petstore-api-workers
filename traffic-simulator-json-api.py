import asyncio
import httpx
import random
import logging
import time
import sys
from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime
from fake_useragent import UserAgent
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
        logging.WARNING: Colors.WARNING + "%(asctime)s - WARNING: %(message)s" + Colors.ENDC,
        logging.ERROR: Colors.FAIL + "%(asctime)s - ERROR: %(message)s" + Colors.ENDC,
        logging.CRITICAL: Colors.FAIL + Colors.BOLD + "%(asctime)s - CRITICAL: %(message)s" + Colors.ENDC,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

@dataclass
class RequestMetrics:
    """Tracks detailed metrics for requests"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    endpoint_requests: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    endpoint_errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    status_code_counts: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    request_times: List[float] = field(default_factory=list)
    response_sizes: List[int] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

class APITrafficSimulator:
    def __init__(self, 
                 base_url: str, 
                 max_concurrent_requests: int = 10,
                 timeout: float = 10.0,
                 realistic_delays: bool = True):
        """
        Initialize the API Traffic Simulator with HTTP/2 support
        
        :param base_url: Base URL of the API
        :param max_concurrent_requests: Maximum number of concurrent requests
        :param timeout: Request timeout in seconds
        :param realistic_delays: Enable realistic human-like delays between requests
        """
        self.base_url = base_url.rstrip('/')
        self.max_concurrent_requests = max_concurrent_requests
        self.realistic_delays = realistic_delays
        self.ua = UserAgent()
        
        # Initialize metrics tracker
        self.metrics = RequestMetrics()
        
        # Define endpoints with metadata
        self.endpoints = {
            '/albums': {
                'max_items': 100,
                'query_strategy': self._generate_list_strategy('/albums'),
                'item_strategy': self._generate_item_strategy('/albums')
            },
            '/users': {
                'max_items': 10,
                'query_strategy': self._generate_list_strategy('/users'),
                'item_strategy': self._generate_item_strategy('/users')
            },
            '/photos': {
                'max_items': 5000,
                'query_strategy': self._generate_list_strategy('/photos', additional_params={
                    'albumId': lambda: random.randint(1, 10)
                }),
                'item_strategy': self._generate_item_strategy('/photos')
            },
            '/posts': {
                'max_items': 100,
                'query_strategy': self._generate_list_strategy('/posts'),
                'item_strategy': self._generate_item_strategy('/posts')
            },
            '/todos': {
                'max_items': 200,
                'query_strategy': self._generate_list_strategy('/todos'),
                'item_strategy': self._generate_item_strategy('/todos')
            },
            '/comments': {
                'max_items': 500,
                'query_strategy': self._generate_list_strategy('/comments', additional_params={
                    'postId': lambda: random.randint(1, 100)
                }),
                'item_strategy': self._generate_item_strategy('/comments')
            }
        }
        
        # Configure logging with colored output
        self._setup_logging()
        
        # HTTP/2 client configuration with retry logic
        self.http2_client_limits = httpx.Limits(
            max_connections=max_concurrent_requests,
            max_keepalive_connections=max_concurrent_requests
        )
        self.timeout = httpx.Timeout(timeout)
        
        self._print_startup_banner()

    def _setup_logging(self):
        """Setup logging with both file and colored console output"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler (without colors)
        file_handler = logging.FileHandler('api_traffic_simulation.log')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler (with colors)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter())
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _print_startup_banner(self):
        """Print a colorful startup banner"""
        banner = f"""
{Colors.HEADER}{Colors.BOLD}{'='*70}
   JSON API TRAFFIC SIMULATOR v2.0
{'='*70}{Colors.ENDC}

{Colors.OKCYAN}Configuration:{Colors.ENDC}
  • Base URL: {Colors.BOLD}{self.base_url}{Colors.ENDC}
  • Max Concurrent Requests: {Colors.BOLD}{self.max_concurrent_requests}{Colors.ENDC}
  • Timeout: {Colors.BOLD}{self.timeout.read}s{Colors.ENDC}
  • Realistic Delays: {Colors.BOLD}{'Enabled' if self.realistic_delays else 'Disabled'}{Colors.ENDC}
  • Endpoints: {Colors.BOLD}{len(self.endpoints)}{Colors.ENDC}

{Colors.OKGREEN}Starting simulation...{Colors.ENDC}
{Colors.HEADER}{'='*70}{Colors.ENDC}
"""
        print(banner)

    def _generate_list_strategy(self, endpoint: str, additional_params: Optional[Dict[str, Any]] = None) -> callable:
        """
        Generate a strategy for list endpoint queries with realistic parameters
        
        :param endpoint: Base endpoint
        :param additional_params: Optional additional query parameters
        :return: Query parameter generation function
        """
        def generate_params():
            # More realistic pagination patterns
            page_choices = [1, 1, 1, 2, 2, 3]  # Weighted towards first pages
            limit_choices = [10, 20, 25, 50]  # Common page sizes
            
            params = {
                '_page': random.choice(page_choices),
                '_limit': random.choice(limit_choices)
            }
            
            if additional_params:
                for key, value in additional_params.items():
                    # Handle callable values (lambdas)
                    params[key] = value() if callable(value) else value
            
            return params
        return generate_params

    def _generate_item_strategy(self, endpoint: str) -> callable:
        """
        Generate a strategy for individual item retrieval with realistic distribution
        
        :param endpoint: Base endpoint
        :return: Item ID generation function
        """
        def generate_item_id():
            max_items = self.endpoints[endpoint]['max_items']
            # Weighted distribution favoring lower IDs (more popular items)
            if random.random() < 0.7:
                return random.randint(1, min(50, max_items))
            else:
                return random.randint(1, max_items)
        return generate_item_id

    def _get_realistic_delay(self) -> float:
        """Calculate realistic delay between requests based on human behavior"""
        if not self.realistic_delays:
            return random.uniform(0.1, 0.5)
        
        # Simulate different user behavior patterns
        behavior = random.choices(
            ['quick_browse', 'normal_browse', 'careful_read', 'batch_load'],
            weights=[0.3, 0.4, 0.2, 0.1]
        )[0]
        
        delays = {
            'quick_browse': (0.5, 2.0),
            'normal_browse': (2.0, 5.0),
            'careful_read': (5.0, 10.0),
            'batch_load': (0.1, 0.5)
        }
        
        return random.uniform(*delays[behavior])

    async def fetch_endpoint(self, session: httpx.AsyncClient, endpoint: str, item_mode: bool = False) -> None:
        """
        Fetch a specific endpoint with intelligent parameter generation
        
        :param session: Async HTTP client session
        :param endpoint: API endpoint to fetch
        :param item_mode: Whether to fetch a specific item
        """
        try:
            # Increment total and endpoint-specific request count
            self.metrics.total_requests += 1
            self.metrics.endpoint_requests[endpoint] += 1
            
            # Determine query strategy
            if item_mode:
                item_id = self.endpoints[endpoint]['item_strategy']()
                url = f"{self.base_url}{endpoint}/{item_id}"
                params = {}
            else:
                query_strategy = self.endpoints[endpoint]['query_strategy']
                params = query_strategy()
                url = f"{self.base_url}{endpoint}"
            
            # Realistic user agent and headers
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'application/json',
                'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.8', 'en-US,en;q=0.5']),
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': random.choice(['no-cache', 'max-age=0', 'no-store'])
            }
            
            # Realistic delay before request
            await asyncio.sleep(self._get_realistic_delay())
            
            # Perform request with timing
            start_time = time.time()
            response = await session.get(url, params=params, headers=headers)
            request_duration = time.time() - start_time
            
            # Track metrics
            self.metrics.request_times.append(request_duration)
            self.metrics.status_code_counts[response.status_code] += 1
            
            if response.content:
                self.metrics.response_sizes.append(len(response.content))
            
            # Log request details
            request_type = "Item" if item_mode else "List"
            status_color = Colors.OKGREEN if response.status_code == 200 else Colors.WARNING
            
            if response.status_code == 200:
                self.metrics.successful_requests += 1
                self.logger.info(
                    f"{status_color}✓{Colors.ENDC} {request_type:4} {endpoint:20} "
                    f"[{response.status_code}] {request_duration*1000:6.1f}ms "
                    f"({len(response.content):,} bytes)"
                )
                
                # Validate response
                try:
                    data = response.json()
                    if not item_mode and isinstance(data, list):
                        item_count = len(data)
                        max_expected = self.endpoints[endpoint]['max_items']
                        
                        if item_count > max_expected:
                            self.logger.warning(
                                f"Unexpected item count for {endpoint}: "
                                f"Expected ≤{max_expected}, Got {item_count}"
                            )
                except ValueError:
                    self.logger.error(f"Invalid JSON response for {endpoint}")
            else:
                self.metrics.failed_requests += 1
                self.metrics.endpoint_errors[endpoint] += 1
                self.logger.warning(
                    f"{Colors.FAIL}✗{Colors.ENDC} {request_type:4} {endpoint:20} "
                    f"[{response.status_code}] {request_duration*1000:6.1f}ms"
                )
        
        except asyncio.TimeoutError:
            self.metrics.failed_requests += 1
            self.metrics.endpoint_errors[endpoint] += 1
            self.logger.error(f"{Colors.FAIL}⚠{Colors.ENDC} Timeout: {endpoint}")
        except Exception as e:
            self.metrics.failed_requests += 1
            self.metrics.endpoint_errors[endpoint] += 1
            self.logger.error(f"{Colors.FAIL}⚠{Colors.ENDC} Error fetching {endpoint}: {str(e)[:50]}")

    def generate_summary_report(self) -> str:
        """Generate a comprehensive and colorful summary report"""
        total_requests = self.metrics.total_requests
        successful_requests = self.metrics.successful_requests
        failed_requests = self.metrics.failed_requests
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate statistics
        request_times = self.metrics.request_times
        avg_request_time = sum(request_times) / len(request_times) if request_times else 0
        min_request_time = min(request_times) if request_times else 0
        max_request_time = max(request_times) if request_times else 0
        
        response_sizes = self.metrics.response_sizes
        avg_response_size = sum(response_sizes) / len(response_sizes) if response_sizes else 0
        total_data_transferred = sum(response_sizes)
        
        # Calculate throughput
        duration = time.time() - self.metrics.start_time
        requests_per_second = total_requests / duration if duration > 0 else 0
        
        # Build colorful report
        report_lines = [
            f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}",
            f"   API TRAFFIC SIMULATION - SUMMARY REPORT",
            f"{'='*70}{Colors.ENDC}\n",
            
            f"{Colors.OKBLUE}{Colors.BOLD}OVERALL PERFORMANCE{Colors.ENDC}",
            f"{'─'*70}",
            f"  Total Requests:        {Colors.BOLD}{total_requests:,}{Colors.ENDC}",
            f"  Successful:            {Colors.OKGREEN}{successful_requests:,}{Colors.ENDC}",
            f"  Failed:                {Colors.FAIL}{failed_requests:,}{Colors.ENDC}",
            f"  Success Rate:          {Colors.BOLD}{success_rate:.2f}%{Colors.ENDC}",
            f"  Duration:              {Colors.BOLD}{duration:.1f}s{Colors.ENDC}",
            f"  Throughput:            {Colors.BOLD}{requests_per_second:.2f} req/s{Colors.ENDC}\n",
            
            f"{Colors.OKBLUE}{Colors.BOLD}RESPONSE TIMES{Colors.ENDC}",
            f"{'─'*70}",
            f"  Average:               {Colors.BOLD}{avg_request_time*1000:.2f}ms{Colors.ENDC}",
            f"  Minimum:               {Colors.OKGREEN}{min_request_time*1000:.2f}ms{Colors.ENDC}",
            f"  Maximum:               {Colors.WARNING}{max_request_time*1000:.2f}ms{Colors.ENDC}\n",
            
            f"{Colors.OKBLUE}{Colors.BOLD}DATA TRANSFER{Colors.ENDC}",
            f"{'─'*70}",
            f"  Total Transferred:     {Colors.BOLD}{total_data_transferred/1024/1024:.2f} MB{Colors.ENDC}",
            f"  Average Response Size: {Colors.BOLD}{avg_response_size/1024:.2f} KB{Colors.ENDC}\n",
            
            f"{Colors.OKBLUE}{Colors.BOLD}REQUEST DISTRIBUTION BY ENDPOINT{Colors.ENDC}",
            f"{'─'*70}"
        ]
        
        # Add endpoint statistics
        for endpoint, count in sorted(self.metrics.endpoint_requests.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_requests * 100) if total_requests > 0 else 0
            errors = self.metrics.endpoint_errors[endpoint]
            error_rate = (errors / count * 100) if count > 0 else 0
            
            status = Colors.OKGREEN if error_rate < 5 else Colors.WARNING if error_rate < 20 else Colors.FAIL
            report_lines.append(
                f"  {endpoint:20} {count:5} requests ({percentage:5.1f}%)  "
                f"{status}{errors:3} errors ({error_rate:4.1f}%){Colors.ENDC}"
            )
        
        # Add status code breakdown
        report_lines.extend([
            f"\n{Colors.OKBLUE}{Colors.BOLD}STATUS CODE BREAKDOWN{Colors.ENDC}",
            f"{'─'*70}"
        ])
        
        for code, count in sorted(self.metrics.status_code_counts.items()):
            percentage = (count / total_requests * 100) if total_requests > 0 else 0
            code_color = Colors.OKGREEN if code == 200 else Colors.WARNING if code < 500 else Colors.FAIL
            report_lines.append(
                f"  {code_color}HTTP {code}{Colors.ENDC}: {count:5} requests ({percentage:5.1f}%)"
            )
        
        report_lines.extend([
            f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n"
        ])
        
        return "\n".join(report_lines)

    async def simulate_traffic(self, duration: int = 300, request_frequency: float = 2.0) -> None:
        """
        Simulate realistic traffic to API endpoints with HTTP/2
        
        :param duration: Total simulation duration in seconds
        :param request_frequency: Average time between request batches
        """
        async with httpx.AsyncClient(
            http2=True,
            limits=self.http2_client_limits,
            timeout=self.timeout,
            follow_redirects=True
        ) as session:
            start_time = time.time()
            self.metrics.start_time = start_time
            
            self.logger.info(f"Simulation running for {duration} seconds...")
            
            try:
                while time.time() - start_time < duration:
                    # Simulate realistic user behavior patterns
                    behavior = random.choices(
                        ['browse_multiple', 'deep_dive', 'quick_check', 'search_pattern'],
                        weights=[0.4, 0.2, 0.3, 0.1]
                    )[0]
                    
                    tasks = []
                    
                    if behavior == 'browse_multiple':
                        # User browsing multiple endpoints
                        endpoints = random.sample(list(self.endpoints.keys()), k=random.randint(2, 4))
                        for endpoint in endpoints:
                            tasks.append(self.fetch_endpoint(session, endpoint, item_mode=False))
                    
                    elif behavior == 'deep_dive':
                        # User exploring specific items
                        endpoint = random.choice(list(self.endpoints.keys()))
                        tasks.append(self.fetch_endpoint(session, endpoint, item_mode=False))
                        for _ in range(random.randint(2, 5)):
                            tasks.append(self.fetch_endpoint(session, endpoint, item_mode=True))
                    
                    elif behavior == 'quick_check':
                        # Quick single request
                        endpoint = random.choice(list(self.endpoints.keys()))
                        tasks.append(self.fetch_endpoint(session, endpoint, item_mode=random.choice([True, False])))
                    
                    else:  # search_pattern
                        # User searching through paginated results
                        endpoint = random.choice(list(self.endpoints.keys()))
                        for _ in range(random.randint(3, 6)):
                            tasks.append(self.fetch_endpoint(session, endpoint, item_mode=False))
                    
                    # Execute tasks concurrently
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Realistic wait between batches
                    await asyncio.sleep(random.uniform(0.5, request_frequency))
                    
                    # Progress indicator every 10% of duration
                    elapsed = time.time() - start_time
                    progress = (elapsed / duration) * 100
                    if int(progress) % 10 == 0 and int(progress) > 0:
                        self.logger.info(
                            f"{Colors.OKCYAN}Progress: {progress:.0f}% | "
                            f"Requests: {self.metrics.total_requests} | "
                            f"Success Rate: {(self.metrics.successful_requests/max(self.metrics.total_requests, 1)*100):.1f}%{Colors.ENDC}"
                        )
                
                self.logger.info(f"{Colors.OKGREEN}{Colors.BOLD}✓ Traffic simulation completed successfully!{Colors.ENDC}")
                
            except KeyboardInterrupt:
                self.logger.warning(f"{Colors.WARNING}Simulation interrupted by user{Colors.ENDC}")
            except Exception as e:
                self.logger.error(f"{Colors.FAIL}Simulation error: {e}{Colors.ENDC}")

async def main():
    """Main entry point with enhanced configuration"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="JSON API Traffic Simulator v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -d 300 -r 2.0
  %(prog)s --url https://api.example.com --duration 600 --concurrent 20
  %(prog)s -d 120 --no-realistic-delays --debug
        """
    )
    
    parser.add_argument(
        '-u', '--url',
        default='https://json.dlsdemo.com',
        help='Base URL of the JSON API (default: https://json.dlsdemo.com)'
    )
    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=300,
        help='Simulation duration in seconds (default: 300)'
    )
    parser.add_argument(
        '-r', '--rate',
        type=float,
        default=2.0,
        help='Average time between request batches in seconds (default: 2.0)'
    )
    parser.add_argument(
        '-c', '--concurrent',
        type=int,
        default=10,
        help='Maximum concurrent requests (default: 10)'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=float,
        default=10.0,
        help='Request timeout in seconds (default: 10.0)'
    )
    parser.add_argument(
        '--no-realistic-delays',
        action='store_true',
        help='Disable realistic human-like delays between requests'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Update logging level if debug mode
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    simulator = APITrafficSimulator(
        base_url=args.url,
        max_concurrent_requests=args.concurrent,
        timeout=args.timeout,
        realistic_delays=not args.no_realistic_delays
    )
    
    try:
        # Run simulation
        await simulator.simulate_traffic(
            duration=args.duration,
            request_frequency=args.rate
        )
        
        # Generate and display report
        report = simulator.generate_summary_report()
        print(report)
        
        # Save report to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'traffic_simulation_report_{timestamp}.txt'
        with open(report_file, 'w') as f:
            # Strip ANSI codes for file output
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_report = ansi_escape.sub('', report)
            f.write(clean_report)
        
        print(f"{Colors.OKGREEN}Report saved to: {Colors.BOLD}{report_file}{Colors.ENDC}")
        
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Simulation interrupted by user{Colors.ENDC}")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        print(f"{Colors.FAIL}Simulation error: {e}{Colors.ENDC}")
        import traceback
        if args.debug:
            traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
"""
Performance monitoring and health check utilities.
"""

import asyncio
import psutil
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque

from utils.logger import get_logger


@dataclass
class PerformanceMetric:
    """Single performance metric."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Health check result."""
    name: str
    status: str  # 'healthy', 'warning', 'critical'
    message: str
    timestamp: datetime
    response_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Collects and stores performance metrics.
    """
    
    def __init__(self, max_metrics: int = 10000, retention_days: int = 7):
        self.max_metrics = max_metrics
        self.retention_days = retention_days
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_metrics))
        self.lock = threading.Lock()
        self.logger = get_logger("metrics.collector")
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a performance metric."""
        if tags is None:
            tags = {}
        
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags
        )
        
        with self.lock:
            self.metrics[name].append(metric)
    
    def get_metrics(self, name: str, since: Optional[datetime] = None) -> List[PerformanceMetric]:
        """Get metrics for a specific name."""
        with self.lock:
            metrics = list(self.metrics[name])
        
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
        
        return metrics
    
    def get_latest_metric(self, name: str) -> Optional[PerformanceMetric]:
        """Get the latest metric for a name."""
        with self.lock:
            metrics = self.metrics[name]
            return metrics[-1] if metrics else None
    
    def get_average(self, name: str, since: Optional[datetime] = None) -> Optional[float]:
        """Get average value for a metric."""
        metrics = self.get_metrics(name, since)
        if not metrics:
            return None
        
        return sum(m.value for m in metrics) / len(metrics)
    
    def cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        cutoff_time = datetime.utcnow() - timedelta(days=self.retention_days)
        
        with self.lock:
            for name in self.metrics:
                # Remove old metrics
                while self.metrics[name] and self.metrics[name][0].timestamp < cutoff_time:
                    self.metrics[name].popleft()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        with self.lock:
            summary = {}
            for name, metrics in self.metrics.items():
                if metrics:
                    values = [m.value for m in metrics]
                    summary[name] = {
                        'count': len(values),
                        'latest': values[-1],
                        'average': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values)
                    }
        
        return summary


class HealthChecker:
    """
    Manages health checks for various system components.
    """
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.results: Dict[str, HealthCheckResult] = {}
        self.lock = threading.Lock()
        self.logger = get_logger("health.checker")
    
    def register_check(self, name: str, check_func: Callable):
        """Register a health check function."""
        self.checks[name] = check_func
        self.logger.info(f"Registered health check: {name}")
    
    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self.checks:
            return HealthCheckResult(
                name=name,
                status='critical',
                message=f"Health check '{name}' not found",
                timestamp=datetime.utcnow(),
                response_time=0.0
            )
        
        start_time = time.time()
        
        try:
            check_func = self.checks[name]
            
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            
            response_time = time.time() - start_time
            
            # Normalize result
            if isinstance(result, bool):
                status = 'healthy' if result else 'critical'
                message = 'OK' if result else 'Check failed'
                metadata = {}
            elif isinstance(result, dict):
                status = result.get('status', 'healthy')
                message = result.get('message', 'OK')
                metadata = result.get('metadata', {})
            else:
                status = 'healthy'
                message = str(result)
                metadata = {}
            
            health_result = HealthCheckResult(
                name=name,
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                response_time=response_time,
                metadata=metadata
            )
            
            with self.lock:
                self.results[name] = health_result
            
            return health_result
            
        except Exception as e:
            response_time = time.time() - start_time
            
            health_result = HealthCheckResult(
                name=name,
                status='critical',
                message=f"Health check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                response_time=response_time,
                metadata={'exception': str(e)}
            )
            
            with self.lock:
                self.results[name] = health_result
            
            self.logger.error(f"Health check '{name}' failed: {e}")
            return health_result
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        tasks = []
        for name in self.checks:
            tasks.append(self.run_check(name))
        
        results = await asyncio.gather(*tasks)
        return {result.name: result for result in results}
    
    def get_latest_results(self) -> Dict[str, HealthCheckResult]:
        """Get latest health check results."""
        with self.lock:
            return self.results.copy()
    
    def get_overall_status(self) -> str:
        """Get overall system health status."""
        with self.lock:
            if not self.results:
                return 'unknown'
            
            statuses = [result.status for result in self.results.values()]
            
            if 'critical' in statuses:
                return 'critical'
            elif 'warning' in statuses:
                return 'warning'
            else:
                return 'healthy'


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.
    """
    
    def __init__(self, logger, alert_threshold: float = 5.0):
        self.logger = logger
        self.alert_threshold = alert_threshold
        self.metrics_collector = MetricsCollector()
        self.health_checker = HealthChecker()
        
        # Performance tracking
        self.operation_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.error_counts: Dict[str, int] = defaultdict(int)
        
        # System monitoring
        self.process = psutil.Process()
        
        # Register default health checks
        self._register_default_health_checks()
    
    def _register_default_health_checks(self):
        """Register default system health checks."""
        
        def memory_check():
            memory_percent = self.process.memory_percent()
            if memory_percent > 80:
                return {
                    'status': 'critical',
                    'message': f'High memory usage: {memory_percent:.1f}%',
                    'metadata': {'memory_percent': memory_percent}
                }
            elif memory_percent > 60:
                return {
                    'status': 'warning',
                    'message': f'Moderate memory usage: {memory_percent:.1f}%',
                    'metadata': {'memory_percent': memory_percent}
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Memory usage: {memory_percent:.1f}%',
                    'metadata': {'memory_percent': memory_percent}
                }
        
        def cpu_check():
            cpu_percent = self.process.cpu_percent()
            if cpu_percent > 80:
                return {
                    'status': 'critical',
                    'message': f'High CPU usage: {cpu_percent:.1f}%',
                    'metadata': {'cpu_percent': cpu_percent}
                }
            elif cpu_percent > 60:
                return {
                    'status': 'warning',
                    'message': f'Moderate CPU usage: {cpu_percent:.1f}%',
                    'metadata': {'cpu_percent': cpu_percent}
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'CPU usage: {cpu_percent:.1f}%',
                    'metadata': {'cpu_percent': cpu_percent}
                }
        
        def disk_check():
            disk_usage = psutil.disk_usage('/')
            disk_percent = disk_usage.percent
            
            if disk_percent > 90:
                return {
                    'status': 'critical',
                    'message': f'High disk usage: {disk_percent:.1f}%',
                    'metadata': {'disk_percent': disk_percent}
                }
            elif disk_percent > 80:
                return {
                    'status': 'warning',
                    'message': f'Moderate disk usage: {disk_percent:.1f}%',
                    'metadata': {'disk_percent': disk_percent}
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Disk usage: {disk_percent:.1f}%',
                    'metadata': {'disk_percent': disk_percent}
                }
        
        self.health_checker.register_check('memory', memory_check)
        self.health_checker.register_check('cpu', cpu_check)
        self.health_checker.register_check('disk', disk_check)
    
    def track_operation(self, operation_name: str):
        """Context manager for tracking operation performance."""
        return OperationTracker(self, operation_name)
    
    def record_operation_time(self, operation: str, duration: float):
        """Record operation execution time."""
        self.operation_times[operation].append(duration)
        self.metrics_collector.record_metric(f"operation_time_{operation}", duration)
        
        if duration > self.alert_threshold:
            self.logger.warning(
                f"Slow operation detected: {operation} took {duration:.3f}s",
                extra={'operation': operation, 'duration': duration}
            )
    
    def record_error(self, operation: str, error: Exception):
        """Record operation error."""
        self.error_counts[operation] += 1
        self.metrics_collector.record_metric(f"error_count_{operation}", 1)
        
        self.logger.error(
            f"Operation error: {operation} - {str(error)}",
            extra={'operation': operation, 'error_type': type(error).__name__}
        )
    
    def get_operation_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for an operation."""
        times = list(self.operation_times[operation])
        if not times:
            return {}
        
        return {
            'count': len(times),
            'average': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'p95': sorted(times)[int(len(times) * 0.95)] if len(times) > 0 else 0,
            'error_count': self.error_counts[operation]
        }
    
    def collect_system_metrics(self):
        """Collect current system metrics."""
        try:
            # Memory metrics
            memory_info = self.process.memory_info()
            self.metrics_collector.record_metric('memory_rss', memory_info.rss / 1024 / 1024)  # MB
            self.metrics_collector.record_metric('memory_vms', memory_info.vms / 1024 / 1024)  # MB
            self.metrics_collector.record_metric('memory_percent', self.process.memory_percent())
            
            # CPU metrics
            self.metrics_collector.record_metric('cpu_percent', self.process.cpu_percent())
            
            # Thread metrics
            self.metrics_collector.record_metric('thread_count', self.process.num_threads())
            
            # File descriptor metrics (Unix only)
            try:
                self.metrics_collector.record_metric('fd_count', self.process.num_fds())
            except AttributeError:
                pass  # Windows doesn't have this
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
    
    async def run_health_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks and return results."""
        return await self.health_checker.run_all_checks()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        # Collect current metrics
        self.collect_system_metrics()
        
        summary = {
            'system_metrics': self.metrics_collector.get_summary(),
            'operation_stats': {
                op: self.get_operation_stats(op) 
                for op in self.operation_times.keys()
            },
            'health_status': self.health_checker.get_overall_status(),
            'uptime': time.time() - self.process.create_time()
        }
        
        return summary
    
    def log_final_metrics(self):
        """Log final performance metrics on shutdown."""
        summary = self.get_performance_summary()
        
        self.logger.info("Final performance metrics:")
        for operation, stats in summary['operation_stats'].items():
            if stats:
                self.logger.info(
                    f"Operation {operation}: "
                    f"count={stats['count']}, "
                    f"avg={stats['average']:.3f}s, "
                    f"errors={stats['error_count']}"
                )


class OperationTracker:
    """
    Context manager for tracking individual operations.
    """
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is None:
            self.monitor.record_operation_time(self.operation_name, duration)
        else:
            self.monitor.record_error(self.operation_name, exc_val)
            self.monitor.record_operation_time(self.operation_name, duration)

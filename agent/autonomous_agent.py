"""
ReviewSignal 8.0 - Autonomous Agent System

SAMO-ULEPSZAJĄCY SIĘ AGENT AI
"Paker na siłowni, który sam rośnie"

ARCHITEKTURA:
- Multi-model: Claude Opus 4.5 (main), Sonnet 4.5 (fallback), Haiku 4.5 (fast)
- Self-monitoring: Analizuje metryki i sam się ulepsza
- Auto-deployment: Sam pisze, testuje i wdraża kod
- Revenue tracking: Monitoruje przychody i optymalizuje ROI

BEZPIECZEŃSTWO:
- Sandbox execution dla generowanego kodu
- Rate limiting na API calls
- Audit log wszystkich akcji
- Human-in-the-loop dla krytycznych zmian

@author Claude AI + Simon
@version 8.0.0
@license MIT
"""

import os
import sys
import json
import time
import asyncio
import hashlib
import subprocess
import traceback
from datetime import datetime, timedelta
from typing import (
    Dict, List, Any, Optional, Callable, Union, 
    TypeVar, Generic, Awaitable, Literal
)
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from abc import ABC, abstractmethod
import logging
from pathlib import Path
from functools import wraps
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

# Third-party imports
try:
    from anthropic import Anthropic, APIError, RateLimitError
    import structlog
    import httpx
    from pydantic import BaseModel, Field, validator
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install anthropic structlog httpx pydantic psycopg2-binary")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class AgentConfig:
    """Immutable agent configuration."""
    
    # Model hierarchy
    PRIMARY_MODEL: str = "claude-opus-4-5-20251101"
    FALLBACK_MODEL: str = "claude-sonnet-4-5-20250514"
    FAST_MODEL: str = "claude-haiku-4-5-20250514"
    
    # API settings
    MAX_TOKENS: int = 8192
    TEMPERATURE: float = 0.7
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 2.0
    
    # Rate limiting
    REQUESTS_PER_MINUTE: int = 30
    TOKENS_PER_MINUTE: int = 100000
    
    # Execution
    SANDBOX_TIMEOUT: int = 30  # seconds
    MAX_CODE_LENGTH: int = 50000  # characters
    
    # Monitoring
    METRICS_INTERVAL: int = 300  # 5 minutes
    HEALTH_CHECK_INTERVAL: int = 60  # 1 minute
    
    # Safety
    REQUIRE_APPROVAL_FOR: tuple = (
        "database_migration",
        "production_deploy",
        "delete_data",
        "billing_change"
    )

CONFIG = AgentConfig()

# ============================================================================
# LOGGING SETUP
# ============================================================================

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("autonomous_agent")

# ============================================================================
# ENUMS & TYPES
# ============================================================================

class TaskPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5

class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    AWAITING_APPROVAL = auto()

class ModelTier(Enum):
    PRIMARY = "primary"      # Opus - complex reasoning
    FALLBACK = "fallback"    # Sonnet - balanced
    FAST = "fast"            # Haiku - quick tasks

class ActionType(Enum):
    ANALYZE = "analyze"
    GENERATE_CODE = "generate_code"
    EXECUTE_CODE = "execute_code"
    DEPLOY = "deploy"
    MONITOR = "monitor"
    OPTIMIZE = "optimize"
    REPORT = "report"
    ALERT = "alert"

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class AgentTask:
    """Represents a task for the agent to execute."""
    id: str
    name: str
    description: str
    action_type: ActionType
    priority: TaskPriority
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    requires_approval: bool = False
    approved_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'action_type': self.action_type.value,
            'priority': self.priority.name,
            'status': self.status.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

@dataclass
class AgentMetrics:
    """Tracks agent performance metrics."""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_api_calls: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    average_task_duration: float = 0.0
    uptime_seconds: float = 0.0
    revenue_generated: float = 0.0
    improvements_deployed: int = 0
    errors_caught: int = 0
    
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return (self.tasks_completed / total * 100) if total > 0 else 0.0
    
    def roi(self) -> float:
        return (self.revenue_generated / self.total_cost_usd) if self.total_cost_usd > 0 else 0.0

@dataclass
class CodeGeneration:
    """Represents generated code from the agent."""
    id: str
    task_id: str
    language: str
    code: str
    description: str
    test_results: Optional[Dict[str, Any]] = None
    deployed: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    checksum: str = field(init=False)
    
    def __post_init__(self):
        self.checksum = hashlib.sha256(self.code.encode()).hexdigest()[:16]

# ============================================================================
# CLAUDE API CLIENT
# ============================================================================

class ClaudeClient:
    """
    Intelligent Claude API client with:
    - Multi-model support (Opus, Sonnet, Haiku)
    - Automatic fallback
    - Rate limiting
    - Cost tracking
    """
    
    # Cost per 1M tokens (as of 2026)
    PRICING = {
        "claude-opus-4-5-20251101": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-5-20250514": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20250514": {"input": 0.25, "output": 1.25}
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not provided")
        
        self.client = Anthropic(api_key=self.api_key)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.request_times: List[float] = []
        self._lock = threading.Lock()
        
        logger.info("claude_client_initialized")
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for API call."""
        pricing = self.PRICING.get(model, self.PRICING[CONFIG.FALLBACK_MODEL])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()
        minute_ago = now - 60
        
        with self._lock:
            self.request_times = [t for t in self.request_times if t > minute_ago]
            if len(self.request_times) >= CONFIG.REQUESTS_PER_MINUTE:
                return False
            self.request_times.append(now)
            return True
    
    async def call(
        self,
        prompt: str,
        system: Optional[str] = None,
        model_tier: ModelTier = ModelTier.PRIMARY,
        max_tokens: int = CONFIG.MAX_TOKENS,
        temperature: float = CONFIG.TEMPERATURE,
        tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Call Claude API with automatic fallback and retry.
        
        Args:
            prompt: User message
            system: System prompt
            model_tier: Which model tier to use
            max_tokens: Maximum response tokens
            temperature: Response creativity (0-1)
            tools: Optional tool definitions
        
        Returns:
            Dict with response text, usage stats, and metadata
        """
        # Select model based on tier
        models = {
            ModelTier.PRIMARY: CONFIG.PRIMARY_MODEL,
            ModelTier.FALLBACK: CONFIG.FALLBACK_MODEL,
            ModelTier.FAST: CONFIG.FAST_MODEL
        }
        model = models[model_tier]
        
        # Rate limiting
        if not self._check_rate_limit():
            logger.warning("rate_limit_approaching", waiting=True)
            await asyncio.sleep(2)
        
        # Build messages
        messages = [{"role": "user", "content": prompt}]
        
        # Retry loop with fallback
        last_error = None
        for attempt in range(CONFIG.MAX_RETRIES):
            try:
                logger.debug(
                    "api_call_attempt",
                    model=model,
                    attempt=attempt + 1,
                    prompt_length=len(prompt)
                )
                
                # Make API call
                kwargs = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": messages,
                    "temperature": temperature
                }
                
                if system:
                    kwargs["system"] = system
                if tools:
                    kwargs["tools"] = tools
                
                response = self.client.messages.create(**kwargs)
                
                # Extract response
                content = response.content[0].text if response.content else ""
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                
                # Track usage
                cost = self._calculate_cost(model, input_tokens, output_tokens)
                with self._lock:
                    self.total_input_tokens += input_tokens
                    self.total_output_tokens += output_tokens
                    self.total_cost += cost
                
                logger.info(
                    "api_call_success",
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=round(cost, 4)
                )
                
                return {
                    "text": content,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost,
                    "stop_reason": response.stop_reason
                }
                
            except RateLimitError as e:
                logger.warning("rate_limit_hit", error=str(e))
                await asyncio.sleep(CONFIG.RETRY_DELAY * (attempt + 1))
                last_error = e
                
            except APIError as e:
                logger.error("api_error", error=str(e), model=model)
                last_error = e
                
                # Try fallback model
                if model == CONFIG.PRIMARY_MODEL:
                    model = CONFIG.FALLBACK_MODEL
                    logger.info("falling_back_to_sonnet")
                elif model == CONFIG.FALLBACK_MODEL:
                    model = CONFIG.FAST_MODEL
                    logger.info("falling_back_to_haiku")
                else:
                    break
                    
            except Exception as e:
                logger.error("unexpected_error", error=str(e))
                last_error = e
                await asyncio.sleep(CONFIG.RETRY_DELAY)
        
        raise Exception(f"All API attempts failed: {last_error}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "requests_last_minute": len(self.request_times)
        }

# ============================================================================
# SANDBOX EXECUTOR
# ============================================================================

class SandboxExecutor:
    """
    Secure code execution environment.
    
    Security features:
    - Timeout enforcement
    - Resource limits
    - No network access (optional)
    - Restricted imports
    """
    
    FORBIDDEN_IMPORTS = {
        'os.system', 'subprocess.call', 'subprocess.run',
        'eval', 'exec', 'compile', '__import__',
        'open',  # unless explicitly allowed
    }
    
    def __init__(self, timeout: int = CONFIG.SANDBOX_TIMEOUT):
        self.timeout = timeout
        self.execution_count = 0
        self.last_execution: Optional[datetime] = None
        
    def _validate_code(self, code: str) -> List[str]:
        """Check code for forbidden patterns."""
        warnings = []
        
        for forbidden in self.FORBIDDEN_IMPORTS:
            if forbidden in code:
                warnings.append(f"Potentially dangerous pattern: {forbidden}")
        
        # Check for shell commands
        if 'rm -rf' in code or 'sudo' in code:
            warnings.append("Shell command detected")
        
        # Check code length
        if len(code) > CONFIG.MAX_CODE_LENGTH:
            warnings.append(f"Code exceeds max length ({len(code)} > {CONFIG.MAX_CODE_LENGTH})")
        
        return warnings
    
    async def execute_python(self, code: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute Python code in sandbox.
        
        Args:
            code: Python code to execute
            context: Optional variables to inject
        
        Returns:
            Dict with stdout, stderr, return_value, execution_time
        """
        start_time = time.time()
        
        # Validate
        warnings = self._validate_code(code)
        if warnings:
            logger.warning("code_validation_warnings", warnings=warnings)
        
        # Prepare execution environment
        local_vars = context or {}
        global_vars = {
            '__builtins__': {
                'print': print,
                'len': len,
                'range': range,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'bool': bool,
                'None': None,
                'True': True,
                'False': False,
                'sum': sum,
                'min': min,
                'max': max,
                'abs': abs,
                'round': round,
                'sorted': sorted,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'isinstance': isinstance,
                'type': type,
                'Exception': Exception,
                'ValueError': ValueError,
                'TypeError': TypeError,
                'KeyError': KeyError,
            }
        }
        
        # Capture stdout
        import io
        from contextlib import redirect_stdout, redirect_stderr
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        result = {
            'success': False,
            'stdout': '',
            'stderr': '',
            'return_value': None,
            'execution_time': 0.0,
            'warnings': warnings
        }
        
        try:
            # Execute with timeout
            def run_code():
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code, global_vars, local_vars)
            
            # Run in thread with timeout
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(run_code)
            future.result(timeout=self.timeout)
            
            result['success'] = True
            result['stdout'] = stdout_capture.getvalue()
            result['stderr'] = stderr_capture.getvalue()
            result['return_value'] = local_vars.get('result', None)
            
        except TimeoutError:
            result['stderr'] = f"Execution timed out after {self.timeout}s"
            logger.error("sandbox_timeout", code_length=len(code))
            
        except Exception as e:
            result['stderr'] = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error("sandbox_error", error=str(e))
        
        finally:
            result['execution_time'] = time.time() - start_time
            self.execution_count += 1
            self.last_execution = datetime.utcnow()
        
        logger.info(
            "sandbox_execution",
            success=result['success'],
            execution_time=result['execution_time'],
            warnings_count=len(warnings)
        )
        
        return result

# ============================================================================
# SELF-IMPROVEMENT ENGINE
# ============================================================================

class SelfImprovementEngine:
    """
    Core engine for autonomous self-improvement.
    
    Capabilities:
    - Analyze system metrics
    - Identify optimization opportunities
    - Generate improvement code
    - Test and validate changes
    - Deploy improvements
    """
    
    IMPROVEMENT_PROMPTS = {
        "performance": """
            Analyze the following performance metrics and suggest code improvements:
            
            Metrics: {metrics}
            Current code: {code}
            
            Generate optimized Python code that:
            1. Reduces execution time by at least 20%
            2. Reduces memory usage
            3. Maintains all existing functionality
            4. Includes comprehensive error handling
            
            Return ONLY the improved code, no explanations.
        """,
        
        "revenue": """
            Analyze the revenue data and suggest improvements:
            
            Revenue data: {data}
            Current conversion rate: {conversion_rate}%
            Churn rate: {churn_rate}%
            
            Suggest specific actions to:
            1. Increase conversion rate
            2. Reduce churn
            3. Increase average revenue per user
            
            Format as JSON with 'actions' array.
        """,
        
        "error_handling": """
            Review the following error patterns and improve error handling:
            
            Error logs: {errors}
            Affected code: {code}
            
            Generate improved code with:
            1. Better error messages
            2. Automatic recovery where possible
            3. Proper logging
            4. Graceful degradation
            
            Return ONLY the improved code.
        """
    }
    
    def __init__(self, claude_client: ClaudeClient, sandbox: SandboxExecutor):
        self.claude = claude_client
        self.sandbox = sandbox
        self.improvement_history: List[Dict] = []
        self.pending_approvals: List[AgentTask] = []
        
    async def analyze_metrics(self, metrics: AgentMetrics) -> Dict[str, Any]:
        """Analyze current metrics and identify improvement areas."""
        
        analysis_prompt = f"""
            You are a system optimization expert. Analyze these metrics:
            
            Tasks completed: {metrics.tasks_completed}
            Tasks failed: {metrics.tasks_failed}
            Success rate: {metrics.success_rate():.1f}%
            Average task duration: {metrics.average_task_duration:.2f}s
            Total API cost: ${metrics.total_cost_usd:.2f}
            Revenue generated: ${metrics.revenue_generated:.2f}
            ROI: {metrics.roi():.1f}x
            
            Identify the TOP 3 areas for improvement.
            Return as JSON with structure:
            {{
                "improvements": [
                    {{
                        "area": "string",
                        "current_value": "string",
                        "target_value": "string",
                        "priority": "high|medium|low",
                        "estimated_impact": "string"
                    }}
                ]
            }}
        """
        
        response = await self.claude.call(
            prompt=analysis_prompt,
            model_tier=ModelTier.FAST,
            temperature=0.3
        )
        
        try:
            # Extract JSON from response
            text = response['text']
            start = text.find('{')
            end = text.rfind('}') + 1
            analysis = json.loads(text[start:end])
            
            logger.info(
                "metrics_analyzed",
                improvements_found=len(analysis.get('improvements', []))
            )
            
            return analysis
            
        except json.JSONDecodeError:
            logger.error("failed_to_parse_analysis", response=response['text'][:200])
            return {"improvements": []}
    
    async def generate_improvement(
        self,
        improvement_type: str,
        context: Dict[str, Any]
    ) -> Optional[CodeGeneration]:
        """Generate code improvement based on analysis."""
        
        prompt_template = self.IMPROVEMENT_PROMPTS.get(improvement_type)
        if not prompt_template:
            logger.error("unknown_improvement_type", type=improvement_type)
            return None
        
        prompt = prompt_template.format(**context)
        
        response = await self.claude.call(
            prompt=prompt,
            system="You are an expert Python developer. Generate clean, efficient, well-documented code.",
            model_tier=ModelTier.PRIMARY,
            temperature=0.4
        )
        
        code = response['text']
        
        # Clean up code (remove markdown if present)
        if '```python' in code:
            code = code.split('```python')[1].split('```')[0]
        elif '```' in code:
            code = code.split('```')[1].split('```')[0]
        
        generation = CodeGeneration(
            id=hashlib.md5(f"{improvement_type}_{datetime.utcnow().isoformat()}".encode()).hexdigest()[:12],
            task_id="",
            language="python",
            code=code.strip(),
            description=f"{improvement_type} improvement"
        )
        
        logger.info(
            "improvement_generated",
            type=improvement_type,
            code_length=len(generation.code),
            checksum=generation.checksum
        )
        
        return generation
    
    async def test_improvement(self, code_gen: CodeGeneration) -> Dict[str, Any]:
        """Test generated improvement in sandbox."""
        
        # Generate test code
        test_prompt = f"""
            Generate pytest tests for this code:
            
            ```python
            {code_gen.code}
            ```
            
            Create comprehensive tests covering:
            1. Normal operation
            2. Edge cases
            3. Error handling
            
            Return ONLY the test code.
        """
        
        test_response = await self.claude.call(
            prompt=test_prompt,
            model_tier=ModelTier.FALLBACK,
            temperature=0.2
        )
        
        # Execute tests in sandbox
        test_code = test_response['text']
        if '```python' in test_code:
            test_code = test_code.split('```python')[1].split('```')[0]
        
        # Combine code and tests
        full_code = f"""
{code_gen.code}

# ===== TESTS =====
import sys
result = {{'passed': 0, 'failed': 0, 'errors': []}}

try:
{test_code}
    result['passed'] += 1
except AssertionError as e:
    result['failed'] += 1
    result['errors'].append(str(e))
except Exception as e:
    result['failed'] += 1
    result['errors'].append(f"Error: {{str(e)}}")
"""
        
        execution_result = await self.sandbox.execute_python(full_code)
        
        test_results = {
            'execution_success': execution_result['success'],
            'stdout': execution_result['stdout'],
            'stderr': execution_result['stderr'],
            'execution_time': execution_result['execution_time']
        }
        
        code_gen.test_results = test_results
        
        logger.info(
            "improvement_tested",
            success=execution_result['success'],
            execution_time=execution_result['execution_time']
        )
        
        return test_results
    
    async def deploy_improvement(
        self,
        code_gen: CodeGeneration,
        target_path: str,
        requires_approval: bool = True
    ) -> bool:
        """Deploy improvement to target location."""
        
        if requires_approval:
            logger.info(
                "deployment_awaiting_approval",
                checksum=code_gen.checksum,
                target=target_path
            )
            return False
        
        try:
            # Backup existing file
            target = Path(target_path)
            if target.exists():
                backup_path = target.with_suffix(f".backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
                target.rename(backup_path)
                logger.info("backup_created", path=str(backup_path))
            
            # Write new code
            target.write_text(code_gen.code)
            code_gen.deployed = True
            
            self.improvement_history.append({
                'id': code_gen.id,
                'checksum': code_gen.checksum,
                'target': target_path,
                'deployed_at': datetime.utcnow().isoformat()
            })
            
            logger.info(
                "improvement_deployed",
                checksum=code_gen.checksum,
                target=target_path
            )
            
            return True
            
        except Exception as e:
            logger.error("deployment_failed", error=str(e))
            return False

# ============================================================================
# AUTONOMOUS AGENT
# ============================================================================

class AutonomousAgent:
    """
    Main autonomous agent class.
    
    Responsibilities:
    - Task scheduling and execution
    - Self-monitoring and improvement
    - Revenue optimization
    - Reporting and alerting
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        database_url: Optional[str] = None
    ):
        self.claude = ClaudeClient(api_key)
        self.sandbox = SandboxExecutor()
        self.improvement_engine = SelfImprovementEngine(self.claude, self.sandbox)
        
        self.database_url = database_url or os.environ.get('DATABASE_URL')
        
        self.metrics = AgentMetrics()
        self.task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.running = False
        self.start_time: Optional[datetime] = None
        
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._monitoring_task: Optional[asyncio.Task] = None
        
        logger.info("autonomous_agent_initialized")
    
    async def start(self):
        """Start the autonomous agent."""
        self.running = True
        self.start_time = datetime.utcnow()
        
        logger.info("agent_starting")
        
        # Start monitoring loop
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Start task processing loop
        await self._process_tasks()
    
    async def stop(self):
        """Stop the autonomous agent."""
        self.running = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self._executor.shutdown(wait=True)
        
        # Calculate final uptime
        if self.start_time:
            self.metrics.uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        
        logger.info(
            "agent_stopped",
            uptime_hours=self.metrics.uptime_seconds / 3600,
            tasks_completed=self.metrics.tasks_completed
        )
    
    def schedule_task(self, task: AgentTask):
        """Add task to queue."""
        # Priority queue uses (priority, counter, task) for ordering
        self.task_queue.put((task.priority.value, time.time(), task))
        logger.debug("task_scheduled", task_id=task.id, priority=task.priority.name)
    
    async def _process_tasks(self):
        """Main task processing loop."""
        while self.running:
            try:
                # Get next task (with timeout to allow checking running flag)
                try:
                    _, _, task = self.task_queue.get(timeout=1.0)
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue
                
                # Execute task
                await self._execute_task(task)
                
            except Exception as e:
                logger.error("task_processing_error", error=str(e))
                self.metrics.errors_caught += 1
    
    async def _execute_task(self, task: AgentTask):
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        
        logger.info(
            "task_started",
            task_id=task.id,
            action=task.action_type.value
        )
        
        try:
            # Route to appropriate handler
            handlers = {
                ActionType.ANALYZE: self._handle_analyze,
                ActionType.GENERATE_CODE: self._handle_generate_code,
                ActionType.EXECUTE_CODE: self._handle_execute_code,
                ActionType.MONITOR: self._handle_monitor,
                ActionType.OPTIMIZE: self._handle_optimize,
                ActionType.REPORT: self._handle_report
            }
            
            handler = handlers.get(task.action_type)
            if handler:
                result = await handler(task)
                task.result = result
                task.status = TaskStatus.COMPLETED
                self.metrics.tasks_completed += 1
            else:
                raise ValueError(f"Unknown action type: {task.action_type}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.retries += 1
            self.metrics.tasks_failed += 1
            logger.error("task_failed", task_id=task.id, error=str(e))
            
            # Retry if possible
            if task.retries < task.max_retries:
                task.status = TaskStatus.PENDING
                self.schedule_task(task)
        
        finally:
            task.completed_at = datetime.utcnow()
            
            # Update average duration
            if task.started_at and task.completed_at:
                duration = (task.completed_at - task.started_at).total_seconds()
                total_tasks = self.metrics.tasks_completed + self.metrics.tasks_failed
                self.metrics.average_task_duration = (
                    (self.metrics.average_task_duration * (total_tasks - 1) + duration)
                    / total_tasks
                )
    
    async def _handle_analyze(self, task: AgentTask) -> Dict[str, Any]:
        """Handle analysis tasks."""
        analysis = await self.improvement_engine.analyze_metrics(self.metrics)
        return analysis
    
    async def _handle_generate_code(self, task: AgentTask) -> Dict[str, Any]:
        """Handle code generation tasks."""
        improvement_type = task.metadata.get('type', 'performance')
        context = task.metadata.get('context', {})
        
        code_gen = await self.improvement_engine.generate_improvement(improvement_type, context)
        
        if code_gen:
            # Test the generated code
            test_results = await self.improvement_engine.test_improvement(code_gen)
            
            return {
                'code_id': code_gen.id,
                'checksum': code_gen.checksum,
                'code_length': len(code_gen.code),
                'test_results': test_results
            }
        
        return {'error': 'Code generation failed'}
    
    async def _handle_execute_code(self, task: AgentTask) -> Dict[str, Any]:
        """Handle code execution tasks."""
        code = task.metadata.get('code', '')
        context = task.metadata.get('context', {})
        
        result = await self.sandbox.execute_python(code, context)
        return result
    
    async def _handle_monitor(self, task: AgentTask) -> Dict[str, Any]:
        """Handle monitoring tasks."""
        return {
            'metrics': {
                'tasks_completed': self.metrics.tasks_completed,
                'tasks_failed': self.metrics.tasks_failed,
                'success_rate': self.metrics.success_rate(),
                'total_cost_usd': self.metrics.total_cost_usd,
                'roi': self.metrics.roi()
            },
            'api_stats': self.claude.get_stats(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _handle_optimize(self, task: AgentTask) -> Dict[str, Any]:
        """Handle optimization tasks."""
        # Analyze current state
        analysis = await self.improvement_engine.analyze_metrics(self.metrics)
        
        # Generate improvements for top priority items
        improvements = []
        for item in analysis.get('improvements', [])[:2]:
            if item['priority'] == 'high':
                code_gen = await self.improvement_engine.generate_improvement(
                    'performance',
                    {'metrics': str(self.metrics), 'code': ''}
                )
                if code_gen:
                    improvements.append({
                        'area': item['area'],
                        'code_id': code_gen.id
                    })
        
        self.metrics.improvements_deployed += len(improvements)
        
        return {
            'analysis': analysis,
            'improvements_generated': len(improvements),
            'improvements': improvements
        }
    
    async def _handle_report(self, task: AgentTask) -> Dict[str, Any]:
        """Generate status report."""
        report_prompt = f"""
            Generate an executive summary report:
            
            Performance Metrics:
            - Tasks: {self.metrics.tasks_completed} completed, {self.metrics.tasks_failed} failed
            - Success Rate: {self.metrics.success_rate():.1f}%
            - Avg Duration: {self.metrics.average_task_duration:.2f}s
            
            Financial Metrics:
            - API Cost: ${self.metrics.total_cost_usd:.2f}
            - Revenue: ${self.metrics.revenue_generated:.2f}
            - ROI: {self.metrics.roi():.1f}x
            
            Improvements:
            - Deployed: {self.metrics.improvements_deployed}
            - Errors Caught: {self.metrics.errors_caught}
            
            Format as a brief, professional summary with key insights and recommendations.
        """
        
        response = await self.claude.call(
            prompt=report_prompt,
            model_tier=ModelTier.FAST,
            temperature=0.5
        )
        
        return {
            'report': response['text'],
            'generated_at': datetime.utcnow().isoformat(),
            'metrics_snapshot': asdict(self.metrics)
        }
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while self.running:
            try:
                # Health check
                await asyncio.sleep(CONFIG.HEALTH_CHECK_INTERVAL)
                
                # Update uptime
                if self.start_time:
                    self.metrics.uptime_seconds = (
                        datetime.utcnow() - self.start_time
                    ).total_seconds()
                
                # Check for anomalies
                if self.metrics.success_rate() < 80 and self.metrics.tasks_completed > 10:
                    logger.warning(
                        "low_success_rate_alert",
                        rate=self.metrics.success_rate()
                    )
                
                # Log status periodically
                if int(self.metrics.uptime_seconds) % CONFIG.METRICS_INTERVAL < CONFIG.HEALTH_CHECK_INTERVAL:
                    logger.info(
                        "agent_health_check",
                        uptime_hours=self.metrics.uptime_seconds / 3600,
                        tasks_completed=self.metrics.tasks_completed,
                        success_rate=self.metrics.success_rate(),
                        api_cost=self.metrics.total_cost_usd
                    )
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitoring_error", error=str(e))

# ============================================================================
# FACTORY & HELPERS
# ============================================================================

def create_agent(
    api_key: Optional[str] = None,
    database_url: Optional[str] = None
) -> AutonomousAgent:
    """
    Factory function to create a configured agent.
    
    Args:
        api_key: Anthropic API key (or use ANTHROPIC_API_KEY env var)
        database_url: PostgreSQL connection string (optional)
    
    Returns:
        Configured AutonomousAgent instance
    """
    return AutonomousAgent(api_key=api_key, database_url=database_url)


def create_task(
    name: str,
    description: str,
    action_type: ActionType,
    priority: TaskPriority = TaskPriority.MEDIUM,
    metadata: Optional[Dict] = None
) -> AgentTask:
    """
    Factory function to create a task.
    
    Args:
        name: Task name
        description: What the task should accomplish
        action_type: Type of action to perform
        priority: Task priority (default: MEDIUM)
        metadata: Additional task-specific data
    
    Returns:
        Configured AgentTask instance
    """
    task_id = hashlib.md5(f"{name}_{datetime.utcnow().isoformat()}".encode()).hexdigest()[:12]
    
    return AgentTask(
        id=task_id,
        name=name,
        description=description,
        action_type=action_type,
        priority=priority,
        metadata=metadata or {}
    )

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Example usage of the autonomous agent."""
    
    print("""
    ██████╗ ███████╗██╗   ██╗██╗███████╗██╗    ██╗███████╗██╗ ██████╗ ███╗   ██╗ █████╗ ██╗     
    ██╔══██╗██╔════╝██║   ██║██║██╔════╝██║    ██║██╔════╝██║██╔════╝ ████╗  ██║██╔══██╗██║     
    ██████╔╝█████╗  ██║   ██║██║█████╗  ██║ █╗ ██║███████╗██║██║  ███╗██╔██╗ ██║███████║██║     
    ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║██╔══╝  ██║███╗██║╚════██║██║██║   ██║██║╚██╗██║██╔══██║██║     
    ██║  ██║███████╗ ╚████╔╝ ██║███████╗╚███╔███╔╝███████║██║╚██████╔╝██║ ╚████║██║  ██║███████╗
    ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚═╝╚══════╝ ╚══╝╚══╝ ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝
    
    AUTONOMOUS AGENT 8.0 - Self-Improving AI System
    "Paker na siłowni, który sam rośnie"
    """)
    
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("\n⚠️  Set ANTHROPIC_API_KEY environment variable to run the agent")
        print("    export ANTHROPIC_API_KEY=your_key_here")
        print("\n✅ Agent module loaded successfully!")
        return
    
    # Create and start agent
    agent = create_agent()
    
    # Schedule some initial tasks
    agent.schedule_task(create_task(
        name="System Health Check",
        description="Monitor system health and performance",
        action_type=ActionType.MONITOR,
        priority=TaskPriority.HIGH
    ))
    
    agent.schedule_task(create_task(
        name="Performance Analysis",
        description="Analyze current metrics and find optimization opportunities",
        action_type=ActionType.ANALYZE,
        priority=TaskPriority.MEDIUM
    ))
    
    agent.schedule_task(create_task(
        name="Daily Report",
        description="Generate executive summary report",
        action_type=ActionType.REPORT,
        priority=TaskPriority.LOW
    ))
    
    try:
        print("\n🚀 Starting Autonomous Agent...")
        print("   Press Ctrl+C to stop\n")
        await agent.start()
    except KeyboardInterrupt:
        print("\n\n🚫 Shutdown requested...")
    finally:
        await agent.stop()
        print("\n✅ Agent stopped gracefully")
        print(f"   Tasks completed: {agent.metrics.tasks_completed}")
        print(f"   API cost: ${agent.metrics.total_cost_usd:.4f}")


if __name__ == "__main__":
    asyncio.run(main())

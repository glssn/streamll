# StreamLL Task Backlog

## Epic: Module Version Tracking and Change Detection

### Task: Implement Module Version Tracking for Trace Correlation

**Priority**: Medium
**Story Points**: 8
**Labels**: observability, tracing, versioning, feature

**Description**:
Add capability to detect when DSPy modules have changed between traces, enabling correlation of performance/behavior changes with code updates. When a team updates their module (e.g., adds an extra data lookup in `forward()`), StreamLL should be able to identify that traces come from different versions.

**Problem Statement**:
Currently, StreamllEvent captures module_name but has no way to detect if the module's implementation has changed. This makes it impossible to:
- Correlate performance regressions with code changes
- Identify which version of a module generated specific traces
- Detect when teams are running outdated module versions
- A/B test different module implementations

**Proposed Solutions**:

**Option 1: Module Source Code Hashing**
```python
import hashlib
import inspect

def get_module_signature(module):
    source = inspect.getsource(module.__class__)
    return hashlib.sha256(source.encode()).hexdigest()[:12]
```
- ✅ Detects any code change
- ✅ Works in any environment
- ❌ Changes with whitespace/comments
- ❌ Requires source code access

**Option 2: Method Signature Hashing**
```python
def get_module_signature(module):
    methods = inspect.getmembers(module, predicate=inspect.ismethod)
    signatures = [f"{name}:{inspect.signature(method)}" for name, method in methods]
    combined = "|".join(sorted(signatures))
    return hashlib.sha256(combined.encode()).hexdigest()[:12]
```
- ✅ Stable across formatting changes
- ✅ Detects API changes
- ❌ Misses implementation changes
- ❌ Complex for nested classes

**Option 3: Git-Based Versioning**
```python
import subprocess

def get_git_version():
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain']).decode().strip()
    return f"{commit}{'-dirty' if dirty else ''}"
```
- ✅ Precise version tracking
- ✅ Integrates with CI/CD
- ❌ Only works in git repos
- ❌ Doesn't work in production containers

**Option 4: Package Version + File Modification Time**
```python
def get_module_version(module):
    package = module.__module__.split('.')[0]
    version = pkg_resources.get_distribution(package).version
    file_path = inspect.getfile(module.__class__)
    mtime = os.path.getmtime(file_path)
    return f"{version}:{int(mtime)}"
```
- ✅ Works with installed packages
- ✅ Simple to implement
- ❌ mtime unreliable in containers
- ❌ Doesn't detect dependency changes

**Option 5: AST-Based Hashing (Recommended)**
```python
import hashlib
import inspect
import ast

def get_forward_ast_hash(module):
    """Hash the AST of forward() - ignores whitespace/comments"""
    try:
        forward_method = getattr(module, 'forward', None)
        if not forward_method:
            return None
            
        # Get source and parse to AST
        source = inspect.getsource(forward_method)
        tree = ast.parse(source)
        
        # Convert AST to string representation
        ast_dump = ast.dump(tree, annotate_fields=False)
        
        # Hash the AST representation
        return hashlib.sha256(ast_dump.encode()).hexdigest()[:12]
    except (OSError, TypeError, SyntaxError):
        return None
```
- ✅ Ignores whitespace/comments
- ✅ Pure Python, no dependencies
- ✅ Fast with caching
- ✅ Works in any environment
- ❌ Only tracks forward() changes

**Option 6: AST with Dependencies**
```python
def get_forward_with_deps_hash(module):
    """Hash forward() plus any methods it calls"""
    source = inspect.getsource(module.__class__)
    tree = ast.parse(source)
    
    # Find forward and methods it calls
    called_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'forward':
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        if getattr(child.func.value, 'id', None) == 'self':
                            called_methods.add(child.func.attr)
    
    # Hash forward + dependencies
    methods_to_hash = ['forward'] + list(called_methods)
    # ... extract and hash relevant method ASTs
```

**Acceptance Criteria**:
- [ ] Extend StreamllEvent model with version tracking fields
- [ ] Implement version detection mechanism (configurable strategy)
- [ ] Version info automatically captured in start/end events
- [ ] Documentation on how to use version tracking for analysis
- [ ] Example queries for detecting performance regressions between versions
- [ ] Unit tests for version detection methods
- [ ] Integration test showing version change detection

**Technical Details**:
- Add fields to StreamllEvent: `module_version`, `code_signature`, `git_commit`
- Make version tracking opt-in (performance considerations)
- Cache version calculations per module instance
- Consider storing version mapping separately to reduce event size

**Use Cases**:
1. **Performance Regression Detection**: "Module X became 20% slower after commit abc123"
2. **Canary Deployments**: "5% of traffic running new version has higher error rate"
3. **Dependency Impact**: "Upgrading pandas from 1.3 to 2.0 broke our data pipeline"
4. **Development Debugging**: "This trace came from my local changes, not production"

**Definition of Done**:
- Module version tracking implemented and tested
- Performance impact < 5ms per event
- Documentation includes analysis examples
- Can differentiate between identical module names with different implementations

**Dependencies**: 
- None

**Implementation Approach**:
```python
class ModuleVersionTracker:
    def __init__(self, strategy='ast'):
        self.strategy = strategy
        self._cache = {}
    
    def get_version(self, module):
        """Get cached version or compute it"""
        module_id = id(module)
        
        if module_id not in self._cache:
            if self.strategy == 'ast':
                version = get_forward_ast_hash(module)
            elif self.strategy == 'source':
                version = get_forward_signature(module)
            else:
                version = None
                
            self._cache[module_id] = version
            
        return self._cache[module_id]

# In decorator/integration
def trace_decorator(func):
    def wrapper(self, *args, **kwargs):
        version = version_tracker.get_version(self)
        event = StreamllEvent(
            module_version=version,
            # ... other fields
        )
        # ... rest of tracing logic
    return wrapper
```

**Estimator Notes**:
AST-based hashing (Option 5) is recommended as it balances accuracy, performance, and simplicity. It ignores formatting changes while detecting actual logic changes. Start with forward() only, add dependency tracking if needed later.

---

## Epic: Kafka Integration Documentation & DSPy Context

### Task: Enhance Kafka Documentation for DSPy Streaming Context

**Priority**: Medium
**Story Points**: 5
**Labels**: documentation, kafka, dspy-integration

**Description**:
Enhance the Kafka sink documentation to better explain its role in DSPy module observability and provide practical integration patterns specific to StreamLL's use case as a lightweight streaming layer for AI/LLM operations.

**Problem Statement**:
Current Kafka documentation focuses heavily on Kafka configuration but lacks DSPy-specific context. Users need to understand:
- Why choose Kafka over Redis/RabbitMQ for DSPy observability
- How StreamllEvent schema integrates with their data pipeline
- Practical patterns for consuming and analyzing DSPy execution streams

**Acceptance Criteria**:
- [ ] Add "Why Kafka for DSPy Observability" section explaining use cases
- [ ] Document StreamllEvent to Kafka JSON schema mapping with examples
- [ ] Add cloud provider authentication examples:
  - [ ] SASL/PLAIN for Confluent Cloud
  - [ ] IAM auth for AWS MSK
  - [ ] Connection strings for Azure Event Hubs
  - [ ] Basic SSL/TLS setup
- [ ] Create DSPy-specific integration patterns:
  - [ ] Streaming token-by-token LLM responses
  - [ ] Capturing DSPy optimizer events
  - [ ] Filtering which operations to stream
  - [ ] Replaying DSPy executions from Kafka
- [ ] Add practical consumer examples:
  - [ ] Python consumer reconstructing DSPy execution flow
- [ ] Document circuit breaker behavior clearly:
  - [ ] What happens to events when circuit is open
  - [ ] Recovery behavior
  - [ ] Monitoring circuit state
  - [ ] Tuning guidance
##### optional:
- [ ] Add deployment examples:
  - [ ] Docker Compose with DSPy app + Redpanda + consumer
  - [ ] Environment variable configuration
  - [ ] How to disable streaming in tests
- [ ] Document performance impact:
  - [ ] Overhead added to DSPy calls
  - [ ] Memory usage with different buffer sizes
  - [ ] Sync vs async flushing guidelines

**Technical Details**:
- Focus on StreamllEvent Pydantic model alignment
- Show how `schema_version: "1.0"` enables schema evolution
- Include examples of consumer-side validation using same Pydantic model
- Emphasize that StreamLL is observability, not infrastructure management

**Use Cases**:
1. **Token Cost Tracking**: Consume events to calculate OpenAI/Anthropic costs
2. **Performance Analysis**: Identify slow DSPy modules from event streams
3. **Debugging**: Replay failed DSPy executions from Kafka events
4. **Compliance**: Audit trail of all LLM interactions

**Definition of Done**:
- Kafka documentation includes clear DSPy context
- At least 3 practical consumer examples
- Cloud authentication examples for major providers
- Circuit breaker behavior fully documented
- Performance impact guidelines included

**Dependencies**: 
- Existing KafkaSink implementation

**Estimator Notes**:
Build on existing kafka-sink.md but add the missing DSPy context. Focus on practical examples that show value of streaming DSPy events to Kafka specifically.

---

## Epic: Production-Ready Sink Documentation

### Task: Create Cloud Provider-Specific Production Guides

**Priority**: High
**Story Points**: 5
**Labels**: documentation, production, onboarding

**Description**:
Create sink-focused production deployment guides that explicitly mention major cloud providers and managed services. This will help engineers quickly identify if StreamLL works with their existing infrastructure.

**Acceptance Criteria**:
- [ ] Create `docs/production/redis.md` with AWS ElastiCache, Azure Cache for Redis, Google Cloud Memorystore sections
- [ ] Create `docs/production/rabbitmq.md` with Amazon MQ for RabbitMQ, CloudAMQP, Azure Service Bus sections  
- [ ] Create `docs/production/kafka.md` with Amazon MSK, Confluent Cloud, Azure Event Hubs sections
- [ ] Each cloud service section includes:
  - [ ] Exact connection string format with realistic examples
  - [ ] Authentication configuration (IAM/managed identity where applicable)
  - [ ] Known limitations specific to that service
  - [ ] Tested versions/engine compatibility
  - [ ] Performance characteristics observed in testing
- [ ] Add SEO-friendly cloud service names in section headers
- [ ] Include troubleshooting section for common cloud-specific issues

**Technical Details**:
- Use existing StreamLL sink classes as foundation
- Reference performance benchmarks from existing tests (Redis 12x pipeline speedup, RabbitMQ 1.5x batching)
- Include connection string examples that work out-of-the-box
- Mention specific service limitations (e.g., ElastiCache Serverless Redis command support)

**Definition of Done**:
- Documentation published in `/docs/production/`
- At least one fully worked example per major cloud provider (AWS, Azure, GCP)
- Technical review completed by team lead
- Links added to main README.md

**Dependencies**: 
- None

**Estimator Notes**:
Focus on documenting what already works rather than implementing new features. Primary effort is research into cloud service specifics and creating accurate examples.

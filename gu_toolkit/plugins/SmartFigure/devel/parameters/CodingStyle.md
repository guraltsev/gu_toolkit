# CodingStyle.md - Python Code Guidelines for LLM Generation

## 1. Core Principles

### Essential Requirements
- **Clarity First**: Write code that is easy to understand and maintain
- **Type Safety**: Use comprehensive type hints throughout
- **Minimal Complexity**: Implement the simplest solution that meets requirements
- **Complete Documentation**: Document all public interfaces with examples
- **Educational Focus**: Code should demonstrate good practices

### Anti-Patterns to Avoid
- Overly clever or obfuscated implementations
- Premature optimization without profiling
- Deep inheritance hierarchies (prefer composition)
- Global state or mutable module-level variables
- Reinventing standard library functionality

## 2. Code Structure

### Module Organization
```python
"""
Module: [module_name].py

DESIGN OVERVIEW:
===============
1. Purpose and scope of the module
2. Key components and their responsibilities
3. Data flow and interaction patterns
4. Extension points and customization options

API REFERENCE:
==============
[Class/Function listings with brief descriptions]

MAINTENANCE GUIDE:
=================
- Key assumptions and constraints
- Performance considerations
- Testing strategy
- Common extension patterns
"""

# Imports grouped by: stdlib → third-party → local
import os
import sys
from typing import Any, Optional, Union
from dataclasses import dataclass

# Type aliases for domain clarity
ItemID = str
ResultSet = list[dict[str, Any]]

# Constants with descriptive names
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
```

### File Structure Template
```python
"""Module docstring as above"""

# Imports
# Constants
# Type definitions
# Main classes
# Public functions
# Private helpers (prefixed with _)
```

## 3. Type Annotations

### Required Type Hints
```python
from typing import TypeVar, Generic, Optional, Protocol

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# Define protocols for behavior contracts
class Renderable(Protocol):
    """Protocol for objects that can be rendered."""
    def render(self) -> str: ...

def process_items(
    items: list[T],
    processor: Callable[[T], V],
    timeout: int = DEFAULT_TIMEOUT
) -> list[V]:
    """Process items with timeout protection."""
    pass
```

### Type Rules
1. All function parameters must have type hints
2. Return types must be explicitly declared
3. Use `Optional[X]` for nullable returns, not implicit `None`
4. Avoid `Any` when possible; use `Union` or create proper types
5. Define domain-specific type aliases for clarity

## 4. Documentation Standards

### Module Documentation (Required)
```python
"""
Module: data_processor.py

DESIGN OVERVIEW:
===============
Primary responsibility: Transform raw data into structured format.

Components:
- DataLoader: Handles input from various sources
- Transformer: Applies processing rules
- Validator: Ensures data quality
- Exporter: Outputs processed data

Data Flow:
1. Load → 2. Transform → 3. Validate → 4. Export

Extension Points:
- Custom transformers via Transformer protocol
- New validators by subclassing BaseValidator
- Alternative exporters implementing Exporter interface

API REFERENCE:
==============
DataProcessor: Main orchestrator class
    Methods:
    - process(source: Source, rules: Rules) -> Result
    - validate(result: Result) -> bool
    
load_data(): Utility for common data formats

MAINTENANCE GUIDE:
=================
Performance Notes:
- Processing is O(n) with n items
- Memory usage scales with batch size
- Consider streaming for large datasets

Testing Strategy:
- Unit tests for each component
- Integration tests for full pipeline
- Property-based tests for edge cases
"""
```

### Class Documentation Template
```python
class DataProcessor:
    """
    Orchestrates data processing pipeline.
    
    Coordinates loading, transformation, validation, and export
    of data according to provided rules.
    
    Example:
    >>> processor = DataProcessor()
    >>> result = processor.process("data.csv", csv_rules)
    >>> processor.validate(result)
    True
    
    API Reference:
    ------------
    Properties:
        stats: ProcessingStatistics - Runtime metrics
        errors: list[Error] - Collected processing errors
        
    Methods:
        process(source: Source, rules: Rules) -> Result
        validate(result: Result) -> bool
        reset() -> None
        
    Developer's Guide:
    ----------------
    Extension Points:
    1. Add new source type:
       - Implement Source protocol
       - Register with SourceRegistry
       
    2. Custom validation:
       - Subclass BaseValidator
       - Add to validator chain
       
    Performance Notes:
    - Caches expensive transformations
    - Uses lazy evaluation where possible
    - Thread-safe for concurrent reads
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        """
        Initialize processor with optional configuration.
        
        Args:
            config: Processor configuration. Uses defaults if None.
            
        Raises:
            ConfigurationError: Invalid configuration values
            
        Example:
        >>> config = Config(timeout=60)
        >>> processor = DataProcessor(config)
        """
        self._config = config or Config()
        self._initialize_components()
    
    def process(self, source: Source, rules: Rules) -> Result:
        """
        Execute full processing pipeline.
        
        Args:
            source: Data source to process
            rules: Processing rules to apply
            
        Returns:
            Processed result with metadata
            
        Raises:
            SourceError: Unreadable or invalid source
            ProcessingError: Transformation failure
            
        Example:
        >>> result = processor.process(file_source, json_rules)
        >>> len(result.items)
        150
        """
        # Implementation...
```

### Function Documentation
```python
def transform_data(
    input_data: InputType,
    transformer: Transformer,
    options: Optional[TransformOptions] = None
) -> OutputType:
    """
    Apply transformation to input data.
    
    Args:
        input_data: Data to transform
        transformer: Transformation logic
        options: Optional transformation parameters
        
    Returns:
        Transformed data
        
    Raises:
        ValueError: Invalid input format
        TransformationError: Unrecoverable transform failure
        
    Examples:
    >>> result = transform_data(raw_data, json_transformer)
    >>> result.is_valid()
    True
    
    >>> transform_data(None, json_transformer)
    Traceback (most recent call last):
        ...
    ValueError: input_data cannot be None
    """
    if input_data is None:
        raise ValueError("input_data cannot be None")
    
    # Implementation...
```

### Private Members (Minimal Documentation)
```python
def _parse_config(self, raw: dict) -> Config:
    """Parse raw config dict into Config object."""
    # Implementation...
    
def _validate_output(self, output: OutputType) -> bool:
    """
    Internal validation logic.
    
    Returns True if output meets quality thresholds.
    """
    # Implementation...
```

## 5. Testing Requirements

### Doctest Standards
```python
def calculate_total(items: list[Item], discount: float = 0.0) -> float:
    """
    Calculate total cost with optional discount.
    
    Args:
        items: List of priced items
        discount: Percentage discount (0.0 to 1.0)
        
    Returns:
        Final total after discount
        
    Examples:
    >>> calculate_total([Item(price=10), Item(price=20)])
    30.0
    
    >>> calculate_total([Item(price=100)], discount=0.1)
    90.0
    
    Error cases:
    >>> calculate_total([], discount=1.5)
    Traceback (most recent call last):
        ...
    ValueError: Discount must be between 0 and 1
    
    Performance check:
    >>> import timeit
    >>> timeit.timeit(lambda: calculate_total([Item(price=i) for i in range(100)]))
    < 0.001  # Should be fast for 100 items
    """
    if not 0 <= discount <= 1:
        raise ValueError("Discount must be between 0 and 1")
    
    subtotal = sum(item.price for item in items)
    return subtotal * (1 - discount)
```

## 6. Naming Conventions

### Standard Patterns
- **Classes**: `Noun` or `NounVerb` (e.g., `DataProcessor`, `FileLoader`)
- **Methods**: `verb_noun` (e.g., `process_data`, `validate_input`)
- **Functions**: `action_descriptor` (e.g., `calculate_total`, `format_output`)
- **Variables**: Descriptive nouns (e.g., `user_count`, `config_file`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_PORT`)

### Prefix/Suffix Conventions
- `is_`, `has_`, `can_` for boolean values/methods
- `_` prefix for private members
- `_` suffix to avoid keyword conflicts (rarely needed)
- Avoid single-letter names except in mathematical contexts or loops

## 7. Error Handling

### Validation Pattern
```python
def validate_config(config: dict) -> Config:
    """
    Validate and normalize configuration.
    
    Args:
        config: Raw configuration dictionary
        
    Returns:
        Validated Config object
        
    Raises:
        ConfigurationError: For any invalid values
        ValueError: For malformed structure
    """
    required_keys = {"host", "port", "timeout"}
    missing = required_keys - config.keys()
    
    if missing:
        raise ValueError(f"Missing required keys: {missing}")
    
    if not isinstance(config["port"], int):
        raise ConfigurationError("Port must be integer")
    
    if config["timeout"] <= 0:
        raise ConfigurationError("Timeout must be positive")
    
    return Config(**config)
```

### Exception Guidelines
1. Use built-in exceptions when appropriate (ValueError, TypeError)
2. Create custom exceptions for domain-specific errors
3. Include relevant context in error messages
4. Document all raised exceptions in docstrings
5. Clean up resources in `finally` blocks when needed

## 8. Performance Guidelines

### Optimization Rules
1. **Measure First**: Profile before optimizing
2. **Algorithm First**: Improve complexity before constants
3. **Cache Judiciously**: Only cache expensive, repeated operations
4. **Lazy Evaluation**: Consider for potentially unused computations
5. **Batch Operations**: Prefer batch processing over single-item loops

### Example
```python
def process_batch(items: list[Item]) -> list[Result]:
    """
    Process items in batch for efficiency.
    
    Performance Notes:
    - O(n) time complexity
    - Memory usage scales with batch size
    - Consider chunking for very large lists
    """
    # Batch implementation...
```

## 9. Extension Patterns

### Plugin Architecture
```python
class PluginRegistry:
    """Manages extensible plugin system."""
    
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
    
    def register(self, name: str, plugin: Plugin) -> None:
        """Register plugin for extension point."""
        self._plugins[name] = plugin
    
    def get_plugin(self, name: str) -> Plugin:
        """Retrieve plugin by name."""
        return self._plugins[name]
```

## 10. Complete Template

```python
"""
Module: [module_name].py

DESIGN OVERVIEW:
===============
[Concise design documentation]

API REFERENCE:
==============
[API listing]

MAINTENANCE GUIDE:
=================
[Maintenance notes]
"""

import os
from typing import Optional, Protocol

# Type definitions
Result = dict[str, any]

class Processor(Protocol):
    """Protocol for data processors."""
    def process(self, data: any) -> Result: ...

class DataHandler:
    """
    Main handler for data operations.
    
    Example:
    >>> handler = DataHandler()
    >>> result = handler.process_input("test")
    >>> result["status"]
    'processed'
    
    API Reference:
    ------------
    Methods:
        process_input(data: any) -> Result
        validate_result(result: Result) -> bool
        
    Developer's Guide:
    ----------------
    [Extension and maintenance notes]
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize with optional configuration."""
        self.config = config or default_config
    
    def process_input(self, data: any) -> Result:
        """
        Process input data.
        
        Args:
            data: Input to process
            
        Returns:
            Processing result
            
        Example:
        >>> handler.process_input({"test": "data"})
        {"status": "success", "processed": True}
        """
        # Implementation...
    
    def _internal_helper(self) -> None:
        """Brief private method docs."""
        pass

def utility_function(value: str) -> int:
    """
    Utility function example.
    
    Example:
    >>> utility_function("123")
    123
    """
    return int(value)
```

## 11. Code Review Checklist

- [ ] Type hints present for all public interfaces
- [ ] Documentation includes purpose, examples, and API reference
- [ ] Doctests cover normal and edge cases
- [ ] No magic numbers (use named constants)
- [ ] Error handling for invalid inputs
- [ ] Performance considerations documented
- [ ] Extension points identified
- [ ] Single responsibility principle followed
- [ ] Tests pass including doctests
- [ ] Avoids overengineering (simplest working solution)

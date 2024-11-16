import pytest
import asyncio
from decouple import config
from src.streaming_code_generator import (
    StreamingCodeGenerator,
    StreamStatus,
    APIError,
    StreamProcessError
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API key from environment
API_KEY = config('OPENAI_API_KEY')

@pytest.fixture
def generator():
    """Create a generator instance with real API key"""
    return StreamingCodeGenerator(
        api_key=API_KEY,
        model="gpt-3.5-turbo",
        timeout=30,
        chunk_size=1024
    )

class StreamCollector:
    """Helper class to collect stream data and progress updates"""
    def __init__(self):
        self.chunks = []
        self.progress_updates = []
    
    def chunk_callback(self, chunk: str):
        self.chunks.append(chunk)
        
    def progress_callback(self, stats):
        self.progress_updates.append({
            'chunks': stats.chunks_processed,
            'status': stats.status
        })

@pytest.mark.asyncio
async def test_simple_code_generation(generator):
    """
    This test verifies the basic functionality of generating a simple code snippet from a prompt.
    It tests whether the generated code contains expected elements (like def and return), checks the response structure (text, stats, and completion time), and ensures that the streaming process works correctly by validating progress updates.
    """
    collector = StreamCollector()
    
    prompt = "Write a simple Python function that adds two numbers"
    
    try:
        result = await generator.generate_code_with_explanation(
            prompt=prompt,
            callback=collector.chunk_callback,
            progress_callback=collector.progress_callback
        )
        
         # Check if the result is in the expected structure
        assert isinstance(result, dict)
        assert all(key in result for key in ['text', 'stats', 'completion_time'])
        
        # Content validation: Check if the generated code contains the function definition and return statement
        generated_code = result['text']
        assert 'def' in generated_code  # Should contain function definition
        assert 'return' in generated_code  # Should contain return statement
        
        # Stats validation: Check if the streaming stats are correct
        assert result['stats'].status == StreamStatus.COMPLETED
        assert result['stats'].chunks_processed > 0
        assert result['stats'].total_tokens > 0
        assert result['completion_time'] > 0
        
        # Validate progress tracking: Ensure that progress updates were collected
        assert len(collector.progress_updates) > 0
        assert collector.progress_updates[-1]['status'] == StreamStatus.COMPLETED
        
        logger.info(f"Generated code:\n{generated_code}")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

@pytest.mark.asyncio
async def test_timeout_handling():
    """
    This test ensures that the system handles timeout scenarios correctly.
    It creates a generator instance with a very short timeout and tests how the system behaves when a long-running task exceeds the timeout period. The test expects an APIError to be raised in this case.
    """
    # Create generator with very short timeout
    short_timeout_generator = StreamingCodeGenerator(
        api_key=API_KEY,
        timeout=0.001  # Extremely short timeout to force timeout error
    )
    
    collector = StreamCollector()
    
    # Use a long, complex prompt to increase processing time
    prompt = """Write a complex Python program that implements:
    1. A binary search tree with full balancing
    2. Methods for insertion, deletion, and traversal
    3. Complete error handling and edge cases
    4. Comprehensive documentation and type hints
    5. Multiple example use cases and test cases
    Please provide detailed explanations for each part.
    """
    
    try:
        await short_timeout_generator.generate_code_with_explanation(
            prompt=prompt,
            callback=collector.chunk_callback,
            max_retries=1
        )
        # If no error occurs, the test should fail
  
        pytest.fail("Expected APIError was not raised")
    except APIError as e:
        # If APIError is raised, check the message
        assert "Failed after 1 attempts" in str(e)
    except Exception as e:
        pytest.fail(f"Wrong exception type raised: {type(e).__name__}")

@pytest.mark.asyncio
async def test_complex_code_generation(generator):
    """
        This test validates the generation of more complex code and checks the quality of the generated code.
        The test ensures that the generated code includes the necessary structure (function definitions, type hints, docstrings) and checks whether streaming is correctly handled by validating the chunking process.
    """
    collector = StreamCollector()
    
    prompt = """
    Write a Python function that:
    1. Takes a list of numbers
    2. Filters out negative numbers
    3. Squares the remaining numbers
    4. Returns the sum of the squares
    Include docstring and type hints.
    """
    
    try:
        result = await generator.generate_code_with_explanation(
            prompt=prompt,
            callback=collector.chunk_callback,
            progress_callback=collector.progress_callback
        )
        
        generated_code = result['text']
        
        # Validate code quality
        assert 'def' in generated_code
        assert 'list' in generated_code.lower()  # Should mention list in type hints or docstring
        assert 'return' in generated_code
        assert '"""' in generated_code or "'''" in generated_code  # Should have docstring
        
        # Validate streaming worked properly
        assert len(collector.chunks) > 0
        assert result['stats'].chunks_processed == len(collector.chunks)
        
        logger.info(f"Generated complex code:\n{generated_code}")
        
    except Exception as e:
        logger.error(f"Complex code generation failed: {str(e)}")
        raise

@pytest.mark.asyncio
async def test_concurrent_requests(generator):
    """
        This test verifies that the system can handle multiple concurrent requests to generate code from different prompts.
        The test runs several code generation requests concurrently and ensures that each request is processed successfully and that the results are correct.
    """
    async def generate_code(prompt):
        collector = StreamCollector()
        return await generator.generate_code_with_explanation(prompt, collector.chunk_callback)
    
    prompts = [
        "Write a function to calculate factorial",
        "Write a function to check if a number is prime",
        "Write a function to reverse a string"
    ]
    
    try:
        # Run concurrent requests
        results = await asyncio.gather(
            *[generate_code(prompt) for prompt in prompts]
        )
        
        # Verify all requests completed successfully
        assert len(results) == len(prompts)
        for result in results:
            assert result['stats'].status == StreamStatus.COMPLETED
            assert result['completion_time'] > 0
            
    except Exception as e:
        logger.error(f"Concurrent requests test failed: {str(e)}")
        raise



def test_format_chunk_validation(generator):
    """
      Test how individual chunks of data are formatted before being processed.
      This test checks how chunks are formatted before being processed.
    """
    # Test valid chunk
    valid_chunk = type('Chunk', (), {
        'choices': [type('Choice', (), {
            'delta': type('Delta', (), {'content': 'test'})()
        })()]
    })()
    assert generator.format_chunk(valid_chunk) == 'test'
    
    # Test empty chunk
    empty_chunk = type('Chunk', (), {
        'choices': [type('Choice', (), {
            'delta': type('Delta', (), {'content': ''})()
        })()]
    })()
    assert generator.format_chunk(empty_chunk) == ''
    
    # Test malformed chunk
    malformed_chunk = type('Chunk', (), {'choices': []})()
    assert generator.format_chunk(malformed_chunk) == ''

if __name__ == "__main__":
    logging.info("Running StreamingCodeGenerator tests...")
    pytest.main([__file__, "-v"])
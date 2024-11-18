import asyncio
import time
from typing import AsyncIterator, Callable, Any, Dict, Optional
from openai import OpenAI
from openai.types.completion import Completion
from dataclasses import dataclass
from decouple import config
from enum import Enum
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Different states the streaming process can be in
class StreamStatus(Enum):
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class StreamStats:
    start_time: float
    chunks_processed: int = 0
    total_tokens: int = 0
    status: StreamStatus = StreamStatus.INITIALIZING

class StreamingError(Exception):
    """Base exception for streaming errors"""
    pass

class APIError(StreamingError):
    """API-related errors"""
    pass

class StreamProcessError(StreamingError):
    """Stream processing errors"""
    pass

class StreamingCodeGenerator:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        timeout: int = 60,
        chunk_size: int = 1024
    ):
        """
        Initialize the StreamingCodeGenerator with configurations.
        
        Args:
            api_key: OpenAI API key
            model: Model to use for generation
            timeout: Request timeout in seconds
            chunk_size: Size of chunks to process
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.timeout = timeout
        self.chunk_size = chunk_size
        self.stats = None

    async def generate_code_with_explanation(
        self,
        prompt: str,
        callback: Callable[[str], None],
        max_retries: int = 3,
        progress_callback: Optional[Callable[[StreamStats], None]] = None
    ) -> Dict[str, Any]:
        """
        Stream code generation and explanation with progress tracking.
        
        Args:
            prompt: Description of code to generate
            callback: Function to handle each stream chunk
            max_retries: Maximum number of retry attempts
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing final response and statistics
        """
        self.stats = StreamStats(start_time=time.time())

         # Attempt multiple retries in case of an error
        for attempt in range(max_retries):
            try:
                # Update the status to show processing has started
                self.stats.status = StreamStatus.PROCESSING

                # Request to the OpenAI API to create a chat completion (with streaming enabled)
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert code developer. Your task is to generate  codes and provide clear explanations of the code in real-time. Ensure that the code you produce is efficient and follows best practices. The output should be structured and easy to understand, suitable for both beginners and experienced developers."}
,
                        {"role": "user", "content": prompt}
                    ],
                    stream=True,
                    timeout=self.timeout
                )

                # Handle the streaming response
                final_response = await self.handle_stream(
                    stream,
                    callback,
                    progress_callback
                )

                 # If successful, update status to completed and return results
                self.stats.status = StreamStatus.COMPLETED
                return {
                    "text": final_response,
                    "stats": self.stats,
                    "completion_time": time.time() - self.stats.start_time
                }
            # Handle any exceptions that may occur during the request
            except Exception as e:
                 # Mark the status as error and log it
                self.stats.status = StreamStatus.ERROR
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                
                 # If the maximum number of retries has been reached, raise an error
                if attempt == max_retries - 1:
                    raise APIError(f"Failed after {max_retries} attempts: {str(e)}")
                
                # Wait a bit before retrying (exponential backoff)
                await asyncio.sleep(min(2 ** attempt, 10))  

    async def handle_stream(
        self,
        stream: Any,
        callback: Callable[[str], None],
        progress_callback: Optional[Callable[[StreamStats], None]] = None
    ) -> str:
        """
            Process streaming response with progress tracking.
            
            Args:
                stream: API response stream
                callback: Function to process each chunk
                progress_callback: Optional callback for progress updates
                
            Returns:
                 A single string that combines all processed chunks from the stream.
        """
        # Initialize an accumulator for tracking the full response while streaming
        full_response = ""

        try:
              # Iterate over each chunk of data in the API stream
            for chunk in stream:
                 # Check if the current task has been cancelled. 
                 # If so, raise an exception to stop processing gracefully.
                if asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()
                
                # Format the incoming chunk 
                formatted_chunk = self.format_chunk(chunk)
                
                # If the formatted chunk is valid (not empty or None), process it
                if formatted_chunk:
                    # Increment the counter for processed chunks
                    self.stats.chunks_processed += 1
                    # Count the number of tokens (words) in the chunk and update the total tokens
                    self.stats.total_tokens += len(formatted_chunk.split())
                    # Add to full response
                    full_response += formatted_chunk
                    # Immediately stream the chunk
                    callback(formatted_chunk)

                # If a progress tracking callback is provided, use it to report the current stats.
                if progress_callback:
                    progress_callback(self.stats)

            # Pause briefly to yield control back to the event loop, preventing CPU overuse.
            await asyncio.sleep(0.01)

        # Exception handling: If the task is cancelled during processing
        except asyncio.CancelledError:
            # Log a warning message indicating that the stream processing was cancelled.
            logger.warning("Stream processing cancelled")
            # Re-raise the cancellation error to propagate it up the chain.
            raise

        # General exception handling: Capture any other error that occurs during stream processing
        except Exception as e:
            # Raise a custom StreamProcessError with the error details.
            raise StreamProcessError(f"Error processing stream: {str(e)}")

        # After the whole stream has been processed, mark the status as COMPLETED
        self.stats.status = StreamStatus.COMPLETED

        # If a progress callback is provided, make a final call to indicate that processing is done.
        if progress_callback:
            progress_callback(self.stats)

        return full_response

    def format_chunk(self, chunk: Any) -> str:
        """
        Format individual stream chunks for output.
        
        Args:
            chunk: Raw chunk from the stream. It is expected to have a nested structure containing
                a field that includes the content we want to extract.
                
        Returns:
            Formatted string extracted from the chunk. If there's an error or the content
            is missing, returns an empty string.
        """
        
        try:
            # Check if the chunk has an attribute 'choices', and if the first item in 'choices' has a 'delta'
            # attribute with a 'content' field.
            if hasattr(chunk.choices[0].delta, 'content'):
                # Return the 'content' from the chunk. If it's None or empty, return an empty string.
                return chunk.choices[0].delta.content or ""
        
        # If any exception occurs during the formatting (e.g., accessing invalid attributes), it is handle it here.
        except Exception as e:
            # Log a warning message with the exception details for debugging purposes.
            logger.warning(f"Error formatting chunk: {str(e)}")
        
        # If the content is not accessible or an error occurred, return an empty string.
        return ""


async def main():
    """Example usage of the StreamingCodeGenerator"""
    prompt = input("Enter your prompt: ")
    
    # Initialize generator
    api_key = config("OPENAI_API_KEY")
    generator = StreamingCodeGenerator(api_key)
    
    # Define callbacks
    def print_chunk(chunk: str):
        print(chunk, end="", flush=True)
    

    
    try:
        # Generate with progress tracking
        result = await generator.generate_code_with_explanation(
            prompt,
            print_chunk,
        )
        
        print("\n\n--- Generation Complete ---")
        print(f"Time taken: {result['completion_time']:.2f} seconds")
        print(f"Total tokens: {result['stats'].total_tokens}")
        
    except StreamingError as e:
        print(f"\nError: {str(e)}")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")

if __name__ == "__main__":
    asyncio.run(main())
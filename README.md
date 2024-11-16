# Streaming Code Generator

A robust Python library for streaming code generation using OpenAI's API, with real-time progress tracking and error handling.

## Features

- Asynchronous streaming code generation
- Real-time progress tracking
- Robust error handling with retries
- Customizable chunk processing
- Comprehensive testing suite

## Project Structure
```
streaming-code-generator/
├── src/
│   └── streaming_code_generator.py
├── test/
│   └── test_streaming_code_generator.py
├── .env
├── requirements.txt
└── README.md
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Borngod/stream_generator.git
cd streaming-code-generator
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies from requirements.txt:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory:
```
OPENAI_API_KEY=your_openai_api_key_here
```

## Usage

```python
import asyncio
from src.streaming_code_generator import StreamingCodeGenerator
from decouple import config

async def main():
    # Initialize generator
    api_key = config("OPENAI_API_KEY")
    generator = StreamingCodeGenerator(api_key)
    
    # Define callback for streaming chunks
    def print_chunk(chunk: str):
        print(chunk, end="", flush=True)
    
    # Generate code with streaming
    result = await generator.generate_code_with_explanation(
        "Write a Python function that adds two numbers",
        print_chunk
    )

if __name__ == "__main__":
    asyncio.run(main())
```

## Testing

Run the test suite:
```bash
pytest test/streaming_code_generator.py -v
```

### Known Issues and Solutions

- The chunk processing count may mismatch between StreamStats and actual chunks due to empty chunk handling. This was fixed by ensuring all chunks are counted in the progress tracking, while still maintaining accurate token counting for non-empty chunks.

## Key Components

- `StreamingCodeGenerator`: Main class handling code generation and streaming
- `StreamStats`: Tracks streaming progress and statistics
- `StreamStatus`: Enum for different streaming states
- Custom error classes for specific error handling

## Configuration

The generator accepts several parameters:
- `api_key`: OpenAI API key
- `model`: Model to use (default: "gpt-3.5-turbo")
- `timeout`: Request timeout in seconds (default: 60)
- `chunk_size`: Size of chunks to process (default: 1524)

## Requirements

See `requirements.txt` for a complete list of dependencies. Key requirements include:
- openai
- python-decouple
- pytest
- pytest-asyncio

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests to ensure everything works
5. Submit a pull request

## License

MIT License

## Development Notes

- Uses Python 3.12.1+
- Requires asyncio for async/await functionality
- Implements exponential backoff for retries
- Includes comprehensive error handling

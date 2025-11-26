# InvoiceParser

AI-powered invoice parser using Google Gemini for extracting structured data from PDF and image documents.

## Features

- 🤖 **AI-Powered Parsing**: Uses Google Gemini for accurate data extraction
- 📄 **Multiple Formats**: Supports PDF, PNG, JPG, JPEG, TIFF, BMP
- 🎨 **Image Enhancement**: Advanced preprocessing for better OCR quality
- 🔄 **Multiple Input Channels**: CLI, Telegram Bot, Web API, Email
- 📊 **Multiple Export Formats**: JSON, Excel
- ✅ **Test Mode**: Compare results with reference files
- 🐳 **Docker Ready**: Easy deployment with Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Google Gemini API key

### Installation

1. Create `.env` file from example:
```bash
cp .env.example .env
```

2. Edit `.env` and add your Gemini API key:
```bash
GEMINI_API_KEY=your_api_key_here
```

3. Build and run with Docker Compose:
```bash
docker-compose up --build
```

## Usage

### CLI Mode

Process a single document:
```bash
docker-compose run --rm app python -m invoiceparser.app.main_cli parse --path /app/invoices/invoice.pdf
```

Process all documents in a directory:
```bash
docker-compose run --rm app python -m invoiceparser.app.main_cli parse --path /app/invoices
```

Run in TEST mode:
```bash
docker-compose run --rm app python -m invoiceparser.app.main_cli parse --path /app/invoices --mode TEST
```

### Web API

Start the web server:
```bash
docker-compose up app
```

The API will be available at `http://localhost:8000`

### Telegram Bot

1. Set up your bot token in `.env`
2. Start: `docker-compose --profile telegram up`
3. Send documents to your bot

### Email Integration

1. Configure email settings in `.env`
2. Start: `docker-compose --profile email up`

## Configuration

All configuration is done via `.env` file. See `.env.example` for all available options.

## Project Structure

```
invoice_parser/
├── src/invoiceparser/
│   ├── core/           # Domain models
│   ├── services/       # Business logic
│   ├── preprocessing/  # Image/PDF processing
│   ├── adapters/       # Input channels
│   ├── exporters/      # Output formats
│   ├── infra/          # Configuration, logging
│   └── app/            # Entry points
├── prompts/            # Gemini prompts
├── tests/              # Unit tests
├── invoices/           # Input documents
├── output/             # Results
├── logs/               # Application logs
└── examples/           # Reference files for TEST mode
```

## License

This project is provided as-is for educational purposes.
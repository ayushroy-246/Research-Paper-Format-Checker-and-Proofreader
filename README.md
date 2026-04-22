# Research Paper Format Checker and Proofreader

An AI-powered web application that automatically validates research paper formatting, grammar, and citations against IEEE and Springer standards. Upload your PDF and receive comprehensive feedback on structure, style, and academic conventions.

## Overview

This project consists of a React frontend and Flask backend that work together to analyze research papers for:

- **Format Compliance**: IEEE and Springer formatting standards
- **Grammar & Style**: Academic writing conventions and language quality
- **Citations**: Reference accuracy and formatting
- **Structure**: Proper document organization and sections
- **Report Generation**: Detailed feedback report

## Project Structure

```
Research-Paper-Format-Checker-and-Proofreader/
├── backend/                    # Flask API server
│   ├── app.py                 # Main Flask application
│   ├── requirements.txt       # Python dependencies
│   ├── configs/               # Configuration files
│   │   ├── format_rules.py
│   │   ├── ieee_config.json
│   │   └── springer_config.json
│   ├── modules/               # Core functionality
│   │   ├── pdf_ingestion.py     # PDF extraction and parsing
│   │   ├── grammar_checker.py   # Grammar and style analysis
│   │   ├── format_checker.py    # Format validation
│   │   ├── citation_checker.py  # Citation verification
│   │   ├── report_generator.py  # Report creation
│   │   └── utils.py
│   ├── outputs/               # Generated outputs
│   └── tests/                 # Backend tests
│
└── frontend/                  # React + Vite application
    ├── src/
    │   ├── App.jsx            # Main app component
    │   ├── main.jsx
    │   ├── components/        # Reusable components
    │   │   ├── FileUpload.jsx
    │   │   ├── Header.jsx
    │   │   └── Footer.jsx
    │   └── pages/             # Page components
    │       ├── UploadPage.jsx
    │       └── ResultsPage.jsx
    ├── package.json
    ├── vite.config.js
    └── index.html
```

## Features

- **PDF Upload & Parsing**: Extract text and metadata from research papers
- **Multi-Format Support**: IEEE and Springer standards validation
- **Grammar Analysis**: 3-layer checking system (heuristics, LanguageTool, academic style)
- **Citation Checking**: Verify reference formatting and accuracy
- **Visual Feedback**: Interactive results page with detailed analysis
- **Report Generation**: Downloadable comprehensive feedback report

## Technology Stack

### Backend
- **Framework**: Flask 2.3+
- **PDF Processing**: PyMuPDF, pdfplumber, pdfminer
- **Grammar**: language-tool-python
- **Reports**: ReportLab
- **CORS**: flask-cors

### Frontend
- **Framework**: React 19.2+
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **Routing**: React Router
- **Form Handling**: React Hook Form
- **Visualization**: react-d3-speedometer

## Getting Started

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the environment:
- Windows: `venv\Scripts\activate`
- macOS/Linux: `source venv/bin/activate`

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Create a `.env` file:
```env
FRONTEND_URL=http://localhost:5173
PORT=5000
```

6. Run the server:
```bash
python app.py
```

Server will be available at `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file (if needed):
```env
VITE_BACKEND_URL=http://localhost:5000
```

4. Start the development server:
```bash
npm run dev
```

Application will be available at `http://localhost:5173`

## API Endpoints

### Health Check
- `GET /api/health` - Server health check

### PDF Upload
- `POST /api/upload` - Upload and extract PDF content
- **Payload**: FormData with PDF file
- **Response**: Extracted structure and metadata

### Analysis
- `POST /api/analyze` - Run all checks on uploaded PDF
- **Response**: Grammar, format, and citation issues

### Report Generation
- `POST /api/generate-report` - Generate comprehensive report
- **Response**: PDF report file

## Development

### Running Tests

Backend:
```bash
pytest tests/
```

Frontend:
```bash
npm run lint
```

### Build Frontend

```bash
cd frontend
npm run build
```

Output will be in `frontend/dist/`

## Deployment

### Frontend - Vercel

1. Push your repository to GitHub
2. Visit [vercel.com](https://vercel.com)
3. Import your GitHub repository
4. Set root directory to `frontend/`
5. Environment variables: Set `VITE_BACKEND_URL` to your Render backend URL
6. Deploy

### Backend - Render

1. Push your repository to GitHub
2. Visit [render.com](https://render.com)
3. Create new Web Service
4. Connect your GitHub repository
5. Configure:
   - Root directory: `backend/`
   - Environment: Python 3
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
   - Environment variables: Add required config (FRONTEND_URL, etc.)
6. Deploy

## Team Roles

- **Member 1**: PDF Ingestion & Data Extraction
- **Member 2**: Format Checking & Validation Logic
- **Member 3**: Grammar & Academic Style Analysis
- **Member 4**: Citation & Reference Verification
- **Member 5**: UI/UX & Report Generation

## Configuration

### Format Standards

Edit `backend/configs/format_rules.py` to customize:
- Section requirements
- Citation format rules
- Font and spacing standards
- Heading styles

### IEEE & Springer Standards

Configuration files:
- `backend/configs/ieee_config.json`
- `backend/configs/springer_config.json`

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests to ensure nothing breaks
4. Submit a pull request

## Environment Variables

### Backend
```
FRONTEND_URL      - Frontend application URL (for CORS)
PORT              - Server port (default: 5000)
```

### Frontend
```
VITE_BACKEND_URL  - Backend API URL
```

## Troubleshooting

### CORS Issues
Ensure `FRONTEND_URL` in backend `.env` matches your frontend domain.

### PDF Processing Errors
Check that the PDF file is valid and not corrupted. Supported formats: PDF text-based documents.

### Port Already in Use
Change the port in `.env` or using environment variables during startup.

## License

This project is developed as a collaborative team effort for academic purposes.

## Support

For issues or questions, please open an issue in the GitHub repository.

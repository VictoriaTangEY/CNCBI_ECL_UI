# CNCBI UI Application

## Setup Instructions

### Prerequisites
- Node.js (v16 or higher)
- Python (v3.8 or higher)
- pip (Python package manager)

### Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r pyscripts/requirements.txt
   ```

2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

### Running the Application

#### Option 1: Run both frontend and backend together
```bash
npm start
```

#### Option 2: Run frontend and backend separately
```bash
# Terminal 1 - Backend
npm run backend

# Terminal 2 - Frontend  
npm run frontend
```

#### Option 3: Development mode (frontend only)
```bash
npm run dev
```

### Backend Endpoints

- **Upload File**: `POST http://localhost:5001/upload`
  - Form data: `file` (file), `fileType` (string: 'parameter' or 'dataCorrection'), `suffix` (string: user input)
  - File naming: 
    - Parameter files: `param_YYYYMMDDHHMMSS_suffix.ext` (folder: `param_YYYYMMDDHHMMSS_suffix`)
    - Data correction files: `dc_YYYYMMDDHHMMSS_suffix.ext` (folder: `dc_YYYYMMDDHHMMSS_suffix`)
    - If no suffix: `param_YYYYMMDDHHMMSS.ext` (folder: `param_YYYYMMDDHHMMSS`)
- **Test**: `GET http://localhost:5001/test`

### Frontend

The frontend will be available at: `http://localhost:5173`

## Project Structure

```
app_vue/
├── src/                    # Vue.js frontend source code
├── pyscripts/             # Python backend scripts
│   ├── backend_server.py  # Consolidated backend server
│   └── requirements.txt   # Python dependencies
├── package.json           # Node.js dependencies and scripts
└── README.md             # This file
```

## Notes

- The backend server runs on port 5001
- The frontend development server runs on port 5173
- All Python functionality is now consolidated in `backend_server.py`
- No batch files are required for setup

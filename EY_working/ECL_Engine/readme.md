# CNCBI ECL Engine

## Project Structure (Just for reference, still updating now...)

```
ECL_Engine/
├── core/
│   ├── ecl_engine/
│   │   ├── cashflow_ead.py      # Cash flow and EAD calculations
│   │   ├── collateral_allocation.py  # Collateral processing
│   │   ├── lgd_calculation.py    # LGD calculations
│   │   └── model_segmentation.py # Model segmentation logic
│   └── io_handler/
│       ├── data_preprocessor.py  # Data preprocessing
│       ├── load_parameters.py    # Parameter loading
│       └── output_handler.py     # Output file handling
├── services/
│   └── ecl_engine_service.py    # Main service layer
├── utils/
│   ├── loggers.py               # Logging utilities
│   └── write_my_csv.py          # CSV writing utilities
├── config/
│   └── env_setting.py          # Environment configuration
├── main.py                     # Entry point
└── run_config_file.json        # Configuration file
```

## Key Features (Just for reference, still updating now...)

1. **Data Processing**

   - Standardizes input data formats
   - Handles date conversions and validations
   - Merges multiple data sources

2. **ECL Calculations**

   - Cash flow generation
   - EAD computation
   - Collateral allocation
   - LGD calculation
   - Final ECL results

3. **User Interface**
   - Web-based dashboard
   - Configuration management
   - Results visualization
   - Report generation

## Setup Instructions

### Prerequisites

- Python 3.9.21
- Conda environment manager
- PowerShell (for Windows)

### Initial Setup

1. Activate virtual environment (if any):

```powershell
conda activate cncbi_engine
```

2. Navigate to the project directory:

```powershell
cd ECL_Engine
```

3. Install dependencies:
   In the developing phase, it is recommended to install one by one. After all the packages are confirmed, can use:

```powershell
pip install -r requirements.txt
```

### Configuration

Before running the ECL engine, configure the `run_config_file.json` with the following settings:

```json
{
  "DATA_PATH": "C:\\Users\\SA814XM\\Engagement\\01_CNCBI\\CNCBI_ECL_Engine\\02_engine_server\\99_data\\01_merged_data_folder", // path of the merged data folder
  "DATA_YYMM": 20241231, // the reporting date

  "PARAM_PATH": "C:\\Users\\SA814XM\\Engagement\\01_CNCBI\\CNCBI_ECL_Engine\\02_engine_server\\99_data\\02_param_upload_folder", // path of the parameter folder

  "OUTPUT_PATH": "C:\\Users\\SA814XM\\Engagement\\01_CNCBI\\CNCBI_ECL_Engine\\02_engine_server\\99_data\\03_output_folder", // path of the output folder

  "run_mode": 4 // ECL calculation mode
}
```

### Running the ECL Engine

1. Navigate to the engine script folder

```powershell
cd .../ECL_Engine/src
```

2. Run the scripts

```powershell
python main.py --configPath run_config_file.json
```

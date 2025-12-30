# Test Documentation Analysis

Analyzes GitHub repositories to calculate the Test Engagement Ratio based on pull request activity.

## Setup
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Environment:**
   Create `.env` with your GitHub token:
   ```
   GITHUB_AUTH_TOKEN=your_token_here
   ```

## Usage
Run the analysis script:
```bash
python3 src/calculate.py
```
This reads from `dataset_test_documentation.csv` and outputs to `output.csv`.

## Testing
Run unit tests:
```bash
python3 -m unittest discover tests
```
# PR Deployment Impact Analyzer Web Application

This web application provides a user interface for the PR Agent's Deployment Impact analysis tool. It allows users to input a PR URL through a web interface and view the deployment impact analysis results.

## Features

- Simple web interface to input PR URLs
- Real-time analysis of deployment impact
- Markdown rendering of analysis results
- Responsive design for desktop and mobile

## Setup

### Prerequisites

- Python 3.8 or higher
- PR Agent installed and configured

### Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Make sure your PR Agent configuration is properly set up (API keys, etc.)

### Running the Application

1. Start the Flask application:

```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

## Usage

1. Enter a valid GitHub or GitLab pull request URL in the input field
2. Click the "Analyze Deployment Impact" button
3. Wait for the analysis to complete (this may take a few minutes)
4. Review the detailed deployment impact analysis

## Environment Variables

- `SECRET_KEY`: Flask secret key for session management (defaults to a development key)
- `FLASK_ENV`: Set to `development` for debug mode or `production` for production mode

## Integration with PR Agent

This web application integrates with the PR Agent's deployment impact analysis tool. It uses the same underlying code but presents the results through a web interface instead of as a comment on the PR.

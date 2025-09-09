# CIIS IPDR Analysis Platform

The CIIS IPDR Analysis Platform is a full-stack web application designed for law enforcement and investigative agencies to ingest, analyze, and visualize complex Internet Protocol Detail Record (IPDR) and Call Detail Record (CDR) data. It transforms raw, heterogeneous log files from various telecom service providers into a standardized format, revealing actionable intelligence through correlation, network analysis, and suspicious activity detection.

## Key Features

- **Polymorphic Log Parsing Engine**: Ingests and normalizes diverse data formats (CSV, JSON, XML, TXT, LOG) from different providers into a single canonical data model.
- **A-Party/B-Party Correlation**: Automatically identifies and correlates initiating (A-Party) and receiving (B-Party) entities to map communication patterns.
- **Suspicious Activity Detection**: Utilizes a sophisticated engine with heuristic, rule-based, and unsupervised machine learning models (Isolation Forest) to flag anomalous behaviors like:
    - Late-night activity
    - Port scanning
    - High-frequency communications
    - Geographic anomalies
    - Statistical outliers
- **Interactive Network Visualizations**: Generates interactive graphs to explore relationships between subscribers, phone numbers, and IP addresses.
- **Geographic Mapping**: Plots communication data and suspicious activities on an interactive map, including network overlays and location-based clustering.
- **Secure Authentication & Case Management**: Features a robust user authentication system and allows for case-specific data uploads and analysis.
- **RESTful API**: A comprehensive FastAPI backend provides clear, powerful endpoints for data processing and analysis.

## Architecture Overview

The platform is built with a modern, decoupled architecture.

- **Backend**: A Python backend powered by **FastAPI** handles all business logic, data processing, and machine learning.
    - **Data Processing**: **Pandas** is used for high-performance data manipulation.
    - **Network Analysis**: **NetworkX** is used to model and analyze communication graphs.
    - **ML & Analytics**: **Scikit-learn** is used for anomaly detection.
    - **Database**: **SQLite** is used for lightweight, persistent storage of user, session, and case data.

- **Frontend**: A responsive user interface built with **React** and **TypeScript**.
    - **Visualization**: **Plotly.js** and **React Graph Vis** are used to render interactive charts, maps, and network graphs.

```
+----------------------+      +-------------------------+
|   React Frontend     |      |     FastAPI Backend     |
| (TypeScript, Plotly) |      | (Python, Pandas, ML)    |
+----------------------+      +-------------------------+
          ^                             |
          | (REST API Calls)            | (User/Case Data)
          v                             v
+----------------------+      +-------------------------+
|        User          |      |      SQLite Database    |
+----------------------+      +-------------------------+
```

## Getting Started

Follow these instructions to set up and run the project on your local machine.

### Prerequisites

- **Node.js** (v16 or later) and **npm**
- **Python** (v3.10 or later) and **pip**

### Backend Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    # On Windows, use: venv\Scripts\activate
    ```

3.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the `backend` directory. You can copy the example if one exists, or create a new one. This file is used for sensitive information.
    ```
    # backend/.env
    FRONTEND_ORIGIN="http://localhost:3000"
    MAPBOX_TOKEN="your_mapbox_token_if_available" 
    ```

5.  **Run the backend server:**
    ```bash
    uvicorn main:app --reload
    ```
    The backend API will be available at `http://127.0.0.1:8000`.

### Frontend Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```

2.  **Install the required npm packages:**
    ```bash
    npm install
    ```

3.  **Run the frontend development server:**
    ```bash
    npm start
    ```
    The application will open in your browser at `http://localhost:3000`.

## Core Modules Explained

The backend's intelligence is segmented into several key modules:

-   `data_normalizer.py`: The polymorphic parsing engine. Its `DataNormalizer` class can read multiple file formats, detect the provider, and transform the data to match the project's standard schema.
-   `communication_mapping.py`: The graph engine. Its `CommunicationMapper` class uses `networkx` to build complex graph models of the communication data, enabling deep relationship analysis.
-   `suspicious_activity_detector.py`: The core detection engine. It runs a suite of tests to find anomalies, including heuristic checks (e.g., late-night calls) and a statistical model (`IsolationForest`) to find outlier behaviors.
-   `relationship_extractor.py`: Identifies and extracts A-Party to B-Party relationships, calculating risk scores for individual connections.
-   `communication_filters.py`: Provides a library of functions to filter the dataset, allowing an investigator to exclude routine traffic or focus on high-priority signals.

## API Endpoints

The backend provides several key endpoints for interacting with the system.

-   `POST /auth/login`: Authenticates a user and returns a session token.
-   `POST /process-data`: Ingests and analyzes the primary dataset.
-   `GET /correlation/a2b`: Returns A-Party to B-Party correlation data, including connection counts.
-   `GET /map/suspicious-phones/html`: Renders an interactive HTML map of suspicious phone activity.
-   `GET /link-analysis/phone`: Provides data for an ego-network graph for a specific phone number.
-   `POST /cases/{case_id}/ai-analyze`: Uploads and analyzes a dataset specific to an investigation case.

## Testing

The project includes a suite of tests for the backend logic. To run the tests, ensure you have `pytest` installed (`pip install pytest`) and run the following command from the project's root directory:

```bash
pytest backend/
```

## Configuration

-   **`backend/.env`**: Used for environment-specific variables and secrets.
-   **`backend/config.yml.example`**: An example configuration file. Copy this to `config.yml` to define application-level settings like IP address allow/deny lists.

## Contributing

Contributions are welcome! Please follow these steps to contribute:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/YourFeature`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/YourFeature`).
6.  Open a Pull Request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

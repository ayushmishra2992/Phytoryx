# PHYTORYX
### Intelligence Rooted in Nature 🌿

**An AI-powered botanical and environmental intelligence platform combining leaf-image analysis, phyllotaxy classification, morphological measurements, FTIR spectral interpretation, and environmental data.**

<p align="center">
  <img src="docs/screenshots/phytoryx-banner.png" alt="PHYTORYX Banner" width="100%">
</p>

<p align="center">
  <b>AI • Computer Vision • Vision Transformers • FTIR • Environmental Intelligence</b>
</p>

---

## 1. Overview

PHYTORYX is an AI-powered research and analysis platform designed to explore the relationship between plant leaf characteristics and environmental information.

The platform uses computer vision and deep learning to identify leaf phyllotaxy patterns, extract morphological characteristics, interpret FTIR spectral information, and retrieve location-based environmental data.

It brings these different analytical components together through a web-based interface and generates structured reports for further inspection.

The project aims to make botanical image analysis and environmental information more accessible through an integrated digital platform.

**Live Frontend:** https://phytoryx.vercel.app/v2

> Note: The public frontend is accessible, but the complete AI analysis workflow currently requires a separately running backend. Public backend hosting and integration are still pending.

---

## 2. Problem Statement

Plant leaves contain useful structural and morphological characteristics that can be studied using computer vision and analytical techniques.

However, botanical image classification, leaf morphology, spectral analysis, and environmental information are often handled independently.

PHYTORYX explores an integrated approach that brings these components together.

The major objectives are:

- Automate the classification of leaf phyllotaxy patterns.
- Extract measurable morphological characteristics from leaf images.
- Interpret relevant FTIR spectral bands.
- Retrieve location- and time-based environmental information.
- Generate consolidated analytical reports.
- Provide a user-friendly interface for accessing the results.

---

## 3. Key Features

### A. AI-Based Phyllotaxy Classification

Uses a Vision Transformer (ViT)-based deep learning model to classify uploaded leaf images into four categories:

| Class | Description |
|---|---|
| Alternate | Leaves arranged alternately along the stem |
| Opposite | Leaves arranged in opposite pairs |
| Whorled | Three or more leaves arising from a node |
| Not a Leaf | Input rejected as an unfamiliar or non-leaf image |

The classification system also includes an unfamiliar-input rejection mechanism to reduce unsupported predictions.

### B. Leaf Morphological Analysis

Extracts image-based morphological measurements, including:

- Leaf area
- Perimeter
- Length and width
- Aspect ratio
- Solidity
- Circularity
- Extent
- Colour statistics

Physical measurements are not inferred from pixels unless an appropriate scale reference is supplied.

### C. FTIR Spectral Analysis

Supports FTIR spectral data interpretation through uploaded files.

The system identifies and interprets indicative spectral peak regions to assist with the study of possible chemical functional groups.

Supported input formats include CSV, XLSX and JCAMP-DX, subject to parser compatibility.

**Important:** FTIR peak interpretation is indicative. It does not independently establish pollutant identity, concentration or source attribution.

### D. Environmental Intelligence

Retrieves environmental information using external data sources.

Integrated sources include:

- Open-Meteo
- Copernicus Atmosphere Monitoring Service (CAMS)
- OpenAQ

The platform distinguishes between modelled atmospheric information and measurements reported by monitoring stations.

Leaf photographs are not treated as direct AQI measurements.

### E. Report Generation

The platform supports structured analytical outputs:

- PDF reports
- JSON reports
- HTML reports

These reports consolidate available classification, morphology, spectral and environmental information.

---

## 4. Application Screenshots

The following section provides a visual overview of the PHYTORYX application.
<img width="1917" height="952" alt="image" src="https://github.com/user-attachments/assets/bff4c685-21b0-4f1b-9da4-56c80028a0c4" />
<img width="1912" height="967" alt="image" src="https://github.com/user-attachments/assets/8e0e40ac-ead6-47c1-9dc4-dbcd78260f21" />
<img width="1917" height="977" alt="image" src="https://github.com/user-attachments/assets/cf1f82a9-0518-418d-bc14-1f07d27758db" />
<img width="1917" height="980" alt="image" src="https://github.com/user-attachments/assets/e8679957-8cdc-437a-a2bb-16128e21084e" />
<img width="1917" height="952" alt="image" src="https://github.com/user-attachments/assets/a027c855-84d2-4fe7-b4ad-597c54b02ea3" />
<img width="1917" height="822" alt="image" src="https://github.com/user-attachments/assets/1e76aa92-85b3-446e-9af0-cff418f37c64" />
<img width="1916" height="903" alt="image" src="https://github.com/user-attachments/assets/8e7714c3-0dea-4244-8cc1-8631bae7bfbb" />

**Add your actual application screenshots inside `docs/screenshots/` and replace the filenames below if necessary.**


## 5. System Architecture

PHYTORYX follows a modular architecture consisting of a frontend, backend, AI inference pipeline, analytical modules and external environmental data sources.

```text
                   USER
                    |
                    v
          NEXT.JS WEB APPLICATION
                    |
                    v
              FASTAPI BACKEND
                    |
         +----------+-----------+
         |          |           |
         v          v           v
    VISION       MORPHOLOGY     FTIR
  TRANSFORMER     ANALYSIS   INTERPRETATION
         |          |           |
         +----------+-----------+
                    |
                    v
          ENVIRONMENTAL DATA
          Open-Meteo / CAMS
                / OpenAQ
                    |
                    v
          REPORT GENERATION
             PDF / JSON / HTML
                    |
                    v
              USER OUTPUT
```

The frontend and backend are separate services. The backend performs model inference and analytical processing, while the frontend provides the user interface.

---

## 6. Technology Stack

| Component | Technologies |
|---|---|
| Frontend | Next.js, React, TypeScript |
| Backend | Python, FastAPI |
| Deep Learning | PyTorch, Hugging Face Transformers |
| AI Architecture | Vision Transformer (ViT) |
| Image Processing | OpenCV, scikit-image |
| Data Processing | NumPy, Pandas, scikit-learn |
| Spectral Analysis | Python-based FTIR processing |
| Environmental Data | Open-Meteo, CAMS, OpenAQ |
| Reports | PDF, JSON, HTML |
| Containerization | Docker |
| Version Control | Git and GitHub |

---

## 7. Dataset and Model Information

The project uses a curated leaf-image dataset for phyllotaxy classification.

### Leaf Image Dataset

| Category | Number of Images |
|---|---:|
| Alternate | 88 |
| Opposite | 83 |
| Whorled | 94 |
| **Total** | **265** |

The dataset was cleaned and deduplicated before use.

A SHA-256-based manifest was created to support dataset integrity verification.

### Model

The classification pipeline uses a Vision Transformer architecture.

The project also implements a rejection mechanism for unfamiliar inputs.

The model and its performance should be evaluated on appropriate independent test datasets. Historical experimental results should not be interpreted as guaranteed real-world performance.

---

## 8. Research Background

PHYTORYX draws inspiration from research involving plant phyllotaxy, Vision Transformers, FTIR spectral analysis and environmental monitoring.

One of the relevant research works is:

**Yadav, N. (2026).** *Prediction of Streetwise AQI from Deposited Pollutant on Leaf Phyllotaxy Using Vision Transformer and FTIR Spectral Data.* Global NEST Journal.

DOI: https://doi.org/10.30955/gnj.07998

The project builds on the broader research direction of combining botanical image analysis with environmental information while maintaining clear distinctions between measured, modelled and inferred results.

---

## 9. Installation and Local Setup

### Prerequisites

- Python 3.10 or compatible version supported by the project dependencies
- Node.js and npm
- Git
- PyTorch-compatible environment
- NVIDIA GPU is recommended for accelerated inference; CPU execution may be possible depending on the configuration.

### Step 1: Clone the Repository

```bash
git clone https://github.com/ayushmishra2992/Phytoryx.git

cd Phytoryx
```

Switch to the development branch if required:

```bash
git checkout release/1.1.0
```

### Step 2: Set Up the Backend

Create and activate a Python virtual environment:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install the project dependencies:

```bash
pip install -r requirements.txt
```

Install a compatible PyTorch and torchvision build according to your hardware and the project's pinned dependency requirements.

Ensure that the required model checkpoints and project data are available in their expected locations. Some model and dataset files may require separate access.

Start the backend:

```bash
python -m uvicorn api.v2_app:app --host 127.0.0.1 --port 8000
```

Backend health check:

```text
http://127.0.0.1:8000/health
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### Step 3: Set Up the Frontend

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Open the application:

```text
http://localhost:3000/v2
```

The frontend expects the backend to be available at the configured API address.

---

## 10. Docker Support

PHYTORYX includes Docker support for running the backend in a containerized environment.

The repository includes a Dockerfile and deployment documentation.

Refer to:

- `docs/DOCKER.md`
- `docs/DEPLOYMENT_READINESS.md`

The backend container is designed for CPU-based execution. Check the Docker documentation for the exact build, startup and resource requirements.

---

## 11. Current Project Status

| Module | Status |
|---|---|
| Next.js frontend | Implemented |
| FastAPI backend | Implemented |
| ViT-based classification | Implemented |
| Four-class classification | Implemented |
| Unfamiliar-input rejection | Implemented |
| Morphological analysis | Implemented |
| FTIR file processing | Implemented |
| Environmental data integration | Implemented |
| PDF report generation | Implemented |
| JSON and HTML reports | Implemented |
| Docker backend | Tested |
| Public frontend | Accessible on Vercel |
| Public backend hosting | Pending |
| Public end-to-end AI workflow | Pending |

---

## 12. Limitations and Future Scope

PHYTORYX is an evolving research and engineering project. Its current capabilities have specific limitations.

### Current Limitations

- The available leaf dataset is relatively small.
- Image-based classification does not establish plant species identity.
- FTIR spectral interpretation is indicative and does not prove pollutant attribution.
- Environmental information may be modelled or station-measured depending on the source.
- Leaf photographs are not direct substitutes for calibrated pollution-monitoring instruments.
- Reliable multimodal fusion requires appropriately paired and sufficiently large datasets.
- Public backend hosting and complete public frontend-backend integration are still pending.

### Future Scope

Potential future research and development directions include:

1. Expansion of the leaf-image dataset across species and geographical regions.
2. Improved model generalization and uncertainty estimation.
3. More extensive FTIR spectral analysis.
4. Reliability-aware environmental prediction.
5. Improved multimodal integration of image, spectral and environmental information.
6. Better validation using independently collected field data.
7. Publicly accessible backend infrastructure.

---

## 13. Repository Structure

The main project components are organized as follows:

```text
PHYTORYX/
|
|-- api/                    # FastAPI application
|-- frontend/               # Next.js frontend
|-- models/                 # Model checkpoints
|-- data/                   # Dataset and processed data
|-- docs/                   # Technical documentation
|-- scripts/                # Utility and automation scripts
|-- legacy/                 # Earlier project components
|
|-- requirements.txt
|-- Dockerfile
|-- README.md
|-- CLAUDE.md
```

Refer to the actual repository for the complete directory structure and individual module details.

---

## 14. Project Links

- **GitHub Repository:** https://github.com/ayushmishra2992/Phytoryx
- **Live Frontend:** https://phytoryx.vercel.app/v2
- **API Documentation (Local):** http://127.0.0.1:8000/docs
- **Backend Health Check (Local):** http://127.0.0.1:8000/health

The public frontend link currently provides access to the interface. Complete AI-powered analysis requires the separately hosted backend.

---

## 15. Acknowledgements

PHYTORYX is developed as an academic and technical project exploring the intersection of artificial intelligence, botanical analysis, computer vision and environmental monitoring.

We acknowledge the researchers, open-source communities, documentation teams and data providers whose work supports the development of this project.

---

## 16. Author and Project Information

**Project:** PHYTORYX

**Tagline:** Intelligence Rooted in Nature.

**Authors:**
- [Ayush Mishra](https://github.com/ayushmishra2992)
- [Riya Katiyar](https://github.com/riyakatiyar123)

**Repository:** [PHYTORYX](https://github.com/ayushmishra2992/Phytoryx)
---

<p align="center">
  <b>PHYTORYX — Intelligence Rooted in Nature 🌿</b>
  <br>
  <i>Bringing botanical intelligence and environmental information together.</i>
</p>

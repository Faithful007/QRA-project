# QRA Program User Manual: Quantitative Risk Analysis for Tunnel Fire Safety

## 1. Introduction

The Quantitative Risk Analysis (QRA) Program is a specialized desktop application designed to evaluate the fire safety of road tunnels by assessing the probability of fire accidents and the resulting consequences. This manual serves as a comprehensive guide for users, covering installation, interface navigation, data input, simulation execution, and risk interpretation.

### 1.1. System Overview

The QRA Program is built in Python using the PyQt6 framework for the graphical user interface (GUI) and SQLAlchemy for persistent data management. It implements a multi-step QRA procedure, culminating in a social risk evaluation using the F-N curve criteria.

### 1.2. Core Components

The system consists of two main windows:
1.  **Main Application Window**: Contains five tabbed interfaces for data configuration.
2.  **QRA Main Control Window**: A separate, floating window used to execute the simulation and view high-level results.

## 2. Installation and Setup

The application is packaged for Windows with automated setup scripts.

1.  **Prerequisites**: Ensure Python 3.8 or later is installed and added to your system's PATH.
2.  **Extraction**: Extract the provided `qra-program-windows-v2.zip` file to a local directory.
3.  **Setup**: Double-click `setup.bat` to create the virtual environment and install dependencies.
4.  **Launch**: Double-click `run.bat` to start the application.

## 3. Data Configuration Tabs

The main application window contains five tabs for comprehensive project configuration. Data entered in these tabs is saved to the internal database upon clicking the "Save All" button in the File menu.

### 3.1. Tab 1: Tunnel Basic Settings
This tab defines the physical and traffic characteristics of the tunnel.

| Section | Key Inputs | Description |
| :--- | :--- | :--- |
| **Tunnel Geometry** | Name, Mode (One-Way/Two-Way), Length, Area, Lanes | Defines the physical structure and operational mode. |
| **Traffic Volume & Vehicle Classification** | Volume (+/- Direction), PCU, Length, Occupancy | Defines the traffic flow and the characteristics of the 7 vehicle types (Passenger Car, Small Bus, Large Bus, etc.). |

### 3.2. Tab 2: Traffic Management
This tab configures the distribution of traffic and speed within the tunnel.

| Section | Key Inputs | Description |
| :--- | :--- | :--- |
| **Traffic Flow Configuration** | Total Traffic Volume, Peak Hour Factor | Defines the overall traffic pattern. |
| **Vehicle Distribution by Speed** | Speed distribution tables for various vehicle types. | Used to model the probability of congestion and accident scenarios. |

### 3.3. Tab 3: HAR EVAC Analysis
This tab is critical for defining the fire and evacuation parameters used in the ASET/RSET calculation.

| Section | Key Inputs | Description |
| :--- | :--- | :--- |
| **Hazard Definition** | Fire Size (HRR), Fire Growth Rate (Slow, Medium, Fast) | Defines the severity and growth of the fire scenario. |
| **Evacuation Characteristics** | Reaction Time, Hesitation Time, Walking Speed | Defines human response and movement during an emergency. |
| **Tenability Limits** | Critical Temperature, Visibility Limit | Defines the conditions under which the tunnel environment becomes untenable (ASET criteria). |

### 3.4. Tab 4: Simulation Settings
This tab manages the technical settings for the simulation run.

| Section | Key Inputs | Description |
| :--- | :--- | :--- |
| **Program Settings** | Time Interval, Monitoring Points | Configures the simulation resolution and data collection points. |
| **Fire Point Configuration** | Fire Point Location Table | Defines the specific locations within the tunnel where fire scenarios are modeled. |

### 3.5. Tab 5: MDB Database Creation
This tab is used for managing external data sources, typically for FDS (Fire Dynamics Simulator) or CFD (Computational Fluid Dynamics) inputs.

| Section | Key Inputs | Description |
| :--- | :--- | :--- |
| **Database Type** | Selection of external database format. | Used for importing/exporting complex simulation data. |
| **Chemical Properties** | Table for defining material properties. | Used in advanced fire modeling. |

## 4. Simulation Execution and QRA Procedure

The QRA procedure is executed via the **QRA Main Control Window**.

### 4.1. The QRA Procedure Flow

The system follows the multi-step process shown in the Process Flow Diagram (PFD) [1]:

1.  **Accident Scenario Creation**: Based on traffic and tunnel configuration.
2.  **CFD & FED Analysis (ASET/RSET)**: Calculates the Available Safe Egress Time (ASET) and Required Safe Egress Time (RSET) based on fire and evacuation settings.
3.  **QRA Analysis**:
    *   **Accident Frequency (F)**: Calculates the annual probability of a fire accident.
    *   **Fatality Analysis (N)**: Estimates the average number of fatalities per accident, based on the safety margin (ASET - RSET) and occupancy.
4.  **Risk Comparison**: Compares the calculated (F, N) point against the F-N curve criteria.

### 4.2. Running the Simulation

1.  Ensure all data tabs are configured and saved.
2.  In the **QRA Main Control Window**, click the **Simulation** button.
3.  The system will execute the QRA procedure and update the status labels.

### 4.3. Interpreting Results (F-N Curve)

The final output is the **Risk Status**, which is determined by comparing the calculated (F, N) point to the F-N curve boundaries [2]:

| Risk Status | F-N Curve Region | Improvement Required | Description |
| :--- | :--- | :--- | :--- |
| **Acceptable** | Below Acceptable Boundary | No | Risk is socially acceptable; no further action required. |
| **ALARP** | Between Acceptable and Unacceptable Boundaries | Yes | Risk is As Low As Reasonably Practicable; further risk reduction efforts must be considered. |
| **Unacceptable** | Above Unacceptable Boundary | Yes | Risk is socially unacceptable; immediate and significant safety improvements are mandatory. |

Detailed F-N curve data, including the calculated F and N values, can be viewed by clicking the **Result Analysis** button.

## 5. References

[1] Process Flow Diagram (PFD) for the QRA Program. (Internal Document)
[2] Social Risk Evaluation Criteria (F-N Curve) for Road Tunnel Fire Safety. (Source: Korean Ministry of Land, Infrastructure and Transport, 2025.08 Guideline - *Approximation used in this software*).

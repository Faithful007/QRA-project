# QRA Procedure Flowchart Analysis and Implementation Plan

This document maps the steps from the provided QRA procedure flowchart to the application's components and outlines the necessary changes.

## 1. Flowchart Steps Mapping

| Flowchart Step (Korean) | Flowchart Step (English) | Application Component | Action Required |
| :--- | :--- | :--- | :--- |
| 통계자료 조사, 교통량 조사, 사고자료 조사 | Statistical Data, Traffic Data, Accident Data Survey | `TunnelBasicSettingsTab`, `TrafficManagementTab` | Data input is already handled by these tabs. |
| 방재시설 계획 | Fire Safety Facility Plan | `SimulationSettingsTab` | Data input is already handled by this tab. |
| 사고 시나리오 작성 | Accident Scenario Creation | `HAREVACAnalysisTab` | Data input is already handled by this tab (Fire characteristics, Evacuation). |
| 사고빈도 예측 | Accident Frequency Prediction | `QRACalculator` | New method required: `calculate_accident_frequency()`. |
| CFD & FED 분석 | CFD & FED Analysis | `QRACalculator` | Simplified: `calculate_aset()` (FED is a component of ASET). |
| 사망자 분석 | Fatality Analysis | `QRACalculator` | New method required: `calculate_fatalities()`. |
| QRA 분석 (리스크분석, FN Curve 작성, 위험크기 비교) | QRA Analysis (Risk Analysis, FN Curve Generation, Risk Comparison) | `QRACalculator` | New method required: `generate_fn_curve()` and `compare_risk_to_criteria()`. |
| 위험기준 설정 (사회적 위험기준, 개인적 위험기준) | Risk Criteria Setting (Social, Individual) | `HAREVACAnalysisTab` | Data input is needed for individual risk criteria. Social risk (F-N Curve) is hardcoded. |
| 기준 만족 (YES/NO) | Criteria Satisfied (YES/NO) | `QRACalculator` | Final output of `run_simulation()`. |
| 개선방안 수립 | Improvement Plan Formulation | N/A | User action based on results. |
| 공식 종료 | Formal End | `MainControlWindow` | Final state display. |

## 2. F-N Curve Criteria Implementation

The F-N curve defines three zones based on Fatality Frequency (F, events/year) and Number of Fatalities (N, persons):

| Zone | Name (English) | Description | Action |
| :--- | :--- | :--- | :--- |
| 허용 불가 구간 | Unacceptable Region | Risk level is too high; requires immediate safety improvements. | **Risk > Unacceptable Threshold** |
| ALARP 구간 | ALARP Region | As Low As Reasonably Practicable; requires cost-benefit analysis for improvements. | **Unacceptable Threshold > Risk > Acceptable Threshold** |
| 허용 가능 구간 | Acceptable Region | Risk is socially acceptable; no further action required. | **Risk < Acceptable Threshold** |

**Implementation Details:**
- The F-N curve will be defined by two linear equations (on a log-log scale) that represent the boundaries of the Unacceptable and Acceptable regions.
- The `QRACalculator` will generate a single (F, N) point for the current scenario and compare its position to these boundaries.

## 3. Data Model Update Plan

A new model is needed to store the results of the QRA Analysis, including the calculated F and N values and the final risk status.

- **Model Name:** `QRAResult`
- **Fields:**
    - `tunnel_config_id` (FK)
    - `accident_frequency_per_year` (F)
    - `fatalities_per_accident` (N)
    - `risk_status` (String: 'Unacceptable', 'ALARP', 'Acceptable')
    - `improvement_required` (Boolean)

## 4. UI Update Plan

- **`MainControlWindow`**:
    - The "Simulation" button will now trigger the full, multi-step QRA procedure.
    - A new area will be added to display the final **Risk Status** and a simple text representation of the F-N curve comparison.
    - The "Result Analysis" button will be updated to show the detailed QRA results, including the F-N plot.

This analysis confirms the required changes and sets the stage for the next phase: updating the data model.

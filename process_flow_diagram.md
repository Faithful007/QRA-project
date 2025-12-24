graph TD
    subgraph QRA Program System
        A[Start Application] --> B(Initialize DB & Load Default Config);
        B --> C{Main Window & Tabs};
        B --> D{Main Control Window};
        
        subgraph Data Input & Configuration (Tabs 1-5)
            C --> C1[Tab 1: Tunnel Basic Settings];
            C --> C2[Tab 2: Traffic Management];
            C --> C3[Tab 3: HAR EVAC Analysis];
            C --> C4[Tab 4: Simulation Settings];
            C --> C5[Tab 5: MDB Database Creation];
            C1 --> E(Save Data to DB);
            C2 --> E;
            C3 --> E;
            C4 --> E;
            C5 --> E;
        end
        
        subgraph QRA Simulation (Main Control)
            D --> D1[Click 'Simulation' Button];
            D1 --> F(Load All Config Data from DB);
            F --> G1[Calculate ASET (Fire/Evac Config)];
            F --> G2[Calculate RSET (Evac/Tunnel Config)];
            F --> H1[Calculate Accident Frequency (F)];
            F --> H2[Calculate Fatalities per Accident (N)];
            G1 & G2 --> H2;
            H1 & H2 --> I(Compare (F, N) to F-N Criteria);
            I --> J{Risk Status: Acceptable, ALARP, Unacceptable};
            J --> K(Save QRAResult to DB);
            K --> D2[Update Main Control Status];
        end
        
        subgraph Result Analysis
            D --> D3[Click 'Result Analysis' Button];
            D3 --> L(Load QRAResult from DB);
            L --> M[Display Detailed Results & F-N Curve Data];
        end
        
        E --> F;
        D2 --> D;
    end
    
    style C1 fill:#f9f,stroke:#333,stroke-width:2px
    style C2 fill:#f9f,stroke:#333,stroke-width:2px
    style C3 fill:#f9f,stroke:#333,stroke-width:2px
    style C4 fill:#f9f,stroke:#333,stroke-width:2px
    style C5 fill:#f9f,stroke:#333,stroke-width:2px
    style D1 fill:#ccf,stroke:#333,stroke-width:2px
    style D3 fill:#ccf,stroke:#333,stroke-width:2px
    style J fill:#ff9,stroke:#333,stroke-width:2px
    style M fill:#afa,stroke:#333,stroke-width:2px
    style I fill:#ccc,stroke:#333,stroke-width:2px
    style K fill:#ccc,stroke:#333,stroke-width:2px
    style D2 fill:#ccc,stroke:#333,stroke-width:2px
    style F fill:#ccc,stroke:#333,stroke-width:2px
    style G1 fill:#ccc,stroke:#333,stroke-width:2px
    style G2 fill:#ccc,stroke:#333,stroke-width:2px
    style H1 fill:#ccc,stroke:#333,stroke-width:2px
    style H2 fill:#ccc,stroke:#333,stroke-width:2px
    style L fill:#ccc,stroke:#333,stroke-width:2px

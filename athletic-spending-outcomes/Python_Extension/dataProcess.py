import pandas as pd
import numpy as np
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "Data"

actToSAT = {
    36:1590, 35:1540, 34:1500, 33:1460, 32:1430, 31:1400, 30:1370, 29:1340,
    28:1310, 27:1280, 26:1240, 25:1210, 24:1180, 23:1140, 22:1110, 21:1080,
    20:1040, 19:1010, 18:970, 17:930, 16:890, 15:850, 14:800, 13:760, 12:710,
    11:670, 10:630, 9:590
}

univAdmit = pd.read_csv(DATA / "Raw" / "adm2023_RV.csv")

univAdmitClean = univAdmit[["UNITID", "APPLCN", "ADMSSN", "SATNUM", "ACTNUM",
                            "SATVR50", "SATMT50", "ACTCM50"]].rename(
    columns={"ADMSSN": "admTotal"}
).assign(satTotal= lambda d: d["SATVR50"] + d["SATMT50"],
        actAsSat=lambda d: d["ACTCM50"].map(actToSAT),
        admRate=lambda d: d["admTotal"] / d["APPLCN"],
        testScore=lambda d: (
            d["satTotal"].fillna(0) * d["SATNUM"].where(d["satTotal"].notna(), 0)
            + d["actAsSat"].fillna(0) * d["ACTNUM"].where(d["actAsSat"].notna(), 0)
            ) / (
                d["SATNUM"].where(d["satTotal"].notna(), 0)
                + d["ACTNUM"].where(d["actAsSat"].notna(), 0)
                )).drop(
                    columns=["APPLCN", "admTotal", "SATNUM", "ACTNUM", "SATVR50", "SATMT50",
                             "ACTCM50", "satTotal", "actAsSat"]
                )

univData  = pd.read_csv(DATA / "Clean" / "univData.csv")

univData2 = pd.merge(univData, univAdmitClean, on="UNITID", how="left")

univData2["testScoreMissing"] = univData2["testScore"].isna().astype(int)

univFinAid = pd.read_csv(DATA / "Raw" / "sfa2223_RV.csv")

univFinAidClean = univFinAid[["UNITID", "SCUGRAD", "UPGRNTP"]].rename(
    columns={"SCUGRAD": "ugTotal", "UPGRNTP": "upPell"}
)

univData2 = pd.merge(univData2, univFinAidClean, on="UNITID", how="left")
univData2["expPerStudent"] = univData2["totalExp"] / univData2["ugTotal"]
univData2["upPell"] = univData2["upPell"] / 100

univData2.to_csv(DATA / "Clean" / "features.csv")
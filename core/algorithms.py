from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Dict, List, Tuple, TYPE_CHECKING

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None
try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover
    np = None

if TYPE_CHECKING:
    import pandas as pd  # type: ignore

DATA_DIR = Path(__file__).resolve().parents[1] / "Algoritthm implementation" / "data"

POLICY_REQUIRED_COLUMNS = [
    "Sec_Protocol",
    "Sec_Placement",
    "Data Lifetime",
    "Device",
    "Exposure",
    "Purdue Layer",
    "C_level",
    "A_level",
    "I_level",
    "Business impact",
]

UTILITY_REQUIRED_COLUMNS = [
    "Possible Deployed CAT",
    "Has_Enc",
    "Device",
    "Purdue Layer",
    "Protocols",
]


def _require_pandas():
    if pd is None:
        raise ImportError("pandas is required to run algorithm calculations.")


def _require_numpy():
    if np is None:
        raise ImportError("numpy is required to run algorithm calculations.")


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower().replace("_", " "))


def _get_col(df, desired: str) -> str:
    target = _normalize(desired)
    for col in df.columns:
        if _normalize(str(col)) == target:
            return col
    raise KeyError(desired)


def _find_col_optional(df, *candidates):
    norm = {re.sub(r"[\s_]+", "", str(c)).lower(): c for c in df.columns}
    for cand in candidates:
        key = re.sub(r"[\s_]+", "", cand).lower()
        if key in norm:
            return norm[key]
    return None


def _require_columns(df, required: List[str]) -> Dict[str, str]:
    mapping = {}
    for name in required:
        try:
            mapping[name] = _get_col(df, name)
        except KeyError:
            raise ValueError(f"Missing required column: {name}")
    return mapping


def _cat_value(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().upper()
    if text.startswith("CAT-"):
        try:
            return int(text.replace("CAT-", ""))
        except ValueError:
            return None
    if text.isdigit():
        return int(text)
    return None


def _safe_int_cat(value) -> int | None:
    if isinstance(value, (int, float)) and value in (1, 3, 5):
        return int(value)
    if isinstance(value, str):
        val = value.strip()
        if val.isdigit():
            num = int(val)
            if num in (1, 3, 5):
                return num
    return None


def _normalize_weights(*weights):
    total = sum(weights)
    if total == 0:
        return weights
    return tuple(w / total for w in weights)


def compute_possible_deployed_cat(df):
    _require_pandas()
    mapping = _require_columns(df, POLICY_REQUIRED_COLUMNS)

    sec_protocol = df[mapping["Sec_Protocol"]].astype(str)
    sec_placement = df[mapping["Sec_Placement"]].astype(str)
    data_lifetime = df[mapping["Data Lifetime"]].astype(str)
    device = df[mapping["Device"]].astype(str)
    exposure = df[mapping["Exposure"]].astype(str)
    purdue = df[mapping["Purdue Layer"]].astype(str)

    protocols = [
        "TLS",
        "DLTS",
        "IPsec",
        "MACsec",
        "SSH",
        "DLMS",
        "COSEM",
        "OPC UA",
        "DNP3",
        "BACnet/SC",
        "HTTPS",
    ]
    pattern = r"\b(?:%s)\b" % "|".join(map(re.escape, protocols))
    mask = sec_protocol.str.contains(pattern, case=False, na=False)
    mask_1 = sec_placement.str.contains(r"\bWAN\b", case=False, na=False)
    mask_7 = sec_placement.str.contains(r"\bGatewayOnly\b", case=False, na=False)
    mask_2 = data_lifetime.str.contains(r"(?<!\w)10y(?:\+)?(?!\w)", case=False, na=False)
    mask_3 = device.str.contains(r"\bResource Constrained\b", case=False, na=False)
    mask_4 = exposure.str.contains(r"\blow\b", case=False, na=False)

    def default_vote(j: int) -> str:
        if mask_2[j]:
            return "CAT-5"
        if mask_3[j] and mask_4[j]:
            return "CAT-1"
        return "CAT-3"

    def impact_vote(j: int) -> str:
        c = str(df[mapping["C_level"]][j]).strip()
        a = str(df[mapping["A_level"]][j]).strip()
        i = str(df[mapping["I_level"]][j]).strip()
        b = str(df[mapping["Business impact"]][j]).strip()
        if c == "L" and a == "L" and i == "L" and b == "L":
            return "CAT-1"
        return "CAT-3"

    def exposure_vote(j: int) -> str:
        if exposure.str.contains(r"\blow\b", case=False, na=False)[j]:
            return "CAT-1"
        return "CAT-3"

    def lifetime_vote(j: int) -> str:
        if mask_2[j]:
            return "CAT-5"
        return "CAT-3"

    cats: List[object] = []
    for idx in range(len(df)):
        if mask[idx]:
            required_cat = max(
                _cat_value(default_vote(idx)) or 0,
                _cat_value(impact_vote(idx)) or 0,
                _cat_value(lifetime_vote(idx)) or 0,
                _cat_value(exposure_vote(idx)) or 0,
            )
            if mask_3[idx]:
                endcap = 1
                if required_cat > endcap:
                    if mask_7[idx]:
                        deployable = required_cat
                    else:
                        deployable = endcap
                else:
                    deployable = required_cat
            else:
                deployable = required_cat
            cats.append(deployable)
        else:
            purdue_val = str(purdue[idx]).replace("–", "-")
            if mask_1[idx] or purdue_val == "L2-L2":
                required_cat = max(
                    _cat_value(default_vote(idx)) or 0,
                    _cat_value(impact_vote(idx)) or 0,
                    _cat_value(lifetime_vote(idx)) or 0,
                    _cat_value(exposure_vote(idx)) or 0,
                )
                if mask_3[idx]:
                    endcap = 1
                    if required_cat > endcap:
                        if mask_7[idx]:
                            deployable = required_cat
                        else:
                            deployable = endcap
                    else:
                        deployable = required_cat
                else:
                    deployable = required_cat
                cats.append(deployable)
            else:
                cats.append("PQC unprotected")

    df = df.copy()
    df["Possible Deployed CAT"] = cats
    return df


@lru_cache
def _load_reference_data():
    _require_pandas()
    cpu_xls = pd.ExcelFile(DATA_DIR / "oqs_speed_parsed_nist_sizes.xlsx")
    cpu_sig = pd.read_excel(cpu_xls, "SIG_wide")
    cpu_kem = pd.read_excel(cpu_xls, "KEM_wide")

    mcu_xls = pd.ExcelFile(DATA_DIR / "pqm4_size_nist_sizes.xlsx")
    mcu_sig = pd.read_excel(mcu_xls, "SIG_table")
    mcu_kem = pd.read_excel(mcu_xls, "KEM_table")
    return cpu_kem, cpu_sig, mcu_kem, mcu_sig


def _build_server_maps(df_cpu_benchmarking_kem, cats=(1, 3, 5)):
    maps = {c: {"cpu_us": {}, "bytes": {}} for c in cats}
    for j in range(len(df_cpu_benchmarking_kem)):
        cat_raw = df_cpu_benchmarking_kem.loc[j, "NIST_Category"]
        if pd.isna(cat_raw):
            continue
        try:
            cat = int(float(cat_raw))
        except Exception:
            continue
        if cat not in maps:
            continue
        alg = df_cpu_benchmarking_kem.loc[j, "Algorithm"]
        cpu_us = float(df_cpu_benchmarking_kem.loc[j, "decaps__Time_us_mean"]) + float(
            df_cpu_benchmarking_kem.loc[j, "encaps__Time_us_mean"]
        )
        b = float(df_cpu_benchmarking_kem.loc[j, "PK_bytes"]) + float(
            df_cpu_benchmarking_kem.loc[j, "CT_bytes"]
        )
        maps[cat]["cpu_us"][alg] = cpu_us
        maps[cat]["bytes"][alg] = b
    return maps


def _build_mcu_maps(df_mcu_benchmarking_kem, cats=(1, 3, 5)):
    maps = {c: {"cycles": {}, "bytes": {}, "ram": {}} for c in cats}
    for k in range(len(df_mcu_benchmarking_kem)):
        cat_raw = df_mcu_benchmarking_kem.loc[k, "NIST_Category"]
        if pd.isna(cat_raw):
            continue
        try:
            cat = int(float(cat_raw))
        except Exception:
            continue
        if cat not in maps:
            continue
        alg = df_mcu_benchmarking_kem.loc[k, "Algorithm"]
        cyc = float(df_mcu_benchmarking_kem.loc[k, "Encapsulation [cycles] (mean)"]) + float(
            df_mcu_benchmarking_kem.loc[k, "Decapsulation [cycles] (mean)"]
        )
        b = float(df_mcu_benchmarking_kem.loc[k, "PK_bytes"]) + float(
            df_mcu_benchmarking_kem.loc[k, "CT_bytes"]
        )
        ram_peak = max(
            float(df_mcu_benchmarking_kem.loc[k, "Encapsulation [bytes]"]),
            float(df_mcu_benchmarking_kem.loc[k, "Decapsulation [bytes]"]),
        )
        maps[cat]["cycles"][alg] = cyc
        maps[cat]["bytes"][alg] = b
        maps[cat]["ram"][alg] = ram_peak
    return maps


def _rank_server(server_map, time_ref_us, bytes_ref, w_cpu=0.7, w_bytes=0.3):
    cpu_map = server_map["cpu_us"]
    b_map = server_map["bytes"]
    out = []
    for alg in cpu_map.keys():
        cpu_norm = cpu_map[alg] / time_ref_us
        b_norm = b_map.get(alg, 0.0) / bytes_ref
        u = w_cpu * cpu_norm + w_bytes * b_norm
        out.append({"Name": alg, "utility": u})
    out.sort(key=lambda x: x["utility"])
    return out


def _rank_mcu(mcu_map, cycles_ref, bytes_ref, ram_ref, w_cpu=0.6, w_bytes=0.2, w_ram=0.2):
    w_cpu, w_bytes, w_ram = _normalize_weights(w_cpu, w_bytes, w_ram)
    c_map = mcu_map["cycles"]
    b_map = mcu_map["bytes"]
    r_map = mcu_map["ram"]
    out = []
    for alg in c_map.keys():
        cpu_norm = c_map[alg] / cycles_ref
        b_norm = b_map.get(alg, 0.0) / bytes_ref
        r_norm = r_map.get(alg, 0.0) / ram_ref
        u = w_cpu * cpu_norm + w_bytes * b_norm + w_ram * r_norm
        out.append({"Name": alg, "utility": u})
    out.sort(key=lambda x: x["utility"])
    return out


def _build_server_sig_maps(df_cpu_sig, cats=(1, 3, 5)):
    maps = {c: {"cpu_us": {}, "bytes": {}} for c in cats}
    for j in range(len(df_cpu_sig)):
        cat_raw = df_cpu_sig.loc[j, "NIST_Category"]
        if pd.isna(cat_raw):
            continue
        try:
            cat = int(float(cat_raw))
        except Exception:
            continue
        if cat not in maps:
            continue
        alg = df_cpu_sig.loc[j, "Algorithm"]
        cpu_us = float(df_cpu_sig.loc[j, "sign__Time_us_mean"]) + float(
            df_cpu_sig.loc[j, "verify__Time_us_mean"]
        )
        b = float(df_cpu_sig.loc[j, "PK_bytes"]) + float(df_cpu_sig.loc[j, "SIG_bytes"])
        maps[cat]["cpu_us"][alg] = cpu_us
        maps[cat]["bytes"][alg] = b
    return maps


def _find_col_sig(df, candidates):
    cols = list(df.columns)
    strip_map = {str(c).strip(): c for c in cols}
    for cand in candidates:
        if cand in cols:
            return cand
    for cand in candidates:
        if cand in strip_map:
            return strip_map[cand]
    for col in cols:
        lc = str(col).lower()
        for cand in candidates:
            if cand.lower() in lc:
                return col
    raise KeyError(f"None of candidates found: {candidates}")


def _build_mcu_sig_maps(df_mcu_sig, cats=(1, 3, 5)):
    maps = {c: {"cycles": {}, "bytes": {}, "ram": {}} for c in cats}
    col_sign_cyc = _find_col_sig(
        df_mcu_sig,
        ["Sign[Cycles](mean)", "Sign[Cycles] (mean)", "Sign Cycles (mean)", "Sign[Cycles]"],
    )
    col_ver_cyc = _find_col_sig(
        df_mcu_sig,
        ["Verify[Cycles](mean)", "Verify[Cycles] (mean)", "Verify Cycles (mean)", "Verify[Cycles]"],
    )
    col_sign_ram = _find_col_sig(df_mcu_sig, ["Sign(bytes)", "Sign [bytes]", "Sign (bytes)"])
    col_ver_ram = _find_col_sig(df_mcu_sig, ["Verify(bytes)", "Verify [bytes]", "Verify (bytes)"])

    for k in range(len(df_mcu_sig)):
        cat_raw = df_mcu_sig.loc[k, "NIST_Category"]
        if pd.isna(cat_raw):
            continue
        try:
            cat = int(float(cat_raw))
        except Exception:
            continue
        if cat not in maps:
            continue
        alg = df_mcu_sig.loc[k, "Algorithm"]
        cyc = float(df_mcu_sig.loc[k, col_sign_cyc]) + float(df_mcu_sig.loc[k, col_ver_cyc])
        b = float(df_mcu_sig.loc[k, "PK_bytes"]) + float(df_mcu_sig.loc[k, "SIG_bytes"])
        ram_peak = max(float(df_mcu_sig.loc[k, col_sign_ram]), float(df_mcu_sig.loc[k, col_ver_ram]))
        maps[cat]["cycles"][alg] = cyc
        maps[cat]["bytes"][alg] = b
        maps[cat]["ram"][alg] = ram_peak
    return maps


def _rank_server_sig(server_map, time_ref_us, bytes_ref, mult=1, w_cpu=0.7, w_bytes=0.3):
    cpu_map = server_map["cpu_us"]
    b_map = server_map["bytes"]
    out = []
    for alg in cpu_map.keys():
        cpu_norm = (cpu_map[alg] * mult) / time_ref_us
        b_norm = (b_map.get(alg, 0.0) * mult) / bytes_ref
        u = w_cpu * cpu_norm + w_bytes * b_norm
        out.append({"Name": alg, "utility": u})
    out.sort(key=lambda x: x["utility"])
    return out


def _rank_mcu_sig(mcu_map, cycles_ref, bytes_ref, ram_ref, mult=1, w_cpu=0.6, w_bytes=0.2, w_ram=0.2):
    w_cpu, w_bytes, w_ram = _normalize_weights(w_cpu, w_bytes, w_ram)
    c_map = mcu_map["cycles"]
    b_map = mcu_map["bytes"]
    r_map = mcu_map["ram"]
    out = []
    for alg in c_map.keys():
        cpu_norm = (c_map[alg] * mult) / cycles_ref
        b_norm = (b_map.get(alg, 0.0) * mult) / bytes_ref
        r_norm = (r_map.get(alg, 0.0)) / ram_ref
        u = w_cpu * cpu_norm + w_bytes * b_norm + w_ram * r_norm
        out.append({"Name": alg, "utility": u})
    out.sort(key=lambda x: x["utility"])
    return out


def compute_utility_scores(df):
    _require_pandas()
    _require_numpy()
    mapping = _require_columns(df, UTILITY_REQUIRED_COLUMNS)
    cat_col = mapping["Possible Deployed CAT"]
    has_enc = df[mapping["Has_Enc"]].astype(str)
    device = df[mapping["Device"]].astype(str)
    purdue = df[mapping["Purdue Layer"]].astype(str)
    protocols = df[mapping["Protocols"]].astype(str)
    cat = df[cat_col]

    auth_col = _find_col_optional(df, "Auth_Type", "Auth Type")

    mask_device = device.str.contains(r"\bServers\b|\bgateway\b", case=False, na=False)
    mask_constrained = device.str.contains(r"\bResource Constrained\b", case=False, na=False)

    bucket_low = purdue.str.contains(r"\bL0\b|\bL1\b|\bL2\b", case=False, na=False)
    bucket_med = purdue.str.contains(r"\bL3\b", case=False, na=False)
    bucket_high = purdue.str.contains(r"\bL4\b|\bL5\b", case=False, na=False)

    protocol_high = protocols.str.contains(
        r"\bEthernet\b|\bWireless\b|\bVPN\b|\bTLS\b|\bWebService\b|\bInternet\b",
        case=False,
        na=False,
    )

    if auth_col:
        auth_type = df[auth_col].astype(str)
        mask_auth = auth_type.str.contains(r"\bServerCert\b", case=False, na=False)
        mask_auth_mut = auth_type.str.contains(r"\bMutCert\b", case=False, na=False)
    else:
        mask_auth = pd.Series(False, index=df.index)
        mask_auth_mut = pd.Series(False, index=df.index)

    strict_us, medium_us, loose_us = 10_000, 50_000, 200_000
    strict_cyc, medium_cyc, loose_cyc = 1_200_000, 6_000_000, 24_000_000

    n_pkts_server, n_pkts_emb, n_pkts_cons = 10, 6, 3
    bytes_ref_eth_server = 1500 * n_pkts_server
    bytes_ref_mtu_server = 512 * n_pkts_server
    bytes_ref_eth_emb = 1500 * n_pkts_emb
    bytes_ref_mtu_emb = 512 * n_pkts_emb
    bytes_ref_eth_cons = 1500 * n_pkts_cons
    bytes_ref_mtu_cons = 512 * n_pkts_cons

    default_ram_ref = 131072

    cpu_kem, cpu_sig, mcu_kem, mcu_sig = _load_reference_data()
    server_maps = _build_server_maps(cpu_kem, cats=(1, 3, 5))
    mcu_maps = _build_mcu_maps(mcu_kem, cats=(1, 3, 5))
    server_sig_maps = _build_server_sig_maps(cpu_sig, cats=(1, 3, 5))
    mcu_sig_maps = _build_mcu_sig_maps(mcu_sig, cats=(1, 3, 5))

    df = df.copy()
    df["Enc_Ranking_By_Utility"] = ""
    df["Enc_Best_Alg"] = ""
    df["Enc_Best_Utility"] = 0.0
    df["Auth_Ranking_By_Utility"] = ""
    df["Auth_Best_Alg"] = ""
    df["Auth_Best_Utility"] = 0.0

    id_col = _find_col_optional(df, "ID")
    if id_col:
        groups = df.groupby(id_col).indices
    else:
        groups = {idx: [idx] for idx in df.index}

    for _, indices in groups.items():
        idx = indices[0]

        if str(df.loc[idx, cat_col]).strip() == "PQC unprotected":
            continue

        cat_val = _safe_int_cat(df.loc[idx, cat_col])
        if cat_val is None:
            continue

        if bucket_low.loc[idx]:
            time_ref_us = strict_us
            cycles_ref = strict_cyc
        elif bucket_med.loc[idx]:
            time_ref_us = medium_us
            cycles_ref = medium_cyc
        elif bucket_high.loc[idx]:
            time_ref_us = loose_us
            cycles_ref = loose_cyc
        else:
            time_ref_us = medium_us
            cycles_ref = medium_cyc

        if protocol_high.loc[idx]:
            bytes_ref_server = bytes_ref_eth_server
            bytes_ref_emb = bytes_ref_eth_emb
            bytes_ref_cons = bytes_ref_eth_cons
        else:
            bytes_ref_server = bytes_ref_mtu_server
            bytes_ref_emb = bytes_ref_mtu_emb
            bytes_ref_cons = bytes_ref_mtu_cons

        if str(has_enc.loc[idx]).strip().upper() != "NO":
            if mask_constrained.loc[idx]:
                enc_ranked = _rank_mcu(
                    mcu_maps[cat_val],
                    cycles_ref,
                    bytes_ref_cons,
                    default_ram_ref,
                    w_cpu=0.6,
                    w_bytes=0.2,
                    w_ram=0.2,
                )
            elif mask_device.loc[idx]:
                enc_ranked = _rank_server(
                    server_maps[cat_val], time_ref_us, bytes_ref_server, w_cpu=0.7, w_bytes=0.3
                )
            else:
                enc_ranked = _rank_mcu(
                    mcu_maps[cat_val],
                    cycles_ref,
                    bytes_ref_emb,
                    default_ram_ref,
                    w_cpu=0.6,
                    w_bytes=0.2,
                    w_ram=0.2,
                )

            if enc_ranked:
                ranking_str = ", ".join([f'{x["Name"]}:{x["utility"]:.8f}' for x in enc_ranked])
                best = enc_ranked[0]
                df.loc[indices, "Enc_Ranking_By_Utility"] = ranking_str
                df.loc[indices, "Enc_Best_Alg"] = best["Name"]
                df.loc[indices, "Enc_Best_Utility"] = best["utility"]

        if not (mask_auth.loc[idx] or mask_auth_mut.loc[idx]):
            continue

        mult = 2 if mask_auth_mut.loc[idx] else 1
        if mask_constrained.loc[idx]:
            auth_ranked = _rank_mcu_sig(
                mcu_sig_maps[cat_val],
                cycles_ref,
                bytes_ref_cons,
                default_ram_ref,
                mult=mult,
                w_cpu=0.6,
                w_bytes=0.2,
                w_ram=0.2,
            )
        elif mask_device.loc[idx]:
            auth_ranked = _rank_server_sig(
                server_sig_maps[cat_val],
                time_ref_us,
                bytes_ref_server,
                mult=mult,
                w_cpu=0.7,
                w_bytes=0.3,
            )
        else:
            auth_ranked = _rank_mcu_sig(
                mcu_sig_maps[cat_val],
                cycles_ref,
                bytes_ref_emb,
                default_ram_ref,
                mult=mult,
                w_cpu=0.6,
                w_bytes=0.2,
                w_ram=0.2,
            )

        if auth_ranked:
            ranking_str = ", ".join([f'{x["Name"]}:{x["utility"]:.8f}' for x in auth_ranked])
            best = auth_ranked[0]
            df.loc[indices, "Auth_Ranking_By_Utility"] = ranking_str
            df.loc[indices, "Auth_Best_Alg"] = best["Name"]
            df.loc[indices, "Auth_Best_Utility"] = best["utility"]

    # Confidence scores
    float_re = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

    def parse_alg_utils(cell):
        if pd.isna(cell):
            return [], []
        s = str(cell).replace("…", "").replace("...", "").strip()
        if not s:
            return [], []
        algs, utils = [], []
        for part in s.split(","):
            part = part.strip()
            if ":" not in part:
                continue
            alg, val = part.split(":", 1)
            alg = alg.strip()
            val = val.strip()
            try:
                u = float(val)
            except ValueError:
                m = float_re.search(val)
                if not m:
                    continue
                u = float(m.group(0))
            algs.append(alg)
            utils.append(u)
        return algs, utils

    def softmax_probs_from_util(cell, alpha=0.01, eps=1e-12):
        algs, utils = parse_alg_utils(cell)
        if not algs:
            return [], np.array([])
        u = np.array(utils, dtype=float)
        umin = float(u.min())
        tau = max(alpha * umin, eps)
        s = -(u - umin) / tau
        s = s - s.max()
        e = np.exp(s)
        p = e / e.sum()
        return algs, p

    def topk_confidence_string(cell, k=3, alpha=0.01, digits=6):
        algs, p = softmax_probs_from_util(cell, alpha=alpha)
        if len(algs) == 0:
            return np.nan
        items = sorted(zip(algs, p), key=lambda x: x[1], reverse=True)[:k]
        return ", ".join([f"{a}:{v:.{digits}f}" for a, v in items])

    df["Enc_Confidence_Top3"] = df["Enc_Ranking_By_Utility"].apply(
        lambda x: topk_confidence_string(x, k=3, alpha=0.01)
    )
    df["Auth_Confidence_Top3"] = df["Auth_Ranking_By_Utility"].apply(
        lambda x: topk_confidence_string(x, k=3, alpha=0.01, digits=6)
    )

    # Migration priority
    def as_text(val):
        if pd.isna(val):
            return ""
        return str(val).strip()

    def yn_maybe(val, unknown=0.5):
        s = as_text(val).lower()
        if s in {"y", "yes", "true", "1"}:
            return 1.0
        if s in {"n", "no", "false", "0"}:
            return 0.0
        if "maybe" in s or "partial" in s:
            return 0.5
        if "unknown" in s or s == "":
            return unknown
        return unknown

    def exposure_score_from_protocols(proto):
        s = as_text(proto).lower()
        if "internet" in s or "external" in s or "b2b" in s:
            return 1.0
        if "wan" in s or "extranet" in s or "cell" in s or "phone" in s:
            return 0.7
        if "lan" in s or "ethernet" in s or "internal" in s or "intranet" in s:
            return 0.4
        if "isolated" in s or "offline" in s:
            return 0.1
        return 0.4

    def business_impact_score(val):
        s = as_text(val).lower()
        if "high" in s:
            return 1.0
        if "medium" in s:
            return 0.6
        if "low" in s:
            return 0.3
        return np.nan

    def lifetime_score(val):
        s = as_text(val).lower().replace(" ", "")
        if not s:
            return np.nan
        if "10y" in s or "10+" in s:
            return 1.0
        if "5-10" in s or "5to10" in s:
            return 0.8
        if "1-5" in s or "1to5" in s:
            return 0.5
        if "<1" in s or "0-1" in s or "lessthan1" in s:
            return 0.2
        return np.nan

    def purdue_layer_to_impact(val):
        s = as_text(val).upper()
        nums = [int(n) for n in re.findall(r"\d", s)]
        if not nums:
            return 0.6
        m = min(nums)
        if m <= 2:
            return 1.0
        if m == 3:
            return 0.7
        return 0.3

    def placement_friction(val):
        s = as_text(val).lower()
        if "endtoend" in s or "end-to-end" in s:
            return 1.0
        if "gatewayonly" in s or "gateway-only" in s:
            return 0.6
        if "vpn" in s or "partial" in s:
            return 0.4
        return 0.6

    def purdue_friction(val):
        s = as_text(val).upper()
        nums = [int(n) for n in re.findall(r"\d", s)]
        if not nums:
            return 0.7

        def fr(layer):
            if layer <= 2:
                return 1.0
            if layer == 3:
                return 0.7
            return 0.4

        return max(fr(n) for n in nums)

    def device_friction(val):
        s = as_text(val).lower()
        if "constrained" in s:
            return 1.0
        if "embedded" in s or "mcu" in s:
            return 0.7
        if "server" in s or "gateway" in s:
            return 0.3
        return 0.7

    col_protocols = _find_col_optional(df, "Protocols", "Protocol")
    col_purdue = _find_col_optional(df, "Purdue Layer", "Purdue_Layer")
    col_exposure = _find_col_optional(df, "Exposure")
    col_impact = _find_col_optional(df, "Business impact", "Impact")
    col_lifetime = _find_col_optional(df, "Data lifetime", "Lifetime")
    col_pii = _find_col_optional(df, "Contains PII", "PII")
    col_fw = _find_col_optional(df, "Firmware upgradable", "Firmware_upgradable")
    col_cm = _find_col_optional(df, "Crypto modifiable", "Crypto_modifiable")
    col_vendor = _find_col_optional(
        df,
        "Vendor Support of PQC",
        "Vendor support of PQC",
        "Vendor_Support_of_PQC",
    )
    col_place = _find_col_optional(df, "Sec_Placement", "Sec Placement")
    col_devtype = _find_col_optional(df, "Device type", "Device_type", "DeviceType", "Device")

    if col_exposure:
        E = df[col_exposure].apply(exposure_score_from_protocols)
    else:
        E = df[col_protocols].apply(exposure_score_from_protocols) if col_protocols else pd.Series(0.4, index=df.index)

    if col_impact:
        I = df[col_impact].apply(business_impact_score)
        if col_purdue:
            I = I.fillna(df[col_purdue].apply(purdue_layer_to_impact))
        else:
            I = I.fillna(0.6)
    else:
        I = df[col_purdue].apply(purdue_layer_to_impact) if col_purdue else pd.Series(0.6, index=df.index)

    if col_lifetime:
        L = df[col_lifetime].apply(lifetime_score).fillna(0.5)
    else:
        L = pd.Series(0.5, index=df.index)

    include_pii = False
    if include_pii and col_pii:
        P = df[col_pii].apply(lambda x: 1.0 if as_text(x).lower() in {"y", "yes", "true", "1"} else 0.0)
        R = (0.45 * E + 0.35 * I + 0.20 * L + 0.10 * P) / 1.10
    else:
        R = 0.45 * E + 0.35 * I + 0.20 * L

    FW = df[col_fw].apply(yn_maybe) if col_fw else pd.Series(0.5, index=df.index)
    CM = df[col_cm].apply(yn_maybe) if col_cm else pd.Series(0.5, index=df.index)

    def vendor_score(val):
        s = as_text(val).lower()
        if s in {"y", "yes", "true", "1"}:
            return 1.0
        if "unknown" in s or s == "" or "n/unknown" in s:
            return 0.5
        if s in {"n", "no", "false", "0"}:
            return 0.0
        return 0.5

    V = df[col_vendor].apply(vendor_score) if col_vendor else pd.Series(0.5, index=df.index)
    F = 0.4 * FW + 0.4 * CM + 0.2 * V

    S = df[col_place].apply(placement_friction) if col_place else pd.Series(0.6, index=df.index)
    Pu = df[col_purdue].apply(purdue_friction) if col_purdue else pd.Series(0.7, index=df.index)
    D = df[col_devtype].apply(device_friction) if col_devtype else pd.Series(0.7, index=df.index)
    C = 0.4 * S + 0.3 * Pu + 0.3 * D

    score = 0.5 * R + 0.3 * F - 0.2 * C
    level = np.select([score >= 0.5, score >= 0.3], ["High", "Medium"], default="Low")
    df["Migration_Priority"] = [
        f"{s:.3f} ({lvl})" if pd.notna(s) else np.nan for s, lvl in zip(score, level)
    ]

    return df

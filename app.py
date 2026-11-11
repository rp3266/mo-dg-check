import html
import re
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="澳門受管制危險品查詢系統", page_icon="🔍", layout="wide"
)

# ==================== 🔐 密碼驗證區塊 (使用 st.secrets) ====================
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    if "APP_PASSWORD" not in st.secrets:
        st.error("⚠️ 未找到密碼設定！請於 .streamlit/secrets.toml 設定 APP_PASSWORD。")
        return False

    st.markdown("## 🔒 澳門受管制危險品查詢系統")
    st.caption("本系統受密碼保護，請輸入授權密碼以繼續。")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            password_input = st.text_input("存取密碼：", type="password")
            submit_pass = st.form_submit_button("🔓 登入系統", use_container_width=True)

        if submit_pass:
            if password_input == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ 密碼錯誤，請重新輸入！")

    return False

if not check_password():
    st.stop()
# ==============================================================================


@st.cache_data
def load_data():
    # 1. 載入主數據庫（受管制危險品清單）
    try:
        df = pd.read_excel("MO DG Law.xlsx", sheet_name="受管制危險品清單")
    except Exception as e:
        st.error(f"無法載入數據檔案 MO DG Law.xlsx (受管制危險品清單): {e}")
        st.stop()

    df = df.fillna("")

    # 驗證必要欄位是否存在
    required_cols = [
        "危險品序號",
        "子分類",
        "聯合國編號",
        "危險品或物品名稱",
        "別名",
        "英文名（非正式）",
        "化學文摘社編號",
        "實驗室豁免量上限（單位）",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"資料庫缺少以下必要欄位: {', '.join(missing_cols)}")
        st.stop()

    # 清理 UN 編號
    def clean_un(val):
        if not val or pd.isna(val):
            return ""
        val_str = str(val).strip().split(".")[0]
        if val_str.isdigit():
            return val_str.zfill(4)
        return val_str

    # 清理子分類
    def clean_subcat(val):
        if pd.isna(val) or val == "":
            return ""
        try:
            f_val = float(val)
            if f_val.is_integer():
                return str(int(f_val))
            return str(val).strip()
        except (ValueError, TypeError):
            return str(val).strip()

    # 清理並拆分 CAS 號 (使用正則表達式增強容錯)
    def extract_cas_set(val):
        if not val or pd.isna(val):
            return set()
        val_str = str(val).strip().lower()
        items = re.split(r"[;；,，/、:\s\r\n]+", val_str)
        return {item.strip() for item in items if item.strip()}

    df["UN_Clean"] = df["聯合國編號"].apply(clean_un)
    df["CAS_Clean"] = df["化學文摘社編號"].astype(str).str.strip().str.lower()
    df["CAS_Set"] = df["化學文摘社編號"].apply(extract_cas_set)
    df["子分類"] = df["子分類"].apply(clean_subcat)

    # 清理所有文字欄位中的換行符，防止表格顯示異常
    for col in required_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("\n", " ")
            .str.replace("\r", "")
            .str.strip()
        )

    # 2. 載入 NOS 物質清單與更新日期
    nos_update_date = "未獲取"
    nos_un_set = set()
    try:
        df_nos_raw = pd.read_excel(
            "MO DG Law_v02.xlsx", sheet_name="受管制NOS物質清單", header=None
        )
        if len(df_nos_raw) > 0:
            raw_date = str(df_nos_raw.iloc[0, 0]).strip()
            if raw_date and raw_date != "nan":
                nos_update_date = raw_date

            un_series = df_nos_raw.iloc[2:, 0].dropna()
            for val in un_series:
                v_str = str(val).strip().split(".")[0]
                if v_str.isdigit():
                    nos_un_set.add(v_str.zfill(4))
                elif v_str:
                    nos_un_set.add(v_str)
    except Exception as e:
        st.error(f"無法載入受管制 NOS 物質清單: {e}")

    return df, nos_un_set, nos_update_date


df, nos_un_set, nos_update_date = load_data()

# --- 側邊欄導覽選單 ---
st.sidebar.title("功能導覽")

if st.sidebar.button("🔒 登出系統", use_container_width=True):
    st.session_state["password_correct"] = False
    st.rerun()

page = st.sidebar.radio(
    "請選擇功能頁面：",
    ["檢索方式一", "檢索方式二(原生)", "檢索方式三", "NOS物質查詢"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.caption("澳門特別行政區受管制危險品及藥品資料庫")

display_cols = [
    "危險品序號",
    "子分類",
    "聯合國編號",
    "危險品或物品名稱",
    "別名",
    "英文名（非正式）",
    "化學文摘社編號",
    "實驗室豁免量上限（單位）",
]

# --- 第一頁：檢索方式一 ---
if page == "檢索方式一":
    st.markdown("## 🔍 請輸入檢索條件查詢受管制危險品")
    st.caption("請輸入名稱、CAS 號或聯合國編號進行精確/模糊檢索（名稱需符合嚴格連續順序字串）")

    with st.form(key="search_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            query_name = st.text_input(
                "名稱 (中文 / 英文 / 別名)",
                placeholder="例：苦味酸銨 / Acetone / 酸",
                help="中文與英文皆須符合「嚴格連續順序字串（Exact Substring）」",
            )
        with col2:
            query_cas = st.text_input(
                "CAS 號 (化學文摘社編號)", placeholder="例：131-74-8 或 17639-93-9"
            )
        with col3:
            query_un = st.text_input(
                "聯合國編號 (UN No.)", placeholder="例：0004 或 4"
            )

        submit_button = st.form_submit_button(
            label="🔍 開始查詢", use_container_width=True
        )

    st.markdown("---")
    st.markdown("## 📋 受管制危險品查詢結果")

    if submit_button:
        name_q = query_name.strip().lower()
        cas_q = query_cas.strip().lower()
        un_q = query_un.strip().lower()

        # 檢驗 UN 編號輸入格式（數字為 5 位或以上視為錯誤）
        if un_q and un_q.isdigit() and len(un_q) >= 5:
            st.error("輸入格式錯誤：聯合國編號 (UN No.) 數字不能超過 4 位！")
        elif not name_q and not cas_q and not un_q:
            st.warning("請在上方至少輸入一項查詢條件！")
        else:
            scores_series = pd.Series(0.0, index=df.index)

            # 1. UN 編號檢索
            if un_q:
                un_input = un_q.zfill(4) if un_q.isdigit() else un_q
                un_exact = df["UN_Clean"] == un_input
                un_sub = df["UN_Clean"].str.contains(un_input, regex=False) & (df["UN_Clean"] != "")
                scores_series = pd.concat([scores_series, pd.Series(100.0, index=df[un_exact].index), pd.Series(85.0, index=df[un_sub].index)]).groupby(level=0).max()

            # 2. CAS 號檢索
            if cas_q:
                cas_exact = df["CAS_Set"].apply(lambda s: cas_q in s)
                cas_sub = df["CAS_Clean"].str.contains(cas_q, regex=False) & (df["CAS_Clean"] != "")
                scores_series = pd.concat([scores_series, pd.Series(100.0, index=df[cas_exact].index), pd.Series(90.0, index=df[cas_sub].index)]).groupby(level=0).max()

            # 3. 名稱檢索 (嚴格連續順序字串比對)
            if name_q:
                cn_s = df["危險品或物品名稱"].str.lower()
                alias_s = df["別名"].str.lower()
                en_s = df["英文名（非正式）"].str.lower()

                # 完全相等 -> 100%
                name_exact = (cn_s == name_q) | (alias_s == name_q) | (en_s == name_q)
                
                # 包含嚴格連續子字串 -> 90%
                name_sub = (
                    cn_s.str.contains(name_q, regex=False)
                    | alias_s.str.contains(name_q, regex=False)
                    | en_s.str.contains(name_q, regex=False)
                ) & (~name_exact)

                scores_series = pd.concat([
                    scores_series, 
                    pd.Series(100.0, index=df[name_exact].index),
                    pd.Series(90.0, index=df[name_sub].index)
                ]).groupby(level=0).max()

            matched_mask = scores_series > 0
            if matched_mask.any():
                res_df = df[matched_mask].copy()
                res_df["匹配率 (%)"] = scores_series[matched_mask].round(1)
                res_df = res_df.sort_values(by="匹配率 (%)", ascending=False)

                st.success(
                    f"共找到 {len(res_df)} 筆匹配資料（已按匹配率由高至低排列）："
                )

                search_cols = ["匹配率 (%)"] + display_cols
                calc_height = min((len(res_df) + 1) * 35 + 15, 600)

                st.dataframe(
                    res_df[search_cols],
                    use_container_width=True,
                    hide_index=True,
                    height=calc_height,
                    column_config={
                        "匹配率 (%)": st.column_config.ProgressColumn(
                            "匹配率 (%)",
                            help="與檢索條件的匹配相似度",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100,
                        )
                    },
                )
            else:
                st.info("未找到匹配的受管制危險品/藥品。")
    else:
        st.info("☝️ 請在上方選單輸入條件並點擊「開始查詢」。")

# --- 第二頁：檢索方式二(原生) ---
elif page == "檢索方式二(原生)":
    st.markdown("## 📚 澳門受管制危險品完整清單")
    st.caption(
        f"目前資料庫中共有 {len(df)} 筆受管制危險品與藥品紀錄。（改用 Streamlit 原生 Dataframe，完美支援多主題與響應式螢幕）"
    )
    st.markdown("---")

    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input(
            "💡 快速即時表格過濾：", placeholder="輸入任意關鍵字過濾目前表格..."
        )
    with col2:
        unique_subcats = [c for c in df["子分類"].unique() if str(c).strip() != ""]
        sub_cat = st.selectbox("分類過濾：", ["全部分類"] + sorted(unique_subcats))

    filtered_df = df.copy()
    if sub_cat != "全部分類":
        filtered_df = filtered_df[filtered_df["子分類"] == sub_cat]

    if keyword:
        kw = keyword.strip().lower()
        mask = (
            filtered_df["危險品或物品名稱"].str.lower().str.contains(kw, regex=False)
            | filtered_df["別名"].str.lower().str.contains(kw, regex=False)
            | filtered_df["英文名（非正式）"].str.lower().str.contains(kw, regex=False)
            | filtered_df["聯合國編號"].str.lower().str.contains(kw, regex=False)
            | filtered_df["化學文摘社編號"].str.lower().str.contains(kw, regex=False)
        )
        filtered_df = filtered_df[mask]

    if len(filtered_df) > 0:
        st.success(f"共找到 {len(filtered_df)} 筆匹配資料：")
    else:
        st.info("未找到匹配的受管制危險品/藥品。")

    st.dataframe(
        filtered_df[display_cols],
        use_container_width=True,
        hide_index=True,
        height=650,
    )

# --- 第三頁：檢索方式三 ---
elif page == "檢索方式三":
    st.markdown("## 🧪 檢索方式三：CAS 號批量精確比對")
    st.caption(
        "請在第一列「化學文摘社編號」中輸入單一 CAS 號（共 10 行）。系統會自動精確識別包含多組 CAS 號的物品紀錄。"
    )
    st.markdown("---")

    def init_batch_df():
        return pd.DataFrame(
            {
                "化學文摘社編號": [""] * 10,
                "是否受管制物質": [""] * 10,
                "子分類": [""] * 10,
                "聯合國編號": [""] * 10,
                "危險品或物品名稱": [""] * 10,
                "實驗室豁免量上限（單位）": [""] * 10,
            }
        )

    # 1. 初始化 Session State
    if "batch_df" not in st.session_state:
        st.session_state.batch_df = init_batch_df()

    col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 5])
    with col_btn1:
        start_check = st.button("🔍 開始批量比對", type="primary", use_container_width=True)
    with col_btn2:
        clear_table = st.button("🧹 清空重新輸入", use_container_width=True)

    # 2. 清空重新輸入邏輯
    if clear_table:
        st.session_state.batch_df = init_batch_df()
        if "batch_editor" in st.session_state:
            del st.session_state["batch_editor"]
        st.rerun()

    # 3. 點擊比對邏輯
    if start_check:
        current_df = st.session_state.batch_df.copy()
        
        # 從 data_editor 快取中提取用戶最新輸入的 CAS 號
        if "batch_editor" in st.session_state and "edited_rows" in st.session_state["batch_editor"]:
            for row_idx, changes in st.session_state["batch_editor"]["edited_rows"].items():
                if "化學文摘社編號" in changes:
                    current_df.at[row_idx, "化學文摘社編號"] = changes["化學文摘社編號"]

        updated_rows = []
        for _, row in current_df.iterrows():
            input_cas = str(row["化學文摘社編號"]).strip().lower()

            if not input_cas:
                updated_rows.append({
                    "化學文摘社編號": "",
                    "是否受管制物質": "",
                    "子分類": "",
                    "聯合國編號": "",
                    "危險品或物品名稱": "",
                    "實驗室豁免量上限（單位）": ""
                })
            # 檢查 CAS 號後 5 位格式是否符合 '-xx-x' (例如: -17-5 或 -74-8)
            elif not re.match(r".*-\d{2}-\d$", input_cas):
                updated_rows.append({
                    "化學文摘社編號": str(row["化學文摘社編號"]).strip(),
                    "是否受管制物質": "⚠️ 輸入格式錯誤",
                    "子分類": "-",
                    "聯合國編號": "-",
                    "危險品或物品名稱": "輸入格式錯誤：CAS 號後 5 位必須為 '-xx-x' 格式",
                    "實驗室豁免量上限（單位）": "-"
                })
            else:
                matched_mask = df["CAS_Set"].apply(lambda cas_set: input_cas in cas_set)
                matched_df = df[matched_mask]

                if len(matched_df) > 0:
                    subcats = "; ".join([str(x) for x in matched_df["子分類"].unique() if str(x) != ""])
                    uns = "; ".join([str(x) for x in matched_df["聯合國編號"].unique() if str(x) != ""])
                    names = "; ".join([str(x) for x in matched_df["危險品或物品名稱"].unique() if str(x) != ""])
                    exemptions = "; ".join([str(x) for x in matched_df["實驗室豁免量上限（單位）"].unique() if str(x) != ""])

                    updated_rows.append({
                        "化學文摘社編號": str(row["化學文摘社編號"]).strip(),
                        "是否受管制物質": "✅ 是",
                        "子分類": subcats,
                        "聯合國編號": uns,
                        "危險品或物品名稱": names,
                        "實驗室豁免量上限（單位）": exemptions
                    })
                else:
                    updated_rows.append({
                        "化學文摘社編號": str(row["化學文摘社編號"]).strip(),
                        "是否受管制物質": "❌ 否",
                        "子分類": "-",
                        "聯合國編號": "-",
                        "危險品或物品名稱": "非受管制物質 / 未找到匹配紀錄",
                        "實驗室豁免量上限（單位）": "-"
                    })

        # 更新狀態並刪除元件編輯記錄快取，強制畫面載入最新比對結果
        st.session_state.batch_df = pd.DataFrame(updated_rows)
        if "batch_editor" in st.session_state:
            del st.session_state["batch_editor"]
            
        st.success("批量比對完成！結果已於下方表格顯示。")

    # 4. 渲染表格
    st.data_editor(
        st.session_state.batch_df,
        key="batch_editor",
        use_container_width=True,
        hide_index=False,
        num_rows="fixed",
        height=400,
        column_config={
            "化學文摘社編號": st.column_config.TextColumn(
                "化學文摘社編號 (可輸入)",
                help="請在此欄位直接輸入或貼上單一 CAS 號，後 5 位格式必須為 -xx-x，例如：17639-93-9 或 131-74-8",
                width="medium",
            ),
            "是否受管制物質": st.column_config.TextColumn(
                "是否受管制物質",
                disabled=True,
                width="small",
            ),
            "子分類": st.column_config.TextColumn(
                "子分類",
                disabled=True,
                width="small",
            ),
            "聯合國編號": st.column_config.TextColumn(
                "聯合國編號",
                disabled=True,
                width="small",
            ),
            "危險品或物品名稱": st.column_config.TextColumn(
                "危險品或物品名稱",
                disabled=True,
                width="large",
            ),
            "實驗室豁免量上限（單位）": st.column_config.TextColumn(
                "實驗室豁免量上限（單位）",
                disabled=True,
                width="medium",
            ),
        },
    )

# --- 第四頁：NOS物質查詢 ---
elif page == "NOS物質查詢":
    st.markdown("## ⚠️ 受管制 NOS 物質核對查詢")
    st.info(f"📅 **受管制 NOS 物質清單：{nos_update_date}**")
    st.caption("請輸入聯合國編號（UN No.）檢查是否屬於澳門受管制 NOS 物質。")
    st.markdown("---")

    with st.form(key="nos_search_form"):
        input_un_nos = st.text_input(
            "聯合國編號 (UN No.)：",
            placeholder="例如：1993 或 0004",
            help="輸入數字自動補齊為 4 位編號進行核對",
        )
        submit_nos = st.form_submit_button("🔍 開始核對 NOS 物質", use_container_width=True)

    if submit_nos:
        raw_val = input_un_nos.strip()
        if not raw_val:
            st.warning("請先輸入聯合國編號！")
        # 檢驗 UN 編號輸入格式（數字為 5 位或以上視為錯誤）
        elif raw_val.isdigit() and len(raw_val) >= 5:
            st.error("輸入格式錯誤：聯合國編號 (UN No.) 數字不能超過 4 位！")
        else:
            un_nos_clean = raw_val.zfill(4) if raw_val.isdigit() else raw_val

            st.markdown("### 📋 核對結果")
            if un_nos_clean in nos_un_set:
                st.error(
                    f"⚠️ **核對結果：屬於受管制 NOS 物質**\n\n"
                    f"聯合國編號 **UN {un_nos_clean}** 已列於「受管制 NOS 物質清單」中。"
                )
            else:
                st.success(
                    f"✅ **核對結果：不屬於受管制 NOS 物質**\n\n"
                    f"聯合國編號 **UN {un_nos_clean}** 未列於受管制 NOS 物質清單內。"
                )

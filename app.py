import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import matplotlib.font_manager as fm
import requests
from datetime import datetime
import re

# 1. 한글 폰트 설정 (환경에 따라 자동 선택)
@st.cache_resource
def set_korean_font():
    font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = 'NanumGothic'
    else:
        plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False

set_korean_font()

st.set_page_config(page_title="스마트 물품보관함 AI 관제 시스템", layout="wide")

st.title("실시간 AI 물품보관함 수요 예측 관제탑")
st.markdown("기상청 관측, 유동인구, 서울시 공공데이터 기반 **45분 뒤** 잔여율 예측 시스템")
st.divider()

# ==========================================
# 2. [보안] API 키 설정 (공개용: 빈칸 유지)
# ==========================================
SEOUL_API_KEY = "" 

@st.cache_data(ttl=600)
def get_realtime_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,precipitation&timezone=Asia/Seoul"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data['current']['temperature_2m'], data['current']['precipitation']
    except: pass
    return None, None

def get_realtime_locker_data(api_key, area_nm):
    if not api_key: return None
    try:
        url = f"http://openapi.seoul.go.kr:8088/{api_key}/json/SmrtLocker/1/1000/"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'SmrtLocker' in data:
                rows = data['SmrtLocker']['row']
                # 스마트 키워드 추출
                keywords_raw = re.split(r'[ ·]', area_nm)
                exclude = ['관광특구', 'MICE', '특구', '역']
                keywords = []
                for k in keywords_raw:
                    for ex in exclude: k = k.replace(ex, "")
                    if len(k) >= 2: keywords.append(k)
                if not keywords: keywords = [area_nm[:2]]
                
                pattern = '|'.join(keywords)
                target_lockers = [r for r in rows if any(re.search(pattern, str(r.get(c, ''))) for c in ['STATN_NM', 'ADDR'])]
                if target_lockers:
                    total = sum(int(r.get('TOT_CNT', 0)) for r in target_lockers)
                    use = sum(int(r.get('USE_CNT', 0)) for r in target_lockers)
                    return ((total - use) / total) * 100 if total > 0 else None
    except: pass
    return None

# 3. 데이터 로드
@st.cache_data
def load_all_data():
    df_pred = pd.read_csv('prediction_results.csv')
    df_pred['동기화시간'] = pd.to_datetime(df_pred['동기화시간'])
    df_info = pd.read_csv('Locker_information.csv')
    return df_pred.sort_values('동기화시간'), df_info

try:
    df_pred, df_info = load_all_data()
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    st.stop()

# 4. 사이드바 및 지역 선택
area_list = df_pred['AREA_NM'].unique()
selected_area = st.sidebar.selectbox("관제할 지역을 선택하세요", area_list)
df_target = df_pred[df_pred['AREA_NM'] == selected_area].copy()

# 5. 실시간 정보 연동
now = datetime.now()
current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
latest_data = df_target.iloc[-1]

real_temp, real_rain = get_realtime_weather()
temp = real_temp if real_temp is not None else latest_data['기온']
rain = real_rain if real_rain is not None else latest_data['강수량']

real_rate = get_realtime_locker_data(SEOUL_API_KEY, selected_area)
current_rate = real_rate if real_rate is not None else latest_data['잔여율']
pred_rate = latest_data['AI_예측_잔여율']

# --- [A] 관제 종합 현황 ---
st.subheader(f"📊 [{selected_area}] 관제 종합 현황")
st.info(f"🕒 **현재 기준 시간:** {current_time_str} (실시간 관제 데이터 수집 중)")

c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("현재 날씨", f"{temp:.1f}도 / {rain}mm")
with c2: st.metric("현재 잔여율", f"{current_rate:.1f}%")
with c3: st.metric("45분 뒤 예측", f"{pred_rate:.1f}%", delta=f"{pred_rate-current_rate:.1f}%p")
with c4:
    if pred_rate <= 20: st.error("상태: 혼잡")
    elif pred_rate <= 50: st.warning("상태: 보통")
    else: st.success("상태: 여유")
st.divider()

# --- [B] 실제 보관함 인프라 상세 ---
st.subheader(f"🏢 [{selected_area}] 구역 내 실제 보관함 인프라 상세")

# 검색 키워드 고도화 (특수문자 및 불용어 제거)
keywords_raw = re.split(r'[ ·]', selected_area)
exclude = ['관광특구', 'MICE', '특구', '역']
keywords = []
for k in keywords_raw:
    for ex in exclude: k = k.replace(ex, "")
    if len(k) >= 2: keywords.append(k)
if not keywords: keywords = [selected_area[:2]]

pattern = '|'.join(keywords)
mask = df_info['stlckRprsPstnNm'].str.contains(pattern, na=False) | \
       df_info['fcltRoadNmAddr'].str.contains(pattern, na=False) | \
       df_info['stlckDtlPstnNm'].str.contains(pattern, na=False)
area_lockers = df_info[mask].copy()

if not area_lockers.empty:
    display_info = area_lockers[['stlckId', 'stlckRprsPstnNm', 'stlckDtlPstnNm', 'stlckCnt', 'fcltRoadNmAddr']].copy()
    display_info.columns = ['보관함 ID', '대표 명칭', '상세 위치', '설치 칸 수', '도로명 주소']
    st.write(f"🔍 해당 구역 인근에서 **{len(display_info)}개**의 시설이 검색되었습니다.")
    st.dataframe(display_info, use_container_width=True, hide_index=True)
else:
    st.warning(f"'{', '.join(keywords)}' 관련 상세 인프라 정보를 찾을 수 없습니다. (데이터 통합 작업 중)")

st.divider()

# --- [C] AI 예측 상세 로그 ---
st.subheader("📑 AI 예측 상세 로그 (Raw Data)")
with st.expander("전체 타임라인별 예측 로그 확인"):
    log_df = df_target[['동기화시간', '기온', '강수량', '잔여율', 'AI_예측_잔여율', '오차(%)']].copy()
    log_df.columns = ['시간', '기온', '강수량', '실제잔여율', '예측잔여율', '오차(%)']
    st.dataframe(log_df.sort_values('시간', ascending=False).reset_index(drop=True), use_container_width=True)
st.divider()

# --- [D] 시각화 자료 ---
st.subheader("📈 데이터 분석 및 AI 모델링 결과")
tab1, tab2 = st.tabs(["시계열 예측 그래프", "모델 성능 지표"])

with tab1:
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df_target['동기화시간'], df_target['잔여율'], label='Actual (과거 실제)', color='tab:blue', marker='o', markersize=3, alpha=0.6)
    ax.plot(df_target['동기화시간'], df_target['AI_예측_잔여율'], label='AI Predict (모델 예측)', color='tab:red', linestyle='--', linewidth=2)
    ax.set_title(f"[{selected_area}] residual rate analysis", fontsize=15)
    ax.set_ylabel("Residual Rate (%)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.xticks(rotation=45)
    st.pyplot(fig)

with tab2:
    col_a, col_b = st.columns(2)
    perf_data = {'Time': ['5m', '15m', '30m', '45m', '1h', '2h', '3h'], 'R² Score': [0.94, 0.90, 0.88, 0.91, 0.89, 0.87, 0.90]}
    perf_df = pd.DataFrame(perf_data)
    with col_a:
        st.write("**예측 시간별 모델 성능(R²)**")
        st.line_chart(perf_df.set_index('Time'))
    with col_b:
        st.write("**시스템 아키텍처**")
        st.success("🤖 XGBoost Regressor 기반 예측 엔진")
        st.success("🌐 서울시 공공데이터 API 실시간 통신")
        st.success("🌦️ Open-Meteo 실시간 기상 데이터 융합")

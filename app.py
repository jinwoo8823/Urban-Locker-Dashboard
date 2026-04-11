import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import random
import matplotlib.font_manager as fm
import os

# 1. 한글 폰트 설정 (배포 환경 및 로컬 대응)
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

# 2. 페이지 설정
st.set_page_config(page_title="스마트 물품보관함 AI 관제 시스템", layout="wide")

st.title("실시간 AI 물품보관함 수요 예측 관제탑")
st.markdown("기상청 실시간 관측(AWS) 및 유동인구 기반 **45분 뒤** 잔여율 예측 시스템 (최적 정확도 구간)")
st.divider()

# 3. 데이터 로드
@st.cache_data
def load_data():
    # 데이터셋 로드
    df = pd.read_csv('prediction_results.csv')
    df['동기화시간'] = pd.to_datetime(df['동기화시간'])
    df = df.sort_values('동기화시간')
    return df

try:
    df = load_data()
except FileNotFoundError:
    st.error("prediction_results.csv 파일을 찾을 수 없습니다. AI 예측 코드를 먼저 실행해주세요.")
    st.stop()

# 4. 사이드바 검색 및 필터링
st.sidebar.header("검색 옵션")
area_list = df['AREA_NM'].unique()
selected_area = st.sidebar.selectbox("관제할 지역을 선택하세요", area_list)

df_target = df[df['AREA_NM'] == selected_area].copy()

if df_target.empty:
    st.warning("선택한 지역의 데이터가 없습니다.")
    st.stop()

# 5. 실시간 데이터 추출
latest_data = df_target.iloc[-1]
current_time = latest_data['동기화시간'].strftime('%Y-%m-%d %H:%M')
# 45분 뒤 예측 시각 계산
pred_time_label = (latest_data['동기화시간'] + pd.Timedelta(minutes=45)).strftime('%H:%M')

current_rate = latest_data['잔여율']
pred_rate = latest_data['AI_예측_잔여율'] 
temp = latest_data['기온']
rain = latest_data['강수량']

# 6. 상단 요약 대시보드 (KPI)
st.subheader(f"[{selected_area}] 실시간 종합 현황 (기준: {current_time})")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="현재 날씨 (기온 / 강수량)", value=f"{temp:.1f}도 / {rain}mm")
with col2:
    st.metric(label="현재 보관함 잔여율", value=f"{current_rate:.1f}%")
with col3:
    delta_rate = pred_rate - current_rate
    st.metric(label=f"{pred_time_label} 예정 (45분 뒤 예측)", value=f"{pred_rate:.1f}%", delta=f"{delta_rate:.1f}%p 변화 예상", delta_color="inverse")
with col4:
    if pred_rate <= 15:
        status = "혼잡 (매진 임박)"
        st.error(status)
    elif pred_rate <= 40:
        status = "보통 (수요 증가)"
        st.warning(status)
    else:
        status = "여유"
        st.success(status)

st.divider()

# ==========================================
# 1. [B2G 관리자 상세 뷰] - 가상 시뮬레이션 데이터
# ==========================================
st.subheader(f"[{selected_area}] 개별 보관함 실시간 상세 관제 (관리자 모드)")

total_lockers = 120
available = int(total_lockers * (current_rate / 100))
in_use = total_lockers - available - 5
repair = 3
closed = 2

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("총 보관함", f"{total_lockers}개")
m2.metric("사용 가능", f"{available}개")
m3.metric("사용/예약 중", f"{in_use}개")
m4.metric("수리 중", f"{repair}개")
m5.metric("폐쇄", f"{closed}개")

st.markdown("**세부 시리얼 넘버 및 남은 시간 모니터링**")

def generate_mock_lockers(area, total, avail, use, rep, cls):
    mock_data = []
    statuses = ['사용 가능'] * avail + ['사용 중'] * use + ['수리 중'] * rep + ['폐쇄'] * cls
    random.shuffle(statuses)
    sizes = ['소형', '중형', '대형']
    
    for i, status in enumerate(statuses):
        serial = f"{area}-A-{1000 + i}"
        size = random.choice(sizes)
        if status == '사용 중':
            time_left = f"{random.randint(0, 23)}시간 {random.randint(0, 59)}분"
        elif status == '수리 중':
            time_left = "점검 필요 (에러코드 E-02)"
        else:
            time_left = "-"
        mock_data.append([serial, size, status, time_left])
    return pd.DataFrame(mock_data, columns=['시리얼 번호', '사이즈', '현재 상태', '남은 시간/비고'])

df_mock_lockers = generate_mock_lockers(selected_area, total_lockers, available, in_use, repair, closed)

def color_status(val):
    if val == '사용 가능': color = '#28a745'
    elif val == '사용 중': color = '#dc3545'
    elif val == '수리 중': color = '#ffc107'
    elif val == '폐쇄': color = '#6c757d'
    else: color = 'black'
    return f'color: {color}; font-weight: bold'

st.dataframe(
    df_mock_lockers.style.map(color_status, subset=['현재 상태']),
    use_container_width=True,
    height=400
)

st.divider()

# ==========================================
# 2. [AI 미래 예측 분석 뷰] - 실제 데이터 분석 결과
# ==========================================
st.subheader("과거 추이 및 AI 미래 예측 그래프")

fig, ax = plt.subplots(figsize=(12, 4))

ax.plot(df_target['동기화시간'], df_target['잔여율'], label='실제 잔여율 (%)', color='tab:blue', linewidth=2, marker='o', markersize=4)
ax.plot(df_target['동기화시간'], df_target['AI_예측_잔여율'], label='AI 45분 뒤 예측 (%)', color='tab:red', linestyle='--', linewidth=2, alpha=0.7)

ax.set_ylabel('보관함 잔여율 (%)')
ax.set_ylim(-5, 105)
ax.grid(True, alpha=0.3)
ax.legend(loc='upper right')

plt.xticks(rotation=45)
fig.tight_layout()

st.pyplot(fig)

st.divider()

# ==========================================
# 3. [상세 데이터 표] - 타임라인 데이터
# ==========================================
st.subheader("AI 예측 상세 데이터")
with st.expander("AI 예측 상세 데이터 표 보기 (전체 타임라인)"):
    display_df = df_target[['동기화시간', '기온', '강수량', '잔여율', 'AI_예측_잔여율', '오차(%)']].copy()
    display_df.columns = ['동기화시간', '기온', '강수량', '현재 잔여율', '45분 뒤 예상 잔여율', '오차(%)']
    st.dataframe(display_df.reset_index(drop=True), use_container_width=True)

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.font_manager as fm
import os

# 한글 폰트 설정 (로컬 및 클라우드 자동 인식)
@st.cache_resource
def set_korean_font():
    # Streamlit Cloud 리눅스 서버의 나눔고딕 경로
    font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = 'NanumGothic'
    else:
        # 내 컴퓨터(Windows) 환경일 경우
        plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False

set_korean_font()

# 페이지 기본 설정
st.set_page_config(page_title="스마트 물품보관함 AI 관제 시스템", layout="wide")

# 상단 제목 영역
st.title("실시간 AI 물품보관함 수요 예측 관제탑")
st.markdown("기상청 실시간 관측(AWS) 및 유동인구 기반 30분 뒤 잔여율 예측 시스템")
st.divider()

# 데이터 불러오기 (캐싱)
@st.cache_data
def load_data():
    df = pd.read_csv('prediction_results.csv')
    df['동기화시간'] = pd.to_datetime(df['동기화시간'])
    df = df.sort_values('동기화시간')
    return df

try:
    df = load_data()
except FileNotFoundError:
    st.error("prediction_results.csv 파일을 찾을 수 없습니다. AI 예측 코드를 먼저 실행해주세요.")
    st.stop()

# 사이드바: 지역 선택
st.sidebar.header("검색 옵션")
area_list = df['AREA_NM'].unique()
selected_area = st.sidebar.selectbox("관제할 지역을 선택하세요", area_list)

# 선택된 지역 데이터 필터링
df_target = df[df['AREA_NM'] == selected_area].copy()

if df_target.empty:
    st.warning("선택한 지역의 데이터가 없습니다.")
    st.stop()

# 최신 데이터 추출
latest_data = df_target.iloc[-1]
current_time = latest_data['동기화시간'].strftime('%Y-%m-%d %H:%M')
pred_time = latest_data['예측시간(30분뒤)']
current_rate = latest_data['잔여율']
pred_rate = latest_data['AI_예측_잔여율']
temp = latest_data['기온']
rain = latest_data['강수량']

# 상단 요약 정보 (KPI 위젯)
st.subheader(f"[{selected_area}] 실시간 종합 현황 (기준: {current_time})")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="현재 날씨 (기온 / 강수량)", value=f"{temp:.1f}도 / {rain}mm")
with col2:
    st.metric(label="현재 보관함 잔여율", value=f"{current_rate:.1f}%")
with col3:
    # 잔여율이 떨어지면 마이너스(-) 델타로 표시하여 시각적 경고 효과
    delta_rate = pred_rate - current_rate
    st.metric(label="30분 뒤 AI 예상 잔여율", value=f"{pred_rate:.1f}%", delta=f"{delta_rate:.1f}%p 변화 예상", delta_color="inverse")
with col4:
    # 혼잡도 상태 계산
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

# 중앙 메인 시각화 영역 (AI 예측 트렌드 그래프)
st.subheader("과거 추이 및 AI 미래 예측 그래프")

# 차트 그리기
fig, ax = plt.subplots(figsize=(12, 4))

# 과거~현재 실제 잔여율 (파란선)
ax.plot(df_target['동기화시간'], df_target['잔여율'], label='실제 잔여율 (%)', color='tab:blue', linewidth=2, marker='o', markersize=4)

# 과거~현재 AI 예측 잔여율 (빨간 점선)
ax.plot(df_target['동기화시간'], df_target['AI_예측_잔여율'], label='AI 예측 잔여율 (%)', color='tab:red', linestyle='--', linewidth=2, alpha=0.7)

ax.set_ylabel('보관함 잔여율 (%)')
ax.set_ylim(-5, 105)
ax.grid(True, alpha=0.3)
ax.legend(loc='upper right')

plt.xticks(rotation=45)
fig.tight_layout()

st.pyplot(fig)

# 하단 데이터 상세 보기
with st.expander("AI 예측 상세 데이터 표 보기"):
    st.dataframe(df_target[['동기화시간', '기온', '강수량', '잔여율', 'AI_예측_잔여율', '오차(%)']].reset_index(drop=True), use_container_width=True)

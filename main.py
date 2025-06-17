import streamlit as st
import pandas as pd
import io
import matplotlib.pyplot as plt
import koreanize_matplotlib
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# 파일 업로드
st.title("📊 문항 분석 시각화 앱")

st.markdown("""
### 📂 사용 안내

- 분석하고 싶은 과목 시험의 **나이스 교과목별학생답정오표**를 **여러 개 한꺼번에 선택하여 업로드**하세요.

- **교과목별학생답정오표 다운로드 방법**  
    교과담임 → 지필평가조회/통계 → 지필평가조회  
    → 교과목별학생답정오표  
    → 계산할 지필평가 선택 및 조회  
    → **저장 버튼(디스켓 모양) 클릭 → [XLS data] 형식으로 저장**
""")

uploaded_files = st.file_uploader("엑셀 파일 업로드 (여러 개 가능)", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    df_list = []
    first = True

    for uploaded_file in uploaded_files:
        st.success(f"📂 파일 처리 중: {uploaded_file.name}")
        temp_df = pd.read_excel(uploaded_file, header=None)

        if first:
            temp_df = temp_df[temp_df.iloc[:, 2].notna()]
            first = False
        else:
            temp_df = temp_df[temp_df.iloc[:, 1].notna()]
        
        df_list.append(temp_df)

    df = pd.concat(df_list, ignore_index=True)

    # 정답 정보 추출
    question_numbers = df.iloc[0, 3:]
    answers = df.iloc[1, 3:]

    df1 = pd.DataFrame({
        '문항번호': question_numbers.values,
        '정답': answers.values
    })

    mask = df1.apply(lambda col: col.map(lambda x: str(x).isdigit()))
    df1 = df1[mask.all(axis=1)].astype(int).reset_index(drop=True)

    # 학생 데이터 처리
    student_df = df.iloc[3:, :].reset_index(drop=True)
    score_col_index = df.iloc[0].tolist().index('과목총점')

    반번호 = student_df.iloc[:, 1]
    총점 = pd.to_numeric(student_df.iloc[:, score_col_index], errors='coerce')

    upper_cut = 총점.quantile(0.73)
    lower_cut = 총점.quantile(0.27)

    def classify(score):
        if score >= upper_cut:
            return '상위'
        elif score > lower_cut:
            return '중위'
        elif score <= lower_cut:
            return '하위'
        else:
            return score

    집단구분 = 총점.apply(classify)
    df2 = pd.concat([반번호, 총점, 집단구분], axis=1)
    df2.columns = ['반/번호', '총점', '집단']
    df2 = df2[df2['반/번호'].notna()].reset_index(drop=True)

    # 문항 응답 데이터 추출
    question_cols = df.iloc[0].apply(lambda x: isinstance(x, (int, float)) and not pd.isna(x))
    question_col_indices = question_cols[question_cols].index.tolist()

    question_data = {}
    for col_idx in question_col_indices:
        col_name = df.iloc[0, col_idx]
        col_values = df.iloc[3:, col_idx]
        question_data[col_name] = col_values.reset_index(drop=True)

    question_df = pd.DataFrame(question_data)
    question_df = question_df.iloc[:len(df2)].reset_index(drop=True)
    df2 = pd.concat([df2.reset_index(drop=True), question_df], axis=1)

    # 정답 매핑 및 '.' 처리
    answer_map = dict(zip(df1['문항번호'], df1['정답']))
    for qnum in df1['문항번호'].values:
        if qnum in df2.columns:
            df2[qnum] = df2[qnum].apply(lambda x: answer_map[qnum] if str(x).strip() == '.' else x)

    # 총점 분포 산점도
    df2_sorted = df2.sort_values(by='총점').reset_index(drop=True)
    color_map = {'상위': 'red', '중위': 'blue', '하위': 'green'}
    colors = df2_sorted['집단'].map(color_map)

    mid_start_y = df2_sorted[df2_sorted['집단'] == '중위']['총점'].min()
    high_start_y = df2_sorted[df2_sorted['집단'] == '상위']['총점'].min()

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(x=df2_sorted.index, y=df2_sorted['총점'], c=colors)
    ax.axhline(y=mid_start_y, color='blue', linestyle='--', label='중위컷')
    ax.axhline(y=high_start_y, color='red', linestyle='--', label='상위컷')
    ax.text(len(df2_sorted) - 1, mid_start_y + 1, f"{mid_start_y:.1f}", color='blue', ha='right')
    ax.text(len(df2_sorted) - 1, high_start_y + 1, f"{high_start_y:.1f}", color='red', ha='right')
    ax.set_title("총점 분포", fontsize=14)
    ax.set_xlabel("학생(총점 오름차순 정렬)")
    ax.set_ylabel("총점")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)

    # 문항별 선택 비율 및 변별도 시각화
    보기들 = [1, 2, 3, 4, 5]
    집단들 = ['상위', '중위', '하위']
    보기_색상 = {1: 'blue', 2: 'green', 3: 'purple', 4: 'orange', 5: 'brown'}

    def get_bar_colors(answer, choices, base_color, highlight_color='gold'):
        return [highlight_color if str(choice) == str(answer) else base_color for choice in choices]

    st.subheader("📌 문항별 정답률 및 선택 비율 분석")
    for 문항번호, 정답 in zip(df1['문항번호'], df1['정답']):
        if 문항번호 not in df2.columns:
            continue

        정답 = int(str(정답).strip())
        total_counts = df2[문항번호].value_counts().reindex(보기들, fill_value=0)
        group_counts = {
            group: df2[df2['집단'] == group][문항번호].value_counts().reindex(보기들, fill_value=0)
            for group in 집단들
        }

        전체응답자수 = len(df2[문항번호].dropna())
        집단별_응답자수 = {
            group: len(df2[df2['집단'] == group][문항번호].dropna())
            for group in 집단들
        }

        total_ratio = total_counts / 전체응답자수 * 100 if 전체응답자수 > 0 else total_counts
        group_ratios = {
            group: (group_counts[group] / 집단별_응답자수[group] * 100) if 집단별_응답자수[group] > 0 else group_counts[group]
            for group in 집단들
        }

        상위_df = pd.to_numeric(df2[df2['집단'] == '상위'][문항번호].apply(str).str.strip(), errors='coerce').dropna()
        하위_df = pd.to_numeric(df2[df2['집단'] == '하위'][문항번호].apply(str).str.strip(), errors='coerce').dropna()

        전체_정답자수 = pd.to_numeric(df2[문항번호].apply(str).str.strip(), errors='coerce').eq(정답).sum()
        전체_정답률 = (전체_정답자수 / 전체응답자수) if 전체응답자수 > 0 else 0
        상위_정답률 = (상위_df.eq(정답).sum() / len(상위_df)) if len(상위_df) > 0 else 0
        하위_정답률 = (하위_df.eq(정답).sum() / len(하위_df)) if len(하위_df) > 0 else 0
        변별도 = 상위_정답률 - 하위_정답률

        fig = plt.figure(figsize=(15, 7), constrained_layout=True)
        grid = fig.add_gridspec(2, 4)
        fig.suptitle(f"문항 {문항번호} - 정답률 ({전체_정답률:.2f}), 변별도 ({변별도:.2f})", fontsize=18, fontweight='bold', ha='left', x=0.05)

        ax_main = fig.add_subplot(grid[:, 0:2])
        plot_data = pd.DataFrame(index=집단들)
        for 보기 in 보기들:
            보기별_비율 = []
            for 집단 in 집단들:
                집단_df = df2[df2['집단'] == 집단][문항번호].dropna()
                응답수 = len(집단_df)
                선택수 = pd.to_numeric(집단_df.apply(str).str.strip(), errors='coerce').eq(보기).sum()
                비율 = (선택수 / 응답수) * 100 if 응답수 > 0 else 0
                보기별_비율.append(비율)
            plot_data[보기] = 보기별_비율

        for 보기 in 보기들:
            color = 'gold' if 보기 == 정답 else 보기_색상.get(보기, 'gray')
            lw = 4 if 보기 == 정답 else 2
            ax_main.plot(plot_data.index, plot_data[보기], marker='o', label=f'{보기}번', color=color, linewidth=lw)

        ax_main.set_ylabel("선택 비율 (%)")
        ax_main.grid(True)
        ax_main.legend(title="보기 번호")

        ax1 = fig.add_subplot(grid[0, 2])
        ax1.bar(total_ratio.index, total_ratio.values,
                color=get_bar_colors(정답, total_ratio.index.astype(str), 'gray'))
        ax1.set_title("전체 보기 선택 비율")
        ax1.set_ylim(0, 100)

        ax2 = fig.add_subplot(grid[0, 3])
        ax2.bar(group_ratios['상위'].index, group_ratios['상위'].values,
                color=get_bar_colors(정답, group_ratios['상위'].index.astype(str), 'red'))
        ax2.set_title("상위 집단")
        ax2.set_ylim(0, 100)

        ax3 = fig.add_subplot(grid[1, 2])
        ax3.bar(group_ratios['중위'].index, group_ratios['중위'].values,
                color=get_bar_colors(정답, group_ratios['중위'].index.astype(str), 'blue'))
        ax3.set_title("중위 집단")
        ax3.set_ylim(0, 100)

        ax4 = fig.add_subplot(grid[1, 3])
        ax4.bar(group_ratios['하위'].index, group_ratios['하위'].values,
                color=get_bar_colors(정답, group_ratios['하위'].index.astype(str), 'green'))
        ax4.set_title("하위 집단")
        ax4.set_ylim(0, 100)

        st.pyplot(fig)

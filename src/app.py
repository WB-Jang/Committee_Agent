import streamlit as st
import os
import tempfile
import docx
import textwrap
import contextlib
from read_docx_util import read_docx
from pdf_converter import batch_convert_to_pdf
from PyPDF2 import PdfReader
from highlighting import highlight_errors
import time 

# --- LangChain 관련 임포트 ---
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

import re

# [함수] 마크다운 문법 무시하고 글자 크기 유지
def escape_markdown_special_chars(text):
    if not text: return text
    text = re.sub(r'#(?![0-9a-fA-F]{3,6})', '&#35;', text)
    text = text.replace('*', '&#42;').replace('_', '&#95;')
    return text

# [함수] 파일 변경 시 상태 리셋
def reset_state():
    keys_to_reset = ["proofreading_results", "logic_results", "style_results", "highlighted_preview"]
    for key in keys_to_reset:
        if key in st.session_state:
            st.session_state[key] = None

# --- 읽기 함수 ---
def read_raw_docx(file_path):
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        return f"파일을 읽는 중 오류가 발생했습니다: {str(e)}"

def read_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# --- 체인 생성 함수들 ---
def get_proofreading_chain(api_key):
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0, google_api_key=api_key)
    template = """
    당신은 한국어 교정 전문가입니다. 아래 텍스트에서 오타, 비문, 어색한 표현을 찾아주세요.
    [텍스트]: {text}
    [응답 형식]: JSON 포맷 (error_sentence, correction, reason)
    """
    # (실제 템플릿 내용은 위 코드와 동일하므로 생략하거나 유지)
    template = """
    당신은 한국어 교정 전문가입니다. 아래 텍스트에서 오타, 비문, 어색한 표현을 찾아주세요.

    [텍스트]:
    {text}

    [응답 형식]:
    반드시 아래와 같은 **JSON 포맷**으로만 응답하세요. 다른 말은 하지 마세요.
    오류가 없으면 빈 리스트 [] 를 반환하세요.

    [
      {{
        "error_sentence": "오류가 포함된 원본 문장 또는 단어 구절 (원본 텍스트와 정확히 일치해야 함)",
        "correction": "수정 제안 내용",
        "reason": "수정 이유"
      }},
      ...
    ]
    """
    prompt = PromptTemplate.from_template(template)
    return prompt | llm | StrOutputParser()

def get_logical_error_chain(api_key):
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0, google_api_key=api_key)
    template = """
    [역할(Role)]: 전문 팩트체커
    [텍스트]: {text}
    [지시사항]: 시간, 장소, 인물, 수치, 인과관계, 모순 검증.
    [응답 형식]:
    반드시 아래와 같은 **JSON 포맷**으로만 응답하세요. 다른 말은 하지 마세요.
    오류가 없으면 빈 리스트 [] 를 반환하세요.

    [
      {{
        "error_sentence": "오류가 포함된 원본 문장 또는 단어 구절 (원본 텍스트와 정확히 일치해야 함)",
        "correction": "수정 제안 내용",
        "reason": "논리적 모순에 대한 상세 설명"
      }},
      ...
    ]
    """
    prompt = PromptTemplate.from_template(template)
    return prompt | llm | StrOutputParser()

def get_english_chain(api_key):
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0, google_api_key=api_key)
    template = """
    [역할(Role)]: 수석 비즈니스 영어 에디터 (Reporting Style)
    [텍스트]: {text}
    [검증 기준]: 객관성, 간결성, 격식(No contractions/slang), 명확성.
    [응답 형식]:
    반드시 아래와 같은 **JSON 포맷**으로만 응답하세요. 다른 말은 하지 마세요.
    수정할 사항이 없으면 빈 리스트 [] 를 반환하세요.

    [
      {{
        "error_sentence": "스타일에 맞지 않는 원본 문장 또는 단어 구절 (원본 텍스트와 정확히 일치해야 함)",
        "correction": "더 전문적이고 보고서에 적합한 수정 제안 (영어)",
        "reason": "해당 표현이 보고용 문체로 부적절한 이유 (한국어로 설명)"
      }},
      ...
    ]
    """
    prompt = PromptTemplate.from_template(template)
    return prompt | llm | StrOutputParser()

# --- 공통 분석 처리 함수 ---
def process_analysis(api_key, file_path, chain_func, progress_text, result_key):
    """
    앞에서 만들어진 api_key, 파일 경로와 chain들을 공통으로 받고
    같은 형식의 결과물을 return할 수 있도록 함수를 구성함
    """
    if not api_key:
        st.error("API Key를 입력해주세요.")
        return

    sections = read_docx(file_path)
    try:
        chain = chain_func(api_key)
    except Exception as e:
        st.error(f"체인 생성 실패: {e}")
        return

    results = []
    full_highlighted_content = []
    
    progress_bar = st.progress(0) # 진행률 바 생성(최초 숫자를 괄호 안에 입력)
    status_text = st.empty() # 동적으로 콘텐츠를 업데이트할 수 있는 빈 컨테이너 생성, 추후에 write() 메서드를 통해 텍스트 등을 입력할 수 있음
    status_text.write(progress_text) # 생성된 빈 컨테이너에 progress_text를 입력함

    for i, section in enumerate(sections):
        title = section.get('title', '제목 없음')
        content = section.get('content', '')

        try:
            with contextlib.redirect_stdout(None): # "'ascii' codec can't encode characters" 오류를 방지하기 위함. langchain 호출 시 불필요한 출력이 발생하는 경우가 있는데, 이 출력 중 일부가 한글 인코딩 문제를 발생시키는 경우가 있어서, 불필요한 로그를 출력하지 않도록 하여, 한글 인코딩 문제 예방함
                response_json = chain.invoke({"text": content})

            # 하이라이팅 처리 (모든 체인이 동일한 JSON 구조를 가지므로 공통 사용 가능)
            highlighted_text, errors = highlight_errors(content, response_json)
            safe_highlighted = escape_markdown_special_chars(highlighted_text) # 마크다운 특수 문자가 의도치 않게 렌더링 되어 스타일이 깨지는 것을 방지하기 위한 함수 사용

            if errors:
                results.append({"title": title, "errors": errors})

            # HTML 미리보기 생성
            section_html = textwrap.dedent(f"""
                <div style="margin-bottom: 25px;">
                    <div style="font-size: 16px; font-weight: bold; color: #1f2937; margin-bottom: 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px;">
                        {title}
                    </div>
                    <div style="font-size: 14px; color: #374151;">
                        {safe_highlighted}
                    </div>
                </div>
            """).strip()
            full_highlighted_content.append(section_html)

        except Exception as e:
            full_highlighted_content.append(f"<p style='color:red;'>⚠️ Error: {e}</p>")

        progress_bar.progress((i + 1) / len(sections))

    # 모든 Section을 분석한 결과 저장
    st.session_state[result_key] = results
    # 왼쪽 미리보기 화면도 현재 분석 결과에 맞춰 업데이트
    st.session_state.highlighted_preview = "\n".join(full_highlighted_content)
    
    status_text.empty()
    progress_bar.empty()
    st.rerun()

# --- 결과 카드 출력 헬퍼 함수 ---
def display_results(results_data):
    if not results_data:
        st.info("검출된 수정 사항이 없습니다.")
        return

    st.info(f"총 {len(results_data)}개의 섹션에서 수정 사항이 발견되었습니다.")
    for res in results_data:
        with st.expander(f"📌 {res['title']}", expanded=True):
            errors = res.get('errors', [])
            for error in errors:
                original = error.get('error_sentence', '')
                correction = error.get('correction', '')
                reason = error.get('reason', '')

                st.markdown(textwrap.dedent(f"""
                <div style="background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="display: flex; align-items: baseline; margin-bottom: 8px;">
                        <span style="background-color: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.95em; text-decoration: line-through; margin-right: 8px;">
                            {original}
                        </span>
                        <span style="color: #6b7280; font-size: 0.9em; margin-right: 8px;">➞</span>
                        <span style="background-color: #dcfce7; color: #166534; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.95em;">
                            {correction}
                        </span>
                    </div>
                    <div style="font-size: 0.9em; color: #4b5563; background-color: #f9fafb; padding: 8px; border-radius: 6px;">
                        💡 <b>이유:</b> {reason}
                    </div>
                </div>
                """), unsafe_allow_html=True)


# --- 메인 함수 ---
def main():
    st.set_page_config(page_title="Committee Agent 통합 플랫폼", layout='wide')

    # 세션 상태 초기화 : session_state는 streamlit이 재실행되어 초기화되더라도 데이터를 유지함
    if "proofreading_results" not in st.session_state: st.session_state.proofreading_results = None
    if "logic_results" not in st.session_state: st.session_state.logic_results = None
    if "style_results" not in st.session_state: st.session_state.style_results = None
    if "highlighted_preview" not in st.session_state: st.session_state.highlighted_preview = None

    st.title("문서 작업 통합 도구 (Correction & Conversion)")

    tab1, tab2 = st.tabs(["📄 문서 복합 분석", "🔄 PDF 일괄 변환"])

    with tab1:
        col1, col2 = st.columns([1, 1])

        # =========================================================
        # [왼쪽] 1. 파일 업로드 및 미리보기
        # =========================================================
        with col1:
            st.subheader("1. 파일 업로드 및 확인")
            openai_api_key = st.text_input("Google API Key 입력 (Gemini)", type="password", key="api_key_tab1")

            uploaded_file = st.file_uploader(
                "검수할 파일 업로드 (Word/PDF)",
                type=["docx", "pdf"],
                key="uploader_tab1",
                on_change=reset_state
            )

            if uploaded_file is not None: 
                
                # Stramlit의 file_uploader는 파일의 내용을 RAM으로 잡고 있는데, python-docx에서는 파일의 경로를 입력해야 해서, 임시 파일을 만들고, 
                # 그 임시 파일에 업로드 파일의 내용을 넣은뒤, 저장된 임시 파일의 경로를 python-docx에 입력으로 전달하기 위함 
                
                suffix = '.docx' if uploaded_file.name.endswith('.docx') else '.pdf'
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name

                if suffix == '.docx':
                    raw_text = read_raw_docx(tmp_file_path) # 위에서 작성한 임시 파일 경로를 입력으로 줌
                else:
                    raw_text = read_pdf(uploaded_file) # 위에서 작성한 임시 파일 경로를 입력으로 줌

                # AI 분석 결과가 있다면, 분석 결과를 보여주고, 없다면 원문(raw_text)을 그대로 보여줌
                if st.session_state.highlighted_preview:
                    st.markdown("⬇️ **분석 결과 미리보기 (하이라이트)**")
                    preview_content = st.session_state.highlighted_preview.strip()
                    container_html = textwrap.dedent(f"""
                        <div style="height: 600px; overflow-y: scroll; border: 1px solid #dee2e6; padding: 20px; border-radius: 5px; background-color: #ffffff; color: #333333; font-family: sans-serif; font-size: 14px; line-height: 1.6;">
                            {preview_content}
                        </div>
                    """)
                    st.markdown(container_html, unsafe_allow_html=True)
                else:
                    st.text_area("내용 미리보기", raw_text, height=600)

        # =========================================================
        # [오른쪽] 2. AI 분석 컨트롤 및 결과
        # =========================================================
        with col2:
            st.subheader("2. AI 분석 실행")

            if uploaded_file and suffix == '.docx':
                # 3개의 실행 버튼 배치
                btn_col1, btn_col2, btn_col3 = st.columns(3) # col2 안에서 버튼을 가로로 3등분하여 배치

                with btn_col1:
                    if st.button("📝 오타 검수\n(Basic)", use_container_width=True):
                        process_analysis(openai_api_key, tmp_file_path, get_proofreading_chain, "오타 검수 중...", "proofreading_results")
                
                with btn_col2:
                    if st.button("🧠 논리 검증\n(Logic)", use_container_width=True):
                        process_analysis(openai_api_key, tmp_file_path, get_logical_error_chain, "논리적 정합성 검증 중...", "logic_results")

                with btn_col3:
                    if st.button("👔 스타일 교정\n(English)", use_container_width=True):
                        process_analysis(openai_api_key, tmp_file_path, get_english_chain, "Business Style Tone&Manner 분석 중...", "style_results")

                st.markdown("---")
                
                # 결과 탭 구성
                res_tab1, res_tab2, res_tab3 = st.tabs(["📝 오타/비문", "🧠 논리/팩트", "👔 영어 스타일"])

                with res_tab1:
                    if st.session_state.proofreading_results:
                        display_results(st.session_state.proofreading_results)
                    else:
                        st.info("실행 결과가 없습니다.")

                with res_tab2:
                    if st.session_state.logic_results:
                        display_results(st.session_state.logic_results)
                    else:
                        st.info("실행 결과가 없습니다.")

                with res_tab3:
                    if st.session_state.style_results:
                        display_results(st.session_state.style_results)
                    else:
                        st.info("실행 결과가 없습니다.")
            
            elif uploaded_file and suffix != '.docx':
                st.warning("현재 AI 정밀 분석은 .docx 파일만 지원합니다.")
            else:
                st.info("왼쪽에서 파일을 먼저 업로드해주세요.")

    # 탭 2: PDF 변환 (기존 유지)
    with tab2:
        st.header("📂 Word/PPT -> PDF 일괄 변환")
        default_path = os.getcwd()
        target_folder = st.text_input("변환할 파일이 있는 폴더 경로를 입력하세요:", value=default_path)

        if st.button("일괄 변환 시작", type="primary"):
            st.write("---")
            log_area = st.empty()
            for msg_type, msg in batch_convert_to_pdf(target_folder):
                if msg_type == "Error": st.error(msg)
                elif msg_type == "Success": st.success(msg)
                elif msg_type == "Info": st.info(msg)
                elif msg_type == "Progress":
                    with log_area: st.write(f"⏳ {msg}")
            st.success("모든 작업이 종료되었습니다.")
            log_area.empty()

if __name__ == "__main__":
    main()

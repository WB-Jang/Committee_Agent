import os
import subprocess
import sys

def convert_to_pdf_linux(input_path, output_folder):
    """
    LibreOffice를 사용하여 단일 파일을 PDF로 변환합니다.
    """
    try:
        # libreoffice 명령어가 설치되어 있는지 확인이 필요하지만,
        # 여기서는 설치되었다고 가정하고 실행합니다.
        cmd = [
            'libreoffice',
            '--headless',
            '--convert-to', 'pdf',
            input_path,
            '--outdir', output_folder
        ]

        # 명령어 실행 (타임아웃 60초 설정)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)

        if result.returncode != 0:
            return False, result.stderr.decode('utf-8')

        return True, "Success"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def batch_convert_to_pdf(target_folder):
    """
    지정된 폴더 내의 Word, PPT 파일을 모두 찾아 PDF로 변환합니다.
    """
    if not os.path.exists(target_folder):
        yield "Error", f"폴더를 찾을 수 없습니다: {target_folder}"
        return

    # 결과가 저장될 폴더 (원본폴더/pdf_output)
    output_folder = os.path.join(target_folder, "pdf_output")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    extensions = ('.docx', '.doc', '.pptx', '.ppt')
    files = [f for f in os.listdir(target_folder) if f.lower().endswith(extensions) and not f.startswith('~$')]

    if not files:
        yield "Info", "변환할 지원 파일(.docx, .pptx 등)이 없습니다."
        return

    yield "Info", f"총 {len(files)}개의 파일을 변환합니다. 결과 저장 경로: {output_folder}"

    for file in files:
        input_path = os.path.join(target_folder, file)
        yield "Progress", f"변환 중: {file}..."

        success, msg = convert_to_pdf_linux(input_path, output_folder)

        if success:
            yield "Success", f"[성공] {file}"
        else:
            yield "Error", f"[실패] {file} : {msg}"

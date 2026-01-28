import threading
import subprocess
import time
import os  
from pyngrok import ngrok
from dotenv import load_dotenv

def run_stramlit():
    # 1. 현재 시스템의 환경 변수를 복사해옵니다.
    curr_env = os.environ.copy()

    # 2. Python 출력과 시스템 언어 설정을 UTF-8로 강제합니다.
    #    (이 부분이 없으면 한글 출력 시 아스키 코덱 에러가 발생합니다)
    curr_env["PYTHONIOENCODING"] = "utf-8"
    curr_env["LANG"] = "C.UTF-8"
    curr_env["LC_ALL"] = "C.UTF-8"

    cmd = ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"] # app.py 내에 다른 프로그램들을 복잡하게 import하고 있으므로, "scr/app.py"를 사용하는 것이 아니라, subprocess에서 cwd='src'로 해결할 것
 
    # 3. subprocess 실행 시, 위에서 설정한 환경 변수(env)를 전달합니다.
    subprocess.run(cmd, env=curr_env, cwd="src") # src로 cwd를 설정을 해두는 것이 더 안전한 듯

# 기존 스레드 실행 로직 유지
thread = threading.Thread(target=run_stramlit, daemon=True)
thread.start()

time.sleep(5)

# Ngrok 설정
load_dotenv()
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN") # os.getenv() -> 없으면 None 반환 vs os.environ[] -> 없으면 에러 발생 

if NGROK_AUTH_TOKEN:
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    print("성공: Ngrok 토큰이 설정되었습니다.")
else:
    print("실패: .env 파일을 찾았으나 토큰을 불러오지 못했습니다.")


# 기존에 열려있는 터널이 있다면 닫아서 에러 방지
tunnels = ngrok.get_tunnels()
for t in tunnels:
    ngrok.disconnect(t.public_url)

public_url = ngrok.connect(8501, "http")
print("외부 접속 URL : ", public_url)

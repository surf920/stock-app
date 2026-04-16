"""
認証ゲート - 全ページの先頭で require_auth() を呼ぶ
"""
import hmac
import time
import streamlit as st


def _check_password(input_password: str) -> bool:
    """タイミング攻撃耐性のあるパスワード比較"""
    try:
        correct = st.secrets["APP_PASSWORD"]
    except (KeyError, FileNotFoundError):
        st.error("APP_PASSWORD が設定されていません。Streamlit Secrets に追加してください。")
        st.stop()
    return hmac.compare_digest(input_password.encode(), correct.encode())


def require_auth():
    """認証されていなければログイン画面を出して停止"""
    if st.session_state.get("authenticated"):
        return

    # ログイン画面
    st.title("🔒 Macro Intelligence HQ")
    st.markdown("アクセスにはパスワードが必要です。")

    password = st.text_input("パスワード", type="password", key="auth_password_input")

    if st.button("ログイン", key="auth_login_btn"):
        # ブルートフォース対策: 失敗時に遅延
        if _check_password(password):
            st.session_state["authenticated"] = True
            st.session_state["auth_failures"] = 0
            st.rerun()
        else:
            fails = st.session_state.get("auth_failures", 0) + 1
            st.session_state["auth_failures"] = fails
            # 失敗が増えるごとに遅延を長く (1秒, 2秒, 4秒...)
            time.sleep(min(2 ** (fails - 1), 30))
            st.error(f"パスワードが違います (試行回数: {fails})")

    st.stop()


def add_logout_button():
    """サイドバーにログアウトボタンを追加 (任意)"""
    with st.sidebar:
        st.divider()
        if st.button("🚪 ログアウト"):
            st.session_state["authenticated"] = False
            st.rerun()

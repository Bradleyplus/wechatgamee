import streamlit as st
import requests
import uuid
import time

# ---------------------- 页面配置与样式 ----------------------
st.set_page_config(
    page_title="双人井字棋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .board-container {
        width: 100% !important;
        max-width: 210px !important;
        margin: 0 auto !important;
    }
    .stButton > button {
        width: 100% !important;
        height: 60px !important;
        font-size: 1.5rem !important;
        padding: 0 !important;
        margin: 1px !important;
    }
    .debug-box {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        font-size: 0.8rem;
        margin: 10px 0;
    }
    .room-id-box {
        color: #2196F3;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------- 云存储配置（必须与LeanCloud控制台完全一致） ----------------------
# 1. 从LeanCloud控制台“设置-应用凭证”复制以下信息
APP_ID = "M4eT4HnMmoRZrfmhpCcon7Kf-gzGzoHsz"  # 例如："hiwS1jgaGdLqJhk2UtEwHGdK-gzGzoHsz"（确保无拼写错误）
APP_KEY = "qGwYdl4RNFMDpxoydgFHMnD6"  # 例如："bENg8Yr0ULGdt7NJB70i2VOW"（确保无拼写错误）
# 2. 从LeanCloud控制台“设置-应用凭证-服务地址”复制REST API地址，末尾加“/1.1/classes/GameState”
BASE_API_URL = "https://m4et4hnm.lc-cn-n1-shared.com/1.1/classes/GameState"  # 例如："https://hiwS1jga.lc-cn-n1-shared.com/1.1/classes/GameState"

HEADERS = {
    "X-LC-Id": APP_ID,
    "X-LC-Key": APP_KEY,  # 仅填AppKey，不要加其他内容
    "Content-Type": "application/json"
}

# ---------------------- 核心工具函数（修复胜利判断） ----------------------
def check_winner(board):
    """优化胜利判断：确保所有连线情况被正确识别"""
    win_patterns = [
        # 横向
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        # 纵向
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        # 对角线
        (0, 4, 8), (2, 4, 6)
    ]
    for (a, b, c) in win_patterns:
        if board[a] == board[b] == board[c] != "":
            return board[a]  # 返回胜利方（X/O）
    if "" not in board:
        return "平局"
    return None  # 未分胜负


def get_device_id():
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id


# ---------------------- 房间管理 ----------------------
def force_clean_room(room_id):
    try:
        params = {"where": f'{{"room_id":"{room_id}"}}'}
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        if res.status_code == 200 and res.json().get("results"):
            for record in res.json()["results"]:
                requests.delete(f"{BASE_API_URL}/{record['objectId']}", headers=HEADERS, timeout=10)
            st.success(f"房间 {room_id} 清理完成！")
            time.sleep(1)
            return True
        st.info(f"房间 {room_id} 暂无记录")
    except Exception as e:
        st.error(f"清理失败：{str(e)}")
    return False


def load_room(room_id):
    try:
        params = {
            "where": f'{{"room_id":"{room_id}"}}',
            "limit": 1,
            "order": "-createdAt"
        }
        res = requests.get(BASE_API_URL, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("results"):
            room_data = data["results"][0]
            room_data["players"] = room_data.get("players", {})
            return room_data
        return None
    except Exception as e:
        st.error(f"加载失败：{str(e)}")
        return None


def create_room(room_id):
    existing_room = load_room(room_id)
    if existing_room:
        st.warning(f"房间 {room_id} 已存在！正在加入...")
        return existing_room

    device_id = get_device_id()
    init_data = {
        "room_id": room_id,
        "board": ["", "", "", "", "", "", "", "", ""],
        "current_player": "X",
        "game_over": False,
        "winner": None,
        "players": {device_id: "X"}
    }
    try:
        res = requests.post(BASE_API_URL, headers=HEADERS, json=init_data, timeout=10)
        res.raise_for_status()
        new_data = res.json()
        init_data["objectId"] = new_data["objectId"]
        st.success(f"房间 {room_id} 创建成功（ID：{new_data['objectId'][:8]}）")
        return init_data
    except Exception as e:
        st.error(f"创建失败：{str(e)} | 响应：{res.text if 'res' in locals() else '无'}")
        return None


def enter_room(room_id):
    device_id = get_device_id()
    room_data = load_room(room_id)

    if not room_data:
        return create_room(room_id)

    if device_id in room_data["players"]:
        st.info(f"已在房间 {room_id} 中（角色：{room_data['players'][device_id]}）")
        return room_data

    if len(room_data["players"]) < 2:
        updated_players = room_data["players"].copy()
        updated_players[device_id] = "O"
        updated_data = {
            "players": updated_players,
            "current_player": room_data["current_player"],
            "board": room_data["board"]
        }
        try:
            put_url = f"{BASE_API_URL}/{room_data['objectId']}"
            res = requests.put(put_url, headers=HEADERS, json=updated_data, timeout=10)
            res.raise_for_status()

            time.sleep(1.5)
            verified_room = load_room(room_id)
            if verified_room and device_id in verified_room["players"]:
                st.success(f"以O角色加入房间（房间ID：{verified_room['objectId'][:8]}）")
                return verified_room
            st.error("加入失败：角色未保存")
            return None
        except Exception as e:
            st.error(f"加入失败：{str(e)} | 响应：{res.text if 'res' in locals() else '无'}")
            return None

    st.error("房间已满（2人）")
    return None


# ---------------------- 状态恢复 ----------------------
def auto_restore_state(room_id):
    if st.session_state.entered_room:
        room_data = load_room(room_id)
        if not room_data:
            st.warning("房间不存在，请重新进入")
            st.session_state.entered_room = False
            return False
        device_id = get_device_id()
        if device_id in room_data["players"]:
            st.session_state.object_id = room_data["objectId"]
            st.session_state.board = room_data.get("board", ["", "", "", "", "", "", "", "", ""])
            st.session_state.current_player = room_data.get("current_player", "X")
            st.session_state.game_over = room_data.get("game_over", False)
            st.session_state.winner = room_data.get("winner")
            st.session_state.players = room_data["players"]
            st.session_state.my_role = room_data["players"][device_id]
            return True
        st.session_state.entered_room = False
        st.warning("你不在该房间内，请重新进入")
    return False


# ---------------------- 主页面逻辑 ----------------------
st.title("🎮 呆瓜宝小游戏 - 双人井字棋")

room_id = st.selectbox(
    "🔑 选择房间号",
    options=["8888", "6666"],
    index=0,
    key="room_selector"
)

# 初始化会话状态
required_states = {
    "entered_room": False,
    "my_role": None,
    "object_id": None,
    "board": ["", "", "", "", "", "", "", "", ""],
    "current_player": "X",
    "game_over": False,
    "winner": None,
    "players": {}
}
for key, default in required_states.items():
    if key not in st.session_state:
        st.session_state[key] = default

# 调试信息
device_id = get_device_id()
st.markdown(f"""
<div class="debug-box">
- 你的设备ID：<strong>{device_id[:8]}...</strong><br>
- 房间号：<strong>{room_id}</strong><br>
{'- 房间唯一ID：<span class="room-id-box">{st.session_state.object_id[:8]}...</span>' if st.session_state.object_id else ''}
</div>
""", unsafe_allow_html=True)

auto_restore_state(room_id)

# 操作按钮
if st.button("⚠️ 强制清理房间", use_container_width=True, type="secondary"):
    if force_clean_room(room_id):
        st.rerun()

col_refresh, col_exit = st.columns(2)
with col_refresh:
    if st.button("🔄 刷新", use_container_width=True):
        auto_restore_state(room_id)
        st.success("刷新完成")

with col_exit:
    if st.button("🚪 退出房间", use_container_width=True) and st.session_state.entered_room:
        room_data = load_room(room_id)
        if room_data:
            device_id = get_device_id()
            players = room_data["players"].copy()
            if device_id in players:
                del players[device_id]
                requests.put(
                    f"{BASE_API_URL}/{room_data['objectId']}",
                    headers=HEADERS,
                    json={"players": players},
                    timeout=10
                )
        st.session_state.entered_room = False
        st.success("已退出房间")
        st.rerun()

# 进入房间
if not st.session_state.entered_room:
    if st.button("📥 进入房间", use_container_width=True, type="primary"):
        with st.spinner(f"正在加入房间 {room_id}..."):
            room_data = enter_room(room_id)
            if room_data:
                st.session_state.entered_room = True
                st.session_state.object_id = room_data["objectId"]
                st.session_state.board = room_data["board"]
                st.session_state.current_player = room_data["current_player"]
                st.session_state.players = room_data["players"]
                st.session_state.my_role = room_data["players"][device_id]
                st.rerun()

# 游戏界面（修复落子逻辑）
if st.session_state.entered_room and st.session_state.my_role:
    st.divider()
    st.info(f"""
    房间 {room_id}（玩家数：{len(st.session_state.players)}/2）<br>
    你的角色：{st.session_state.my_role} | 当前回合：{st.session_state.current_player}
    {">>> 等待对手落子..." if st.session_state.my_role != st.session_state.current_player else ">>> 轮到你落子啦！"}
    """)

    st.markdown(f"""
    <div class="debug-box">
    房间内玩家：<br>
    {[f"- {k[:8]}...({v})" for k, v in st.session_state.players.items()]}
    </div>
    """, unsafe_allow_html=True)

    # 游戏结束提示（提前显示）
    if st.session_state.game_over:
        result = f"{st.session_state.winner} 获胜！" if st.session_state.winner != "平局" else "平局！"
        st.success(f"🏆 游戏结束：{result}")

    # 棋盘渲染（修复按钮禁用逻辑）
    st.subheader("游戏棋盘")
    with st.container():
        st.markdown('<div class="board-container">', unsafe_allow_html=True)
        rows = [st.columns(3, gap="small") for _ in range(3)]
        grid = [col for row in rows for col in row]

        for i in range(9):
            with grid[i]:
                cell_value = st.session_state.board[i]
                display_text = cell_value if cell_value else " "

                # 修复禁用条件：仅当“游戏结束、格子非空、非当前回合”时禁用
                is_disabled = (
                        st.session_state.game_over
                        or (cell_value != "")
                        or (st.session_state.my_role != st.session_state.current_player)
                )

                # 落子按钮（确保胜利步可点击）
                if st.button(
                        label=display_text,
                        key=f"cell_{i}",
                        disabled=is_disabled,
                        use_container_width=True,
                        type="primary" if cell_value == "X" else "secondary"
                ):
                    # 落子
                    st.session_state.board[i] = st.session_state.my_role
                    # 立即判断胜利（关键：落子后先检查胜负）
                    winner = check_winner(st.session_state.board)

                    if winner:
                        st.session_state.game_over = True
                        st.session_state.winner = winner
                        st.session_state.current_player = None  # 游戏结束，无回合
                    else:
                        # 切换回合（仅当未分胜负时）
                        st.session_state.current_player = "O" if st.session_state.current_player == "X" else "X"

                    # 同步到云端
                    try:
                        update_data = {
                            "board": st.session_state.board,
                            "current_player": st.session_state.current_player,
                            "game_over": st.session_state.game_over,
                            "winner": st.session_state.winner
                        }
                        requests.put(
                            f"{BASE_API_URL}/{st.session_state.object_id}",
                            headers=HEADERS,
                            json=update_data,
                            timeout=10
                        )
                        # 胜利提示（落子后立即显示）
                        if winner:
                            st.success(f"🎉 你赢啦！（角色：{st.session_state.my_role}）")
                        else:
                            st.success("落子成功！对手刷新后可见")
                    except Exception as e:
                        st.warning(f"同步失败：{str(e)}")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # 重新开始
    if st.button("🔄 重新开始游戏", use_container_width=True) and st.session_state.game_over:
        st.session_state.board = ["", "", "", "", "", "", "", "", ""]
        st.session_state.current_player = "X"
        st.session_state.game_over = False
        st.session_state.winner = None
        try:
            requests.put(
                f"{BASE_API_URL}/{st.session_state.object_id}",
                headers=HEADERS,
                json={
                    "board": st.session_state.board,
                    "current_player": "X",
                    "game_over": False,
                    "winner": None
                },
                timeout=10
            )
            st.success("游戏已重新开始！")
        except Exception as e:
            st.warning(f"重新开始失败：{str(e)}")
        st.rerun()

st.caption("""
💡 最后一步落子问题修复说明：
1. 放置制胜一步时，请确保“你的角色”与“当前回合”一致
2. 制胜一步会立即触发“你赢啦！”的提示
""")
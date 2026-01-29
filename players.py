import streamlit as st
import json
import random
import os
import re

# --- 配置部分 ---
DATA_FILE = 'soccer_data.json'
POSITIONS = ["左前锋", "右前锋", "中锋", "前卫", "后腰", "左后卫", "右后卫", "守门员"]
POS_LIMITS = {pos: 1 for pos in POSITIONS}
TEAMS = ["无偏好", "白队", "橙队"]

# --- 页面设置 ---
st.set_page_config(page_title="足球分队系统", page_icon="⚽", layout="wide")

# --- 自适应布局 ---
def get_layout_config():
    return True  
# --- 1. 数据管理 ---
def load_data():
    if not os.path.exists(DATA_FILE): return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # 迁移旧数据
    migrated = False
    for name, stats in data.items():
        if 'p3' not in stats:
            stats['p3'] = stats.get('p2', POSITIONS[0])
            migrated = True
    if migrated: save_data(data)
    return data

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- 2. 文本解析工具 ---
def parse_text_input(text):
    clean_names = []
    if not text: return clean_names
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        name = re.sub(r'^\d+[\.\、\s]*', '', line).strip()
        if name: clean_names.append(name)
    return clean_names

# --- 3. 核心算法 ---

def assign_positions_flexible(team_players, db):
    assignments = {} 
    taken_positions = set()
    
    # 按照 last_p1 排序
    candidates = team_players[:]
    random.shuffle(candidates)
    candidates.sort(key=lambda x: db[x]['last_p1'], reverse=True)
    
    remaining_candidates = []

    # --- Round 1: 分配 P1 ---
    for p in candidates:
        p1 = db[p]['p1']
        if p1 not in taken_positions:
            assignments[p] = p1
            taken_positions.add(p1)
        else:
            remaining_candidates.append(p)
            
    # --- Round 2: 分配 P2 ---
    candidates = remaining_candidates[:]
    remaining_candidates = []
    for p in candidates:
        p2 = db[p]['p2']
        if p2 not in taken_positions:
            assignments[p] = p2
            taken_positions.add(p2)
        else:
            remaining_candidates.append(p)

    # --- Round 3: 分配 P3 ---
    candidates = remaining_candidates[:]
    remaining_candidates = []
    for p in candidates:
        p3 = db[p]['p3']
        if p3 not in taken_positions:
            assignments[p] = p3
            taken_positions.add(p3)
        else:
            remaining_candidates.append(p)
            
    # --- Round 4: 强制调剂 ---
    candidates = remaining_candidates[:]
    remaining_candidates = []
    
    # 获取剩余空位列表
    empty_slots = [pos for pos in POSITIONS if pos not in taken_positions]
    
    for p in candidates:
        if empty_slots:
            # 还有空位
            slot = empty_slots.pop(0)
            assignments[p] = f"{slot} (调剂)" # 标记为调剂
            taken_positions.add(slot)
        else:
            # 没位置了
            remaining_candidates.append(p)

    # --- Round 5: 替补 ---
    for p in remaining_candidates:
        assignments[p] = "替补"

    return assignments

def calculate_balanced_teams_smart(attendees, db):
    """
    智能平衡分队：
    1. 优先满足队伍偏好。
    2. 在分配无偏好人员时，尝试让两队战力分差 < 10%。
    3. 尝试多次随机分配无偏好人员，取战力最平衡的一组。
    """
    # 1. 分组
    pref_white = [p for p in attendees if db[p].get('team_pref') == '白队']
    pref_orange = [p for p in attendees if db[p].get('team_pref') == '橙队']
    no_pref = [p for p in attendees if db[p].get('team_pref') not in ['白队', '橙队']]
    
    # 目标每队人数
    total_len = len(attendees)
    target_w = total_len // 2
    
    best_white = []
    best_orange = []
    min_skill_diff_percent = 100.0 # 初始设个大数
    
    for _ in range(50):
        # 复制并打乱无偏好组
        current_no_pref = no_pref[:]
        random.shuffle(current_no_pref)
        
        # 基础班底
        temp_white = pref_white[:]
        temp_orange = pref_orange[:]
        
        # 动态平衡人数
        while current_no_pref:
            p = current_no_pref.pop()
            if len(temp_white) < len(temp_orange):
                temp_white.append(p)
            elif len(temp_orange) < len(temp_white):
                temp_orange.append(p)
            else:
                # 人数一样，随机给
                if random.random() < 0.5: temp_white.append(p)
                else: temp_orange.append(p)
        
        # 强制人数修正 
        all_temp = temp_white + temp_orange

        while len(temp_white) > len(temp_orange) + 1:
            candidates = [x for x in temp_white if x in no_pref]
            if not candidates: candidates = temp_white 
            mover = candidates[-1] # 取一个
            temp_white.remove(mover)
            temp_orange.append(mover)
            
        while len(temp_orange) > len(temp_white) + 1:
            candidates = [x for x in temp_orange if x in no_pref]
            if not candidates: candidates = temp_orange
            mover = candidates[-1]
            temp_orange.remove(mover)
            temp_white.append(mover)
            
        # 计算战力
        sw = sum(db[p]['skill'] for p in temp_white)
        so = sum(db[p]['skill'] for p in temp_orange)
        
        # 防止除以0
        avg_skill = (sw + so) / 2 if (sw+so) > 0 else 1
        diff_percent = abs(sw - so) / avg_skill * 100
        
        # 如果这是目前发现的最平衡组合，或者是第一次，存下来
        if diff_percent < min_skill_diff_percent:
            min_skill_diff_percent = diff_percent
            best_white = temp_white[:]
            best_orange = temp_orange[:]
            
        if diff_percent <= 10.0:
            break
            
    # 最终分配位置
    roles_white = assign_positions_flexible(best_white, db)
    roles_orange = assign_positions_flexible(best_orange, db)
    
    final_sw = sum(db[p]['skill'] for p in best_white)
    final_so = sum(db[p]['skill'] for p in best_orange)
    
    return best_white, best_orange, roles_white, roles_orange, final_sw, final_so, min_skill_diff_percent

def update_history(db, roles_white, roles_orange):
    all_roles = {**roles_white, **roles_orange}
    for name in db:
        if name in all_roles:
            assigned = all_roles[name]
            # 只有拿到第一志愿才清零，调剂/替补/P2/P3 都增加权重
            if assigned == db[name]['p1']:
                db[name]['last_p1'] = 0
            else:
                db[name]['last_p1'] += 1
    return db

# --- 4. UI 界面 ---

st.title("⚽ 足球分队系统")

tab1, tab2 = st.tabs(["📅 比赛分队", "📝 球员管理"])

# === TAB 1: 比赛日 ===
with tab1:
    db = load_data()
    all_players = sorted(list(db.keys()))
    
    with st.container():
        st.subheader("1. 名单录入")
        col_text, col_select = st.columns([1, 1], gap="medium")
        with col_text:
            raw_text = st.text_area("方式A: 粘贴名单", height=150, placeholder="1. xx\n2. xxx\n3. xxxx\n...")
            if st.button("⬇️ 识别并同步", use_container_width=True):
                parsed = parse_text_input(raw_text)
                valid = [n for n in parsed if n in db]
                st.session_state['selected_attendees'] = valid
                unknown = [n for n in parsed if n not in db]
                if unknown: st.toast(f"未知球员: {unknown}", icon="⚠️")
        with col_select:
            current = st.session_state.get('selected_attendees', [])
            current = [n for n in current if n in all_players]
            attendees = st.multiselect("方式B: 点选", all_players, default=current)
            st.session_state['selected_attendees'] = attendees
            st.caption(f"已选: {len(attendees)} 人")

    st.divider()
    if st.button("🚀 生成平衡对阵", type="primary", use_container_width=True):
        if len(attendees) < 10:
            st.error("人数过少")
        else:
            res = calculate_balanced_teams_smart(attendees, db)
            st.session_state['match_result'] = res

    if 'match_result' in st.session_state:
        tw, to, rw, ro, sw, so, diff = st.session_state['match_result']
        
        # 战力平衡提示
        st.subheader("📊 对阵结果")
        if diff <= 10:
            st.success(f"⚖️ 战力平衡！差距仅 {diff:.1f}% (目标 <10%)")
        else:
            st.warning(f"⚠️ 战力差距 {diff:.1f}% (已尽力平衡，受限于到场人员偏好)")

        c1, c2 = st.columns([1, 1], gap="medium")
        with c1:
            st.info(f"⚪ **白队 ({len(tw)}人)** - 战力: {sw:.1f}")
            # 排序：位置正常的排前，调剂的排后，替补最后
            def sort_key_white(p):
                role = rw[p]
                if "替补" in role: return 999
                if "调剂" in role: return 100
                if role in POSITIONS: return POSITIONS.index(role)
                return 50
            
            for p in sorted(tw, key=sort_key_white):
                role = rw[p]
                if "调剂" in role:
                    st.write(f"⚠️ **{role}**: {p}") # 黄色警告色
                elif "替补" in role:
                    st.caption(f"💤 **{role}**: {p}")
                else:
                    st.write(f"**{role}**: {p}")
                    
        with c2:
            st.info(f"🟠 **橙队 ({len(to)}人)** - 战力: {so:.1f}")
            def sort_key_orange(p):
                role = ro[p]
                if "替补" in role: return 999
                if "调剂" in role: return 100
                if role in POSITIONS: return POSITIONS.index(role)
                return 50
            for p in sorted(to, key=sort_key_orange):
                role = ro[p]
                if "调剂" in role:
                    st.write(f"⚠️ **{role}**: {p}")
                elif "替补" in role:
                    st.caption(f"💤 **{role}**: {p}")
                else:
                    st.write(f"**{role}**: {p}")

        st.divider()
        if st.button("💾 确认并更新历史", use_container_width=True):
            db = update_history(db, rw, ro)
            save_data(db)
            st.toast("✅ 历史记录已更新！")
            del st.session_state['match_result']

# === TAB 2: 球员管理  ===
with tab2:
    st.header("球员名册管理")
    mode = st.radio("模式", ["添加", "编辑"], horizontal=True)
    db = load_data()
    
    if mode == "添加":
        with st.form("add"):
            name = st.text_input("姓名")
            team_pref = st.selectbox("偏好", TEAMS)
            skill = st.slider("能力", 1.0, 10.0, 6.0)

            st.write("**位置志愿**")
            pos_cols = st.columns(3, gap="small")
            with pos_cols[0]:
                p1 = st.selectbox("P1", POSITIONS)
            with pos_cols[1]:
                p2 = st.selectbox("P2", POSITIONS)
            with pos_cols[2]:
                p3 = st.selectbox("P3", POSITIONS)
            if st.form_submit_button("保存", use_container_width=True):
                if name:
                    db[name] = {"team_pref": team_pref, "skill": skill, "p1": p1, "p2": p2, "p3": p3, "last_p1": 0}
                    save_data(db)
                    st.success("已添加")
                    st.rerun()
    else:
        st.subheader("编辑球员")
        edit = st.selectbox("选择球员", sorted(db.keys()))
        if edit:
            d = db[edit]
            with st.form("edit"):
                tp = st.selectbox("偏好", TEAMS, index=TEAMS.index(d.get('team_pref','无偏好')))
                sk = st.slider("能力", 1.0, 10.0, d.get('skill', 6.0))
                st.write("**位置志愿**")
                pos_cols = st.columns(3, gap="small")
                # 安全获取索引
                def get_idx(val): return POSITIONS.index(val) if val in POSITIONS else 0
                with pos_cols[0]:
                    np1 = st.selectbox("P1", POSITIONS, index=get_idx(d.get('p1')))
                with pos_cols[1]:
                    np2 = st.selectbox("P2", POSITIONS, index=get_idx(d.get('p2')))
                with pos_cols[2]:
                    np3 = st.selectbox("P3", POSITIONS, index=get_idx(d.get('p3')))
                if st.form_submit_button("更新", use_container_width=True):
                    db[edit].update({'team_pref': tp, 'skill': sk, 'p1': np1, 'p2': np2, 'p3': np3})
                    save_data(db)
                    st.success("已更新")
                    st.rerun()
    
    st.divider()
    st.subheader("📋 所有球员表格")
    if db:
        # 构建表格数据 
        table_data = []
        for name in sorted(db.keys()):
            player = db[name]
            table_data.append({
                "球员": name,
                "能力": f"{player.get('skill', 0):.1f}",
                "偏好": player.get('team_pref', '无偏好'),
                "P1": player.get('p1', '-'),
                "P2": player.get('p2', '-'),
                "P3": player.get('p3', '-'),
                "权重": player.get('last_p1', 0)
            })

        st.dataframe(
            table_data, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "球员": st.column_config.TextColumn(width="large"),
                "能力": st.column_config.TextColumn(width="small"),
                "偏好": st.column_config.TextColumn(width="medium"),
                "P1": st.column_config.TextColumn(width="small"),
                "P2": st.column_config.TextColumn(width="small"),
                "P3": st.column_config.TextColumn(width="small"),
                "权重": st.column_config.NumberColumn(width="small")
            }
        )
    else:
        st.info("暂无球员数据")
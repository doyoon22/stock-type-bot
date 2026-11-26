# =====================================================================
# 나랑 닮은 종목 찾기 — 투자 유형 16종 진단 챗봇 (Streamlit, 규칙 기반)
#
# 구성
#   1) 비밀번호 확인 → 2) 닉네임 → 3) 12문항 대화형 진단 (4개 축 × 3문항)
#   4) 결과: 16유형 중 하나 + 닮은 종목 + 조심할 실수 + 투자 궁합
#   5) 자유 대화: 궁합 비교, 유형 도감, 투자 용어 설명 (키워드 규칙 기반)
#
# 4개 축
#   방향  M(대세: 남들 벌 때 같이)  / C(역발상: 남들 잃을 때 나만)
#   위험  D(수비: 잃지 않는 게 먼저) / O(공격: 크게 먹는 게 먼저)
#   형태  F(집중: 한 종목에 확신)     / B(분산: 바구니로 묶어서)
#   근거  N(숫자: 실적·배당·금리)     / V(스토리: 비전과 이야기)
# =====================================================================
import hashlib
import re

import streamlit as st

st.set_page_config(page_title="나랑 닮은 종목 찾기", page_icon="📈", layout="centered")

# 비밀번호는 원문 대신 SHA-256 해시로만 저장 (공개 저장소에 올려도 비밀번호가 드러나지 않음)
PASSWORD_HASH = "673e2c891578b2eee583e6db47ce41eb744198505afb4253142ea3902b23f3c5"

# ---------------------------------------------------------------------
# 1. 질문 데이터 (축 하나당 3문항, 선택지 A/B)
# ---------------------------------------------------------------------
QUESTIONS = [
    # 방향: M / C
    {"axis": 0, "q": "주변 친구들이 다 돈 벌었다는 종목이 있어. 너라면?",
     "A": ("지금이라도 같이 탄다", "M"), "B": ("이미 늦었어, 다른 데를 본다", "C")},
    {"axis": 0, "q": "시장이 폭락해서 뉴스가 온통 공포 분위기야. 너는?",
     "A": ("일단 팔고 상황을 지켜본다", "M"), "B": ("오히려 싸게 살 기회다", "C")},
    {"axis": 0, "q": "둘 중 더 기분 좋은 상황은?",
     "A": ("남들 다 벌 때 나도 같이 번 것", "M"), "B": ("남들 다 잃을 때 나만 번 것", "C")},
    # 위험: D / O
    {"axis": 1, "q": "100만 원을 1년 투자한다면 어느 쪽?",
     "A": ("확실하게 105만 원", "D"), "B": ("반반 확률로 140만 원 또는 80만 원", "O")},
    {"axis": 1, "q": "투자한 돈이 한 달 만에 -20%가 됐어.",
     "A": ("잠이 안 온다, 당장 빼고 싶다", "D"), "B": ("원래 그런 거지, 버틴다", "O")},
    {"axis": 1, "q": "투자의 목표는?",
     "A": ("물가보다 조금 더 버는 것", "D"), "B": ("인생을 바꿀 만한 수익", "O")},
    # 형태: F / B
    {"axis": 2, "q": "식당을 차린다면 어떤 가게?",
     "A": ("메뉴 하나로 승부하는 전문점", "F"), "B": ("메뉴 여러 개인 든든한 백반집", "B")},
    {"axis": 2, "q": "투자 공부에 쓸 시간이 생기면?",
     "A": ("한 회사를 깊게 파고든다", "F"), "B": ("고르기 귀찮다, 알아서 섞어줘", "B")},
    {"axis": 2, "q": "확신이 드는 종목을 찾았어.",
     "A": ("비중을 크게 싣는다", "F"), "B": ("그래도 여러 개로 나눠 담는다", "B")},
    # 근거: N / V
    {"axis": 3, "q": "종목을 고를 때 제일 먼저 보는 건?",
     "A": ("실적, 배당, PER 같은 숫자", "N"), "B": ("CEO의 비전과 미래 이야기", "V")},
    {"axis": 3, "q": "둘 중 더 설레는 뉴스는?",
     "A": ("분기 영업이익 30% 증가", "N"), "B": ("화성에 공장을 짓겠다", "V")},
    {"axis": 3, "q": "친구에게 종목을 추천한다면?",
     "A": ("표와 숫자로 근거를 보여준다", "N"), "B": ("이 회사가 바꿀 세상을 이야기한다", "V")},
]

AXES = [("M", "C", "대세", "역발상"), ("D", "O", "수비", "공격"),
        ("F", "B", "집중", "분산"), ("N", "V", "숫자", "스토리")]

# 선택 직후 봇이 보내는 짧은 반응 (글자별)
REACTIONS = {
    "M": "흐름을 타는 감각이 있네 🌊", "C": "남들과 반대로 가는 배짱이 보여 🦅",
    "D": "원금을 지키는 신중함, 좋아 🛡️", "O": "승부사 기질이 느껴지는데? 🔥",
    "F": "한 놈만 판다… 확신형이구나 🎯", "B": "달걀은 한 바구니에 안 담는 타입 🧺",
    "N": "숫자로 말하는 냉정함 📊", "V": "이야기에 설레는 낭만파 ✨",
}

# ---------------------------------------------------------------------
# 2. 16개 유형 데이터
#    vol: 변동성, div: 배당, mkt: 시장(코스피·S&P500)과 움직이는 방향
# ---------------------------------------------------------------------
TYPES = {
    "MDFN": dict(name="배당 받는 은행원", emoji="🏦", stock="KB금융", kind="국내 주식 · 은행지주",
                 vol="중간", div="있음", mkt="같은 방향",
                 why="남들과 같은 길을 가되, 숫자로 확인된 안정적인 대형주에 집중하는 타입. 국내 대표 금융지주처럼 꾸준히 벌고 배당으로 돌려주는 기업과 닮았어.",
                 caution="배당만 보고 사면 '배당 함정'에 빠질 수 있어. 배당률이 높은 이유가 주가 하락 때문은 아닌지 꼭 확인해."),
    "MDFV": dict(name="국민 개미", emoji="🐜", stock="삼성전자", kind="국내 주식 · 반도체",
                 vol="중간", div="있음", mkt="같은 방향",
                 why="모두가 아는 회사, 모두가 믿는 이야기에 마음이 가는 타입. 소액주주가 가장 많은 국민주 삼성전자와 닮았어.",
                 caution="'국민주니까 언젠가 오르겠지'는 희망이지 근거가 아니야. 반도체 업황 사이클에 따라 몇 년씩 횡보할 수 있다는 걸 기억해."),
    "MDBN": dict(name="월급 설계자", emoji="📅", stock="미국 배당 ETF (SCHD)", kind="미국 ETF · 배당성장",
                 vol="낮음", div="있음 (분기)", mkt="같은 방향",
                 why="시장 흐름은 따르되 숫자로 설계된 바구니를 선호하는 타입. 배당을 꾸준히 늘려온 미국 기업들을 묶은 배당 ETF와 닮았어.",
                 caution="배당 ETF도 주식이라 시장이 빠지면 같이 빠져. 배당을 받는다고 원금이 보장되는 건 아니야."),
    "MDBV": dict(name="미국 장기 거주자", emoji="🗽", stock="S&P500 ETF", kind="미국 ETF · 지수",
                 vol="중간", div="있음 (소액)", mkt="같은 방향",
                 why="'미국에 묻어두면 된다'는 이야기를 믿고 바구니째 사는 타입. 미국 대형주 500개를 담은 S&P500 ETF와 닮았어.",
                 caution="과거에 장기 우상향했다고 미래도 보장되진 않아. 원·달러 환율에 따라 원화 수익률이 달라진다는 것도 챙겨."),
    "MOFN": dict(name="실적 사냥꾼", emoji="🎯", stock="엔비디아", kind="미국 주식 · AI 반도체",
                 vol="높음", div="거의 없음", mkt="같은 방향 (더 크게)",
                 why="시장의 주도주에 올라타되, 폭발하는 실적이라는 숫자로 확신을 얻는 타입. AI 반도체 수요로 실적이 급성장한 엔비디아와 닮았어.",
                 caution="실적이 좋아도 기대가 너무 높으면 '좋은 실적에도 주가 하락'이 나와. 이미 주가에 얼마나 반영됐는지 봐야 해."),
    "MOFV": dict(name="화성 이민 준비생", emoji="🚀", stock="테슬라", kind="미국 주식 · 전기차",
                 vol="매우 높음", div="없음", mkt="같은 방향 (더 크게)",
                 why="지금의 실적보다 세상을 바꿀 비전에 베팅하는 타입. 전기차·자율주행·로봇이라는 이야기로 움직이는 테슬라와 닮았어.",
                 caution="스토리 주식은 하루에도 크게 출렁여. 비전이 맞아도 그 사이 -50%를 견딜 수 있는지 스스로에게 물어봐."),
    "MOBN": dict(name="두 배 질주러", emoji="🏎️", stock="KODEX 레버리지", kind="국내 ETF · 코스피200 2배",
                 vol="매우 높음", div="없음", mkt="같은 방향 (하루 2배)",
                 why="시장이 오를 거라 계산되면 그 상승을 두 배로 먹고 싶은 타입. 코스피200 하루 수익률의 2배를 따라가는 레버리지 ETF와 닮았어.",
                 caution="레버리지는 '하루' 수익률의 2배라서, 오르락내리락하면 지수가 제자리여도 손실이 쌓여(변동성 끌림). 장기 보유용이 아니야."),
    "MOBV": dict(name="테마 서퍼", emoji="🏄", stock="2차전지 테마 ETF", kind="국내 ETF · 테마",
                 vol="높음", div="거의 없음", mkt="같은 방향 (테마 따라)",
                 why="지금 가장 뜨거운 이야기에 바구니째 올라타는 타입. 개미 열풍을 이끈 2차전지 테마 ETF와 닮았어.",
                 caution="테마는 유행이 끝나면 빠르게 식어. 뉴스에서 가장 시끄러울 때가 고점인 경우가 많다는 걸 기억해."),
    "CDFN": dict(name="오마하의 제자", emoji="🧓", stock="버크셔 해서웨이", kind="미국 주식 · 지주회사",
                 vol="낮음", div="없음", mkt="같은 방향 (덜 출렁임)",
                 why="남들이 두려워할 때 숫자로 저평가를 확인하고 사는 가치투자 타입. 워런 버핏의 버크셔 해서웨이와 닮았어.",
                 caution="싸 보이는 데엔 이유가 있을 수 있어(가치 함정). 싸다는 것만으로 사지 말고 회복할 이유를 찾아."),
    "CDFV": dict(name="공기업 부활 신봉자", emoji="⚡", stock="한국전력", kind="국내 주식 · 공기업",
                 vol="중간", div="실적 따라 다름", mkt="정책 영향이 큼",
                 why="남들이 외면한 회사가 언젠가 정상화된다는 이야기에 베팅하는 타입. 전기요금 정상화 기대에 따라 움직이는 한국전력과 닮았어.",
                 caution="요금을 정부가 정하는 구조라 실적이 정책에 크게 좌우돼. '언젠가'가 언제인지는 아무도 몰라."),
    "CDBN": dict(name="금리 계산기", emoji="🧮", stock="미국 장기국채 ETF (TLT)", kind="미국 ETF · 국채",
                 vol="중간", div="이자 (월)", mkt="주식과 반대일 때가 많음",
                 why="위기 때 금리가 내려가면 오르는 구조를 숫자로 계산하는 타입. 미국 20년 이상 장기국채를 담은 TLT와 닮았어.",
                 caution="국채라고 안전한 게 아니야. 금리가 오르면 장기채 가격은 크게 떨어져(2022년처럼). 금리 방향이 핵심이야."),
    "CDBV": dict(name="금고지기", emoji="🪙", stock="금 ETF", kind="원자재 ETF · 금",
                 vol="중간", div="없음", mkt="위기 때 반대로 움직일 때가 많음",
                 why="수천 년 된 '위기엔 금'이라는 이야기를 믿고 지키는 타입. 금 가격을 따라가는 금 ETF와 닮았어.",
                 caution="금은 이자도 배당도 없어. 평온한 시기엔 오랫동안 제자리일 수 있어."),
    "COFN": dict(name="바겐세일 헌터", emoji="🏷️", stock="카카오", kind="국내 주식 · 플랫폼",
                 vol="높음", div="거의 없음", mkt="같은 방향",
                 why="많이 떨어진 성장주를 숫자로 따져보고 반등에 거는 타입. 2021년 고점 대비 크게 떨어진 국민 성장주 카카오와 닮았어.",
                 caution="'이만큼 떨어졌으니 오르겠지'는 기준점 편향일 수 있어. 예전 가격이 아니라 지금의 실적과 성장성을 봐."),
    "COFV": dict(name="몰락한 왕의 부활 신봉자", emoji="👑", stock="알리바바", kind="미국 상장 중국 주식 · 플랫폼",
                 vol="높음", div="소액", mkt="중국 정책 영향이 큼",
                 why="모두가 '끝났다'고 하는 왕의 귀환에 베팅하는 타입. 규제 이후 급락했던 중국 대표 플랫폼 알리바바와 닮았어.",
                 caution="국가 정책 리스크는 회사가 아무리 잘해도 통제할 수 없어. 한 종목에 너무 큰 비중을 싣지 마."),
    "COBN": dict(name="나 홀로 하락 베팅러", emoji="🐻", stock="KODEX 인버스", kind="국내 ETF · 코스피200 -1배",
                 vol="중간", div="없음", mkt="반대 방향 (하루 -1배)",
                 why="남들이 잃을 때 나만 버는 구조를 계산하는 타입. 코스피200이 떨어지면 수익이 나는 인버스 ETF와 닮았어.",
                 caution="시장은 장기적으로 오르는 경향이 있어서 인버스를 오래 들고 있으면 불리해. 하루 수익률 기준이라 횡보장에서도 손실이 쌓여."),
    "COBV": dict(name="종말론자", emoji="🌋", stock="KODEX 200선물인버스2X", kind="국내 ETF · 코스피200 -2배",
                 vol="매우 높음", div="없음", mkt="반대 방향 (하루 -2배)",
                 why="곧 큰 폭락이 온다는 시나리오에 두 배로 베팅하는 타입. 일명 '곱버스'와 닮았어.",
                 caution="곱버스는 하루 -2배라 시간이 지날수록 녹아내리는 구조야. 폭락이 늦게 오면 맞혀도 돈을 못 벌 수 있어."),
}

# 자유 대화에서 쓰는 투자 용어 설명 (키워드 → 설명)
FAQ = {
    ("인버스",): "인버스 ETF는 지수가 하루 1% 떨어지면 1% 오르도록 만든 상품이야. '하루' 기준이라 오래 들고 있으면 지수 하락폭만큼 벌지 못할 수 있어.",
    ("레버리지",): "레버리지 ETF는 지수 하루 수익률의 2배를 따라가. 오르락내리락하면 지수가 제자리여도 손실이 쌓이는 '변동성 끌림'이 생겨.",
    ("곱버스",): "곱버스는 인버스 2배(하루 -2배) ETF의 별명이야. 하락장 단기 베팅용이지 장기 보유용이 아니야.",
    ("etf",): "ETF는 여러 종목을 한 바구니에 담아 주식처럼 사고팔 수 있게 만든 펀드야. 한 번에 분산투자가 돼.",
    ("배당",): "배당은 회사가 번 돈의 일부를 주주에게 나눠주는 거야. 배당이 많다고 무조건 좋은 회사는 아니니 이유를 같이 봐야 해.",
    ("분산", "분산투자"): "분산투자는 서로 다르게 움직이는 자산을 섞어서, 하나가 떨어져도 전체 손실을 줄이는 방법이야. 이 앱의 '투자 궁합'이 바로 그 원리야.",
    ("per",): "PER(주가수익비율)은 주가를 주당순이익으로 나눈 값이야. 낮으면 이익 대비 싸다는 뜻이지만, 성장성이 낮아서일 수도 있어.",
    ("변동성",): "변동성은 가격이 얼마나 크게 출렁이는지야. 변동성이 크면 크게 벌 수도, 크게 잃을 수도 있어.",
    ("손실회피", "손실 회피"): "손실회피는 같은 크기라도 이익보다 손실을 2배쯤 더 아프게 느끼는 심리야(카너먼·트버스키의 전망이론). 손실 난 종목을 못 팔고 버티게 만들어.",
    ("군집", "군중", "포모", "fomo"): "군집행동은 남들이 사니까 따라 사는 심리야. 대세(M) 성향이 강할수록 고점에서 따라 들어가는 걸 조심해야 해.",
}

AXIS_NAMES = ["방향", "위험", "형태", "근거"]


# ---------------------------------------------------------------------
# 3. 계산 함수
# ---------------------------------------------------------------------
def score_axes(answers):
    """축별로 첫 글자(M/D/F/N)를 고른 횟수(0~3)를 센다."""
    counts = [0, 0, 0, 0]
    for qi, letter in enumerate(answers):
        axis = QUESTIONS[qi]["axis"]
        if letter == AXES[axis][0]:
            counts[axis] += 1
    return counts


def type_code(answers):
    """3문항 중 2개 이상 고른 쪽 글자로 4자리 코드를 만든다."""
    counts = score_axes(answers)
    return "".join(AXES[i][0] if counts[i] >= 2 else AXES[i][1] for i in range(4))


def flip(letter, axis):
    a, b = AXES[axis][0], AXES[axis][1]
    return b if letter == a else a


def best_match(code):
    """환상의 짝꿍: 방향과 형태가 반대(서로 반대로 움직이고, 집중과 분산이 보완), 위험·근거는 같음"""
    return flip(code[0], 0) + code[1] + flip(code[2], 2) + code[3]


def twin(code):
    """쌍둥이: 방향·위험·형태가 같고 근거만 다름 → 같이 웃고 같이 운다(분산 효과 낮음)"""
    return code[0] + code[1] + code[2] + flip(code[3], 3)


def compat(a, b):
    """궁합 점수 0~5점 (분산 효과 중심)
       방향이 다르면 +3 (서로 반대로 움직여 손실을 상쇄),
       형태가 다르면 +1 (집중과 분산이 섞여 균형), 위험 성향이 같으면 +1 (서로의 결정을 이해)"""
    s = 3 * (a[0] != b[0]) + (a[2] != b[2]) + (a[1] == b[1])
    if s >= 5:
        label = "환상의 짝꿍 💞"
    elif s >= 3:
        label = "좋은 궁합 😊"
    elif s == 2:
        label = "무난한 궁합 🙂"
    else:
        label = "쌍둥이 👯 (같이 웃고 같이 운다)"
    reasons = []
    reasons.append("시장 방향이 반대라 한쪽이 떨어질 때 다른 쪽이 버텨줘요." if a[0] != b[0]
                   else "시장 방향이 같아서 오를 때도 떨어질 때도 함께 움직여요.")
    reasons.append("집중과 분산이 섞여서 포트폴리오 균형이 좋아요." if a[2] != b[2]
                   else "투자 형태가 같아서 비슷한 상품에 몰리기 쉬워요.")
    reasons.append("위험 감수 수준이 같아서 서로의 결정을 이해하기 쉬워요." if a[1] == b[1]
                   else "위험 감수 수준이 달라서 한 명은 답답하고 한 명은 불안할 수 있어요.")
    return s, label, reasons


# ---------------------------------------------------------------------
# 4. 화면 스타일
# ---------------------------------------------------------------------
st.markdown("""
<style>
.card {border-radius:18px; padding:22px 24px; margin:6px 0 14px 0;
       background:linear-gradient(135deg,#1E3A5F 0%,#2F6DB5 100%); color:#fff;}
.card .code {font-size:15px; letter-spacing:4px; opacity:.85;}
.card .name {font-size:30px; font-weight:800; margin:4px 0 2px 0;}
.card .stock {font-size:18px; margin-top:6px;}
.card .stock b {background:#fff; color:#1E3A5F; padding:2px 10px; border-radius:8px;}
.chips span {display:inline-block; background:#EEF3F9; color:#1E3A5F; border-radius:999px;
             padding:4px 12px; margin:3px 6px 3px 0; font-size:13px; font-weight:600;}
.box {border-radius:14px; padding:14px 16px; margin:8px 0; border:1px solid #D9E2EC; background:#F8FAFC; color:#1F2933;}
.box.warn {background:#FFF6F0; border-color:#F5C7A9;}
.box h4 {margin:0 0 6px 0; font-size:15px;}
.bar {display:flex; align-items:center; gap:8px; margin:6px 0; font-size:13px; color:inherit;}
.bar .track {flex:1; height:12px; background:#E4E9F0; border-radius:999px; overflow:hidden;}
.bar .fill {height:100%; background:#2F6DB5;}
.bar .lab {width:64px; text-align:center; font-weight:700;}
.small {font-size:12px; opacity:.7;}
</style>
""", unsafe_allow_html=True)


def axis_bars_html(answers):
    counts = score_axes(answers)
    rows = []
    for i, (a, b, an, bn) in enumerate(AXES):
        pa = round(counts[i] / 3 * 100)
        rows.append(f"<div class='bar'><div class='lab'>{an} {a}</div>"
                    f"<div class='track'><div class='fill' style='width:{pa}%'></div></div>"
                    f"<div class='lab'>{bn} {b}</div><div style='width:84px'>{pa}% : {100 - pa}%</div></div>")
    return "".join(rows)


def type_card_html(code):
    t = TYPES[code]
    return (f"<div class='card'><div class='code'>{code}</div>"
            f"<div class='name'>{t['emoji']} {t['name']}</div>"
            f"<div class='stock'>나와 닮은 종목 <b>{t['stock']}</b></div>"
            f"<div class='small' style='margin-top:6px'>{t['kind']}</div></div>"
            f"<div class='chips'><span>변동성 {t['vol']}</span><span>배당 {t['div']}</span>"
            f"<span>시장과 {t['mkt']}</span></div>")


def describe_type(code):
    t = TYPES[code]
    return f"**{code} · {t['emoji']} {t['name']}** — 닮은 종목: **{t['stock']}**\n\n{t['why']}"


# ---------------------------------------------------------------------
# 5. 세션 상태 (대화 단계와 기록을 저장)
# ---------------------------------------------------------------------
def reset():
    st.session_state.stage = "name"          # name → quiz → result
    st.session_state.qi = 0                  # 현재 질문 번호
    st.session_state.answers = []            # 고른 글자 목록
    st.session_state.nick = ""
    st.session_state.chat = []               # 진단이 끝난 뒤 자유 대화 기록
    st.session_state.messages = [
        {"role": "assistant",
         "content": "안녕! 나는 **닮은 종목 찾기 봇**이야 📈\n\n12개 질문으로 너의 투자 성향을 16가지 유형 중 하나로 진단하고, "
                    "**너와 성격이 닮은 대표 종목**을 찾아줄게.\n\n먼저 **닉네임**을 알려줘!"}]


if "authed" not in st.session_state:
    st.session_state.authed = False
if "stage" not in st.session_state:
    reset()


def say(role, text):
    """대화 기록에 메시지를 추가 (결과가 나온 뒤에는 자유 대화 기록에 쌓음)"""
    target = "chat" if st.session_state.stage == "result" else "messages"
    st.session_state[target].append({"role": role, "content": text})


def ask_current():
    q = QUESTIONS[st.session_state.qi]
    say("assistant", f"**Q{st.session_state.qi + 1}. {q['q']}**\n\n"
                     f"A) {q['A'][0]}  \nB) {q['B'][0]}")


def answer(choice):
    """A 또는 B를 고르면 기록하고 다음 질문 또는 결과로 넘어간다."""
    q = QUESTIONS[st.session_state.qi]
    text, letter = q[choice]
    say("user", f"{choice}) {text}")
    st.session_state.answers.append(letter)
    st.session_state.qi += 1
    # 축의 마지막(3번째) 질문을 끝낼 때마다 반응 한마디
    if st.session_state.qi % 3 == 0:
        axis = q["axis"]
        counts = score_axes(st.session_state.answers)
        lead = AXES[axis][0] if counts[axis] >= 2 else AXES[axis][1]
        say("assistant", f"{AXIS_NAMES[axis]} 성향 체크 완료! {REACTIONS[lead]}")
    if st.session_state.qi < len(QUESTIONS):
        ask_current()
    else:
        code = type_code(st.session_state.answers)
        st.session_state.code = code
        t = TYPES[code]
        st.session_state.stage = "result"
        say("assistant", f"🎉 **{st.session_state.nick}님의 투자 유형은 `{code}` · {t['emoji']} {t['name']}!** "
                         f"너와 가장 닮은 종목은 **{t['stock']}**이야.\n\n"
                         f"궁금한 건 자유롭게 물어봐. 예) `궁합 COBN`, `도감`, `인버스가 뭐야?`, `다시`")


def free_chat(text):
    """진단이 끝난 뒤 자유 대화: 키워드 규칙으로 답한다."""
    raw = text.strip()
    low = raw.lower()
    codes = re.findall(r"\b([MC][DO][FB][NV])\b", raw.upper())
    if low in ("다시", "처음", "재시작", "restart"):
        reset()
        return None
    if "도감" in raw or "전체" in raw or "유형 목록" in raw:
        lines = [f"- `{c}` {t['emoji']} {t['name']} → {t['stock']}" for c, t in TYPES.items()]
        return "📚 **16유형 도감**\n\n" + "\n".join(lines) + "\n\n궁금한 코드를 입력하면 자세히 알려줄게."
    if codes and ("궁합" in raw or len(codes) >= 2):
        a = codes[0] if len(codes) >= 2 else st.session_state.code
        b = codes[1] if len(codes) >= 2 else codes[0]
        s, label, reasons = compat(a, b)
        return (f"💘 **{a} {TYPES[a]['name']} × {b} {TYPES[b]['name']}**\n\n"
                f"궁합 점수 **{s} / 5** · {label}\n\n" + "\n".join(f"- {r}" for r in reasons) +
                f"\n\n{TYPES[a]['stock']} + {TYPES[b]['stock']} 조합으로 생각해보면 이해가 쉬워.")
    if codes:
        c = codes[0]
        return describe_type(c) + f"\n\n⚠️ 조심할 점: {TYPES[c]['caution']}"
    if "궁합" in raw:
        c = st.session_state.code
        return (f"`궁합 코드` 형식으로 입력해줘. 예) `궁합 {best_match(c)}`\n\n"
                f"참고로 너의 환상의 짝꿍은 `{best_match(c)}`({TYPES[best_match(c)]['name']})야.")
    for keys, ans in FAQ.items():
        if any(k in low for k in keys):
            return "💡 " + ans
    if "종목" in raw or "추천" in raw:
        c = st.session_state.code
        return (f"너와 닮은 종목은 **{TYPES[c]['stock']}**이야. 다만 이건 성향이 닮았다는 뜻이지 매수 추천이 아니야. "
                f"투자 결정은 꼭 스스로 따져보고 해줘 🙏")
    return ("음, 그건 아직 내가 모르는 질문이야 😅 이렇게 물어봐 줄래?\n\n"
            "- `궁합 COBN` → 친구 유형과 궁합\n- `도감` → 16유형 전체 보기\n- `MDFV` → 유형 설명\n"
            "- `인버스`, `레버리지`, `ETF`, `배당`, `분산투자`, `손실회피` → 용어 설명\n- `다시` → 처음부터")


# ---------------------------------------------------------------------
# 6. 비밀번호 화면
# ---------------------------------------------------------------------
if not st.session_state.authed:
    st.title("📈 나랑 닮은 종목 찾기")
    st.caption("12개 질문으로 알아보는 나의 투자 유형 16종")
    pw = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("입장하기", type="primary"):
        if hashlib.sha256(pw.encode()).hexdigest() == PASSWORD_HASH:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("비밀번호가 맞지 않아요.")
    st.stop()

# ---------------------------------------------------------------------
# 7. 사이드바: 진행률, 다시하기, 안내
# ---------------------------------------------------------------------
with st.sidebar:
    st.header("📈 닮은 종목 찾기")
    done = len(st.session_state.answers)
    st.progress(done / len(QUESTIONS), text=f"진행률 {done} / {len(QUESTIONS)}")
    if st.button("🔄 처음부터 다시", use_container_width=True):
        reset()
        st.rerun()
    st.markdown("**4개 축**\n- 방향: 대세 M / 역발상 C\n- 위험: 수비 D / 공격 O\n"
                "- 형태: 집중 F / 분산 B\n- 근거: 숫자 N / 스토리 V")
    st.caption("※ 이 서비스는 투자 성향을 재미있게 알아보는 교육용 콘텐츠이며, 특정 종목의 매수·매도를 권유하지 않습니다.")

st.title("📈 나랑 닮은 종목 찾기")

# ---------------------------------------------------------------------
# 8. 대화 기록 출력
# ---------------------------------------------------------------------
def show(msgs):
    for m in msgs:
        with st.chat_message(m["role"], avatar="🤖" if m["role"] == "assistant" else "🙂"):
            st.markdown(m["content"])


if st.session_state.stage == "result":
    # 결과가 나오면 진단 대화는 접어두고 결과 카드를 맨 위에 보여줌
    with st.expander("💬 진단 대화 다시 보기"):
        show(st.session_state.messages)
else:
    show(st.session_state.messages)

# ---------------------------------------------------------------------
# 9. 단계별 입력 처리
# ---------------------------------------------------------------------
stage = st.session_state.stage

if stage == "quiz":
    q = QUESTIONS[st.session_state.qi]
    c1, c2 = st.columns(2)
    c1.button(f"A) {q['A'][0]}", key=f"a{st.session_state.qi}", use_container_width=True,
              on_click=answer, args=("A",))
    c2.button(f"B) {q['B'][0]}", key=f"b{st.session_state.qi}", use_container_width=True,
              on_click=answer, args=("B",))

if stage == "result":
    code = st.session_state.code
    t = TYPES[code]
    tab1, tab2, tab3 = st.tabs(["🧾 내 결과", "💘 투자 궁합", "📚 유형 도감"])
    with tab1:
        st.markdown(type_card_html(code), unsafe_allow_html=True)
        st.markdown(f"<div class='box'><h4>🔍 왜 닮았을까?</h4>{t['why']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='box warn'><h4>⚠️ 이 유형이 조심할 실수</h4>{t['caution']}</div>",
                    unsafe_allow_html=True)
        st.markdown("**나의 성향 그래프**")
        st.markdown(axis_bars_html(st.session_state.answers), unsafe_allow_html=True)
        st.download_button("📥 결과 저장하기 (txt)",
                           data=(f"[나랑 닮은 종목 찾기 결과]\n닉네임: {st.session_state.nick}\n"
                                 f"유형: {code} {t['name']}\n닮은 종목: {t['stock']}\n\n왜 닮았을까: {t['why']}\n\n"
                                 f"조심할 실수: {t['caution']}\n\n환상의 짝꿍: {best_match(code)} "
                                 f"{TYPES[best_match(code)]['name']}\n"),
                           file_name=f"my_type_{code}.txt")
    with tab2:
        bm, tw = best_match(code), twin(code)
        st.markdown(f"<div class='box'><h4>💞 환상의 짝꿍 · {bm} {TYPES[bm]['emoji']} {TYPES[bm]['name']}</h4>"
                    f"{t['stock']} + <b>{TYPES[bm]['stock']}</b><br>시장 방향과 투자 형태가 반대라 "
                    f"한쪽이 흔들릴 때 다른 쪽이 받쳐줘. 분산투자의 기본 원리야.</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='box warn'><h4>👯 쌍둥이 · {tw} {TYPES[tw]['emoji']} {TYPES[tw]['name']}</h4>"
                    f"{t['stock']} + <b>{TYPES[tw]['stock']}</b><br>방향·위험·형태가 모두 같아서 같이 웃고 같이 울어. "
                    f"둘 다 들고 있으면 분산 효과가 작아.</div>", unsafe_allow_html=True)
        st.markdown("**친구와 궁합 보기**")
        friend = st.selectbox("친구의 유형을 골라줘", list(TYPES.keys()),
                              format_func=lambda c: f"{c} · {TYPES[c]['name']} ({TYPES[c]['stock']})")
        s, label, reasons = compat(code, friend)
        st.metric("궁합 점수", f"{s} / 5", label)
        for r in reasons:
            st.markdown(f"- {r}")
    with tab3:
        st.caption("유형을 누르면 자세한 설명을 볼 수 있어.")
        for c, tt in TYPES.items():
            with st.expander(f"{c} · {tt['emoji']} {tt['name']} → {tt['stock']}", expanded=(c == code)):
                st.markdown(f"{tt['why']}\n\n**변동성** {tt['vol']} · **배당** {tt['div']} · **시장과** {tt['mkt']}")
                st.markdown(f"⚠️ {tt['caution']}")

    st.divider()
    st.markdown("**💬 무엇이든 물어봐**")
    show(st.session_state.chat)

# ---------------------------------------------------------------------
# 10. 채팅 입력창 (단계에 따라 해석이 달라짐)
# ---------------------------------------------------------------------
placeholder = {"name": "닉네임을 입력해줘", "quiz": "A 또는 B를 입력하거나 버튼을 눌러줘",
               "result": "예) 궁합 COBN / 도감 / 인버스가 뭐야? / 다시"}[stage]
text = st.chat_input(placeholder)
if text:
    if stage == "name":
        nick = text.strip()[:12] or "익명"
        st.session_state.nick = nick
        say("user", nick)
        say("assistant", f"반가워, **{nick}**님! 이제 12개 질문을 시작할게. 버튼을 누르거나 A/B를 입력하면 돼.")
        st.session_state.stage = "quiz"
        ask_current()
    elif stage == "quiz":
        t2 = text.strip().upper()
        if t2 in ("A", "1", "에이"):
            answer("A")
        elif t2 in ("B", "2", "비"):
            answer("B")
        else:
            say("user", text)
            say("assistant", "지금은 **A** 또는 **B**로만 답할 수 있어. 위 질문을 다시 확인해줘 🙏")
    else:
        say("user", text)
        reply = free_chat(text)
        if reply:
            say("assistant", reply)
    st.rerun()

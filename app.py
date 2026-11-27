# =====================================================================
# 투자성향 MBTI (나랑 닮은 종목 찾기) — 투자 유형 16종 진단 챗봇 (Streamlit, 규칙 기반)
#
# 구성
#   1) 비밀번호 확인 → 2) 닉네임 → 3) 12문항 대화형 진단 (4개 축 × 3문항)
#   4) 결과: 16유형 중 하나 + 닮은 종목 + 조심할 실수 + 투자 궁합
#   5) 자유 대화: 종목명 검색(닮은 유형·나와의 궁합), 궁합 비교, 유형 도감, 투자 용어 설명 (키워드 규칙 기반)
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
import streamlit.components.v1 as components

st.set_page_config(page_title="투자성향 MBTI · 나랑 닮은 종목 찾기", page_icon="📈", layout="centered")

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
    {"axis": 0, "q": "투자할 종목을 찾을 때 주로 보는 곳은?",
     "A": ("많이 본 뉴스, 인기 종목 순위", "M"), "B": ("아무도 관심 없는 종목 분석", "C")},
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
    {"axis": 2, "q": "투자 공부를 한다면 어떤 방식이 끌려?",
     "A": ("한 회사의 사업을 깊게 파고든다", "F"), "B": ("여러 산업의 흐름을 넓게 훑어본다", "B")},
    {"axis": 2, "q": "확신이 드는 종목을 찾았어.",
     "A": ("비중을 크게 싣는다", "F"), "B": ("그래도 여러 개로 나눠 담는다", "B")},
    # 근거: N / V
    {"axis": 3, "q": "종목을 고를 때 제일 먼저 보는 건?",
     "A": ("실적, 배당, PER 같은 숫자", "N"), "B": ("CEO와 브랜드 같은 기업 이미지", "V")},
    {"axis": 3, "q": "둘 중 더 설레는 뉴스는?",
     "A": ("분기 영업이익 30% 증가", "N"), "B": ("화성에 공장을 짓겠다", "V")},
    {"axis": 3, "q": "친구에게 종목을 추천한다면?",
     "A": ("표와 숫자로 근거를 보여준다", "N"), "B": ("이 회사가 바꿀 세상을 이야기한다", "V")},
]

AXES = [("M", "C", "대세", "역발상"), ("D", "O", "수비", "공격"),
        ("F", "B", "집중", "분산"), ("N", "V", "숫자", "스토리")]

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

# ---------------------------------------------------------------------
# 2-1. 종목 성격 사전: 종목명을 입력하면 그 종목이 16유형 중 어디와 닮았는지 알려줌
#      code: 4자리 유형, kind: 분류, alias: 검색용 다른 이름, why: 그렇게 분류한 이유
#      ※ 성향을 재미있게 비유한 것이며 종목 평가·추천이 아님
# ---------------------------------------------------------------------
STOCKS = {
    # 16유형 대표 종목
    "KB금융": dict(code="MDFN", kind="국내 주식 · 은행지주", alias=("kb", "kb금융지주", "국민은행"),
                 why="꾸준한 이자 이익을 배당과 자사주로 주주에게 돌려주는 대표 금융주야."),
    "삼성전자": dict(code="MDFV", kind="국내 주식 · 반도체", alias=("삼전", "samsung"),
                 why="소액주주가 가장 많은 국민주. '반도체 1등'이라는 이야기에 모두가 기대를 거는 종목이야."),
    "SCHD": dict(code="MDBN", kind="미국 ETF · 배당성장", alias=("슈드", "미국배당etf", "미국배당다우존스"),
                 why="배당을 꾸준히 늘려온 미국 우량 기업들을 숫자 기준으로 골라 담은 ETF야."),
    "S&P500 ETF": dict(code="MDBV", kind="미국 ETF · 지수", alias=("s&p500", "s&p", "sp500", "spy", "voo", "ivv", "에스앤피"),
                       why="미국 대형주 500개를 통째로 담아 '미국은 결국 오른다'는 이야기에 베팅하는 상품이야."),
    "엔비디아": dict(code="MOFN", kind="미국 주식 · AI 반도체", alias=("nvidia", "nvda"),
                 why="AI 반도체 수요로 폭발한 실적이 주가를 끌어올린 시장 주도주야."),
    "테슬라": dict(code="MOFV", kind="미국 주식 · 전기차", alias=("tesla", "tsla"),
                why="전기차·자율주행·로봇이라는 비전으로 움직이는 대표 스토리 주식이야."),
    "KODEX 레버리지": dict(code="MOBN", kind="국내 ETF · 코스피200 2배", alias=("코덱스레버리지", "코스피레버리지"),
                       why="코스피200 하루 수익률의 2배를 따라가, 오를 거라 계산되면 상승을 두 배로 먹으려는 상품이야."),
    "2차전지 테마 ETF": dict(code="MOBV", kind="국내 ETF · 테마", alias=("2차전지", "이차전지"),
                        why="전기차 시대라는 뜨거운 이야기에 관련 종목을 바구니째 올라타는 상품이야."),
    "버크셔 해서웨이": dict(code="CDFN", kind="미국 주식 · 지주회사", alias=("버크셔", "berkshire", "brk", "워런버핏", "버핏"),
                     why="남들이 두려워할 때 숫자로 저평가를 찾아 사는 워런 버핏의 회사야."),
    "한국전력": dict(code="CDFV", kind="국내 주식 · 공기업", alias=("한전", "kepco"),
                 why="전기요금 정상화라는 '언젠가'의 이야기에 따라 움직이는 공기업이야."),
    "TLT": dict(code="CDBN", kind="미국 ETF · 장기국채", alias=("미국장기채", "장기국채", "미국채"),
                why="금리가 내려가면 가격이 오르는 구조라, 위기 때 금리를 계산하는 투자자가 찾는 상품이야."),
    "금 ETF": dict(code="CDBV", kind="원자재 ETF · 금", alias=("금현물", "골드", "gld", "iau"),
                  why="'위기엔 금'이라는 수천 년 된 이야기를 믿고 자산을 지키는 상품이야."),
    "카카오": dict(code="COFN", kind="국내 주식 · 플랫폼", alias=("kakao",),
                why="고점 대비 크게 떨어진 국민 성장주라, 숫자로 반등 가능성을 따져보는 투자자가 많아."),
    "알리바바": dict(code="COFV", kind="미국 상장 중국 주식 · 플랫폼", alias=("alibaba", "baba"),
                 why="규제로 급락했던 중국 대표 플랫폼. '몰락한 왕의 귀환'에 거는 종목이야."),
    "KODEX 인버스": dict(code="COBN", kind="국내 ETF · 코스피200 -1배", alias=("코덱스인버스", "코스피인버스"),
                      why="코스피200이 떨어지면 수익이 나는, 남들과 반대로 가는 상품이야."),
    "KODEX 200선물인버스2X": dict(code="COBV", kind="국내 ETF · 코스피200 -2배", alias=("인버스2x", "선물인버스2x", "코덱스곱버스"),
                              why="곧 폭락이 온다는 시나리오에 두 배로 베팅하는 일명 '곱버스'야."),
    # 많이 찾는 인기 종목
    "SK하이닉스": dict(code="MOFN", kind="국내 주식 · 메모리 반도체", alias=("하이닉스", "hynix"),
                    why="AI 서버용 고대역폭 메모리(HBM) 실적으로 주목받은 반도체 주도주야."),
    "애플": dict(code="MDFV", kind="미국 주식 · IT 기기", alias=("apple", "aapl", "아이폰"),
               why="전 세계가 아는 브랜드와 충성 고객이라는 이야기를 가진 초대형 우량주야."),
    "마이크로소프트": dict(code="MDFN", kind="미국 주식 · 소프트웨어·클라우드", alias=("microsoft", "msft", "마소"),
                    why="클라우드와 소프트웨어 구독으로 꾸준히 버는, 숫자가 탄탄한 대형주야."),
    "구글": dict(code="MDFN", kind="미국 주식 · 검색·광고", alias=("알파벳", "google", "googl", "alphabet", "유튜브"),
               why="검색 광고와 유튜브로 매년 막대한 현금을 버는, 실적이 탄탄한 빅테크야."),
    "아마존": dict(code="MOFN", kind="미국 주식 · 이커머스·클라우드", alias=("amazon", "amzn"),
                why="온라인 쇼핑과 클라우드(AWS)라는 두 엔진의 성장 실적으로 평가받는 빅테크야."),
    "메타": dict(code="MOFN", kind="미국 주식 · SNS·광고", alias=("meta", "페이스북", "인스타그램"),
               why="광고 실적 회복과 비용 절감을 숫자로 증명하며 반등했던 빅테크야."),
    "팔란티어": dict(code="MOFV", kind="미국 주식 · AI 소프트웨어", alias=("palantir", "pltr"),
                 why="AI·데이터 분석이라는 비전과 열성 팬덤으로 크게 출렁이는 종목이야."),
    "인텔": dict(code="COFV", kind="미국 주식 · 반도체", alias=("intel", "intc"),
               why="한때 반도체의 왕이었지만 경쟁에서 밀린 뒤 '부활'을 기대하는 투자자들이 지켜보는 종목이야."),
    "코카콜라": dict(code="MDFN", kind="미국 주식 · 음료", alias=("cocacola", "coca-cola", "코크"),
                 why="경기가 나빠도 사람들은 콜라를 마시지. 오랫동안 배당을 늘려온 대표 방어주야."),
    "리얼티인컴": dict(code="MDFN", kind="미국 주식 · 리츠(월배당)", alias=("리얼티", "월배당리츠"),
                  why="'월배당 회사'라는 별명처럼 임대료 수입으로 매달 배당을 주는 부동산 리츠야."),
    "현대차": dict(code="CDFN", kind="국내 주식 · 자동차", alias=("현대자동차", "hyundai"),
                why="이익에 비해 주가가 낮다는 평가를 자주 받아, 숫자로 저평가를 찾는 투자자가 주목하는 종목이야."),
    "네이버": dict(code="COFN", kind="국내 주식 · 플랫폼", alias=("naver",),
                why="고점 대비 많이 떨어진 국내 대표 성장주라, 실적 대비 반등 여부를 따져보는 투자자가 많아."),
    "카카오뱅크": dict(code="COFV", kind="국내 주식 · 인터넷은행", alias=("카뱅",),
                  why="상장 직후 큰 기대를 받았다가 내려온 뒤, 인터넷은행의 성장 이야기에 다시 거는 종목이야."),
    "LG에너지솔루션": dict(code="MOFV", kind="국내 주식 · 2차전지", alias=("엘지엔솔", "lg엔솔", "엔솔"),
                       why="전기차 시대라는 큰 이야기를 대표하는 국내 2차전지 대장주야."),
    "에코프로": dict(code="MOFV", kind="국내 주식 · 2차전지 소재", alias=("ecopro",),
                 why="2차전지 열풍 때 개인투자자가 몰리며 크게 출렁였던 대표 테마주야."),
    "셀트리온": dict(code="MOFV", kind="국내 주식 · 바이오", alias=("celltrion",),
                 why="바이오시밀러로 세계 시장을 넓힌다는 이야기와 개인투자자의 큰 관심을 받는 바이오 대표주야."),
    "한화에어로스페이스": dict(code="MOFN", kind="국내 주식 · 방산", alias=("한화에어로",),
                       why="해외 방산 수출 실적이 숫자로 증명되며 주목받은 종목이야."),
    "KODEX 200": dict(code="MDBN", kind="국내 ETF · 코스피200", alias=("코스피200", "코덱스200", "코스피etf"),
                      why="국내 대표 기업 200개를 묶어 한국 시장 전체를 사는 가장 기본적인 ETF야."),
    "나스닥100 ETF": dict(code="MOBV", kind="미국 ETF · 기술주 지수", alias=("나스닥", "qqq", "qqqm", "나스닥100"),
                       why="미국 대표 기술주 100개를 담아 '기술이 세상을 바꾼다'는 이야기에 바구니째 타는 상품이야."),
    "TQQQ": dict(code="MOBN", kind="미국 ETF · 나스닥100 3배", alias=(),
                 why="나스닥100 하루 수익률의 3배를 따라가는 고위험 레버리지 ETF야."),
    "JEPI": dict(code="MDBN", kind="미국 ETF · 커버드콜", alias=("커버드콜",),
                 why="주가 상승 일부를 포기하는 대신 매달 꾸준한 분배금을 받도록 설계된 ETF야."),
    "비트코인": dict(code="MOFV", kind="가상자산 (주식 아님)", alias=("bitcoin", "btc"),
                 why="'디지털 금'이라는 이야기와 아주 큰 변동성으로 움직이는 대표 가상자산이야."),
}

# 축 글자별로 종목 성격을 풀어서 설명
AXIS_DESC = {
    "M": "시장의 인기 흐름과 함께 움직이는 **대세형**",
    "C": "시장이 외면하거나 반대로 갈 때 빛나는 **역발상형**",
    "D": "덜 출렁이고 지키는 힘이 있는 **수비형**",
    "O": "크게 오르내리는 **공격형**",
    "F": "한 회사에 모든 게 걸린 **집중형** (단일 종목)",
    "B": "여러 자산을 묶은 **분산형** (바구니 상품)",
    "N": "실적·배당·금리 같은 **숫자**로 평가받는 편",
    "V": "비전과 **스토리**로 기대를 모으는 편",
}

# 검색용 별칭 목록: (정규화된 별칭, 종목명), 긴 별칭부터 검사해서 '카카오뱅크'가 '카카오'로 잘못 잡히지 않게 함
ALIASES = sorted(
    {(re.sub(r"\s", "", a.lower()), name)
     for name, s in STOCKS.items() for a in (name, *s["alias"])},
    key=lambda x: -len(x[0]))


def find_stock(text):
    """문장 속에서 사전에 있는 종목명을 찾아 돌려준다 (없으면 None)."""
    low = text.lower()
    flat = re.sub(r"\s", "", low)
    for alias, name in ALIASES:
        if re.fullmatch(r"[a-z0-9&\-]+", alias):
            # 영문 티커는 단어 경계로만 인식 (예: 'spy'가 다른 단어 속에서 잡히지 않게)
            pat = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
            if re.search(pat, low) or re.search(pat, flat):
                return name
        elif alias in flat:
            return name
    return None


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
/* ---- 토스 느낌: 회색 배경 + 흰 카드, 토스 블루, Pretendard, 큼직한 굵은 글씨 ---- */
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
html, body, .stApp, p, div, li, label, input, textarea, button, h1, h2, h3, h4 {
  font-family: 'Pretendard Variable', Pretendard, -apple-system, 'Apple SD Gothic Neo', sans-serif;
  letter-spacing: -0.01em;
}
[data-testid="stDecoration"], [data-testid="stAppDeployButton"] {display:none;}
.block-container {padding-top:2.2rem; padding-bottom:6rem; max-width:680px;}
h1 {font-size:26px !important; font-weight:800 !important; letter-spacing:-0.03em; color:#191F28;}
p, li {color:#333D4B; line-height:1.6;}

/* 버튼: 꽉 찬 너비, 큼직하고 둥글게 */
.stButton > button, .stDownloadButton > button {
  border:none; border-radius:16px; min-height:54px; font-size:16px; font-weight:600;
  background:#FFFFFF; color:#191F28; box-shadow:none; transition:all .15s ease;}
.stButton > button:hover, .stDownloadButton > button:hover {background:#E8F3FF; color:#1B64DA;}
.stButton > button:active {transform:scale(.98);}
.stButton > button p, .stDownloadButton > button p {color:inherit; font-size:16px; font-weight:600;}
.stButton > button[kind="primary"] {background:#3182F6; color:#fff;}
.stButton > button[kind="primary"]:hover {background:#1B64DA; color:#fff;}
.st-key-choice .stButton > button {justify-content:flex-start; text-align:left; padding:0 20px;
  border:1.5px solid transparent;}
.st-key-choice .stButton > button:hover {border-color:#3182F6;}
.st-key-choice .stButton > button > div {justify-content:flex-start; width:100%;}
.st-key-choice .stButton > button p {text-align:left;}
.st-key-back .stButton > button {background:transparent; min-height:40px; padding:0 6px; color:#6B7684;}
.st-key-back .stButton > button p {font-size:14px; font-weight:500;}
.st-key-back .stButton > button:hover {background:#E5E8EB; color:#191F28;}

/* 입력창 */
[data-testid="stTextInput"] input {font-size:16px; padding:14px 16px;}
[data-testid="stTextInput"] div[data-baseweb="input"], [data-baseweb="select"] > div {border:none; border-radius:14px;}
[data-testid="stChatInput"] {border-radius:20px; border:none; box-shadow:0 4px 18px rgba(0,27,55,.08);}

/* 탭: 토스식 세그먼트 컨트롤 */
[data-testid="stTabs"] [role="tablist"] {background:#E5E8EB; border-radius:14px; padding:4px; gap:2px;
  border:none; box-shadow:none;}
[data-testid="stTabs"] [role="tablist"]::after, [data-testid="stTabs"] [role="tablist"]::before {display:none;}
[data-testid="stTab"] {flex:1; display:flex; justify-content:center; border-radius:11px; padding:9px 6px;
  color:#6B7684; border:none; cursor:pointer;}
[data-testid="stTab"] p {font-size:14px; font-weight:600; color:inherit; margin:0; white-space:nowrap;}
[data-testid="stTab"][aria-selected="true"] {background:#FFFFFF; color:#191F28; box-shadow:0 1px 4px rgba(0,0,0,.06);}
[data-testid="stTab"] > div[data-rac] {display:none;}

/* 채팅 말풍선, 접는 상자, 지표 */
[data-testid="stChatMessage"] {background:#FFFFFF; border-radius:20px; padding:14px 16px; margin-bottom:8px;}
/* 내가 보낸 말은 오른쪽 파란 말풍선 (메신저처럼) */
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
  flex-direction:row-reverse; background:#3182F6; width:fit-content; max-width:85%; margin-left:auto;
  padding:10px 16px;}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) > div[aria-hidden="true"] {display:none;}
[aria-label="Chat message from user"] p {color:#FFFFFF; margin:0;}
[aria-label="Chat message from user"] .stMarkdown div {margin-bottom:0 !important;}
[data-testid="stExpander"] details {background:#FFFFFF; border:none; border-radius:16px;}
[data-testid="stMetric"] {background:#FFFFFF; border-radius:20px; padding:18px 20px;}
[data-testid="stMetricValue"] {font-weight:800; color:#3182F6;}
[data-testid="stSidebar"] {border-right:none;}

/* 직접 만든 카드들 */
.card {border-radius:24px; padding:26px 24px; margin:10px 0 12px 0; background:#3182F6; color:#fff;}
.card .code {font-size:14px; font-weight:600; letter-spacing:3px; opacity:.8;}
.card .name {font-size:28px; font-weight:800; margin:6px 0 2px 0; letter-spacing:-0.03em; line-height:1.3;}
.card .stock {font-size:16px; margin-top:12px; opacity:.95;}
.card .stock b {background:#fff; color:#1B64DA; padding:4px 12px; border-radius:10px; font-weight:700;}
.chips {margin:4px 0 8px 0; font-size:13px; color:#6B7684;}
.chips span {display:inline-block; background:#FFFFFF; color:#4E5968; border-radius:999px;
             padding:6px 12px; margin:3px 6px 3px 0; font-size:13px; font-weight:600;}
.box {border-radius:20px; padding:20px 22px; margin:10px 0; background:#FFFFFF; color:#4E5968; line-height:1.65;}
.box h4 {margin:0 0 8px 0; padding:0; font-size:17px; font-weight:700; color:#191F28;}
.box.warn h4 {color:#F04452;}
.box b {color:#191F28;}
.section {font-size:19px; font-weight:700; color:#191F28; margin:22px 0 8px 2px; letter-spacing:-0.02em;}
.bars {background:#FFFFFF; border-radius:20px; padding:12px 22px;}
.bar {display:flex; align-items:center; gap:10px; margin:12px 0; font-size:14px; color:#4E5968;}
.bar .track {flex:1; height:8px; background:#E5E8EB; border-radius:999px; overflow:hidden;}
.bar .fill {height:100%; background:#3182F6; border-radius:999px;}
.bar .lab {width:60px; text-align:center; font-weight:600;}
.bar .lab.on {color:#3182F6; font-weight:800;}
.small {font-size:13px; opacity:.75;}
.stMarkdown code {background:#E8F3FF; color:#1B64DA; border-radius:6px; padding:1px 6px; font-weight:600;
  font-family:inherit; font-size:.92em;}
.hero {padding:28px 4px 8px 4px;}
.hero .emoji {font-size:52px;}
.hero h2 {font-size:28px; font-weight:800; line-height:1.35; color:#191F28; margin:14px 0 10px 0; letter-spacing:-0.03em;}
.hero p {color:#6B7684; font-size:16px; margin:0;}
.hero h2 {margin-bottom:4px;}
.subtitle {font-size:17px; font-weight:700; color:#3182F6; letter-spacing:-0.02em; margin-bottom:10px;}
.qhead {font-size:14px; font-weight:700; color:#3182F6; margin:14px 0 2px 2px;}
.qtext {font-size:22px; font-weight:800; color:#191F28; line-height:1.4; margin:2px 0 14px 2px; letter-spacing:-0.03em;}
</style>
""", unsafe_allow_html=True)


def section(title):
    st.markdown(f"<div class='section'>{title}</div>", unsafe_allow_html=True)


def axis_bars_html(answers):
    counts = score_axes(answers)
    rows = []
    for i, (a, b, an, bn) in enumerate(AXES):
        pa = round(counts[i] / 3 * 100)
        ca, cb = ("lab on", "lab") if pa >= 50 else ("lab", "lab on")
        rows.append(f"<div class='bar'><div class='{ca}'>{an} {a}</div>"
                    f"<div class='track'><div class='fill' style='width:{pa}%'></div></div>"
                    f"<div class='{cb}'>{bn} {b}</div></div>")
    return "<div class='bars'>" + "".join(rows) + "</div>"


def type_card_html(code):
    t = TYPES[code]
    return (f"<div class='card'><div class='code'>{code}</div>"
            f"<div class='name'>{t['emoji']} {t['name']}</div>"
            f"<div class='stock'>나와 닮은 종목 <b>{t['stock']}</b></div>"
            f"<div class='small' style='margin-top:6px'>{t['kind']}</div></div>"
            f"<div class='chips'><span>📊 변동성 {t['vol']}</span><span>💰 배당 {t['div']}</span>"
            f"<span>🧭 시장과 {t['mkt']}</span></div>")


def stock_card_html(name):
    s = STOCKS[name]
    t = TYPES[s["code"]]
    return (f"<div class='card'><div class='small' style='opacity:.85'>{s['kind']}</div>"
            f"<div class='name'>{name}</div>"
            f"<div class='stock'>닮은 유형 <b>{s['code']} · {t['emoji']} {t['name']}</b></div></div>")


def same_type_stocks(name):
    code = STOCKS[name]["code"]
    return [n for n, s in STOCKS.items() if s["code"] == code and n != name]


def describe_stock(name, my_code):
    """채팅용: 종목의 성격 유형 + 축별 풀이 + 나와의 궁합"""
    s = STOCKS[name]
    code = s["code"]
    t = TYPES[code]
    lines = [f"🔎 **{name}** ({s['kind']})는 `{code}` · {t['emoji']} **{t['name']}** 유형과 닮았어!\n",
             s["why"], ""]
    lines += [f"- {c} : {AXIS_DESC[c]}" for c in code]
    if code == my_code:
        lines.append(f"\n🪞 너랑 **완전히 같은 유형**이야! 성격이 똑같아서 끌리겠지만, "
                     f"같은 유형끼리만 모으면 분산 효과가 작다는 것도 기억해.")
    else:
        sc, label, reasons = compat(my_code, code)
        lines.append(f"\n💘 너(`{my_code}`)와 이 종목의 궁합 **{sc} / 5** · {label}")
        lines += [f"- {r}" for r in reasons]
    lines.append("\n※ 성격을 비유한 것일 뿐 매수·매도 추천이 아니야.")
    return "\n".join(lines)


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
    st.session_state.marks = []              # 답할 때마다의 대화 길이 (이전 질문으로 되돌리기용)
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
    # 되돌리기용: 이 답을 하기 직전의 대화 길이를 기억해둠
    st.session_state.setdefault("marks", []).append(len(st.session_state.messages))
    say("user", f"{choice}) {q[choice][0]}")
    st.session_state.answers.append(q[choice][1])
    st.session_state.qi += 1
    if st.session_state.qi < len(QUESTIONS):
        ask_current()
    else:
        code = type_code(st.session_state.answers)
        st.session_state.code = code
        t = TYPES[code]
        st.session_state.stage = "result"
        st.session_state.just_done = True    # 결과 화면을 처음 그릴 때 맨 위로 스크롤하기 위한 표시
        say("assistant", f"🎉 **{st.session_state.nick}님의 투자 유형은 `{code}` · {t['emoji']} {t['name']}!** "
                         f"너와 가장 닮은 종목은 **{t['stock']}**이야.\n\n"
                         f"궁금한 건 자유롭게 물어봐. 예) `테슬라 어때?`, `궁합 COBN`, `도감`, `인버스가 뭐야?`, `다시`")


def go_back():
    """직전 질문으로 돌아가기: 마지막 답과 그 뒤에 쌓인 대화를 지운다."""
    marks = st.session_state.get("marks", [])
    if not marks or st.session_state.qi == 0:
        return
    st.session_state.messages = st.session_state.messages[:marks.pop()]
    st.session_state.answers.pop()
    st.session_state.qi -= 1


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
    stock = find_stock(raw)
    if stock:
        return describe_stock(stock, st.session_state.code)
    for keys, ans in FAQ.items():
        if any(k in low for k in keys):
            return "💡 " + ans
    if any(k in raw for k in ("어때", "무슨 유형", "어떤 유형", "닮았", "성격")):
        examples = ", ".join(list(STOCKS)[16:26])
        return ("그 종목은 아직 내 사전에 없어 😅 지금은 이런 종목들을 알고 있어:\n\n"
                f"{examples} 등 {len(STOCKS)}개\n\n전체 목록은 위의 **🔎 종목 궁합** 탭에서 검색해봐!")
    if "종목" in raw or "추천" in raw:
        c = st.session_state.code
        return (f"너와 닮은 종목은 **{TYPES[c]['stock']}**이야. 다만 이건 성향이 닮았다는 뜻이지 매수 추천이 아니야. "
                f"투자 결정은 꼭 스스로 따져보고 해줘 🙏")
    return ("음, 그건 아직 내가 모르는 질문이야 😅 이렇게 물어봐 줄래?\n\n"
            "- `애플`, `삼성전자`, `비트코인` → 종목 이름으로 닮은 유형·나와의 궁합\n"
            "- `궁합 COBN` → 친구 유형과 궁합\n- `도감` → 16유형 전체 보기\n- `MDFV` → 유형 설명\n"
            "- `인버스`, `레버리지`, `ETF`, `배당`, `분산투자`, `손실회피` → 용어 설명\n- `다시` → 처음부터")


# ---------------------------------------------------------------------
# 6. 비밀번호 화면
# ---------------------------------------------------------------------
if not st.session_state.authed:
    st.markdown("<div class='hero'><div class='emoji'>📈</div>"
                "<h2>투자성향 MBTI</h2>"
                "<div class='subtitle'>나랑 닮은 종목 찾기</div>"
                "<p>12개 질문으로 16가지 투자 유형 중 나는 어디인지 알아봐요</p></div>",
                unsafe_allow_html=True)
    st.markdown("<div class='chips' style='margin:14px 0 22px 2px'><span>🧭 투자 성향 진단</span>"
                "<span>🔎 닮은 종목 찾기</span><span>💘 투자 궁합</span></div>", unsafe_allow_html=True)
    pw = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력해주세요",
                       label_visibility="collapsed")
    if st.button("시작하기", type="primary", use_container_width=True):
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
    st.header("📈 투자성향 MBTI")
    done = len(st.session_state.answers)
    st.progress(done / len(QUESTIONS), text=f"진행률 {done} / {len(QUESTIONS)}")
    if st.button("🔄 처음부터 다시", use_container_width=True):
        reset()
        st.rerun()
    st.markdown("**4개 축**\n- 방향: 대세 M / 역발상 C\n- 위험: 수비 D / 공격 O\n"
                "- 형태: 집중 F / 분산 B\n- 근거: 숫자 N / 스토리 V")
    st.caption("※ 이 서비스는 투자 성향을 재미있게 알아보는 교육용 콘텐츠이며, 특정 종목의 매수·매도를 권유하지 않습니다.")

st.title("📈 투자성향 MBTI")
st.markdown("<div class='subtitle' style='margin:-14px 0 16px 2px'>나랑 닮은 종목 찾기</div>",
            unsafe_allow_html=True)

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
elif st.session_state.stage == "quiz":
    # 지금 질문은 아래 큰 카드로 보여주므로 대화 기록에서는 숨김
    cur = f"**Q{st.session_state.qi + 1}."
    show([m for m in st.session_state.messages if not m["content"].startswith(cur)])
else:
    show(st.session_state.messages)

# ---------------------------------------------------------------------
# 9. 단계별 입력 처리
# ---------------------------------------------------------------------
stage = st.session_state.stage

if stage == "quiz":
    q = QUESTIONS[st.session_state.qi]
    qi = st.session_state.qi
    st.progress((qi + 1) / len(QUESTIONS))
    with st.container(key="choice"):
        st.markdown(f"<div class='qhead'>{qi + 1} / {len(QUESTIONS)}</div>"
                    f"<div class='qtext'>{q['q']}</div>", unsafe_allow_html=True)
        st.button(f"A)  {q['A'][0]}", key=f"a{qi}", use_container_width=True,
                  on_click=answer, args=("A",))
        st.button(f"B)  {q['B'][0]}", key=f"b{qi}", use_container_width=True,
                  on_click=answer, args=("B",))
    if qi > 0:
        with st.container(key="back"):
            st.button("← 이전 질문 다시 고르기", key=f"back{qi}", on_click=go_back)

if stage == "result":
    code = st.session_state.code
    t = TYPES[code]
    tab1, tab4, tab2, tab3 = st.tabs(["🧾 내 결과", "🔎 종목 궁합", "💘 투자 궁합", "📚 유형 도감"])
    with tab4:
        st.caption("궁금한 종목을 검색하면 그 종목이 16유형 중 누구와 닮았는지, 그리고 나와 궁합이 맞는지 알려줘.")
        pick = st.selectbox("종목 검색", list(STOCKS), index=None,
                            placeholder="종목 이름을 입력해봐 (예: 애플, 삼성전자, 비트코인)",
                            format_func=lambda n: f"{n} · {STOCKS[n]['kind']}")
        if pick:
            ps = STOCKS[pick]
            st.markdown(stock_card_html(pick), unsafe_allow_html=True)
            st.markdown(f"<div class='box'><h4>🔍 왜 이 유형일까?</h4>{ps['why']}</div>", unsafe_allow_html=True)
            section("종목 성격 풀이")
            for ch in ps["code"]:
                st.markdown(f"- `{ch}` {AXIS_DESC[ch]}")
            if ps["code"] == code:
                st.success(f"🪞 {st.session_state.nick}님과 완전히 같은 유형이야! "
                           f"끌리는 이유가 있지만, 같은 성격끼리만 모으면 분산 효과가 작아.")
            else:
                s_, label_, reasons_ = compat(code, ps["code"])
                st.metric(f"{st.session_state.nick}님({code})과의 궁합", f"{s_} / 5", label_)
                for r in reasons_:
                    st.markdown(f"- {r}")
            others = same_type_stocks(pick)
            if others:
                st.markdown("<div class='chips'>같은 유형 종목 " +
                            "".join(f"<span>{n}</span>" for n in others) + "</div>",
                            unsafe_allow_html=True)
            st.caption("※ 종목의 성격을 비유한 것일 뿐, 매수·매도 추천이 아닙니다.")
        else:
            st.markdown(f"지금 **{len(STOCKS)}개** 종목을 알고 있어. 채팅창에 `테슬라 어때?`처럼 물어봐도 돼!")
    with tab1:
        st.markdown(type_card_html(code), unsafe_allow_html=True)
        st.markdown(f"<div class='box'><h4>🔍 왜 닮았을까?</h4>{t['why']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='box warn'><h4>⚠️ 이 유형이 조심할 실수</h4>{t['caution']}</div>",
                    unsafe_allow_html=True)
        section("나의 성향 그래프")
        st.markdown(axis_bars_html(st.session_state.answers), unsafe_allow_html=True)
        st.download_button("📥 결과 저장하기 (txt)",
                           data=(f"[투자성향 MBTI · 나랑 닮은 종목 찾기 결과]\n닉네임: {st.session_state.nick}\n"
                                 f"유형: {code} {t['name']}\n닮은 종목: {t['stock']}\n\n왜 닮았을까: {t['why']}\n\n"
                                 f"조심할 실수: {t['caution']}\n\n환상의 짝꿍: {best_match(code)} "
                                 f"{TYPES[best_match(code)]['name']}\n"),
                           file_name=f"my_type_{code}.txt", use_container_width=True)
    with tab2:
        bm, tw = best_match(code), twin(code)
        st.markdown(f"<div class='box'><h4>💞 환상의 짝꿍 · {bm} {TYPES[bm]['emoji']} {TYPES[bm]['name']}</h4>"
                    f"{t['stock']} + <b>{TYPES[bm]['stock']}</b><br>시장 방향과 투자 형태가 반대라 "
                    f"한쪽이 흔들릴 때 다른 쪽이 받쳐줘. 분산투자의 기본 원리야.</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='box warn'><h4>👯 쌍둥이 · {tw} {TYPES[tw]['emoji']} {TYPES[tw]['name']}</h4>"
                    f"{t['stock']} + <b>{TYPES[tw]['stock']}</b><br>방향·위험·형태가 모두 같아서 같이 웃고 같이 울어. "
                    f"둘 다 들고 있으면 분산 효과가 작아.</div>", unsafe_allow_html=True)
        section("친구와 궁합 보기")
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

    section("💬 무엇이든 물어봐")

    if st.session_state.pop("just_done", False):
        # 진단이 막 끝났을 때 한 번만: 화면을 맨 위(결과 카드)로 올리고 완료 알림
        st.toast(f"🎉 {st.session_state.nick}님의 결과가 나왔어요!")
        components.html("""
<script>
// 채팅 앱은 <main>(stAppScrollToBottomContainer)이 스크롤되고, 화면이 그려지는 동안
// 자동으로 맨 아래로 다시 붙기 때문에 약 2초간 맨 위를 유지한다 (사용자가 스크롤하면 즉시 중단).
const doc = window.parent.document;
let stop = false;
['wheel', 'touchstart', 'keydown'].forEach(ev =>
  doc.addEventListener(ev, () => { stop = true; }, {once: true, passive: true}));
const start = Date.now();
const timer = setInterval(() => {
  if (stop || Date.now() - start > 2000) { clearInterval(timer); return; }
  window.parent.scrollTo(0, 0);
  doc.querySelectorAll('main, section').forEach(el => { if (el.scrollTop > 0) el.scrollTop = 0; });
}, 100);
</script>""", height=0)
    show(st.session_state.chat)

# ---------------------------------------------------------------------
# 10. 채팅 입력창 (단계에 따라 해석이 달라짐)
# ---------------------------------------------------------------------
placeholder = {"name": "닉네임을 입력해줘", "quiz": "A 또는 B를 입력하거나 버튼을 눌러줘",
               "result": "예) 애플 어때? / 궁합 COBN / 도감 / 인버스가 뭐야? / 다시"}[stage]
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
        elif t2 in ("이전", "뒤로", "취소", "BACK") and st.session_state.qi > 0:
            go_back()
        else:
            say("user", text)
            say("assistant", "지금은 **A** 또는 **B**로만 답할 수 있어. 위 질문을 다시 확인해줘 🙏\n\n"
                             "앞 질문을 다시 고르고 싶으면 `이전`이라고 입력해줘.")
    else:
        say("user", text)
        reply = free_chat(text)
        if reply:
            say("assistant", reply)
    st.rerun()

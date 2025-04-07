#2025/04/07
import streamlit as st
import pandas as pd
import json
import re
from gpt_api import ask_gpt
from prompt_utils import make_category_extraction_prompt

# --- データ読み込み ---
scores_df = pd.read_csv("./input/cafe_category_scores.csv")
reviews_df = pd.read_csv("./input/cafe_reviews_analysis_v3_part_full.csv")

valid_categories = scores_df.columns[1:].tolist()

category_mapping = {
    # 明確な変換
    "静かさ": "雰囲気", "アクセス": "ロケーション", "おしゃれさ": "雰囲気",
    "きれいさ": "清潔感", "空いてる": "混雑", "空間": "座席",

    # 口コミ実データより拡張
    "味": "ごはん",
    "食事": "ごはん",
    "料理": "ごはん",
    "品質": "ごはん",
    "感情": "その他",
    "感想": "その他",
    "満足度": "その他",
    "パフォーマンス": "サービス",
    "演出": "雰囲気",
    "デザイン": "雰囲気",
    "インテリア": "雰囲気",
    "環境": "雰囲気",
    "見た目": "雰囲気",
    "店": "ロケーション",
    "店舗": "ロケーション",
    "メニュー": "その他",
    "商品": "その他",
    "品揃え": "その他",
    "評判": "客",
    "心理状態": "その他",
    "便利さ": "ロケーション",
    "イベント": "サービス",
    "カスタマイズ": "サービス",
    "茶": "紅茶",
    "ソース": "ごはん",
    "スープ": "ごはん"
}


# --- Streamlit 初期化 ---
st.set_page_config(page_title="カフェ推薦アシスタント", page_icon="☕")
st.title("☕ カフェ推薦アシスタント")

if "step" not in st.session_state:
    st.session_state.step = 1
    st.session_state.weights = {}
    st.session_state.history = []

def extract_categories(user_text):
    prompt = make_category_extraction_prompt(user_text)
    category_weights = ask_gpt(prompt)
    st.write("🔍 GPTの返答:", category_weights)
    json_text = re.search(r"\{.*\}", category_weights, re.DOTALL)
    if not json_text:
        raise ValueError("JSON形式の出力が見つかりませんでした。")
    raw_weights = json.loads(json_text.group())
    mapped = {}
    for k, v in raw_weights.items():
        mapped_key = category_mapping.get(k, k)
        if mapped_key in valid_categories:
            mapped[mapped_key] = v
    return mapped

# --- ユーザー入力ステップ ---
if st.session_state.step == 1:
    user_input = st.text_input("どんなカフェが理想ですか？（例：駅から近くてスイーツが美味しいカフェ）")
    if user_input:
        try:
            extracted = extract_categories(user_input)
            st.session_state.weights.update(extracted)
            st.session_state.history.append(user_input)
            st.session_state.step += 1
            st.rerun()
        except Exception as e:
            st.error("カテゴリ抽出に失敗しました。もう一度お試しください。")
            st.write("エラー内容:", e)

elif st.session_state.step == 2:
    followup = st.text_input("他に気になることはありますか？（例：静かな場所がいい、価格も気になる）")
    if followup:
        try:
            extracted = extract_categories(followup)
            st.session_state.weights.update(extracted)
            st.session_state.history.append(followup)
            st.session_state.step += 1
            st.rerun()
        except Exception as e:
            st.error("解析に失敗しました。もう一度お試しください。")
            st.write("エラー内容:", e)

elif st.session_state.step == 3:
    final = st.text_input("さらに重視したいことがあれば教えてください。（例：清潔感があると嬉しい）")
    if final:
        try:
            extracted = extract_categories(final)
            st.session_state.weights.update(extracted)
            st.session_state.history.append(final)
            st.session_state.step += 1
            st.rerun()
        except Exception as e:
            st.error("解析に失敗しました。もう一度お試しください。")
            st.write("エラー内容:", e)

# --- 最終推薦 ---
elif st.session_state.step == 4:
    weights = st.session_state.weights

    def weighted_score(row):
        return sum(
            row[c] * weights[c] for c in weights if c in row and not pd.isna(row[c])
        )

    scores_df["score"] = scores_df.apply(weighted_score, axis=1)
    top4 = scores_df.sort_values("score", ascending=False).head(4)

    st.success("✅ あなたの希望に合うカフェを提案します！")

    for i in range(4):
        row = top4.iloc[i]
        cafe_name = row["カフェ名"]
        st.subheader(f"☕ {cafe_name}（スコア: {row['score']:.2f}）")

        # スコア上位カテゴリを表示（上位5カテゴリ）
        top_categories = (
            row[weights.keys()]
            .sort_values(ascending=False)
            .dropna()
            .head(5)
        )
        st.markdown("📊 **カテゴリースコア**")
        st.dataframe(top_categories.rename("スコア"))

        # 関連口コミの表示（重複除去あり）
        st.markdown("🗣 **実際の口コミ**")
        related_reviews = reviews_df[
            (reviews_df["カフェ名"] == cafe_name) &
            (reviews_df["カテゴリ"].isin(weights.keys())) &
            (reviews_df["スコア"] >= 0.5)
        ].dropna().drop_duplicates(subset="口コミ").sort_values("スコア", ascending=False).head(3)

        if related_reviews.empty:
            st.write("口コミが見つかりませんでした。")
        else:
            for _, review_row in related_reviews.iterrows():
                cat = review_row["カテゴリ"]
                txt = review_row["口コミ"]
                st.markdown(f"- 💬 **{cat}**: {txt}")


    if st.button("🔄 最初からやり直す"):
        st.session_state.clear()
        st.rerun()

import streamlit as st
import pymysql
import pandas as pd

# --- Configuration ---
responses_table = "responses_1"
question_mapping_table = "question_mapping_1"

def connect_to_db():
    try:
        connection.close()  # Close any existing connection
    except:
        pass  # Ignore error if no connection exists

    connection = pymysql.connect(
        host= 'myinstancerestored.c5isyysu810z.us-east-2.rds.amazonaws.com',
        user='admin',
        password='Omega1745!',
        database='study_data',
        port=3306,
    )
    return connection
connection = connect_to_db()

# --- Fetch Q4 answer_texts for dropdown ---
q_answers_query = f"""
SELECT DISTINCT q_question_code, answer_text
FROM {question_mapping_table}
ORDER BY q_question_code, answer_text
"""
q_answers_df = pd.read_sql(q_answers_query, connection)

# Make dropdown grouped by q_question_code
q_answers_df['display'] = q_answers_df['q_question_code'] + " - " + q_answers_df['answer_text']
q_answers = q_answers_df['display'].tolist()

selected_answer = st.selectbox("Select answer for data cut:", [""] + q_answers)

if selected_answer:
    # Extract q_question_code and answer_text back out
    q_code, answer_text = selected_answer.split(" - ", 1)

    q_code_query = f"""
    SELECT question_code
    FROM {question_mapping_table}
    WHERE q_question_code = '{q_code}'
    AND answer_text = '{answer_text}'
    """
    q_code_df = pd.read_sql(q_code_query, connection)
    selected_questions = q_code_df['question_code'].tolist()


    # --- Data cut function (identical to yours) ---
    def fetch_data_and_sample_size(connection, selected_questions):
        question_code_filter = "', '".join(selected_questions)
        if question_code_filter:
        # Calculate the sample size: Participants who said "Yes" to all selected questions
            sample_size_query = f"""
        SELECT COUNT(DISTINCT participant_id) AS sample_size
        FROM (
            SELECT participant_id
            FROM {responses_table}
            WHERE LOWER(response_text) = 'yes'
            AND question_code IN ('{question_code_filter}')
            GROUP BY participant_id
            HAVING COUNT(DISTINCT question_code) = {len(selected_questions)}
        ) AS filtered_participants
        """
        else:
            sample_size_query = "SELECT 0 AS sample_size"

        sample_size_df = pd.read_sql(sample_size_query, connection)
        sample_size = sample_size_df['sample_size'][0] if not sample_size_df.empty else 0

        if question_code_filter:
        # Main query for data
            query = f"""
            WITH filtered_responses AS (
            SELECT participant_id
            FROM {responses_table}
            WHERE LOWER(response_text) = 'yes'
            AND question_code IN ('{question_code_filter}')
            GROUP BY participant_id
            HAVING COUNT(DISTINCT question_code) = {len(selected_questions)}
        ),
        cut_percentage AS (
            SELECT 
                r.question_code,
                ROUND(
                    COUNT(CASE WHEN LOWER(r.response_text) = 'yes' THEN 1 END) * 100.0 / 
                    COUNT(CASE WHEN LOWER(r.response_text) IN ('yes', 'no') THEN 1 END)
                ) AS cutpercentage
            FROM filtered_responses fr
            JOIN {responses_table} r ON fr.participant_id = r.participant_id
            GROUP BY r.question_code
        )
        SELECT 
            qm.question_code,
            CASE 
                WHEN LENGTH(qm.question_text) > 60 THEN CONCAT(LEFT(qm.question_text, 60), '...')
                ELSE qm.question_text
            END AS question_text,
            qm.answer_text AS answer_text,
            CONCAT(cp.cutpercentage, '%') AS cutpercentage_display,
            cp.cutpercentage AS cut_percentage,
            ROUND(
                cp.cutpercentage * 100.0 / 
                MAX(cp.cutpercentage) OVER (PARTITION BY qm.q_question_code), 
                2
            ) AS score,
            qm.q_question_code
        FROM cut_percentage cp
        JOIN {question_mapping_table} qm ON cp.question_code = qm.question_code
        ORDER BY 
            CASE 
                WHEN qm.q_question_code IN ('Q27', 'Q28', 'Q29', 'Q30', 'Q31', 'Q32', 'Q33', 'Q34', 'Q35', 'Q36', 'Q37', 'Q38', 'Q39') 
                    THEN score
                ELSE CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(qm.question_code, 'Q', -1), '_', 1) AS UNSIGNED)
            END DESC, 
            qm.question_code;
            """
        else:
            query = f"SELECT * FROM {responses_table} WHERE 1=0"

        df = pd.read_sql(query, connection)
        return df, sample_size




    # --- Run data cut ---
    df_cut, sample_size = fetch_data_and_sample_size(connection, selected_questions)

# --- Filter to only Q15, Q16, Q17, Q20 ---
    df_cut_filtered = df_cut[df_cut['q_question_code'].isin(['Q15', 'Q16', 'Q17', 'Q20', 'Q23'])]

    st.write(f"Sample size for selected Q4 answer: {sample_size}")

# --- Custom labels for subheaders ---
    labels = {
        "Q15": "Subject Scores",
        "Q16": "Format Scores",
        "Q17": "Style Scores",
        "Q20": "Humor Scores",
        "Q23": "Brand Attribute Scores"
    }

# --- Display results grouped by q_question_code with custom subheaders ---
    selected_answers = {}
    for q_code in ['Q15', 'Q16', 'Q17', 'Q20', 'Q23']:
        df_group = df_cut_filtered[df_cut_filtered['q_question_code'] == q_code]
        if not df_group.empty:
            st.subheader(labels.get(q_code, q_code))
        
        # Drop numeric cut_percentage before display
            df_display = df_group.drop(columns=['cut_percentage'])
            st.dataframe(df_display)

        # Dropdown to select one answer per question
            answer_options = df_group['answer_text'].unique().tolist()
            selected = st.selectbox(
                f"Select one answer for {labels[q_code]}",
                options=["None"] + answer_options,
                key=f"select_{q_code}"
            )
            if selected != "None":
                selected_answers[q_code] = df_group[df_group['answer_text'] == selected]

# --- Calculate average score from selected answers ---
    if selected_answers:
        st.markdown("### Average Score from Selected Answers")
        scores = []
        for q_code, df_cut in selected_answers.items():
        # Assuming you have a column 'cut_percentage' that represents the score
            score = df_cut['score'].values[0]
            scores.append(score)
        if scores:
            avg_score = sum(scores) / len(scores)
            st.metric("Average Score", f"{avg_score:.2f}/100")




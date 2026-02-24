import streamlit as st

st.set_page_config(page_title="Balloon Demo", layout="centered")

# Initialize state
if "balloon_up" not in st.session_state:
    st.session_state.balloon_up = False

st.title("🎈 Balloon Controller")

# ---- TEMPORARY BUTTON CONTROL ----
if st.button("Toggle Balloon"):
    st.session_state.balloon_up = not st.session_state.balloon_up


# ---- FUTURE MODEL CONTROL (Replace Later) ----
# Example placeholder:
# model_output = 1  # Replace this with: your_model.predict(data)
# if model_output == 1:
#     st.session_state.balloon_up = True
# else:
#     st.session_state.balloon_up = False


# Determine balloon position
bottom_position = "250px" if st.session_state.balloon_up else "20px"

# Balloon HTML + CSS
st.markdown(
    f"""
    <div style="position: relative; height: 300px; border: 2px solid #ddd; border-radius: 10px;">
        <div style="
            position: absolute;
            bottom: {bottom_position};
            left: 50%;
            transform: translateX(-50%);
            width: 80px;
            height: 100px;
            background-color: red;
            border-radius: 50%;
            transition: bottom 0.6s ease-in-out;
        ">
        </div>
    </div>
    """,
    unsafe_allow_html=True
)